#!/usr/bin/env python3
"""仅重建 data/pivots_2020_clean.pkl — 与 backtest_x3_2020.py 第 1-2 段同口径
(pivot + clean_data.clean_pivots), 不跑回测。"""
import gc
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]  # 仓库根目录 (research/ 的上级), 路径可移植
DATA = BASE / "data"
sys.path.insert(0, str(BASE))
os.chdir(BASE)

import numpy as np
import pandas as pd

daily = pd.read_pickle(DATA / "ashare_daily_long_2020.pkl")
uni = pd.read_pickle(DATA / "universe_2020.pkl")
print(f"原始: {len(daily):,} 行, {daily['code'].nunique()} 只, "
      f"{daily['date'].min().date()} ~ {daily['date'].max().date()}", flush=True)

piv = {}
for col in ["open", "high", "low", "close", "volume", "amount"]:
    p = daily.pivot_table(index="date", columns="code", values=col).sort_index()
    piv[col] = p.astype("float32")
    gc.collect()
del daily
gc.collect()

close = piv["close"].where(piv["close"] > 0)
last_close = close.iloc[-1]
shares = (uni.set_index("code")["float_cap"] / last_close).replace(
    [float("inf"), float("-inf")], float("nan")).dropna()
piv["close"] = close
piv["shares"] = shares.astype("float32")
print(f"pivots: {close.shape[0]} 交易日 × {close.shape[1]} 只, shares {len(shares)}", flush=True)

from clean_data import clean_pivots
piv_clean, cstats = clean_pivots(piv)
pd.to_pickle(piv_clean, DATA / "pivots_2020_clean.pkl")
print("已保存 data/pivots_2020_clean.pkl", cstats, flush=True)

idx = piv_clean["close"].index
last = piv_clean["close"].iloc[-1]
print(f"clean pivots: {idx[0].date()} ~ {idx[-1].date()} ({len(idx)}d), "
      f"末日有价 {int(last.notna().sum())} 只")
