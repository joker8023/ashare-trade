#!/usr/bin/env python
"""只做多头实盘信号：amihud N=100/R=90 + 中证500MA15（无做空、无杠杆）
与回测同格子，诚实成本0.5%。用法: python daily_longonly.py [--commit]"""
import argparse, json, os
from pathlib import Path
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import engine as E
import risk_control as R

BASE = Path(__file__).resolve().parent
OUT = BASE / "results" / "signals"
STATE = BASE / "state"
OUT.mkdir(parents=True, exist_ok=True)
STATE.mkdir(parents=True, exist_ok=True)

N, REBAL = 100, 90
MA, INDEX = 15, "000905"
STATE_FILE = STATE / "longonly_holdings.json"


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

    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    seasoned = c.shift(250).notna()
    fac = E.FACTORS["amihud"](p)
    dates = c.index
    grid = [dates[i] for i in range(300, len(dates) - REBAL - 2, REBAL)]
    past = [t for t in grid if t <= today]
    t = past[-1]
    nxt = grid[grid.index(t) + 1] if grid.index(t) + 1 < len(grid) else None
    valid = seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna() & fac.loc[t].notna()
    cap = c.loc[t] * p["shares"]
    lo, hi = cap.quantile(0.05), cap.quantile(0.30)
    valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
    picks = list(fac.loc[t, valid[valid].index].nlargest(N).index)
    uni = pd.read_pickle(BASE / "data" / "universe.pkl").set_index("code")
    df = pd.DataFrame([{"代码": x, "名称": uni["name"].get(x, ""),
                        "现价": round(float(c.loc[today, x]), 2)} for x in picks])

    print("=" * 78)
    print(f"只做多头实盘信号 — 数据日 {today.date()}（N100/R90/中证500MA15）")
    print("=" * 78)
    print(f"【择时】中证500 {midx.loc[:today].iloc[-1]:.1f} vs MA15 {ma.loc[:today].iloc[-1]:.1f} → "
          f"{'持有（100%仓位）' if above else '空仓观望'}")
    print(f"【持仓】{len(picks)}只 @调仓日{t.date()}，下次约{nxt.date() if nxt is not None else '—（数据截止）'}")
    print(df.head(20).to_string(index=False))
    print(f"... 共 {len(df)} 只")

    tag = today.strftime("%Y%m%d")
    df.to_csv(OUT / f"longonly_{tag}.csv", index=False, encoding="utf-8-sig")
    if a.commit:
        STATE_FILE.write_text(json.dumps({
            "date": str(today.date()), "timing_above": above,
            "long": picks, "next_rebal": str(nxt.date()) if nxt is not None else None,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"状态已存: {STATE_FILE}")


if __name__ == "__main__":
    main()
