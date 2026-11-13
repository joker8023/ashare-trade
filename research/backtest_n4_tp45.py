#!/usr/bin/env python3
"""均衡型 N4 TP45 e0.9 回测 — team/FINAL_REPORT.md 的综合首选画像。
口径与 team/audit/batch_006/run_profiles.py 完全一致:
  prior_check.run_strategy(factor="amihud_60", n=4, rebal=30, take=0.45,
    stop=None, stop_exec="next", exclude=主板以外(688/689/300/301/8/4),
    capital=50000, lot=100, cost_one_way=None(现实费率), slip=0.002,
    exposure=0.9, phase=0)
数据: data/pivots_long_clean.pkl (三年新浪数据清洗版)。
run_start 放到数据起点, 让网格从第 300 个交易日起跑满全程;
窗口按净值序列尾部切片 (锚定净值末端), 与 R30 窗口表同法。
"""
import json
import os
import sys

ROOT = os.path.expanduser("~/workspace/ashare-trade")
sys.path.insert(0, os.path.join(ROOT, "team", "audit"))
os.chdir(ROOT)

import pandas as pd

import prior_check as pc

WINDOWS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504}


def win_stats(eq: pd.Series, days: int):
    sub = eq.tail(days + 1)
    ret = sub.iloc[-1] / sub.iloc[0] - 1
    mdd = (sub / sub.cummax() - 1).min()
    return {"days": int(len(sub) - 1), "start": str(sub.index[0].date()),
            "end": str(sub.index[-1].date()),
            "ret_pct": round(float(ret) * 100, 2),
            "mdd_pct": round(float(mdd) * 100, 2)}


def main():
    inp = pc.get_inputs()
    res = pc.run_strategy(
        inp, factor="amihud_60", n=4, rebal=30, take=0.45, stop=None,
        stop_exec="next", exclude=("688", "689", "300", "301", "8", "4"),
        capital=50_000.0, lot=100, cost_one_way=None, slip=0.002,
        run_start="2023-11-10",
        eval_start=pd.Timestamp("2025-02-13"),
        eval_end=pd.Timestamp("2026-11-10"),
        phase=0, legacy_grid=False, exposure=0.9)
    eq = res.eq.dropna()
    eq.to_pickle("results/r30_bt/n4_tp45_e09_equity.pkl")
    out = {"eq_days": int(len(eq)), "eq_start": str(eq.index.min().date()),
           "eq_end": str(eq.index.max().date()),
           "base": float(eq.iloc[0]), "final": float(eq.iloc[-1]),
           "total_ret_pct": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
           "windows": {w: win_stats(eq, d) for w, d in WINDOWS.items()},
           "n_trades": int(len(res.trades)),
           "total_cost": float(res.meta.get("total_cost", 0.0))}
    m = pc.metrics(res, eval_start=pd.Timestamp("2025-02-13"),
                   eval_end=pd.Timestamp("2026-11-10"))
    out["metrics_full"] = {k: (round(float(v), 4) if isinstance(v, (int, float))
                               and v == v else v)
                           for k, v in m.items()
                           if k in ("total", "mdd", "sharpe", "calmar", "vol",
                                    "win_period", "win_month", "win_trade")}
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
