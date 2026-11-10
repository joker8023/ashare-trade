#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
c5_check.py — C5 三 sleeve 组合 + C3 对照的独立对抗性复算

C5 = amihud_60 / 主板 / N=5 / R=30 / TP50% / 3 个 sleeve (phase −8/0/+8) /
     资金三等分 / 每份 exposure 0.9 / 合成净值
C3 = 同因子 N=6 / 满仓 / 单 sleeve phase 0 / realistic+滑点

依赖审计员自写引擎 prior_check.py（不 import engine/harness/ledger）。
输出: team/audit/out/c5.json + team/audit/out/c3.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prior_check as pc

OUT = os.path.join(pc.ROOT, "team", "audit", "out")
MB = ("688", "689", "300", "301", "8", "4")   # 主板
CAP = 50_000.0
N_SLEEVE = 3


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (c - h, c + h)


def _month_stats(eq: pd.Series):
    base = float(eq.loc[:pc.BASE_DATE].iloc[-1]) if len(eq.loc[:pc.BASE_DATE]) else float(eq.iloc[0])
    mm = eq.loc[:pc.EVAL_END].resample("ME").last()
    allm = pd.concat([pd.Series([base], index=[pc.BASE_DATE]), mm.loc["2026-01-01":]])
    allm = allm[~allm.index.duplicated(keep="last")].sort_index()
    mr = allm.pct_change().dropna().loc[:"2026-10-31"]
    return int((mr > 0).sum()), int(len(mr))


def combined_metrics(eq: pd.Series, trades: pd.DataFrame, periods: pd.DataFrame) -> dict:
    eq = eq.dropna()
    base = float(eq.loc[:pc.BASE_DATE].iloc[-1]) if len(eq.loc[:pc.BASE_DATE]) else float(eq.iloc[0])
    w = eq.loc[pc.EVAL_START:pc.EVAL_END]
    total = float(w.iloc[-1] / base - 1)
    curve = pd.concat([pd.Series([base], index=[pc.BASE_DATE]), w])
    mdd = float((curve / curve.cummax() - 1).min())
    wm, wmn = _month_stats(eq)
    per = periods[periods["complete"].fillna(False).astype(bool)] if len(periods) else periods
    if len(per):
        per = per[(per.start >= pc.EVAL_START) & (per.end <= pc.EVAL_END)]
    wp = float((per.ret > 0).mean()) if len(per) else float("nan")
    tr = trades[(trades.exit_date >= pc.EVAL_START) & (trades.exit_date <= pc.EVAL_END)] if len(trades) else trades
    wt = float((tr.net_ret > 0).mean()) if len(tr) else float("nan")
    return dict(total=total, mdd=mdd, win_period=wp, n_periods=int(len(per)),
                win_month=f"{wm}/{wmn}", win_trade=wt, n_trades=int(len(tr)),
                period_rets=[round(float(x), 6) for x in per.ret] if len(per) else [],
                base=base, end=float(w.iloc[-1]))


def combine(eqs, trades_list, periods=None) -> dict:
    """A: 三份资金各自复利后相加（官方口径）。"""
    eq = None
    for e in eqs:
        eq = e if eq is None else eq.add(e, fill_value=np.nan)
    eq = eq.dropna()
    tr = pd.concat(trades_list, ignore_index=True) if trades_list else pd.DataFrame()
    if periods is None:
        # 用 phase 0 sleeve 的段边界作为组合段边界
        periods = trades_list[0].attrs.get("periods") if trades_list else pd.DataFrame()
    return dict(eq=eq, trades=tr, metrics=combined_metrics(eq, tr, periods))


# ---------------------------------------------------------------------------
# 运行
# ---------------------------------------------------------------------------
def run_sleeve(phase: int, *, exposure=0.90, n=5, lot=1, cost_one_way=0.005,
               slip=0.0, capital=CAP / N_SLEEVE, run_start="2024-01-01",
               take=0.50, factor="amihud_60", exclude=MB, rebal=30):
    r = pc.run_strategy(
        pc.get_inputs(), factor=factor, n=n, rebal=rebal, take=take, stop=None,
        stop_exec="next", exclude=exclude, capital=capital, lot=lot,
        cost_one_way=cost_one_way, slip=slip, run_start=run_start, phase=phase,
        legacy_grid=False, exposure=exposure)
    r.periods.attrs = {}
    return r


