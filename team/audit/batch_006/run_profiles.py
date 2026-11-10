#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_profiles.py — batch_006 四画像 Top2 的攻击性复算（fresh 5 万 realistic 整手）

四画像（Lead task-10 规则，在 batch_006_results.csv 上选）：
  收益型 max fresh_total
  均衡型 max fresh_total/|fresh_mdd| 且 fresh_win_period>=70%
  稳健型 max fresh_win_month 且 fresh_mdd>=-8%
  高胜率型 max min(fresh_win_period, fresh_win_month, fresh_win_trade) 且 fresh_total>=15%

每个候选输出：fresh_total/mdd/wp/wm/wt、exposure/cash/nhold、Top3、ex-top3、2024/2025 OOS、phase ±5。
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import prior_check as pc

ROOT = pc.ROOT
MB = ("688", "689", "300", "301", "8", "4")


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (c - h, c + h)


def run(n, take, exposure, phase, run_start="2026-01-05", exclude=None):
    return pc.run_strategy(pc.get_inputs(), factor="amihud_60", n=n, rebal=30, take=take,
                           stop=None, stop_exec="next", exclude=tuple(exclude or MB),
                           capital=50_000.0, lot=100, cost_one_way=None, slip=0.002,
                           run_start=run_start, phase=phase, legacy_grid=False,
                           exposure=exposure)


def metrics_fresh(r):
    m = pc.metrics(r)
    w = r.exposure.loc[pc.EVAL_START:pc.EVAL_END]
    nh = r.nhold.loc[pc.EVAL_START:pc.EVAL_END]
    tr = r.trades
    ev = tr[(tr.exit_date >= pc.EVAL_START) & (tr.exit_date <= pc.EVAL_END)] if len(tr) else tr
    pnl = ev.groupby("code")["net_pnl"].sum().sort_values(ascending=False) if len(ev) else pd.Series(dtype=float)
    tot = float(pnl.sum()) if len(pnl) else 0.0
    return dict(m=m, w=w, nh=nh, ev=ev, pnl=pnl, tot=tot,
                top3=list(pnl.index[:3]) if len(pnl) else [],
                top3_share=float(pnl.head(3).sum() / tot) if tot else np.nan,
                top1_share=float(pnl.iloc[0] / tot) if tot else np.nan)


def main(cands: list[dict]) -> dict:
    out = {}
    for c in cands:
        cid, n, take, exp, ph = c["id"], c["n"], c["take"], c["exp"], c["phase"]
        r = run(n, take, exp, ph)
        f = metrics_fresh(r)
        m = f["m"]
        row = dict(
            fresh_total=m["total_2026"], mdd=m["mdd_2026"], wp=m["win_period"], n_periods=m["n_periods"],
            wm=m["win_month"], win_month_n=m["win_month_n"], wt=m["win_trade"], n_trades=m["n_trades"],
            exposure=float(f["w"].mean()), cash=float(1 - f["w"].mean()),
            nhold=float(f["nh"].mean()), top3=f["top3"], top3_share=f["top3_share"],
            top1_share=f["top1_share"], n_codes=int(len(f["pnl"])),
            monthly=m["monthly_rets"],
            wilson_wp=list(wilson(int(round(m["win_period"] * m["n_periods"])), m["n_periods"])),
            wilson_wt=list(wilson(m["trade_win_n"], m["n_trades"])),
            wilson_wm=list(wilson(int(m["win_month_n"].split("/")[0]), int(m["win_month_n"].split("/")[1]))),
        )
        # ex-top3
        if f["top3"]:
            rx = run(n, take, exp, ph, exclude=MB + tuple(f["top3"]))
            mx = pc.metrics(rx)
            row["ex_top3"] = dict(total=mx["total_2026"], mdd=mx["mdd_2026"], wp=mx["win_period"],
                                  wt=mx["win_trade"], retention=(mx["total_2026"] / m["total_2026"]
                                                                 if m["total_2026"] else np.nan))
        # OOS 2024/2025（同参数，2024 预热）
        rw = run(n, take, exp, ph, run_start="2024-01-01")
        eq = rw.eq
        oos = {}
        for y, bd in [(2024, "2023-12-31"), (2025, "2024-12-31")]:
            seg = eq.loc[f"{y}-01-01":f"{y}-12-31"]
            b = eq.loc[:bd]
            bv = float(b.iloc[-1]) if len(b) else 50_000.0
            oos[y] = dict(total=float(seg.iloc[-1] / bv - 1),
                          mdd=float((seg / seg.cummax() - 1).min()))
        row["oos"] = oos
        # phase ±5
        phs = {}
        for p2 in (ph - 5, ph, ph + 5):
            rr = run(n, take, exp, p2)
            mm = pc.metrics(rr)
            phs[p2] = dict(total=mm["total_2026"], mdd=mm["mdd_2026"], wp=mm["win_period"])
        row["phase"] = phs
        out[cid] = row
    return out


if __name__ == "__main__":
    CAND = [
        # 收益型
        dict(id="b006_G1_N4_TP45_exp100", n=4, take=0.45, exp=1.0, phase=0),
        dict(id="b006_G2_N3_nostopTP_exp100", n=3, take=None, exp=1.0, phase=0),
        # 均衡型
        dict(id="b006_G1_N4_TP45_exp90", n=4, take=0.45, exp=0.9, phase=0),
        dict(id="b006_G1_N4_TP50_exp90", n=4, take=0.50, exp=0.9, phase=0),
        # 稳健型
        dict(id="b006_G1_N4_nostopTP_exp60", n=4, take=None, exp=0.6, phase=0),
        dict(id="b006_G1_N4_TP60_exp60", n=4, take=0.60, exp=0.6, phase=0),
        # 高胜率型
        dict(id="b006_G5_N4_TP50_exp100_pm10", n=4, take=0.50, exp=1.0, phase=-10),
    ]
    res = main(CAND)
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    outp = os.path.join(ROOT, "team", "audit", "out", "batch_006_profiles.json")
    with open(outp, "w") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2, default=str)
    print("wrote", outp)
