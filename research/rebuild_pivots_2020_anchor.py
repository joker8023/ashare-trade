#!/usr/bin/env python3
import argparse, gc, os, shutil, sys
from pathlib import Path
from datetime import datetime
BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
sys.path.insert(0, str(BASE))
os.chdir(BASE)
import pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", default="2026-11-12")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()
    anchor = pd.Timestamp(args.anchor)
    daily = pd.read_pickle(DATA / "ashare_daily_long_2020.pkl")
    uni = pd.read_pickle(DATA / "universe_2020.pkl")
    print("raw rows:", len(daily), "anchor:", anchor.date(), flush=True)
    piv = {}
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        p = daily.pivot_table(index="date", columns="code", values=col).sort_index()
        piv[col] = p.astype("float32")
        gc.collect()
    del daily
    gc.collect()
    close = piv["close"].where(piv["close"] > 0)
    anchor_close = close.loc[anchor]
    print("anchor NaN closes:", int(anchor_close.isna().sum()), flush=True)
    shares = (uni.set_index("code")["float_cap"] / anchor_close).replace([float("inf"), float("-inf")], float("nan")).dropna()
    piv["close"] = close
    piv["shares"] = shares.astype("float32")
    print("shares n:", len(shares), flush=True)
    from clean_data import clean_pivots
    piv_clean, cstats = clean_pivots(piv)
    out = DATA / "pivots_2020_clean.pkl"
    if not args.no_backup and out.exists():
        bk = DATA / "backup_pivots_anchor"
        bk.mkdir(exist_ok=True)
        dst = bk / ("pivots_2020_clean_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_anchorFree.pkl")
        shutil.copy2(out, dst)
        print("backed up old file", flush=True)
    pd.to_pickle(piv_clean, out)
    print("saved", cstats, flush=True)
    idx = piv_clean["close"].index
    print("range:", idx[0].date(), idx[-1].date(), len(idx), flush=True)

if __name__ == "__main__":
    main()
