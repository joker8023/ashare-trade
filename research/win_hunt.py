#!/usr/bin/env python3
"""四窗口全胜筛选 (Kai 标准): 1m/3m/6m/1y 收益全超 X3 R30, 每窗回撤不比 X3 差 3pp 以上。
X3 基准窗口: 1m -7.41/-9.85 | 3m +15.88/-10.75 | 6m +94.77/-13.15 | 1y +144.16/-13.56。
候选池跑前定死: X 家族 (门/带/N 变体) × 股票池三档 (主板 / +科创 / 全市场), S1/T2 × 科创放开。
统一: R30 ph0、TP100、敞口 1.0、真实成本。
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
from design_r30_grid8 import X3Inputs
from fresh5b import F2
from fresh5c import F3

MB = ("688", "689", "300", "301", "8", "4")
STAR = ("300", "301", "8", "4")       # 放开科创板
ALL = ("8", "4")                       # 全市场
X3W = {21: (-7.41, -9.85), 63: (15.88, -10.75), 126: (94.77, -13.15), 252: (144.16, -13.56)}


def winv(eq):
    eq = eq.dropna()
    out = {}
    for d in (21, 63, 126, 252):
        sub = eq.tail(d + 1)
        out[d] = (round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2),
                  round(float((sub / sub.cummax() - 1).min()) * 100, 2))
    out["full"] = (round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
                   round(float((eq / eq.cummax() - 1).min()) * 100, 2))
    return out


def verdict(w):
    beat = all(w[d][0] > X3W[d][0] for d in (21, 63, 126, 252))
    dd_ok = all(w[d][1] >= X3W[d][1] - 3.0 for d in (21, 63, 126, 252))
    return beat, dd_ok


def run(inp, tag, n=4, exclude=MB):
    res = pc.run_strategy(inp, factor="amihud_60", n=n, rebal=30, take=1.0,
                          stop=None, stop_exec="next", exclude=exclude,
                          capital=50_000.0, lot=100, cost_one_way=None, slip=0.002,
                          run_start="2023-11-10",
                          eval_start=pd.Timestamp("2025-02-13"),
                          eval_end=pd.Timestamp("2026-11-10"),
                          phase=0, legacy_grid=False, exposure=1.0,
                          full_liquidate=True)
    w = winv(res.eq)
    beat, dd_ok = verdict(w)
    row = {"tag": tag, "w": {str(k): v for k, v in w.items()},
           "beat_all": beat, "dd_ok": dd_ok, "pass": beat and dd_ok}
    print(json.dumps(row, ensure_ascii=False), flush=True)
    res.eq.dropna().to_pickle(f"results/r30_bt/hunt_{tag}_equity.pkl")
    return row


def main():
    piv = pc.get_inputs().piv
    rows = []
    # A/B/C: X 家族 × 股票池
    for uname, excl in (("STAR", STAR), ("ALL", ALL)):
        rows.append(run(X3Inputs(piv, gate60=-0.15), f"X3_{uname}", exclude=excl))
        rows.append(run(X3Inputs(piv, gate60=-0.20), f"X3g20_{uname}", exclude=excl))
        rows.append(run(X3Inputs(piv, gate60=-0.25), f"X3g25_{uname}", exclude=excl))
        rows.append(run(X3Inputs(piv, gate60=-1.0), f"X3nogate_{uname}", exclude=excl))
        rows.append(run(X3Inputs(piv, band=(0.02, 0.35), gate60=-0.15), f"X3b35_{uname}", exclude=excl))
        rows.append(run(X3Inputs(piv, band=(0.02, 0.50), gate60=-0.15), f"X3b50_{uname}", exclude=excl))
    # D/E: 主板未跑过的变体
    rows.append(run(X3Inputs(piv, gate60=-0.20), "X3g20_MB"))
    rows.append(run(X3Inputs(piv, gate60=-0.25), "X3g25_MB"))
    rows.append(run(X3Inputs(piv, gate60=-1.0), "X3nogate_MB"))
    rows.append(run(X3Inputs(piv, band=(0.02, 0.35), gate60=-0.15), "X3b35_MB"))
    rows.append(run(X3Inputs(piv, gate60=-0.15), "X3_N5_MB", n=5))
    rows.append(run(X3Inputs(piv, gate60=-0.15), "X3_N6_MB", n=6))
    # F: S1/T2 放开科创
    rows.append(run(F2(piv, "S1"), "S1_STAR", n=5, exclude=STAR))
    rows.append(run(F3(piv, "T2"), "T2_STAR", n=6, exclude=STAR))
    rows.append(run(F2(piv, "S1"), "S1_ALL", n=5, exclude=ALL))
    rows.append(run(F3(piv, "T2"), "T2_ALL", n=6, exclude=ALL))
    with open("results/r30_bt/win_hunt.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    npass = sum(r["pass"] for r in rows)
    print(f"\n过关 {npass}/{len(rows)}", flush=True)


if __name__ == "__main__":
    main()
