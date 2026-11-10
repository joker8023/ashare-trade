#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
audit_fresh.py — Round 3 / batch_006 四画像的独立 fresh 审计

口径（Lead task-11）：
  * 2026-01-05 空仓起步（fresh），2026-01-05 ~ 2026-11-04
  * 现实费率：佣金 0.025%（最低 5 元）+ 卖出印花 0.05% + 过户 0.001% + 滑点 0.2%/边
  * 5 万本金 / 100 股整手；只做多、无杠杆
  * t 日收盘信号 / 止损止盈 t 收盘触发、t+1 收盘卖出

审计内容：
  A. fresh_total / mdd / win_period / win_month / win_trade / calmar
  B. 攻击高胜率：实际 exposure、现金占比、平均持仓数、月度收益分布（空仓月识别）
  C. 攻击低回撤：exposure/现金、持仓月份数、是否靠债券停泊（由 spec 判断）
  D. 攻击收益：Top3 集中度、剔除 Top3 后 fresh_total、2024 同参数 MDD、2025 OOS
  E. 相位：-10/0/+10（至少 3 档）
  F. 与 harness batch_006 的逐条对拍（误差 ≤0.5pp）

用法：
  .venv/bin/python team/audit/batch_006/audit_fresh.py baseline
  .venv/bin/python team/audit/batch_006/audit_fresh.py batch --json team/audit/out/batch_006_audit.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))              # team/audit
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))  # team? no
import prior_check as pc                                 # 审计员自写引擎

ROOT = pc.ROOT
RUNS = os.path.join(ROOT, "team", "runs")
OUT = os.path.join(ROOT, "team", "audit", "out")
MB = ("688", "689", "300", "301", "8", "4")              # 主板
CAP = 50_000.0


# ---------------------------------------------------------------------------
# 指标
# ---------------------------------------------------------------------------
def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (c - h, c + h)


def fresh_metrics(r: pc.Result) -> dict:
    m = pc.metrics(r)
    w = r.exposure.loc[pc.EVAL_START:pc.EVAL_END]
    nh = r.nhold.loc[pc.EVAL_START:pc.EVAL_END]
    tr = r.trades
    ev = tr[(tr.exit_date >= pc.EVAL_START) & (tr.exit_date <= pc.EVAL_END)] if len(tr) else tr
    pnl = ev.groupby("code")["net_pnl"].sum().sort_values(ascending=False) if len(ev) else pd.Series(dtype=float)
    tot = float(pnl.sum()) if len(pnl) else 0.0
    wins = ev.loc[ev.net_ret > 0, "net_ret"] if len(ev) else pd.Series(dtype=float)
    losses = ev.loc[ev.net_ret <= 0, "net_ret"] if len(ev) else pd.Series(dtype=float)
    monthly = m["monthly_rets"]
    flat_months = [k for k, v in monthly.items() if abs(v) < 0.005]
    return dict(
        fresh_total=m["total_2026"], fresh_ann=m["ann_2026"], fresh_mdd=m["mdd_2026"],
        win_period=m["win_period"], n_periods=m["n_periods"],
        win_month=m["win_month"], win_month_n=m["win_month_n"],
        win_trade=m["win_trade"], n_trades=m["n_trades"],
        calmar=(m["ann_2026"] / abs(m["mdd_2026"])) if m["mdd_2026"] < 0 else np.nan,
        exposure_mean=float(w.mean()), cash_share=float(1 - w.mean()),
        exposure_min=float(w.min()), exposure_p10=float(w.quantile(0.1)),
        nhold_mean=float(nh.mean()), nhold_min=float(nh.min()),
        n_months_held=int(sum(1 for v in monthly.values() if abs(v) > 1e-9)),
        flat_months=flat_months,
        monthly={k: round(v, 6) for k, v in monthly.items()},
        avg_win=float(wins.mean()) if len(wins) else np.nan,
        avg_loss=float(losses.mean()) if len(losses) else np.nan,
        win_loss_ratio=(float(wins.mean() / abs(losses.mean())) if len(wins) and len(losses) and losses.mean() != 0 else np.nan),
        top1_share=float(pnl.iloc[0] / tot) if len(pnl) and tot else np.nan,
        top3_share=float(pnl.head(3).sum() / tot) if len(pnl) and tot else np.nan,
        top3_codes=list(pnl.index[:3]),
        n_codes=int(len(pnl)),
        wilson_wp=list(wilson(int(round(m["win_period"] * m["n_periods"])), m["n_periods"])),
        wilson_wt=list(wilson(m["trade_win_n"], m["n_trades"])),
        wilson_wm=list(wilson(int(m["win_month_n"].split("/")[0]), int(m["win_month_n"].split("/")[1]))),
    )


