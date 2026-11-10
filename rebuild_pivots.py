"""重建全字段透视缓存 (open/high/low/close/volume/amount) 供因子引擎使用"""
import gc
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"

daily = pd.read_pickle(DATA / "ashare_daily.pkl")
uni = pd.read_pickle(DATA / "universe.pkl")
print(f"原始: {len(daily):,} 行, {daily['code'].nunique()} 只")

piv = {}
for col in ["open", "high", "low", "close", "volume", "amount"]:
    print(f"  透视 {col} ...", flush=True)
    p = daily.pivot_table(index="date", columns="code", values=col).sort_index()
    piv[col] = p.astype("float32")
    gc.collect()

del daily
gc.collect()

close = piv["close"]
close = close.where(close > 0)
last_close = close.iloc[-1]
shares = (uni.set_index("code")["float_cap"] / last_close).replace(
    [float("inf"), float("-inf")], float("nan")).dropna()

piv["close"] = close
piv["shares"] = shares.astype("float32")

pd.to_pickle(piv, DATA / "pivots_full.pkl")
print(f"完成: {list(piv.keys())}")
print(f"形状: {close.shape}")
