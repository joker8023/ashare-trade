"""
team/run_batch.py — 批次回测驱动（PROTOCOL v1.2）
================================================

读取 team/specs/batch_NNN.json（数组），逐 spec 调 team/harness.py 跑，输出：

    team/runs/batch_NNN_results.csv   一行一 spec（含全部指标 + 敏感性/副口径列）
    team/runs/batch_NNN_summary.md    Tier A / A-ann / B / C 分层、Top20、分组聚合、错误统计、
                                      基准对比、相位扫描、耗时、spec 数、harness md5
    team/runs/batch_NNN_errors.csv    失败 spec + 原因（不静默丢弃）
    team/runs/batch_NNN_monthly.csv   2026 逐月收益（含基准行）
    team/runs/batch_NNN_equity/<id>.csv, batch_NNN_trades/<id>.csv   Tier 候选明细
    team/runs/run_log.md              追加一行运行记录

用法：
    python team/run_batch.py --batch 001
    python team/run_batch.py --batch 001 --limit 50 --variants next,same
    python team/run_batch.py --file team/specs/batch_001_addendum.json --tag 001add
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import harness as H

BASE = Path(__file__).resolve().parent.parent
TEAM = Path(__file__).resolve().parent
RUNS = TEAM / "runs"
SPECS = TEAM / "specs"

TOTAL_T, MDD_T, WIN_T = 0.60, -0.15, 0.80
ALL_VARIANTS = ("next", "same", "real", "fresh")


# ---------------------------------------------------------------- 工具
def _f(v, nd=4):
    if v is None:
        return "—"
    try:
        x = float(v)
    except Exception:
        return str(v)
    if math.isnan(x):
        return "—"
    return f"{x:.{nd}f}"


def _pct(v, nd=1):
    if v is None:
        return "—"
    try:
        x = float(v)
    except Exception:
        return str(v)
    if math.isnan(x):
        return "—"
    return f"{x * 100:+.{nd}f}%"


def _hit(row, prefix=""):
    """返回 (total_ok, mdd_ok, win_ok, total, mdd, win)。"""
    t = row.get("total" + prefix)
    m = row.get("mdd" + prefix)
    w = row.get("win_period" + prefix)
    t = -9.9 if t is None else float(t)
    m = -9.9 if m is None else float(m)
    w = -9.9 if w is None else float(w)
    return (t >= TOTAL_T, m >= MDD_T, w >= WIN_T, t, m, w)


def classify(row):
    """PROTOCOL §4 分层（主口径 = stop_exec=next，0.5%/边，phase=0，total_2026）。"""
    t_ok, m_ok, w_ok, t, m, w = _hit(row)
    n_ok = int(t_ok) + int(m_ok) + int(w_ok)
    if t_ok and m_ok and w_ok:
        return "A"
    ta_ok = (row.get("ann") is not None and float(row["ann"]) >= TOTAL_T) and m_ok and w_ok
    if ta_ok:
        return "A-ann"
    if t_ok and m_ok:
        return "B"
    if n_ok == 2:
        return "C"
    return "none"


def closeness(row):
    """离三条线的「乘积接近度」，>1 视为全过。"""
    t_ok, m_ok, w_ok, t, m, w = _hit(row)
    c1 = min(max(t, 0) / TOTAL_T, 1.0) if t is not None else 0.0
    c2 = min(max(m, -0.99) / MDD_T, 1.0) if m is not None else 0.0
    c3 = min(max(w, 0) / WIN_T, 1.0) if w is not None else 0.0
    return c1 * c2 * c3


def flags(row):
    out = []
    t = row.get("total")
    t = float(t) if t is not None else -9.9
    tr = row.get("total_real")
    ts = row.get("total_same")
    if t < TOTAL_T and tr is not None and float(tr) >= TOTAL_T:
        out.append("COST_FRAGILE")
    if t < TOTAL_T and ts is not None and float(ts) >= TOTAL_T:
        out.append("STOP_EXEC_DEPENDENT")
    fresh = row.get("fresh_2026")
    if t >= TOTAL_T and fresh is not None and (t - float(fresh)) > 0.10:
        out.append("FRESH_GAP")
    if row.get("win_trade") is not None and float(row["win_trade"]) < 0.60:
        out.append("LOW_WIN_TRADE")
    return ",".join(out)


# ---------------------------------------------------------------- 相位扫描
def phase_sweep(spec, phases=(-10, -5, 0, 5, 10)):
    out = []
    for ph in phases:
        try:
            r = H.run_spec(dict(spec, phase=ph), variants=("next",))
            out.append(dict(phase=ph, total=r.get("total"), mdd=r.get("mdd"),
                            win_period=r.get("win_period"), n_periods=r.get("n_periods")))
        except Exception as e:
            out.append(dict(phase=ph, total=None, mdd=None, win_period=None, error=str(e)[:120]))
    return out


# ---------------------------------------------------------------- 主流程
def _apply_cost(spec: dict, mode: str, lot: int = 100) -> dict:
    """批次级成本口径覆盖（spec 文件不改）：mode='realistic' 时强制现实费率 + 整手。"""
    sp = json.loads(json.dumps(spec))
    c = sp.setdefault("cost", {})
    c["mode"] = mode
    c.setdefault("lot_size", lot)
    c.setdefault("capital", 50000)
    return sp


def run_batch(specs, tag, outdir: Path = RUNS, variants=ALL_VARIANTS, limit=None,
              do_phase=True, detail_tiers=("A", "A-ann", "B"), cost_mode=None):
    if cost_mode:
        specs = [_apply_cost(sp, cost_mode) for sp in specs]
    t_start = time.time()
    md5_start = H.harness_md5()          # 跑批开始时的版本（之后改文件不影响记录）
    outdir.mkdir(parents=True, exist_ok=True)
    specs = specs[:limit] if limit else specs
    rows, errs = [], []
    cand_details = []
    monthly_rows = []

    for i, sp in enumerate(specs, 1):
        sid = str(sp.get("id") or f"spec{i}")
        t0 = time.time()
        try:
            r = H.run_spec(sp, variants=tuple(variants))
            r["group"] = sp.get("group", "")
            r["notes"] = sp.get("notes", "")
            r["batch"] = tag
            r["tier"] = classify(r)
            r["close"] = round(closeness(r), 4)
            r["flags"] = flags(r)
            rows.append(r)
            if r.get("monthly_2026"):
                monthly_rows.append(dict(id=sid, group=r["group"], monthly_2026=r["monthly_2026"]))
            if r["tier"] in detail_tiers:
                cand_details.append(sid)
        except Exception as e:
            rows.append(dict(id=sid, batch=tag, group=sp.get("group", ""),
                             selector=(sp.get("selector") or {}).get("type"),
                             n=(sp.get("selector") or {}).get("n"),
                             R=sp.get("rebalance_days"), tier="ERROR",
                             status="error", error=f"{type(e).__name__}: {e}",
                             secs=round(time.time() - t0, 3)))
            errs.append(dict(id=sid, group=sp.get("group", ""), error=f"{type(e).__name__}: {e}",
                             trace=traceback.format_exc()[-800:],
                             selector=json.dumps(sp.get("selector"), ensure_ascii=False),
                             exit=json.dumps(sp.get("exit"), ensure_ascii=False)))
        if i % 25 == 0 or i == len(specs):
            el = time.time() - t_start
            print(f"  [{tag}] {i}/{len(specs)}  {el:.1f}s  ({el/max(i,1)*1000:.0f} ms/spec)",
                  flush=True)

    df = pd.DataFrame(rows)
    # ---- 排序：Tier 优先，然后接近度 ----
    order = {"A": 0, "A-ann": 1, "B": 2, "C": 3, "none": 4, "ERROR": 9}
    df["_o"] = df["tier"].map(lambda x: order.get(x, 5))
    df = df.sort_values(["_o", "close"], ascending=[True, False]).reset_index(drop=True)

    elapsed = time.time() - t_start
    # ---- 明细落地 ----
    for sid in cand_details[:40]:
        try:
            sp = next(s for s in specs if str(s.get("id")) == sid)
            row, eq, tr = H.run_spec(sp, detail=True, variants=("next",))
            (outdir / f"batch_{tag}_equity").mkdir(exist_ok=True)
            (outdir / f"batch_{tag}_trades").mkdir(exist_ok=True)
            eq.to_csv(outdir / f"batch_{tag}_equity" / f"{sid}.csv", index=False)
            tr.to_csv(outdir / f"batch_{tag}_trades" / f"{sid}.csv", index=False)
        except Exception:
            pass

    # ---- 相位扫描（Tier 候选） ----
    sweep = {}
    tier_candidates = df[df["tier"].isin(["A", "A-ann", "B"])]["id"].tolist() if do_phase else []
    for sid in tier_candidates[:30]:
        sp = next((s for s in specs if str(s.get("id")) == sid), None)
        if sp is None:
            continue
        sweep[sid] = phase_sweep(sp)
        n_pass = 0
        for x in sweep[sid]:
            if x.get("total") is None:
                continue
            if (x["total"] >= TOTAL_T and (x["mdd"] or -9) >= MDD_T
                    and (x.get("win_period") or -9) >= WIN_T):
                n_pass += 1
        sweep[sid + "__pass"] = n_pass
        if n_pass < 3:
            df.loc[df["id"] == sid, "flags"] = df.loc[df["id"] == sid, "flags"].fillna("").apply(
                lambda s: (s + ",PHASE_LUCK") if "PHASE_LUCK" not in s else s)

    # ---- fresh 口径五相位扫描（Round 3 主口径）----
    fresh_phase = {}
    if do_phase:
        for sp in specs:
            sid = str(sp.get("id"))
            if sid not in set(df["id"]):
                continue
            n_pass, n_ok = 0, 0
            for ph in (-10, -5, 0, 5, 10):
                try:
                    r = H.run_spec(dict(sp, phase=ph), variants=("fresh",))
                    n_ok += 1
                    if ((r.get("fresh_total") or -9) >= 0.60
                            and (r.get("fresh_mdd") or -9) >= -0.15
                            and (r.get("fresh_win_period") or 0) >= 0.80):
                        n_pass += 1
                except Exception:
                    pass
            if n_ok:
                fresh_phase[sid] = n_pass
    df["fresh_phase_pass"] = df["id"].map(lambda x: fresh_phase.get(str(x)))

    # ---- 相位通过数 & fresh gap 列 ----
    df["phase_pass_count"] = df["id"].map(lambda x: sweep.get(str(x) + "__pass", None))
    df["fresh_gap_pp"] = (pd.to_numeric(df.get("total"), errors="coerce")
                          - pd.to_numeric(df.get("fresh_2026"), errors="coerce")) * 100.0

    # ---- 可复现性抽检 ----
    repro = []
    for sp in specs[:3]:
        try:
            a = H.run_spec(sp, variants=("next",))
            b = H.run_spec(sp, variants=("next",))
            diff = [k for k in a if k != "secs" and a.get(k) != b.get(k)]
            repro.append((str(sp.get("id")), len(diff), diff[:3]))
        except Exception as e:
            repro.append((str(sp.get("id")), -1, [str(e)[:60]]))

    meta = dict(tag=tag, n_specs=len(specs), elapsed_sec=round(elapsed, 1),
                ms_per_spec=round(elapsed / max(len(specs), 1) * 1000, 1),
                harness_md5=md5_start, variants=list(variants),
                ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                errors=len(errs), repro=repro)

    write_outputs(df, errs, monthly_rows, sweep, meta, outdir, specs)
    return dict(df=df, errs=errs, meta=meta, sweep=sweep, outdir=outdir)


# ---------------------------------------------------------------- 输出
def write_outputs(df, errs, monthly_rows, sweep, meta, outdir: Path, specs):
    tag = meta["tag"]
    df.drop(columns=[c for c in ("_o",) if c in df.columns]).to_csv(
        outdir / f"batch_{tag}_results.csv", index=False)

    # monthly
    try:
        bm = H.benchmark()
        mrows = [dict(id="__BENCH__", group="benchmark", monthly_2026="|".join(
            f"{k}:{v:.4f}" for k, v in bm["months"].items()))] + monthly_rows
        pd.DataFrame(mrows).to_csv(outdir / f"batch_{tag}_monthly.csv", index=False)
    except Exception:
        bm = None

    if errs:
        pd.DataFrame(errs).to_csv(outdir / f"batch_{tag}_errors.csv", index=False)

    summ = []
    A = lambda s: summ.append(s)
    A(f"# Batch {tag} — 回测结果摘要\n")
    A(f"- 生成时间：{meta['ts']}")
    A(f"- spec 数：**{meta['n_specs']}**（错误 {meta['errors']}）")
    A(f"- 耗时：**{meta['elapsed_sec']}s**（{meta['ms_per_spec']} ms/spec）")
    A(f"- harness md5：`{meta['harness_md5']}`")
    A(f"- 口径：`stop_exec=next`（主，t 日收盘触发→t+1 收盘卖出）；`same`/`real`/`fresh` 为敏感性列")
    A(f"- 成本：主 0.5%/边（fixed）；real = 佣金0.025%+印花0.05%+过户0.001%+滑点0.2%/边+100股整手")
    A(f"- 网格：`dates[300]` 相位，一直排到数据末端（v1.1 修正）；phase=0；win_period 只计完整段")
    A(f"- **Round 3 起主表用 fresh 口径**（2026-01-05 空仓起步、基数 1.0、现实费率含 0.2%/边滑点、5 万整手）："
      f"`fresh_total / fresh_mdd / fresh_win_period / fresh_win_month / fresh_win_trade / fresh_top3_pnl_share / fresh_exposure`")
    A(f"- 连续口径列（无前缀）保留作参考，不再作为判定主表")
    A("")

    # ---- 基准 ----
    if bm is not None:
        A("## 0. 基准（等权小微盘，seasoned+ADV>500万+市值5~30%分位，无成本）\n")
        A(f"- 2026-01-05~2026-11-04：**{_pct(bm['total'])}**，最大回撤 **{_pct(bm['mdd'])}**，"
          f"{bm['n_days']} 个交易日")
        A("- 逐月：" + "  ".join(f"{k} {_pct(v)}" for k, v in bm["months"].items()))
        A("")

    # ---- 分层 ----
    cnt = df["tier"].value_counts().to_dict()
    A("## 1. 分层计数\n")
    A("| Tier | 数量 | 含义 |")
    A("|---|---|---|")
    A(f"| A | {cnt.get('A', 0)} | total≥60% & mdd≤15% & win_period≥80%（待审计） |")
    A(f"| A-ann | {cnt.get('A-ann', 0)} | ann≥60% & mdd≤15% & win_period≥80% |")
    A(f"| B | {cnt.get('B', 0)} | total≥60% & mdd≤15%，胜率未达标 |")
    A(f"| C | {cnt.get('C', 0)} | 三项中满足两项 |")
    A(f"| ERROR | {cnt.get('ERROR', 0)} | 运行失败 |")
    A("")

    key_cols = ["id", "group", "selector", "n", "R", "exit", "stop_exec", "total", "ann", "mdd",
                "win_period", "n_periods", "win_trade", "n_trades", "win_month",
                "fresh_total", "fresh_mdd", "fresh_win_period", "fresh_win_month", "fresh_win_trade",
                "fresh_n_trades", "fresh_calmar", "fresh_top3_pnl_share", "fresh_exposure",
                "fresh_2026", "total_same", "total_real", "win_period_2025", "total_2025", "mdd_2025",
                "exposure_target", "exposure", "n_sleeves", "sleeve_offsets", "n_hold_avg",
                "n_hold_max", "n_distinct_names", "n_hold_star", "n_stop_events",
                "anchor_first_date", "phase_pass_count", "fresh_gap_pp", "close", "flags"]

    def table(sub, title, k=20):
        A(f"## {title}\n")
        if sub.empty:
            A("_无_\n")
            return
        cols = [c for c in key_cols if c in sub.columns]
        A("| " + " | ".join(cols) + " |")
        A("|" + "---|" * len(cols))
        for _, r in sub.head(k).iterrows():
            cells = []
            for c in cols:
                v = r.get(c)
                if c in ("total", "ann", "mdd", "win_period", "win_trade", "win_month",
                         "fresh_2026", "fresh_total", "fresh_mdd", "fresh_win_period",
                         "fresh_win_month", "fresh_win_trade", "fresh_top3_pnl_share",
                         "total_same", "total_real", "win_period_2025",
                         "total_2025", "mdd_2025"):
                    cells.append(_pct(v))
                elif c == "n_periods":
                    cells.append(f"{int(v)}" if pd.notna(v) else "—")
                elif c in ("exposure", "exposure_target"):
                    cells.append(_f(v, 3))
                elif c == "close":
                    cells.append(_f(v, 3))
                else:
                    cells.append("—" if v is None else str(v))
            A("| " + " | ".join(cells) + " |")
        A("")

    table(df[df["tier"] == "A"], "2. Tier A（total≥60% & mdd≤15% & win_period≥80%）")
    table(df[df["tier"] == "A-ann"], "3. Tier A-ann（年化口径）")
    table(df[df["tier"] == "B"], "4. Tier B（收益+回撤达标，胜率差一口气）")
    table(df[df["tier"] == "C"].sort_values("close", ascending=False),
          "5. Tier C（三项中满足两项）")
    table(df[df["tier"] == "none"].sort_values("close", ascending=False).head(10),
          "6. 最接近的 10 个（未分层，按接近度）", k=10)

    # ---- Top 20 by total ----
    A("## 7. Top 20（按 total_2026 排序）\n")
    top = df[df["status"] != "error"].sort_values("total", ascending=False).head(20)
    table(top, "Top20", k=20)

    # ---- 分组聚合 ----
    A("## 8. 按维度聚合\n")
    ok = df[df["status"] != "error"].copy()
    for key in ("group", "selector", "R", "exit"):
        if key not in ok.columns:
            continue
        g = ok.groupby(key).agg(n=("id", "size"), total_med=("total", "median"),
                                total_max=("total", "max"), mdd_med=("mdd", "median"),
                                winp_med=("win_period", "median"),
                                n_A=("tier", lambda s: int((s == "A").sum())),
                                n_B=("tier", lambda s: int((s == "B").sum())))
        g = g.sort_values("total_med", ascending=False)
        A(f"### {key}\n")
        A("| " + key + " | n | total 中位 | total 最大 | mdd 中位 | win_period 中位 | A | B |")
        A("|---|---|---|---|---|---|---|---|")
        for idx, r in g.iterrows():
            A(f"| {idx} | {int(r['n'])} | {_pct(r['total_med'])} | {_pct(r['total_max'])} | "
              f"{_pct(r['mdd_med'])} | {_pct(r['winp_med'])} | {int(r['n_A'])} | {int(r['n_B'])} |")
        A("")

    # ---- 分布 ----
    A("## 9. 分布（total_2026）\n")
    if len(ok):
        q = ok["total"].astype(float).quantile([0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0])
        A("- 分位：" + "  ".join(f"p{int(k*100)}={v*100:+.1f}%" for k, v in q.items()))
        A(f"- 满足 total≥60%：{int((ok['total'].astype(float) >= 0.6).sum())} / {len(ok)}")
        A(f"- 满足 mdd≥-15%：{int((ok['mdd'].astype(float) >= -0.15).sum())} / {len(ok)}")
        A(f"- 满足 win_period≥80%：{int((ok['win_period'].astype(float) >= 0.8).sum())} / {len(ok)}")
        A("")

    # ---- 相位扫描 ----
    if sweep:
        A("## 10. 相位扫描（phase = -10/-5/0/+5/+10 交易日，Tier 候选）\n")
        A("| id | phase | total | mdd | win_period | n_periods |")
        A("|---|---|---|---|---|---|")
        for sid, arr in sweep.items():
            if sid.endswith("__pass"):
                continue
            for x in arr:
                A(f"| {sid} | {x['phase']:+d} | {_pct(x.get('total'))} | {_pct(x.get('mdd'))} | "
                  f"{_pct(x.get('win_period'))} | {x.get('n_periods', '—')} |")
        A("")
        A("相位通过数（三线同时满足的档数，≥3 才不看 PHASE_LUCK）：")
        A("")
        for sid, n in sweep.items():
            if sid.endswith("__pass"):
                A(f"- {sid[:-6]}: **{n}/5**")
        A("")

    # ---- phase 通过数排名 ----
    if "phase_pass_count" in df.columns and df["phase_pass_count"].notna().any():
        A("## 10b. 相位通过数（5 档中三线全过几档）\n")
        sub = df[df["phase_pass_count"].notna()].sort_values(
            ["phase_pass_count", "total"], ascending=[False, False])
        A("| id | phase_pass | total | mdd | win_period | fresh_2026 | fresh_gap_pp |")
        A("|---|---|---|---|---|---|---|")
        for _, r in sub.head(30).iterrows():
            A(f"| {r['id']} | **{int(r['phase_pass_count'])}/5** | {_pct(r['total'])} | {_pct(r['mdd'])} | "
              f"{_pct(r['win_period'])} | {_pct(r.get('fresh_2026'))} | {_f(r.get('fresh_gap_pp'),1)} |")
        A("")

    # ---- 可复现 ----
    A("## 11. 可复现性抽检（同 spec 跑两次，除耗时外必须完全一致）\n")
    for sid, nd, ks in meta["repro"]:
        A(f"- `{sid}`：差异字段 {nd} 个" + (f"（{ks}）" if nd else " ✅"))
    A("")

    # ---- 错误 ----
    A("## 12. 错误 / 跳过\n")
    if errs:
        for e in errs[:30]:
            A(f"- `{e['id']}`: {e['error']}")
    else:
        A("- 无")
    A("")

    A("## 13. harness 限制（引用数字时必须一起引用）\n")
    for x in H.LIMITATIONS:
        A(f"- {x}")
    A("")

    (outdir / f"batch_{tag}_summary.md").write_text("\n".join(summ), encoding="utf-8")

    # ---- run log ----
    log = RUNS / "run_log.md"
    line = (f"| {meta['ts']} | {tag} | {meta['n_specs']} | {meta['elapsed_sec']}s | "
            f"{meta['ms_per_spec']} | {meta['errors']} | "
            f"A={int((df['tier']=='A').sum())} A-ann={int((df['tier']=='A-ann').sum())} "
            f"B={int((df['tier']=='B').sum())} C={int((df['tier']=='C').sum())} | "
            f"{','.join(meta['variants'])} | `{meta['harness_md5'][:8]}` |")
    if not log.exists():
        log.write_text("# 跑批日志\n\n| 时间 | 批次 | spec 数 | 耗时 | ms/spec | 错误 | Tier | variants | 版本 |\n"
                       "|---|---|---|---|---|---|---|---|---|\n", encoding="utf-8")
    with log.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", help="批次号，如 001 → team/specs/batch_001.json")
    ap.add_argument("--file", help="直接指定 spec 文件")
    ap.add_argument("--tag", help="输出标签（默认同批次号）")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--variants", default="next,same,real,fresh")
    ap.add_argument("--no-phase", action="store_true")
    ap.add_argument("--cost-mode", default=None, choices=["fixed", "realistic"],
                    help="批次级成本覆盖：batch_006 起官方口径 = realistic（含 0.2%%/边滑点）")
    a = ap.parse_args(argv)
    if a.file:
        path = Path(a.file)
        tag = a.tag or path.stem.replace("batch_", "")
    elif a.batch:
        path = SPECS / f"batch_{a.batch}.json"
        tag = a.tag or a.batch
    else:
        ap.error("需要 --batch 或 --file")
    specs = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(specs, list):
        ap.error("spec 文件必须是数组")
    print(f"[run_batch] {path} → {len(specs)} specs, tag={tag}", flush=True)
    res = run_batch(specs, tag, variants=tuple(a.variants.split(",")),
                    limit=a.limit, do_phase=not a.no_phase, cost_mode=a.cost_mode)
    m = res["meta"]
    print(f"[run_batch] done: {m['n_specs']} specs, {m['elapsed_sec']}s, errors={m['errors']}")
    print(f"  → {res['outdir']}/batch_{tag}_results.csv")
    print(f"  → {res['outdir']}/batch_{tag}_summary.md")


if __name__ == "__main__":
    main()
