#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
c2_check.py — 对 Lead 提出的 C2 候选 (amihud_60 / 主板 / N5 / R30 / TP50% / 90% 仓位) 的独立对抗性复算

依赖: 同目录 prior_check.py（审计员自写引擎，不 import engine/harness/ledger）。
用法:
  .venv/bin/python team/audit/c2_check.py all --json team/audit/out/c2.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prior_check as pc  # 审计员自己的独立引擎

OUT = os.path.join(pc.ROOT, "team", "audit", "out")
MAINBOARD = ("688", "689", "300", "301", "8", "4")   # 剔科创/创业/北交 → 主板
RETAIL = ("688", "689", "8", "4")                    # Lead §11 的零售池 (仍含创业板)

C2 = dict(
    factor="amihud_60", n=5, rebal=30, take=0.50, stop=None,
    stop_exec="next", exclude=MAINBOARD, capital=50_000.0,
    lot=1, cost_one_way=0.005, run_start="2024-01-01",
    phase=0, legacy_grid=False, exposure=0.90,
)


def run(**over):
    kw = dict(C2)
    kw.update(over)
    r = pc.run_strategy(pc.get_inputs(), **kw)
    return r, pc.metrics(r)


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (c - h, c + h)


def passes(m) -> bool:
    return (m["total_2026"] >= 0.60) and (m["mdd_2026"] >= -0.15) and (m["win_period"] >= 0.80)


def summary(m) -> dict:
    return dict(total=round(m["total_2026"] * 100, 2), ann=round(m["ann_2026"] * 100, 2),
                mdd=round(m["mdd_2026"] * 100, 2),
                wp=round(m["win_period"], 3) if not np.isnan(m["win_period"]) else None,
                n_periods=m["n_periods"],
                wt=round(m["win_trade"] * 100, 1) if not np.isnan(m["win_trade"]) else None,
                n_trades=m["n_trades"],
                wm=m["win_month_n"],
                periods=[round(x * 100, 2) for x in m["period_rets"]],
                partial=round(m["last_partial_ret"] * 100, 2) if not np.isnan(m["last_partial_ret"]) else None,
                cost=round(m["cost_total"], 0),
                passes=passes(m))


