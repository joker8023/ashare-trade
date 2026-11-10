"""
team/lib/run_exposure.py — 官方 C2/C3 仓位缓冲（portfolio.exposure）矩阵
=======================================================================
Lead 指令（PROTOCOL v1.2 追加）：
  C2 = amihud_60 N5 R30 TP50 主板（exclude_star/bj/chinext 全 true）
  C3 = amihud_60 N6 R30 TP50 主板
  矩阵 = 2 策略 × 5 相位(-10/-5/0/+5/+10) × 4 exposure(1.0 参考/0.90/0.875/0.85) × 2 成本口径(0.5%/边主口径、realistic 次口径)

输出（team/runs/batch_003_exposure/）：
  results.csv        一行一 spec（全部指标 + fresh_2026）
  summary.md         官方摘要：Tier 表带 phase_pass_count（5 档中几档三线全过）
  run_batch 的 batch_003exp_*.csv/md 一并落地
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
TEAM = HERE.parent
sys.path.insert(0, str(TEAM))

import harness as H              # noqa: E402
import run_batch as RB           # noqa: E402

OUT = TEAM / "runs" / "batch_003_exposure"
PHASES = (-10, -5, 0, 5, 10)
EXPOS = (1.0, 0.90, 0.875, 0.85)
COSTS = (("fixed", 0.005), ("realistic", 0.005))


def build_specs():
    specs = []
    for name, n in (("C2", 5), ("C3", 6)):
        for expo in EXPOS:
            for cname, one_way in COSTS:
                for ph in PHASES:
                    sid = f"b003_{name}_amihud60_N{n}_R30_tp50_e{expo:.3f}_{cname}_ph{ph:+d}"
                    specs.append(dict(
                        id=sid,
                        group=f"{name}_e{expo:.3f}_{cname}",
                        selector=dict(type="amihud_60", n=n, size_range=[0.05, 0.30],
                                      min_adv=5_000_000, exclude_star=True, exclude_bj=True,
                                      exclude_chinext=True, price_min=None, price_max=None,
                                      params={}),
                        rebalance_days=30,
                        exit=dict(trailing_stop=None, fixed_stop=None, take_profit=0.50,
                                  trailing_take=None, max_hold_days=None, stop_exec="next"),
                        timing=dict(type="none", index=None, ma=None, out_asset="cash"),
                        cost=dict(mode=cname, one_way=one_way, capital=50000, lot_size=100),
                        portfolio=dict(exposure=expo),
                        window=dict(warmup_start="2024-01-01", eval_start="2026-01-05",
                                    eval_end="2026-11-04"),
                        phase=ph,
                        notes=f"{name} exposure={expo} cost={cname} phase={ph}",
                    ))
    return specs


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    specs = build_specs()
    print(f"[exposure] {len(specs)} specs → {OUT}", flush=True)
    t0 = time.time()
    res = RB.run_batch(specs, "003exp", outdir=OUT, variants=("next", "fresh"), do_phase=False)
    df = pd.read_csv(OUT / "batch_003exp_results.csv")
    df["pass3"] = ((df["total"] >= 0.60) & (df["mdd"] >= -0.15) & (df["win_period"] >= 0.80)).astype(int)
    df["phase_pass_count"] = df.groupby("group")["pass3"].transform("sum")
    df.to_csv(OUT / "results.csv", index=False)

    # ---- 相位通过数（每个 strategy×exposure×cost 组，5 档里几档三线全过） ----
    grp = df.groupby(["selector", "n", "group"]).agg(
        n_phase=("phase", "size"), phase_pass=("pass3", "sum"),
        total_med=("total", "median"), total_min=("total", "min"), total_max=("total", "max"),
        mdd_med=("mdd", "median"), mdd_worst=("mdd", "min"),
        wp_med=("win_period", "median"), wt_med=("win_trade", "median"),
        fresh_med=("fresh_2026", "median"), hold=("n_hold_avg", "median"),
        oos25_med=("total_2025", "median")).reset_index().sort_values(
        ["selector", "group"], ascending=[True, True])

    L = []
    A = L.append
    A("# Batch 003 — C2/C3 仓位缓冲（exposure）官方矩阵\n")
    A(f"- 生成：{time.strftime('%Y-%m-%d %H:%M:%S')}；spec 数 **{len(df)}**；"
      f"耗时 {res['meta']['elapsed_sec']}s；harness md5 `{res['meta']['harness_md5']}`")
    A("- 定义：C2 = `amihud_60` N5 R30 TP50 主板；C3 = `amihud_60` N6 R30 TP50 主板；"
      "主板 = exclude_star/bj/chinext 全 true")
    A("- `portfolio.exposure=x`：每次调仓只投入 `cash×x`，其余留现金；不加杠杆、不每日再平衡")
    A("- 主口径 `stop_exec=next`（t 收盘触发→t+1 收盘卖出）；`win_period` 只计完整段（R30 2026 共 6 段）")
    A("- 成本：`fixed` = 0.5%/边（主判定）；`realistic` = 佣金0.025%(最低5)+印花0.05%+过户0.001%+滑点0.2%/边+100股整手")
    A("- `phase_pass_count` = 5 个相位（-10/-5/0/+5/+10）中三线同时满足的档数；Tier A 要求 ≥3")
    A("")

    A("## 1. 按 (策略 × exposure × 成本) 汇总\n")
    A("| 策略 | N | exposure/成本 | 档数 | phase_pass | total 中位 | total 区间 | mdd 中位 | mdd 最差 | win_period 中位 | win_trade 中位 | fresh 中位 | 实际持仓 | 2025 OOS 中位 |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for _, r in grp.iterrows():
        A(f"| {r['selector']} | {int(r['n'])} | {r['group']} | {int(r['n_phase'])} | "
          f"**{int(r['phase_pass'])}/5** | {r['total_med']*100:+.1f}% | "
          f"{r['total_min']*100:+.1f}%~{r['total_max']*100:+.1f}% | {r['mdd_med']*100:+.2f}% | "
          f"{r['mdd_worst']*100:+.2f}% | {r['wp_med']*100:.0f}% | {r['wt_med']*100:.1f}% | "
          f"{r['fresh_med']*100:+.1f}% | {r['hold']:.1f} | {r['oos25_med']*100:+.0f}% |")
    A("")

    A("## 2. 逐相位明细（total / mdd / win_period）\n")
    A("| 策略 | exposure | 成本 | phase | total | mdd | win_period | n_periods | win_trade | fresh_2026 | n_hold |")
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    for _, r in df.sort_values(["selector", "group", "phase"]).iterrows():
        A(f"| {r['selector']} | {r['group'].split('_')[1]} | {r['cost_mode']} | {int(r['phase']):+d} | "
          f"{r['total']*100:+.1f}% | {r['mdd']*100:+.2f}% | {(r['win_period'] or 0)*100:.0f}% | "
          f"{int(r['n_periods'])} | {(r['win_trade'] or 0)*100:.1f}% | "
          f"{(r['fresh_2026'] or 0)*100:+.1f}% | {r['n_hold_avg']:.1f} |")
    A("")

    A("## 3. Tier 判定（主口径 = fixed 成本；phase_pass ≥3 才算 PHASE_ROBUST）\n")
    cand = df[df["cost_mode"] == "fixed"].copy()
    cand["phase_pass_count"] = cand["group"].map(
        df[df["cost_mode"] == "fixed"].groupby("group")["pass3"].sum())
    tier_a = cand[(cand["total"] >= 0.60) & (cand["mdd"] >= -0.15) & (cand["win_period"] >= 0.80)]
    A("| id | phase | exposure | total | mdd | win_period | win_trade | fresh_2026 | phase_pass_count | 结论 |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for _, r in tier_a.sort_values(["selector", "group", "phase"]).iterrows():
        concl = "Tier A（PHASE_ROBUST）" if r["phase_pass_count"] >= 3 else "Tier A 但 PHASE_LUCK"
        A(f"| {r['id']} | {int(r['phase']):+d} | {r['group'].split('_')[1]} | {r['total']*100:+.1f}% | "
          f"{r['mdd']*100:+.2f}% | {r['win_period']*100:.0f}% | {r['win_trade']*100:.1f}% | "
          f"{r['fresh_2026']*100:+.1f}% | {int(r['phase_pass_count'])}/5 | {concl} |")
    A("")
    A("## 4. 口径限制\n")
    for x in H.LIMITATIONS:
        A(f"- {x}")
    A("")

    (OUT / "summary.md").write_text("\n".join(L), encoding="utf-8")
    print(f"[exposure] done {time.time()-t0:.1f}s → {OUT/'summary.md'}")
    print(grp[["selector", "group", "phase_pass", "total_med", "mdd_med", "wp_med"]].to_string())
    return df


if __name__ == "__main__":
    main()