def build_group(shift: int, phases=(-8, 0, 8), **kw) -> dict:
    cap_per = float(kw.get("capital", CAP / N_SLEEVE))
    rs = [run_sleeve(shift + p, **kw) for p in phases]
    # 段边界: 中间 sleeve (shift+0) 的完整段
    mid = rs[1]
    per = mid.periods.copy()
    # 合成: 统一日期轴, 未开始交易的 sleeve 记为其初始资金(现金), 之后 ffill
    idx = pd.DatetimeIndex(sorted(set().union(*[set(r.eq.index) for r in rs])))
    eq = None
    for r in rs:
        e = r.eq.reindex(idx).ffill().fillna(cap_per)
        eq = e if eq is None else eq + e
    # 若组合从 2026 才起步, 在 2026-01-05 补一个纯现金起点
    if eq.index[0] > pc.EVAL_START:
        eq = pd.concat([pd.Series([cap_per * len(rs)], index=[pc.EVAL_START]), eq])
        eq = eq[~eq.index.duplicated(keep='last')].sort_index()
    tr = pd.concat([r.trades.assign(sleeve=p) for r, p in zip(rs, phases)], ignore_index=True)
    m = combined_metrics(eq, tr, per)
    m["sleeves"] = [dict(phase=p, total=float(pc.metrics(r)["total_2026"]),
                         mdd=float(pc.metrics(r)["mdd_2026"]),
                         wp=float(pc.metrics(r)["win_period"]),
                         n_periods=int(pc.metrics(r)["n_periods"]),
                         wt=float(pc.metrics(r)["win_trade"]),
                         n_trades=int(pc.metrics(r)["n_trades"]))
                    for r, p in zip(rs, phases)]
    return dict(eq=eq, trades=tr, periods=per, metrics=m, sleeves=rs, m=mid)


def phase_shift_table(**kw) -> list:
    rows = []
    for s in (-10, -5, 0, 5, 10):
        g = build_group(s, **kw)
        m = g["metrics"]
        rows.append(dict(shift=s, total=round(m["total"] * 100, 2), mdd=round(m["mdd"] * 100, 2),
                         wp=round(m["win_period"], 3), n_periods=m["n_periods"],
                         wt=round(m["win_trade"] * 100, 1), n_trades=m["n_trades"],
                         wm=m["win_month"],
                         pass3=bool(m["total"] >= 0.60 and m["mdd"] >= -0.15 and m["win_period"] >= 0.80)))
    return rows


