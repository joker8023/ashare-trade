#!/usr/bin/env python3
"""新 R30 设计第二轮: 围绕第一轮达标者 D (主板/amihud_60/N4/R30/无止盈/e0.9,
+386.84% / -15.13%) 做敞口与风控微调, 并做 phase 稳健性检查。
基线: 全程 +325.32 / -15.33, 1y +97.10 / -15.33 (两条线都要超)。
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


def run(tag, save=True, **kw):
    args = dict(factor="amihud_60", n=4, rebal=30, take=None, stop=None,
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
    if save:
        eq.to_pickle(f"results/r30_bt/design_{tag}_equity.pkl")
        res.trades.to_pickle(f"results/r30_bt/design_{tag}_trades.pkl")
    return row


def main():
    rows = []
    rows.append(run("D1_main_tpNone_e085", exposure=0.85))
    rows.append(run("D2_main_tpNone_e095", exposure=0.95))
    rows.append(run("D3_main_tpNone_stop20_e09", stop=0.20))
    rows.append(run("D4_main_tp100_e09", take=1.0))
    rows.append(run("D7_main_tpNone_stop25_e085", stop=0.25, exposure=0.85))
    # phase 稳健性 (不参选, 只看脆不脆)
    rows.append(run("D5_main_tpNone_e09_ph10", phase=10, save=False))
    rows.append(run("D6_main_tpNone_e09_ph20", phase=20, save=False))
    with open("results/r30_bt/design_grid2.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