# ---------------------------------------------------------------------------
# spec → 我的引擎参数（只支持可独立复算的子集；不支持则返回 None + 原因）
# ---------------------------------------------------------------------------
def spec_to_engine(s: dict):
    sel = s.get("selector") or {}
    st = str(sel.get("type") or "amihud")
    fac = {"amihud": "amihud", "amihud_60": "amihud_60"}.get(st)
    unsupported = []
    if fac is None:
        unsupported.append(f"selector={st}")
    ex = s.get("exit") or {}
    if ex.get("fixed_stop") is not None:
        unsupported.append("fixed_stop")
    if ex.get("max_hold_days") is not None:
        unsupported.append("max_hold_days")
    if ex.get("trailing_take") is not None:
        unsupported.append("trailing_take")
    if ex.get("staged_take") is not None:
        unsupported.append("staged_take")
    timing = s.get("timing") or {}
    if (timing.get("type") or "none") != "none":
        unsupported.append(f"timing={timing.get('type')}")
    if str((timing.get("out_asset") or "cash")) != "cash":
        unsupported.append(f"out_asset={timing.get('out_asset')}")
    pf = s.get("portfolio") or {}
    if pf.get("vol_target") is not None:
        unsupported.append("vol_target")
    if pf.get("sleeves"):
        unsupported.append("sleeves")
    if unsupported:
        return None, ",".join(unsupported)
    excl = list(MB)
    if sel.get("exclude_star") is False:
        excl = [x for x in excl if x not in ("688", "689")]
    if sel.get("exclude_chinext") is False:
        excl = [x for x in excl if x not in ("300", "301")]
    if sel.get("exclude_bj") is False:
        excl = [x for x in excl if x not in ("8", "4")]
    cost = s.get("cost") or {}
    mode = str(cost.get("mode") or "realistic")
    kw = dict(
        factor=fac, n=int(sel.get("n") or 6), rebal=int(s.get("rebalance_days") or 30),
        stop=ex.get("trailing_stop"), take=ex.get("take_profit"),
        stop_exec="next", exclude=tuple(excl),
        capital=float(cost.get("capital") or CAP), lot=int(cost.get("lot_size") or 100),
        cost_one_way=float(cost.get("one_way") or 0.005) if mode == "fixed" else None,
        slip=0.0 if mode == "fixed" else float(cost.get("slip") or 0.002),
        run_start="2026-01-05", phase=0, legacy_grid=False,
        exposure=float(pf.get("exposure") or 1.0),
        weight_cap=sel.get("max_weight"), rank_fill=bool(sel.get("rank_fill", True)),
    )
    return kw, ""


def run_spec(s: dict) -> dict:
    kw, why = spec_to_engine(s)
    if kw is None:
        return dict(ok=False, reason=why)
    r = pc.run_strategy(pc.get_inputs(), **kw)
    out = fresh_metrics(r)
    out["ok"] = True
    # 相位
    phases = {}
    for ph in (-10, 0, 10):
        k2 = dict(kw)
        k2["phase"] = ph
        rr = pc.run_strategy(pc.get_inputs(), **k2)
        mm = pc.metrics(rr)
        phases[ph] = dict(total=mm["total_2026"], mdd=mm["mdd_2026"], wp=mm["win_period"])
    out["phase"] = phases
    return out


def attack_extras(s: dict, base: dict) -> dict:
    """剔除 Top3 + 2024 MDD + 2025 OOS（用连续预热口径，参数不变）。"""
    kw, why = spec_to_engine(s)
    if kw is None:
        return dict(ok=False, reason=why)
    top3 = base.get("top3_codes") or []
    ex = {}
    if top3:
        k2 = dict(kw)
        k2["run_start"] = "2026-01-05"
        k2["exclude"] = tuple(k2["exclude"]) + tuple(top3)
        rr = pc.run_strategy(pc.get_inputs(), **k2)
        mm = pc.metrics(rr)
        ex = dict(ex_total=mm["total_2026"], ex_mdd=mm["mdd_2026"], ex_wp=mm["win_period"],
                  ex_wt=mm["win_trade"], retention=(mm["total_2026"] / base["fresh_total"]
                                                    if base["fresh_total"] else np.nan))
    # 2024/2025（连续预热，同参数）
    k3 = dict(kw)
    k3["run_start"] = "2024-01-01"
    rr = pc.run_strategy(pc.get_inputs(), **k3)
    eq = rr.eq
    oos = {}
    for y, bd in [(2024, "2023-12-31"), (2025, "2024-12-31")]:
        seg = eq.loc[f"{y}-01-01":f"{y}-12-31"]
        b = eq.loc[:bd]
        bv = float(b.iloc[-1]) if len(b) else CAP
        oos[y] = dict(total=float(seg.iloc[-1] / bv - 1),
                      mdd=float((seg / seg.cummax() - 1).min()))
    return dict(ok=True, ex_top3=ex, oos=oos)


