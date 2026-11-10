#!/usr/bin/env python
"""#7 实盘每日信号：amihud N=25/R=40 + 中证500MA20择时 + LS30/R=60，w=0.35
因子月调仓口径（与回测 engine.returns_series 完全同格子），诚实成本0.5%。
用法: python daily_final7.py [--commit]
"""
import argparse, json, os
from pathlib import Path
import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import engine as E
import risk_control as R

BASE = Path(__file__).resolve().parent
OUT = BASE / "results" / "signals"
STATE = BASE / "state"
OUT.mkdir(parents=True, exist_ok=True)
STATE.mkdir(parents=True, exist_ok=True)

N_LONG, R_LONG = 25, 40
N_LS, R_LS = 30, 60
W = 0.35
MA, INDEX = 20, "000905"
STATE_FILE = STATE / "final7_holdings.json"


def rebalance_grid(dates, step):
    return [dates[i] for i in range(300, len(dates) - step - 2, step)]


def long_holdings(p, today):
    c = p["close"]
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    seasoned = c.shift(250).notna()
    fac = E.FACTORS["amihud"](p)
    dates = c.index
    grid = rebalance_grid(dates, R_LONG)
    past = [t for t in grid if t <= today]
    if not past:
        return [], None, None
    t = past[-1]
    nxt = grid[grid.index(t) + 1] if grid.index(t) + 1 < len(grid) else None
    valid = seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna() & fac.loc[t].notna()
    cap = c.loc[t] * p["shares"]
    lo, hi = cap.quantile(0.05), cap.quantile(0.30)
    valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
    pool = valid[valid].index
    picks = list(fac.loc[t, pool].nlargest(N_LONG).index)
    return picks, t, nxt


def ls_holdings(p, today):
    c = p["close"]
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    seasoned = c.shift(250).notna()
    fac = E.FACTORS["amihud"](p)
    dates = c.index
    grid = rebalance_grid(dates, R_LS)
    past = [t for t in grid if t <= today]
    if not past:
        return [], [], None, None
    t = past[-1]
    nxt = grid[grid.index(t) + 1] if grid.index(t) + 1 < len(grid) else None
    valid = seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna() & fac.loc[t].notna()
    cap = c.loc[t] * p["shares"]
    lo, hi = cap.quantile(0.05), cap.quantile(0.30)
    valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
    pool = valid[valid].index
    longs = list(fac.loc[t, pool].nlargest(N_LS).index)
    shorts = list(fac.loc[t, pool].nsmallest(N_LS).index)
    return longs, shorts, t, nxt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    a = ap.parse_args()
    p = E.piv()
    c = p["close"]
    today = c.index[-1]

    midx = R._index_series(INDEX)
    ma = midx.rolling(MA).mean()
    above = bool(midx.loc[:today].iloc[-1] > ma.loc[:today].iloc[-1])
    pos = 1.0 if above else 0.0

    longs, tL, nxtL = long_holdings(p, today)
    lls, shs, tS, nxtS = ls_holdings(p, today)
    uni = pd.read_pickle(BASE / "data" / "universe.pkl").set_index("code")

    print("=" * 78)
    print(f"#7 实盘信号 — 数据日 {today.date()}（中证500MA20，w=0.35）")
    print("=" * 78)
    print(f"【择时】中证500 {midx.loc[:today].iloc[-1]:.1f} vs MA20 {ma.loc[:today].iloc[-1]:.1f} → "
          f"{'持有' if above else '空仓观望'}，多头目标仓位 {pos*W:.0%}（总资金）")
    print(f"\n【多头腿】{len(longs)}只 @调仓日{tL.date()}，下次调仓约{nxtL.date() if nxtL is not None else '—'}")
    dfL = pd.DataFrame([{"代码": x, "名称": uni['name'].get(x, ''),
                         "现价": round(float(c.loc[today, x]), 2)} for x in longs])
    print(dfL.to_string(index=False))
    print(f"\n【对冲腿LS30】多头端{tS.date()}调仓，下次约{nxtS.date() if nxtS is not None else '—'}")
    print("空头端（融券/期货替代）：")
    dfS = pd.DataFrame([{"代码": x, "名称": uni['name'].get(x, ''),
                         "现价": round(float(c.loc[today, x]), 2)} for x in shs])
    print(dfS.to_string(index=False))

    tag = today.strftime("%Y%m%d")
    dfL.to_csv(OUT / f"final7_{tag}_long.csv", index=False, encoding="utf-8-sig")
    dfS.to_csv(OUT / f"final7_{tag}_short.csv", index=False, encoding="utf-8-sig")
    print(f"\n已存: results/signals/final7_{tag}_{{long,short}}.csv")
    if a.commit:
        STATE_FILE.write_text(json.dumps({
            "date": str(today.date()), "timing_above": above, "w": W,
            "long": longs, "ls_long": lls, "ls_short": shs,
            "next_rebal_long": str(nxtL.date()) if nxtL is not None else None,
            "next_rebal_ls": str(nxtS.date()) if nxtS is not None else None,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"状态已存: {STATE_FILE}")


if __name__ == "__main__":
    main()