def main() -> dict:
    pc.get_inputs()
    out = {}

    # ---------- 0) 官方口径复现: phase −8/0/+8, exposure 0.9, 固定成本 0.5%, 分数股 ----------
    g = build_group(0, exposure=0.90, lot=1, cost_one_way=0.005, slip=0.0, capital=CAP / N_SLEEVE)
    out["C5_05cost"] = g["metrics"]
    out["C5_05cost"]["sleeves"] = g["metrics"]["sleeves"]
    out["C5_05cost"]["exposure_mean"] = {
        p: round(float(r.exposure.loc[pc.EVAL_START:pc.EVAL_END].mean()), 3)
        for r, p in zip(g["sleeves"], (-8, 0, 8))}

    # ---------- 1) 合成口径 A(相加) vs B(等权平均) vs C(每日再平衡) ----------
    rs = g["sleeves"]
    eqs = [r.eq for r in rs]
    base_i = [float(e.loc[:pc.BASE_DATE].iloc[-1]) for e in eqs]
    tot_i = [float(e.loc[pc.EVAL_START:pc.EVAL_END].iloc[-1] / b - 1) for e, b in zip(eqs, base_i)]
    # B: 等权平均 (每份起始资金相同, 但 2026 基数不同 → 两种定义)
    tot_B_equal_return = float(np.mean(tot_i))
    tot_B_equal_base = float(sum(e.loc[pc.EVAL_START:pc.EVAL_END].iloc[-1] for e in eqs) /
                             sum(base_i) - 1)
    # C: 每日再平衡 = 三 sleeve 日收益等权平均
    rets = pd.concat([e.pct_change() for e in eqs], axis=1).dropna()
    dr = rets.mean(axis=1)
    eqC = (1 + dr.loc[pc.EVAL_START:pc.EVAL_END]).cumprod()
    baseC = float(eqC.iloc[0])  # 首日收益已含
    tot_C = float(eqC.iloc[-1] - 1)
    mdd_C = float((eqC / eqC.cummax() - 1).min())
    out["combination_methods"] = dict(
        A_sum=round(g["metrics"]["total"] * 100, 2),
        A_mdd=round(g["metrics"]["mdd"] * 100, 2),
        B_mean_sleeve_returns=round(tot_B_equal_return * 100, 2),
        B_weighted_by_2026_base=round(tot_B_equal_base * 100, 2),
        C_daily_rebalanced=round(tot_C * 100, 2),
        C_daily_rebalanced_mdd=round(mdd_C * 100, 2),
        sleeve_totals=[round(x * 100, 2) for x in tot_i],
        sleeve_base=[round(x, 0) for x in base_i],
        note="A=官方口径(三份各自复利后相加); B=等权平均收益率; C=每日把三 sleeve 拉回等权(不可实施, 仅对照)",
    )

    # ---------- 2) top3 PnL 占比 + 剔除 top3 ----------
    ev = g["trades"]
    ev26 = ev[(ev.exit_date >= pc.EVAL_START) & (ev.exit_date <= pc.EVAL_END)].copy()
    pnl = ev26.groupby("code")["net_pnl"].sum().sort_values(ascending=False)
    totpnl = float(pnl.sum())
    top3 = list(pnl.index[:3])
    out["top3"] = dict(
        pnl=round(totpnl, 0), pnl_pct_of_base=round(totpnl / g["metrics"]["base"] * 100, 2),
        top1=str(pnl.index[0]), top1_pnl=round(float(pnl.iloc[0]), 0),
        top1_share=round(float(pnl.iloc[0] / totpnl) * 100, 1),
        top3_codes=top3, top3_pnl=round(float(pnl.head(3).sum()), 0),
        top3_share=round(float(pnl.head(3).sum() / totpnl) * 100, 1),
        top5_share=round(float(pnl.head(5).sum() / totpnl) * 100, 1),
        top10=pnl.head(10).round(1).to_dict(),
        n_codes=int(len(pnl)),
    )
    gx = build_group(0, exposure=0.90, lot=1, cost_one_way=0.005, slip=0.0,
                     capital=CAP / N_SLEEVE, exclude=MB + tuple(top3))
    out["exclude_top3"] = gx["metrics"]
    out["exclude_top3"]["base_share"] = round(gx["metrics"]["total"] / g["metrics"]["total"] * 100, 1)

    # ---------- 3) realistic 成本 + 5 万整手 ----------
    # 3a) 2024 预热 (账本从 2024 起滚到 2026, 每 sleeve 此时本金已 >1.6万)
    gr = build_group(0, exposure=0.90, lot=100, cost_one_way=None, slip=0.002, capital=CAP / N_SLEEVE)
    out["realistic_warm"] = gr["metrics"]
    out["realistic_warm"]["exposure_mean"] = {
        p: round(float(r.exposure.loc[pc.EVAL_START:pc.EVAL_END].mean()), 3)
        for r, p in zip(gr["sleeves"], (-8, 0, 8))}
    out["realistic_warm"]["skipped_lot"] = {p: int(r.meta.get("skipped_lot", 0))
                                            for r, p in zip(gr["sleeves"], (-8, 0, 8))}
    # 3b) fresh 2026 (2026-01-05 每 sleeve 只有 16,667 → 每票 ~3,333, >33 元买不进)
    gf = build_group(0, exposure=0.90, lot=100, cost_one_way=None, slip=0.002,
                     capital=CAP / N_SLEEVE, run_start="2026-01-05")
    out["realistic_fresh"] = gf["metrics"]
    out["realistic_fresh"]["skipped_lot"] = {p: int(r.meta.get("skipped_lot", 0))
                                             for r, p in zip(gf["sleeves"], (-8, 0, 8))}
    out["realistic_fresh"]["exposure_mean"] = {
        p: round(float(r.exposure.loc[pc.EVAL_START:pc.EVAL_END].mean()), 3)
        for r, p in zip(gf["sleeves"], (-8, 0, 8))}
    out["realistic_fresh"]["rebalance_snapshots"] = [
        {p: r.meta.get("rebalance_snapshots", [])[-3:] for r, p in zip(gf["sleeves"], (-8, 0, 8))}]
    # 3c) fresh 0.5% (分数股)
    gf05 = build_group(0, exposure=0.90, lot=1, cost_one_way=0.005, slip=0.0,
                       capital=CAP / N_SLEEVE, run_start="2026-01-05")
    out["fresh_05cost"] = gf05["metrics"]
    # 3d) fresh 整手 + 0.5% (隔离整手影响)
    gf_lot = build_group(0, exposure=0.90, lot=100, cost_one_way=0.005, slip=0.0,
                         capital=CAP / N_SLEEVE, run_start="2026-01-05")
    out["fresh_lot100_05cost"] = gf_lot["metrics"]
    out["fresh_lot100_05cost"]["skipped_lot"] = {p: int(r.meta.get("skipped_lot", 0))
                                                 for r, p in zip(gf_lot["sleeves"], (-8, 0, 8))}
    # 3e) fresh 分数股 + realistic (隔离整手影响)
    gf_fr = build_group(0, exposure=0.90, lot=1, cost_one_way=None, slip=0.002,
                        capital=CAP / N_SLEEVE, run_start="2026-01-05")
    out["fresh_frac_realistic"] = gf_fr["metrics"]

    # ---------- 4) 整组平移相位表 ----------
    out["phase_shift_05"] = phase_shift_table(exposure=0.90, lot=1, cost_one_way=0.005, slip=0.0,
                                              capital=CAP / N_SLEEVE)
    out["phase_shift_realistic"] = phase_shift_table(exposure=0.90, lot=100, cost_one_way=None,
                                                     slip=0.002, capital=CAP / N_SLEEVE)

    # ---------- 5) 单一 sleeve vs 三 sleeve 集中度 ----------
    out["single_sleeve_vs_group"] = dict(
        single_phase0=dict(total=round(float(pc.metrics(rs[1])["total_2026"]) * 100, 2),
                           mdd=round(float(pc.metrics(rs[1])["mdd_2026"]) * 100, 2),
                           wp=round(float(pc.metrics(rs[1])["win_period"]), 3),
                           top3_share=None),
        group=dict(total=round(g["metrics"]["total"] * 100, 2),
                   mdd=round(g["metrics"]["mdd"] * 100, 2),
                   wp=round(g["metrics"]["win_period"], 3),
                   top3_share=out["top3"]["top3_share"]),
    )
    # 单 sleeve 的 top3 占比
    e1 = rs[1].trades
    e1 = e1[(e1.exit_date >= pc.EVAL_START) & (e1.exit_date <= pc.EVAL_END)]
    p1 = e1.groupby("code")["net_pnl"].sum().sort_values(ascending=False)
    out["single_sleeve_vs_group"]["single_phase0"]["top3_share"] = round(
        float(p1.head(3).sum() / p1.sum()) * 100, 1)

    # ---------- 6) C3 与 C5 的相关性 ----------
    r3 = pc.run_strategy(pc.get_inputs(), factor="amihud_60", n=6, rebal=30, take=0.50, stop=None,
                         stop_exec="next", exclude=MB, capital=CAP, lot=100, cost_one_way=None,
                         slip=0.002, run_start="2024-01-01", phase=0, legacy_grid=False, exposure=1.0)
    m3 = pc.metrics(r3)
    ret5 = g["eq"].pct_change().loc[pc.EVAL_START:pc.EVAL_END]
    ret3 = r3.eq.pct_change().loc[pc.EVAL_START:pc.EVAL_END]
    both = pd.concat([ret5, ret3], axis=1).dropna()
    out["C3"] = dict(
        total=round(m3["total_2026"] * 100, 2), ann=round(m3["ann_2026"] * 100, 2),
        mdd=round(m3["mdd_2026"] * 100, 2), win_period=round(m3["win_period"], 3),
        n_periods=m3["n_periods"], win_trade=round(m3["win_trade"] * 100, 1),
        n_trades=m3["n_trades"], win_month=m3["win_month_n"],
        periods=[round(x * 100, 2) for x in m3["period_rets"]],
        monthly={k: round(v * 100, 2) for k, v in m3["monthly_rets"].items()},
        wilson_wp=list(wilson(int(round(m3["win_period"] * m3["n_periods"])), m3["n_periods"])),
        wilson_wt=list(wilson(m3["trade_win_n"], m3["n_trades"])),
        corr_with_C5_2026=round(float(both.corr().iloc[0, 1]), 3),
        beta_to_C5=round(float(np.cov(both.iloc[:, 1], both.iloc[:, 0])[0, 1] / np.var(both.iloc[:, 0])), 3),
    )
    # C3 top3
    tr3 = r3.trades
    tr3 = tr3[(tr3.exit_date >= pc.EVAL_START) & (tr3.exit_date <= pc.EVAL_END)]
    p3 = tr3.groupby("code")["net_pnl"].sum().sort_values(ascending=False)
    out["C3"]["top3_codes"] = list(p3.index[:3])
    out["C3"]["top3_share"] = round(float(p3.head(3).sum() / p3.sum()) * 100, 1)
    out["C3"]["top5_share"] = round(float(p3.head(5).sum() / p3.sum()) * 100, 1)
    # C3 剔除 top3
    r3x = pc.run_strategy(pc.get_inputs(), factor="amihud_60", n=6, rebal=30, take=0.50, stop=None,
                          stop_exec="next", exclude=MB + tuple(p3.index[:3]), capital=CAP, lot=100,
                          cost_one_way=None, slip=0.002, run_start="2024-01-01", phase=0,
                          legacy_grid=False, exposure=1.0)
    m3x = pc.metrics(r3x)
    out["C3"]["exclude_top3"] = dict(total=round(m3x["total_2026"] * 100, 2),
                                     mdd=round(m3x["mdd_2026"] * 100, 2),
                                     win_period=round(m3x["win_period"], 3),
                                     n_periods=m3x["n_periods"],
                                     win_trade=round(m3x["win_trade"] * 100, 1),
                                     win_month=m3x["win_month_n"])
    # C3 fresh
    r3f = pc.run_strategy(pc.get_inputs(), factor="amihud_60", n=6, rebal=30, take=0.50, stop=None,
                          stop_exec="next", exclude=MB, capital=CAP, lot=100, cost_one_way=None,
                          slip=0.002, run_start="2026-01-05", phase=0, legacy_grid=False, exposure=1.0)
    m3f = pc.metrics(r3f)
    out["C3"]["fresh"] = dict(total=round(m3f["total_2026"] * 100, 2),
                              mdd=round(m3f["mdd_2026"] * 100, 2),
                              win_period=round(m3f["win_period"], 3), n_periods=m3f["n_periods"],
                              win_trade=round(m3f["win_trade"] * 100, 1),
                              win_month=m3f["win_month_n"])
    # C3 2025 OOS
    eq3 = r3.eq
    for lbl, a, b, bd in [("2025", "2025-01-01", "2025-12-31", "2024-12-31"),
                          ("2025H2", "2025-07-01", "2025-12-31", "2025-06-30")]:
        seg = eq3.loc[a:b]
        bb = eq3.loc[:bd]
        base = float(bb.iloc[-1]) if len(bb) else float(eq3.iloc[0])
        per = r3.periods
        p = per[(per.start >= pd.Timestamp(a)) & (per.end <= pd.Timestamp(b)) & per.complete]
        tr = r3.trades
        t = tr[(tr.exit_date >= pd.Timestamp(a)) & (tr.exit_date <= pd.Timestamp(b))]
        mm = eq3.loc[:pd.Timestamp(b)].resample("ME").last()
        am = pd.concat([pd.Series([base], index=[pd.Timestamp(bd)]), mm.loc[a:]])
        am = am[~am.index.duplicated(keep="last")].sort_index()
        mr = am.pct_change().dropna()
        out["C3"][f"oos_{lbl}"] = dict(
            total=round(float(seg.iloc[-1] / base - 1) * 100, 2),
            mdd=round(float((seg / seg.cummax() - 1).min()) * 100, 2),
            win_period=round(float((p.ret > 0).mean()), 3) if len(p) else None,
            n_periods=int(len(p)),
            win_trade=round(float((t.net_ret > 0).mean()), 3) if len(t) else None,
            win_month=f"{int((mr>0).sum())}/{int(len(mr))}")
    # C3 相位表
    c3_phase = []
    for ph in (-10, -5, 0, 5, 10):
        r = pc.run_strategy(pc.get_inputs(), factor="amihud_60", n=6, rebal=30, take=0.50, stop=None,
                            stop_exec="next", exclude=MB, capital=CAP, lot=100, cost_one_way=None,
                            slip=0.002, run_start="2024-01-01", phase=ph, legacy_grid=False, exposure=1.0)
        m = pc.metrics(r)
        c3_phase.append(dict(phase=ph, total=round(m["total_2026"] * 100, 2),
                             mdd=round(m["mdd_2026"] * 100, 2), wp=round(m["win_period"], 3),
                             n_periods=m["n_periods"], wt=round(m["win_trade"] * 100, 1),
                             wm=m["win_month_n"],
                             pass3=bool(m["total_2026"] >= 0.60 and m["mdd_2026"] >= -0.15
                                        and m["win_period"] >= 0.80)))
    out["C3"]["phase_table"] = c3_phase
    # C3 TP 敏感性
    c3_tp = []
    for tp in (0.40, 0.50, 0.60):
        r = pc.run_strategy(pc.get_inputs(), factor="amihud_60", n=6, rebal=30, take=tp, stop=None,
                            stop_exec="next", exclude=MB, capital=CAP, lot=100, cost_one_way=None,
                            slip=0.002, run_start="2024-01-01", phase=0, legacy_grid=False, exposure=1.0)
        m = pc.metrics(r)
        c3_tp.append(dict(tp=tp, total=round(m["total_2026"] * 100, 2),
                          mdd=round(m["mdd_2026"] * 100, 2), wp=round(m["win_period"], 3),
                          wt=round(m["win_trade"] * 100, 1), n_trades=m["n_trades"],
                          wm=m["win_month_n"]))
    out["C3"]["tp_table"] = c3_tp
    # C3 0.5%/边主成本
    r05 = pc.run_strategy(pc.get_inputs(), factor="amihud_60", n=6, rebal=30, take=0.50, stop=None,
                          stop_exec="next", exclude=MB, capital=CAP, lot=1, cost_one_way=0.005,
                          slip=0.0, run_start="2024-01-01", phase=0, legacy_grid=False, exposure=1.0)
    m05 = pc.metrics(r05)
    out["C3"]["cost_05"] = dict(total=round(m05["total_2026"] * 100, 2),
                                mdd=round(m05["mdd_2026"] * 100, 2),
                                win_period=round(m05["win_period"], 3),
                                n_periods=m05["n_periods"],
                                win_trade=round(m05["win_trade"] * 100, 1),
                                win_month=m05["win_month_n"])
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    res = main()
    for k, v in res.items():
        print(f"\n### {k}")
        print(json.dumps(v, ensure_ascii=False, indent=1, default=str))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(res, f, ensure_ascii=False, indent=2, default=str)
        print("\nwrote", args.json)
