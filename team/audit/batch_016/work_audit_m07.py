#!/usr/bin/env python3
"""M07 audit work script (audit-owned). Part1: pure-pkl recompute, no engine import."""
import sys, json
from pathlib import Path
ROOT = Path("/Users/joker/coding/ashare-trade")
import pandas as pd

WINDOWS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}
J04W = {"1m": -4.84, "3m": 15.64, "6m": 37.17, "1y": 160.27, "2y": 1449.34, "3y": 1581.48, "mdd": -27.63, "total": 1765.84}

def mdd(s):
    return float((s / s.cummax() - 1.0).min())

def metrics(eq):
    eq = eq.dropna()
    o = {}
    o["eq0"] = float(eq.iloc[0]); o["eq1"] = float(eq.iloc[-1])
    o["total"] = round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2)
    o["mdd"] = round(mdd(eq) * 100, 2)
    for w, d in WINDOWS.items():
        sub = eq.tail(d + 1)
        o[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
        o[w + "_mdd"] = round(mdd(sub) * 100, 2)
    yrs = {}
    for y in [2023, 2024, 2025, 2026]:
        m = eq[eq.index.year == y]
        if len(m) > 1:
            yrs[str(y)] = round(float(m.iloc[-1] / m.iloc[0] - 1) * 100, 2)
    o["years"] = yrs
    o["first"] = str(eq.index[0]); o["last"] = str(eq.index[-1]); o["n"] = len(eq)
    return o

def main():
    rep = {}
    for tag, pkl, js in [("M07", "results/r30_bt/M07_equity.pkl", "results/r30_bt/M07_final.json"),
                         ("J04", "results/r30_bt/J04_equity.pkl", "results/r30_bt/J04_final.json")]:
        eq = pd.read_pickle(ROOT / pkl)
        if isinstance(eq, pd.DataFrame):
            eq = eq.iloc[:, 0]
        got = metrics(eq)
        want = json.loads((ROOT / js).read_text())
        rep[tag] = {"got": got, "want": {k: want.get(k) for k in ["total", "mdd", "1m", "3m", "6m", "1y", "2y", "3y", "top3_share", "extop3_total"]}}
        diffs = {}
        for k in ["total", "mdd", "1m", "3m", "6m", "1y", "2y", "3y"]:
            diffs[k] = round(abs(got[k] - want[k]), 4)
        rep[tag]["absdiff_pp"] = diffs
        rep[tag]["maxdiff"] = max(diffs.values())
        rep[tag]["years_got"] = got["years"]
        rep[tag]["years_want"] = want.get("years")
    # caliber from equity
    # cross-checks: six-window beats
    m = rep["M07"]["got"]
    beats = {w: round(m[w] - J04W[w], 2) for w in WINDOWS}
    rep["beats_vs_J04"] = beats
    rep["nbeat"] = sum(1 for w in WINDOWS if m[w] > J04W[w])
    rep["mdd_edge"] = round(m["mdd"] - J04W["mdd"], 2)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    (ROOT / "team/audit/batch_016/part1_recompute.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
