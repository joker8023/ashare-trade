"""
team/lib/run_round2.py — Round 2 结构探针（max_weight / staged_take / vol_target）
================================================================================
在 C2/C3 骨架上做对照实验，输出：
  · 主口径（realistic：5 万整手、佣金0.025%最低5+印花0.05%+过户0.001%+滑点0.2%/边）
  · 0.5%/边（主矩阵成本）双跑
  · fresh_2026（2026-01-05 空仓起步，realistic 5 万整手）
  · top1/top3/top5 PnL 占比 + 剔除 top3/top5 重跑（exclude_codes）
  · phase_pass_count（5 相位，realistic 主口径）
  · 2024 / 2025 / 2025H2 OOS
输出：team/runs/round2_probe.md / round2_probe.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
TEAM = HERE.parent
RUNS = TEAM / "runs"
sys.path.insert(0, str(TEAM))

import harness as H              # noqa: E402

WIN = dict(warmup_start="2024-01-01", eval_start="2026-01-05", eval_end="2026-11-04")


def mk(sid, n, *, tp=None, staged=None, mw=None, vt=None, expo=1.0, cost="realistic",
       excl=(), group=""):
    ex = dict(stop_exec="next")
    if tp is not None:
        ex["take_profit"] = tp
    if staged is not None:
        ex["staged_take"] = staged
    sel = dict(type="amihud_60", n=n, size_range=[0.05, 0.30], min_adv=5e6,
               exclude_star=True, exclude_bj=True, exclude_chinext=True,
               exclude_codes=list(excl))
    if mw is not None:
        sel["max_weight"] = mw
    pf = dict(exposure=expo)
    if vt is not None:
        pf["vol_target"] = vt
    return dict(id=sid, group=group, selector=sel, rebalance_days=30, exit=ex,
                timing=dict(type="none"),
                cost=dict(mode=cost, one_way=0.005, capital=50000, lot_size=100),
                portfolio=pf, window=dict(WIN))


def analyse(spec):
    cfg = H.normalize_spec(spec)
    sim = H.run_sim(cfg)
    m = H._window_metrics(sim, cfg["window"]["eval_start"], cfg["window"]["eval_end"],
                          "2025-12-31", cfg)
    b = H.bundle()
    sp = int(np.searchsorted(b.dates, pd.Timestamp(cfg["window"]["eval_start"]), "left"))
    ep = int(np.searchsorted(b.dates, pd.Timestamp(cfg["window"]["eval_end"]), "right") - 1)
    tr = sim["trades"]
    by = (tr[(tr["exit_pos"] >= sp) & (tr["exit_pos"] <= ep)].groupby("code")["pnl"].sum()
          .sort_values(ascending=False)) if len(tr) else pd.Series(dtype=float)
    tot = float(by.sum()) if len(by) else 0.0
    out = {k: m.get(k) for k in ("total", "ann", "mdd", "win_period", "n_periods", "win_trade",
                                 "win_month", "block30_win", "fresh_2026", "n_hold_avg",
                                 "n_hold_max", "n_distinct_names", "top3_pnl_share",
                                 "max_single_name_pnl_share", "n_staged_events",
                                 "total_2025", "win_period_2025", "mdd_2025", "total_2024")}
    out["top1_share"] = float(by.iloc[0] / tot) if tot > 0 else np.nan
    out["top5_share"] = float(by.iloc[:5].sum() / tot) if tot > 0 else np.nan
    out["top3_codes"] = list(by.index[:3])
    out["top5_codes"] = list(by.index[:5])
    return out, by, cfg


def main():
    base = dict(n=6, tp=0.50)
    cfgs = [
        ("C3 对照 N6/TP50/满仓", mk("r2_C3_ctrl", 6, tp=0.5, group="control")),
        ("C3 + staged 30/50/80", mk("r2_C3_staged", 6, staged=[{"gain": 0.30, "frac": 1/3},
                                                              {"gain": 0.50, "frac": 1/3},
                                                              {"gain": 0.80, "frac": 1.0}], group="staged")),
        ("C3 + staged + vol25", mk("r2_C3_staged_vt25", 6, staged=[{"gain": 0.30, "frac": 1/3},
                                                                  {"gain": 0.50, "frac": 1/3},
                                                                  {"gain": 0.80, "frac": 1.0}], vt=0.25, group="staged+vt")),
        ("C3 + staged + vol30", mk("r2_C3_staged_vt30", 6, staged=[{"gain": 0.30, "frac": 1/3},
                                                                  {"gain": 0.50, "frac": 1/3},
                                                                  {"gain": 0.80, "frac": 1.0}], vt=0.30, group="staged+vt")),
        ("C3 + max_weight 0.15", mk("r2_C3_mw15", 6, tp=0.5, mw=0.15, group="max_weight")),
        ("C3 + max_weight 0.12", mk("r2_C3_mw12", 6, tp=0.5, mw=0.12, group="max_weight")),
        ("C3 + max_weight 0.10", mk("r2_C3_mw10", 6, tp=0.5, mw=0.10, group="max_weight")),
        ("C3 + max_weight 0.12 + staged", mk("r2_C3_mw12_staged", 6,
                                             staged=[{"gain": 0.30, "frac": 1/3},
                                                     {"gain": 0.50, "frac": 1/3},
                                                     {"gain": 0.80, "frac": 1.0}], mw=0.12, group="mw+staged")),
        ("C3 + vol25 only", mk("r2_C3_vt25", 6, tp=0.5, vt=0.25, group="vol_target")),
        ("C2 对照 N5/TP50/e0.90", mk("r2_C2_ctrl", 5, tp=0.5, expo=0.90, group="control")),
        ("C2 + staged + e0.90", mk("r2_C2_staged", 5, staged=[{"gain": 0.30, "frac": 1/3},
                                                              {"gain": 0.50, "frac": 1/3},
                                                              {"gain": 0.80, "frac": 1.0}], expo=0.90, group="staged")),
        ("C2 + staged + vol25 + e0.90", mk("r2_C2_staged_vt25", 5, staged=[{"gain": 0.30, "frac": 1/3},
                                                                           {"gain": 0.50, "frac": 1/3},
                                                                           {"gain": 0.80, "frac": 1.0}],
                                          expo=0.90, vt=0.25, group="staged+vt")),
    ]

    rows, L = [], []
    L.append("# Round 2 结构探针（max_weight / staged_take / vol_target）\n")
    L.append("- 骨架：amihud_60 / R30 / 主板（exclude_star/bj/chinext）/ stop_exec=next / phase 0 / 新网格")
    L.append("- 主口径：realistic = 佣金0.025%(最低5元)+印花0.05%+过户0.001%+滑点0.2%/边，5 万、100 股整手")
    L.append("- 对照：C3 = N6 TP50 满仓；C2 = N5 TP50 exposure 0.90")
    L.append("- `fresh` = 2026-01-05 空仓起步（同成本/整手）；`phase_pass` = 5 相位里三线全过的档数\n")

    for name, sp in cfgs:
        a, by, cfg = analyse(sp)
        a["fresh_2026"] = analyse(dict(sp, window=dict(sp["window"],
                                      warmup_start=sp["window"]["eval_start"])))[0]["total"]
        # exclude top3 / top5 重跑（主口径)
        ex3 = dict(sp); ex3["selector"] = dict(sp["selector"], exclude_codes=a["top3_codes"])
        e3, _, _ = analyse(ex3)
        ex5 = dict(sp); ex5["selector"] = dict(sp["selector"], exclude_codes=a["top5_codes"])
        e5, _, _ = analyse(ex5)
        # fixed 成本版
        fx = dict(sp); fx["cost"] = dict(sp["cost"], mode="fixed", one_way=0.005)
        f, _, _ = analyse(fx)
        # 相位
        passes = 0
        for ph in (-10, -5, 0, 5, 10):
            s2 = dict(sp, phase=ph)
            c2 = H.normalize_spec(s2)
            s2sim = H.run_sim(c2)
            m2 = H._window_metrics(s2sim, c2["window"]["eval_start"], c2["window"]["eval_end"],
                                   "2025-12-31", c2)
            if (m2["total"] >= 0.60) and (m2["mdd"] >= -0.15) and (m2["win_period"] or 0) >= 0.80:
                passes += 1
        row = dict(config=name, id=sp["id"], group=sp["group"], **{
            k: a[k] for k in ("total", "mdd", "win_period", "n_periods", "win_trade", "win_month",
                              "block30_win", "fresh_2026", "n_hold_avg", "n_distinct_names",
                              "top1_share", "top3_pnl_share", "top5_share", "n_staged_events",
                              "total_2025", "win_period_2025", "total_2024")})
        row.update(top3_codes=",".join(a["top3_codes"]), top5_codes=",".join(a["top5_codes"]),
                   ex3_total=e3["total"], ex3_mdd=e3["mdd"], ex3_wp=e3["win_period"],
                   ex3_fresh=e3["fresh_2026"],
                   ex5_total=e5["total"], ex5_mdd=e5["mdd"], ex5_wp=e5["win_period"],
                   fixed_total=f["total"], fixed_mdd=f["mdd"], fixed_wp=f["win_period"],
                   phase_pass=passes)
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(RUNS / "round2_probe.csv", index=False)

    L.append("## 1. 主表（realistic 5 万整手）\n")
    L.append("| 配置 | total | mdd | 段胜率 | 按笔 | 月胜率 | fresh | top1 | top3 | top5 | 实际持仓 | 剔除top3 total/mdd/段 | 剔除top5 total/mdd/段 | 0.5%总收益 | phase_pass |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for _, r in df.iterrows():
        L.append(f"| {r['config']} | {(r['total'] or 0)*100:+.1f}% | {(r['mdd'] or 0)*100:+.2f}% | "
                 f"{(r['win_period'] or 0)*100:.1f}% | {(r['win_trade'] or 0)*100:.1f}% | "
                 f"{(r['win_month'] or 0)*100:.0f}% | {(r['fresh_2026'] or 0)*100:+.1f}% | "
                 f"{(r['top1_share'] or 0)*100:.1f}% | {(r['top3_pnl_share'] or 0)*100:.1f}% | "
                 f"{(r['top5_share'] or 0)*100:.1f}% | {r['n_hold_avg']:.1f} | "
                 f"{(r['ex3_total'] or 0)*100:+.1f}%/{(r['ex3_mdd'] or 0)*100:+.1f}%/{(r['ex3_wp'] or 0)*100:.0f}% | "
                 f"{(r['ex5_total'] or 0)*100:+.1f}%/{(r['ex5_mdd'] or 0)*100:+.1f}%/{(r['ex5_wp'] or 0)*100:.0f}% | "
                 f"{(r['fixed_total'] or 0)*100:+.1f}% | {int(r['phase_pass'])}/5 |")
    L.append("")

    L.append("## 2. OOS（同参数）\n")
    L.append("| 配置 | 2025 total | 2025 段胜率 | 2024 total |")
    L.append("|---|---|---|---|")
    for _, r in df.iterrows():
        L.append(f"| {r['config']} | {(r['total_2025'] or 0)*100:+.0f}% | {(r['win_period_2025'] or 0)*100:.0f}% | "
                 f"{(r['total_2024'] or 0)*100:+.0f}% |")
    L.append("")

    L.append("## 3. 剔除口径说明\n")
    L.append("- `exclude_codes` 在**调仓选股阶段**把 Top3/Top5 从池里剔除，之后用 rank N+1.. 补足，"
             "因此剔除后仍是 N 只等权 —— 这模拟「这些票不可买」的真实反事实，比事后删 PnL 更严格。")
    L.append("- top3/top5 占比 = 2026 窗口内已平仓交易按股票汇总的 PnL / 总 PnL。")
    L.append("")

    L.append("## 4. 观察\n")
    for _, r in df.iterrows():
        concl = []
        if (r["total"] or 0) >= 0.60:
            concl.append("收益≥60%")
        if (r["mdd"] or -9) >= -0.15:
            concl.append("回撤≤15%")
        if (r["win_period"] or 0) >= 0.80:
            concl.append("段胜率≥80%")
        if (r["top3_pnl_share"] or 1) <= 0.40:
            concl.append("top3≤40%")
        L.append(f"- **{r['config']}**：{('、'.join(concl) if concl else '无一项达标')}；"
                 f"剔除 top3 后 {(r['ex3_total'] or 0)*100:+.1f}%")
    L.append("")
    L.append("## 5. 限制")
    for x in H.LIMITATIONS:
        L.append(f"- {x}")
    (RUNS / "round2_probe.md").write_text("\n".join(L), encoding="utf-8")
    print(df[["config", "total", "mdd", "win_period", "win_trade", "fresh_2026",
              "top3_pnl_share", "top5_share", "ex3_total", "phase_pass"]].to_string())
    return df


if __name__ == "__main__":
    main()