# ---------------------------------------------------------------------------
# baseline / batch
# ---------------------------------------------------------------------------
def baseline() -> dict:
    out = {}
    for lbl, kw in [("C3_N6_e100", dict(n=6, exposure=1.0)),
                    ("C2_N5_e90", dict(n=5, exposure=0.90)),
                    ("C3_N6_e60", dict(n=6, exposure=0.60))]:
        d = dict(factor="amihud_60", rebal=30, take=0.5, stop=None, stop_exec="next", exclude=MB,
                 capital=CAP, lot=100, cost_one_way=None, slip=0.002, run_start="2026-01-05",
                 phase=0, legacy_grid=False, exposure=1.0)
        d.update(kw)
        r = pc.run_strategy(pc.get_inputs(), **d)
        m = fresh_metrics(r)
        fake = dict(selector=dict(type="amihud_60", n=kw["n"], max_weight=None, rank_fill=True),
                    exit=dict(trailing_stop=None, fixed_stop=None, take_profit=0.5,
                              trailing_take=None, max_hold_days=None, staged_take=None),
                    timing=dict(type="none", out_asset="cash"),
                    portfolio=dict(exposure=kw["exposure"]),
                    cost=dict(mode="realistic", capital=CAP, lot_size=100, slip=0.002),
                    rebalance_days=30)
        m["extras"] = attack_extras(fake, m)
        out[lbl] = m
    return out


def pick_profiles(df: pd.DataFrame) -> dict:
    """按 Lead task-10 的规则选每个画像 Top2。"""
    d = df.copy()
    d["score"] = np.nan
    profiles = {}
    # 收益型
    profiles["收益型"] = list(d.sort_values("fresh_total", ascending=False).head(2)["id"])
    # 均衡型
    eq = d[(d["fresh_mdd"] < 0) & (d["win_period"] >= 0.70)].copy()
    eq["score"] = eq["fresh_total"] / eq["fresh_mdd"].abs()
    profiles["均衡型"] = list(eq.sort_values("score", ascending=False).head(2)["id"])
    # 稳健型
    ro = d[d["fresh_mdd"] >= -0.08].copy()
    ro["_wm"] = ro["win_month"].astype(str).str.split("/").str[0].astype(float) / \
                ro["win_month"].astype(str).str.split("/").str[1].astype(float)
    profiles["稳健型"] = list(ro.sort_values("_wm", ascending=False).head(2)["id"])
    # 高胜率型
    hi = d[d["fresh_total"] >= 0.15].copy()
    hi["_wm"] = hi["win_month"].astype(str).str.split("/").str[0].astype(float) / \
                hi["win_month"].astype(str).str.split("/").str[1].astype(float)
    hi["score"] = hi[["win_period", "_wm", "win_trade"]].min(axis=1)
    profiles["高胜率型"] = list(hi.sort_values("score", ascending=False).head(2)["id"])
    return profiles


def batch() -> dict:
    res_path = os.path.join(RUNS, "batch_006_results.csv")
    if not os.path.exists(res_path):
        return {"status": "batch_006 not ready", "path": res_path}
    df = pd.read_csv(res_path)
    profiles = pick_profiles(df)
    out = {"profiles": profiles, "detail": {}}
    for prof, ids in profiles.items():
        out["detail"][prof] = []
        for sid in ids:
            row = df[df.id == sid].iloc[0].to_dict()
            spec = None
            for f in ("batch_006.json", "batch_006_addendum.json"):
                p = os.path.join(ROOT, "team", "specs", f)
                if os.path.exists(p):
                    for s in json.load(open(p)):
                        if s.get("id") == sid:
                            spec = s
                            break
                if spec:
                    break
            entry = dict(id=sid, harness={k: row.get(k) for k in
                                          ("fresh_total", "fresh_mdd", "win_period", "win_month",
                                           "win_trade", "top3_pnl_share", "exposure", "n_trades")})
            if spec is None:
                entry["audit"] = dict(ok=False, reason="spec not found")
            else:
                m = run_spec(spec)
                m["extras"] = attack_extras(spec, m) if m.get("ok") else dict(ok=False)
                entry["audit"] = m
            out["detail"][prof].append(entry)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", nargs="?", default="baseline")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    res = baseline() if args.what == "baseline" else batch()
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(res, f, ensure_ascii=False, indent=2, default=str)
        print("wrote", args.json)
