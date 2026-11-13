#!/usr/bin/env python3
"""月度网格优化 Stage3: 围绕 LAG5_K1_N4_W60 (+367.81/-14.22) 精修。
lag 邻域扫描 (平台 or 尖峰)、W/band/gate/adv/TP/K 变体、冠军分半验证。
"""
import json
import os
import sys

ROOT = os.path.expanduser("~/workspace/ashare-trade")
sys.path.insert(0, os.path.join(ROOT, "team", "audit"))
sys.path.insert(0, os.path.expanduser("~/workspace/tools"))
os.chdir(ROOT)

import pandas as pd

import prior_check as pc
from design_monthly import MInputs, stats, MB
from design_monthly2 import LagInputs, monthly_sigs


def run_cfg2(sig_all, inp, K, n, tag, take=1.0):
    cap = 50_000.0 / K
    eqs, trades, cost = [], 0, 0.0
    for k in range(K):
        sub = sig_all[k::K]
        inp.grid = (lambda s: (lambda rebal, phase=0, legacy=False: list(s)))(sub)
        res = pc.run_strategy(inp, factor="amihud_60", n=n, rebal=30, take=take,
                              stop=None, stop_exec="next", exclude=MB,
                              capital=cap, lot=100, cost_one_way=None, slip=0.002,
                              run_start="2023-11-10",
                              eval_start=pd.Timestamp("2025-02-13"),
                              eval_end=pd.Timestamp("2026-11-10"),
                              phase=0, legacy_grid=False, exposure=1.0,
                              full_liquidate=True)
        eqs.append(res.eq.dropna())
        trades += len(res.trades)
        cost += float(res.meta.get("total_cost", 0.0))
    idx = eqs[0].index
    for e in eqs[1:]:
        idx = idx.union(e.index)
    comb = None
    for e in eqs:
        s = e.reindex(idx).ffill()
        s[s.index < e.index[0]] = cap
        comb = s if comb is None else comb + s
    t, m, y = stats(comb)
    row = {"tag": tag, "total": t, "mdd": m, "r1y": y, "trades": trades, "cost": round(cost)}
    print(json.dumps(row, ensure_ascii=False), flush=True)
    comb.to_pickle(f"results/r30_bt/monthly_{tag}_equity.pkl")
    return row


def main():
    base = pc.get_inputs()
    dates = base.dates
    sig_first = monthly_sigs(dates, 0)
    rows = []

    for lag in (4, 6, 7, 8, 10):
        inp = LagInputs(base.piv, w=60, lag=lag)
        rows.append(run_cfg2(sig_first, inp, 1, 4, f"LAG{lag}_K1_N4_W60"))
    inp = LagInputs(base.piv, w=40, lag=5)
    rows.append(run_cfg2(sig_first, inp, 1, 4, "LAG5_W40_K1_N4"))
    inp = LagInputs(base.piv, w=90, lag=5)
    rows.append(run_cfg2(sig_first, inp, 1, 4, "LAG5_W90_K1_N4"))
    inp = LagInputs(base.piv, w=60, lag=5, band=(0.05, 0.30))
    rows.append(run_cfg2(sig_first, inp, 1, 4, "LAG5_band0530_K1_N4"))
    inp = LagInputs(base.piv, w=60, lag=5, gate60=-0.20)
    rows.append(run_cfg2(sig_first, inp, 1, 4, "LAG5_gate20_K1_N4"))
    inp = LagInputs(base.piv, w=60, lag=5, min_adv=1e7)
    rows.append(run_cfg2(sig_first, inp, 1, 4, "LAG5_adv10m_K1_N4"))
    inp = LagInputs(base.piv, w=60, lag=5)
    rows.append(run_cfg2(sig_first, inp, 2, 4, "LAG5_K2_N4"))
    inp = LagInputs(base.piv, w=60, lag=5)
    rows.append(run_cfg2(sig_first, inp, 1, 4, "LAG5_TPnone_K1_N4", take=None))
    inp = LagInputs(base.piv, w=60, lag=5)
    rows.append(run_cfg2(sig_first, inp, 1, 4, "LAG5_TP45_K1_N4", take=0.45))

    # 冠军 (LAG5 本体, stage2 已跑) 分半验证
    eq = pd.read_pickle("results/r30_bt/monthly_LAG5_K1_N4_W60_equity.pkl").dropna()
    for name, sub in (("2025段(至12-31)", eq[eq.index <= "2025-12-31"]),
                      ("2026段", eq[eq.index >= "2025-12-31"])):
        print(f"LAG5 分半 {name}: {stats(sub)}", flush=True)

    rows.sort(key=lambda r: -r["total"])
    print("\n=== Stage3 (按收益) ===", flush=True)
    for r in rows:
        print(json.dumps(r, ensure_ascii=False), flush=True)
    with open("results/r30_bt/monthly_stage3.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