def main() -> dict:
    pc.get_inputs()
    out = {}

    # ---------- 0) 基线 ----------
    r90, m90 = run(exposure=0.90)
    r85, m85 = run(exposure=0.85)
    out["C2_90"] = summary(m90)
    out["C2_85"] = summary(m85)
    out["C2_90"]["exposure_mean"] = round(float(r90.exposure.loc["2026-01-05":"2026-11-04"].mean()), 3)
    out["C2_85"]["exposure_mean"] = round(float(r85.exposure.loc["2026-01-05":"2026-11-04"].mean()), 3)

    # ---------- a) phase(-10..+10) × exposure(0.85/0.90) ----------
    grid = []
    for exp in (0.85, 0.90):
        for ph in (-10, -5, 0, 5, 10):
            r, m = run(exposure=exp, phase=ph)
            row = summary(m)
            row.update(exposure=exp, phase=ph)
            grid.append(row)
    out["phase_x_exposure"] = grid
    out["phase_pass_count"] = {
        "0.85": int(sum(1 for g in grid if g["exposure"] == 0.85 and g["passes"])),
        "0.90": int(sum(1 for g in grid if g["exposure"] == 0.90 and g["passes"])),
    }
    out["phase_spread"] = {
        "0.90_total_min": min(g["total"] for g in grid if g["exposure"] == 0.90),
        "0.90_total_max": max(g["total"] for g in grid if g["exposure"] == 0.90),
        "0.85_total_min": min(g["total"] for g in grid if g["exposure"] == 0.85),
        "0.85_total_max": max(g["total"] for g in grid if g["exposure"] == 0.85),
    }

    # ---------- b) Top3 剔除 ----------
    # 先算 2026 逐票 PnL 贡献
    tr = r90.trades
    ev = tr[(tr.exit_date >= pc.EVAL_START) & (tr.exit_date <= pc.EVAL_END)].copy()
    pnl = ev.groupby("code")["net_pnl"].sum().sort_values(ascending=False)
    tot_pnl = float(ev["net_pnl"].sum())
    top3 = list(pnl.index[:3])
    top5 = list(pnl.index[:5])
    out["attribution"] = dict(
        pnl_2026=round(tot_pnl, 0), pnl_pct_of_base=round(tot_pnl / m90["base_equity"] * 100, 2),
        n_codes=int(len(pnl)),
        top1=str(pnl.index[0]), top1_pnl=round(float(pnl.iloc[0]), 0),
        top1_share=round(float(pnl.iloc[0] / tot_pnl) * 100, 1),
        top3_codes=top3, top3_pnl=round(float(pnl.head(3).sum()), 0),
        top3_share=round(float(pnl.head(3).sum() / tot_pnl) * 100, 1),
        top5_share=round(float(pnl.head(5).sum() / tot_pnl) * 100, 1),
        top10=pnl.head(10).round(1).to_dict(),
        bottom5=pnl.tail(5).round(1).to_dict(),
        monthly=m90["monthly_rets"],
    )
    for lbl, over in [("exclude_top1", dict(exclude=MAINBOARD + (top3[0],))),
                      ("exclude_top3", dict(exclude=MAINBOARD + tuple(top3)))]:
        r, m = run(exposure=0.90, **over)
        s = summary(m)
        s["base_share"] = round(m["total_2026"] / m90["total_2026"] * 100, 1)
        out[lbl] = s
    # 逐票明细 (2026)
    out["trades_2026"] = ev[["code", "entry_date", "exit_date", "shares", "entry_px", "exit_px",
                             "gross_ret", "net_ret", "net_pnl", "reason", "hold_days"]].assign(
        entry_date=lambda d: d.entry_date.dt.strftime("%Y-%m-%d"),
        exit_date=lambda d: d.exit_date.dt.strftime("%Y-%m-%d")).to_dict("records")

    # ---------- c) 成本压力 ----------
    r08, m08 = run(exposure=0.90, cost_one_way=0.008)
    out["cost_08"] = summary(m08)
    rrf, mrf = run(exposure=0.90, cost_one_way=None, lot=100)
    out["realfee_50k_lot100"] = summary(mrf)
    r10, m10 = run(exposure=0.90, cost_one_way=None, lot=100, capital=10_000.0)
    out["realfee_10k_lot100"] = summary(m10)

    # ---------- d) OOS 2025 / 2025H2 / 2024 ----------
    eq = r90.eq
    for lbl, a, b, base_date in [
        ("2024", "2024-01-01", "2024-12-31", "2023-12-31"),
        ("2025", "2025-01-01", "2025-12-31", "2024-12-31"),
        ("2025H2", "2025-07-01", "2025-12-31", "2025-06-30"),
    ]:
        seg = eq.loc[a:b]
        bb = eq.loc[:base_date]
        base = float(bb.iloc[-1]) if len(bb) else float(eq.iloc[0])
        per = r90.periods
        p = per[(per.start >= pd.Timestamp(a)) & (per.end <= pd.Timestamp(b)) & per.complete]
        tr = r90.trades
        t = tr[(tr.exit_date >= pd.Timestamp(a)) & (tr.exit_date <= pd.Timestamp(b))]
        mm = eq.loc[:pd.Timestamp(b)].resample("ME").last()
        am = pd.concat([pd.Series([base], index=[pd.Timestamp(base_date)]), mm.loc[a:]])
        am = am[~am.index.duplicated(keep="last")].sort_index()
        mret = am.pct_change().dropna()
        out[f"oos_{lbl}"] = dict(
            total=round(float(seg.iloc[-1] / base - 1) * 100, 2),
            mdd=round(float((seg / seg.cummax() - 1).min()) * 100, 2),
            win_period=round(float((p.ret > 0).mean()), 3) if len(p) else None,
            n_periods=int(len(p)),
            win_trade=round(float((t.net_ret > 0).mean()), 3) if len(t) else None,
            win_month=f"{int((mret>0).sum())}/{int(len(mret))}",
        )

    # ---------- 仓位机制: 调仓日重置 vs 每日恒定的近似 ----------
    # 调仓日重置 = 上面实现的片; 用"每日恒 0.9"不可直接实现, 用 0.9 与 1.0 的线性近似说明
    r100, m100 = run(exposure=1.00)
    out["exposure_mechanics"] = dict(
        e90=summary(m90), e100=summary(m100),
        ratio_total=round(m90["total_2026"] / m100["total_2026"], 3),
        ratio_mdd=round(m90["mdd_2026"] / m100["mdd_2026"], 3),
        note="调仓日把投入比例重置为 exposure; 期间现金比例随持仓市值漂移; 止损/止盈卖出后现金停泊到下一调仓日.",
    )

    # ---------- 胜率口径 ----------
    out["win_rates"] = dict(
        win_period=f"{int(round(m90['win_period']*m90['n_periods']))}/{m90['n_periods']}",
        wilson95=list(wilson(int(round(m90["win_period"] * m90["n_periods"])), m90["n_periods"])),
        win_trade=f"{m90['trade_win_n']}/{m90['n_trades']}",
        win_trade_wilson95=list(wilson(m90["trade_win_n"], m90["n_trades"])),
        win_month=m90["win_month_n"],
        win_month_wilson95=list(wilson(int(m90["win_month_n"].split("/")[0]), int(m90["win_month_n"].split("/")[1]))),
        note="段胜率分母 n=6 极小; Wilson 95% 下界见上",
    )

    # ---------- 多重检验 ----------
    out["multiple_testing"] = dict(
        n_specs_this_round="180+ (Lead 口径)",
        note="C2 是本轮 180+ spec 中的一个; 若单 spec 在无 alpha 下三线全过概率 ~p, 则 180 个中至少一个的概率 1-(1-p)^180. "
             "C2 必须依赖 2025 OOS + 相位稳定性 + Top3 剔除后仍成立, 否则按 data-snooping 降级.",
    )
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", nargs="?", default="all")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    res = main()
    for k, v in res.items():
        if k in ("trades_2026",):
            continue
        print(f"\n### {k}")
        print(json.dumps(v, ensure_ascii=False, indent=1, default=str))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(res, f, ensure_ascii=False, indent=2, default=str)
        print("\nwrote", args.json)
