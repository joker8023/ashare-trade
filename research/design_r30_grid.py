#!/usr/bin/env python3
"""新 R30 策略设计 — 第一轮候选网格 (与均衡型同口径: prior_check 模拟器,
50k/整手/现实费率/滑点0.2%/clean pivots, run_start=数据起点)。
基线 (均衡型 N4 TP45 e0.9): 全程 +325.32% / MDD -15.33%, 1y +97.10% / -15.33%。
达标线 (Kai 定): 1y 与全程的收益、回撤都要超过基线; 1/3/6m 差不多即可。
"""
import json
import os
import sys

ROOT = os.path.expanduser("~/workspace/ashare-trade")
sys.path.insert(0, os.path.join(ROOT, "team", "audit"))
os.chdir(ROOT)

import pandas as pd

import prior_check as pc

MB = ("688", "689", "300", "301", "8", "4")
WINDOWS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252}


def win(eq, days):
    sub = eq.tail(days + 1)
    return (round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2),
            round(float((sub / sub.cummax() - 1).min()) * 100, 2))


def run(tag, **kw):
    args = dict(factor="amihud_60", n=4, rebal=30, take=0.45, stop=None,
                stop_exec="next", exclude=MB, capital=50_000.0, lot=100,
                cost_one_way=None, slip=0.002, run_start="2023-11-10",
                eval_start=pd.Timestamp("2025-02-13"),
                eval_end=pd.Timestamp("2026-11-10"),
                phase=0, legacy_grid=False, exposure=0.9)
    args.update(kw)
    res = pc.run_strategy(pc.get_inputs(), **args)
    eq = res.eq.dropna()
    tot = round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2)
    mdd = round(float((eq / eq.cummax() - 1).min()) * 100, 2)
    w = {k: win(eq, d) for k, d in WINDOWS.items()}
    row = {"tag": tag, "total": tot, "mdd": mdd,
           "w": {k: {"ret": v[0], "mdd": v[1]} for k, v in w.items()},
           "trades": int(len(res.trades)),
           "cost": round(float(res.meta.get("total_cost", 0.0)), 0)}
    print(json.dumps(row, ensure_ascii=False), flush=True)
    eq.to_pickle(f"results/r30_bt/design_{tag}_equity.pkl")
    return row


def main():
    rows = []
    rows.append(run("base_main_tp45_e09"))
    rows.append(run("A_all_tp45_e09", exclude=()))
    rows.append(run("B_all_tpNone_e09", exclude=(), take=None))
    rows.append(run("C_all_tp80_e09", exclude=(), take=0.80))
    rows.append(run("D_main_tpNone_e09", take=None))
    rows.append(run("E_all_tp45_e100", exclude=(), exposure=1.0))
    rows.append(run("F_all_tp45_stop15_e09", exclude=(), stop=0.15))
    rows.append(run("G_main_ami20_tp45_e09", factor="amihud"))
    rows.append(run("H_all_ami20_tp45_e09", factor="amihud", exclude=()))
    rows.append(run("I_all_tp45_e09_n3", exclude=(), n=3))
    rows.append(run("J_noSTAR_tp45_e09", exclude=("688", "689", "8", "4")))
    with open("results/r30_bt/design_grid1.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print("BASELINE: total +325.32 / mdd -15.33 | 1y +97.10 / -15.33")


if __name__ == "__main__":
    main()
