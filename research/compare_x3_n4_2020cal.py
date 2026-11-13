#!/usr/bin/env python3
"""X3 定版 vs 均衡型 N4 TP45 同口径对比 — 2020 长窗数据、同一网格锚点。
数据: data/pivots_2020_clean.pkl (2020-01-02 ~ 2026-11-10)
共同口径: phase 0, legacy_grid=False, run_start=2023-11-10, R30 全量换仓,
  5 万本金 / 整手 / 现实费率 (cost_one_way=None) / slip 0.002, 主板 only。
X3: X3Inputs(band 2-30%, gate60=-0.15) + take=1.0 + exposure=1.0
N4: pc.Inputs 默认 (band 5-30%) + take=0.45 + exposure=0.9
窗口: 净值尾部 tail(d+1) 切片, 与 backtest_n4_tp45.py 的 win_stats 同法。
"""
import gc
import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]  # 仓库根目录 (research/ 的上级), 路径可移植
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "team" / "audit"))
sys.path.insert(0, str(BASE / "research"))
os.chdir(BASE)

import pandas as pd

import prior_check as pc
from design_r30_grid8 import X3Inputs

MB = ("688", "689", "300", "301", "8", "4")
WINDOWS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504}
RUN_START = "2023-11-10"
EVAL_END = pd.Timestamp("2026-11-12")

piv = pd.read_pickle(BASE / "data" / "pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
print(f"数据 {dates[0].date()} ~ {dates[-1].date()} ({len(dates)}d); "
      f"run_start={RUN_START} 首个网格信号日: {first_sig.date()}", flush=True)


def win_stats(eq, days):
    sub = eq.tail(days + 1)
    ret = sub.iloc[-1] / sub.iloc[0] - 1
    mdd = (sub / sub.cummax() - 1).min()
    return {"days": int(len(sub) - 1), "start": str(sub.index[0].date()),
            "end": str(sub.index[-1].date()),
            "ret_pct": round(float(ret) * 100, 2),
            "mdd_pct": round(float(mdd) * 100, 2)}


def summarize(name, res):
    eq = res.eq
    if isinstance(eq, pd.DataFrame):
        eq = eq.iloc[:, 0]
    eq = pd.Series(eq).dropna()
    out = {"name": name, "eq_start": str(eq.index[0].date()),
           "eq_end": str(eq.index[-1].date()), "eq_days": int(len(eq) - 1),
           "total_ret_pct": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
           "full_mdd_pct": round(float((eq / eq.cummax() - 1).min()) * 100, 2),
           "n_trades": int(len(res.trades)),
           "total_cost": round(float(res.meta.get("total_cost", 0.0)), 0),
           "windows": {w: win_stats(eq, d) for w, d in WINDOWS.items()}}
    return eq, out


results = {}

# ---- X3 ----
inp = X3Inputs(piv, gate60=-0.15)
res = pc.run_strategy(inp, factor="amihud_60", n=4, rebal=30, take=1.0,
                      stop=None, stop_exec="next", exclude=MB,
                      capital=50_000.0, lot=100, cost_one_way=None, slip=0.002,
                      run_start=RUN_START, eval_start=first_sig,
                      eval_end=EVAL_END, phase=0, legacy_grid=False,
                      exposure=1.0, full_liquidate=True)
eq_x3, out_x3 = summarize("X3", res)
eq_x3.to_pickle("results/r30_bt/cmp2020_x3_equity.pkl")
results["x3"] = out_x3
print(json.dumps(out_x3, ensure_ascii=False), flush=True)
del inp, res
gc.collect()

# ---- N4 ----
inp = pc.Inputs(piv)
res = pc.run_strategy(inp, factor="amihud_60", n=4, rebal=30, take=0.45,
                      stop=None, stop_exec="next", exclude=MB,
                      capital=50_000.0, lot=100, cost_one_way=None, slip=0.002,
                      run_start=RUN_START, eval_start=first_sig,
                      eval_end=EVAL_END, phase=0, legacy_grid=False,
                      exposure=0.9, full_liquidate=True)
eq_n4, out_n4 = summarize("N4", res)
eq_n4.to_pickle("results/r30_bt/cmp2020_n4_equity.pkl")
results["n4"] = out_n4
print(json.dumps(out_n4, ensure_ascii=False), flush=True)

with open("results/r30_bt/compare_x3_n4_2020cal_1112.json", "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=1)
print("saved results/r30_bt/compare_x3_n4_2020cal_1112.json")
