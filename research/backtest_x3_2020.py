#!/usr/bin/env python3
"""2020 版 pivots 构建 (与 rebuild_pivots_long.py + clean_data.py 同口径) + X3 R30 全程回测 + 按年拆分。
输入: data/ashare_daily_long_2020.pkl, data/universe_2020.pkl
输出: data/pivots_2020_clean.pkl, results/r30_bt/x3_2020_equity.pkl, 按年 JSON 行。
"""
import gc
import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]  # 仓库根目录 (research/ 的上级), 路径可移植
DATA = BASE / "data"
sys.path.insert(0, str(BASE))                       # clean_data
sys.path.insert(0, str(BASE / "team" / "audit"))    # prior_check
sys.path.insert(0, str(BASE / "research"))   # design_r30_grid8
os.chdir(BASE)

import numpy as np
import pandas as pd

# ---------- 1. pivots ----------
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

# ---------- 2. 清洗 (仓库 clean_data 同规则) ----------
from clean_data import clean_pivots
piv_clean, cstats = clean_pivots(piv)
pd.to_pickle(piv_clean, DATA / "pivots_2020_clean.pkl")
print("已保存 data/pivots_2020_clean.pkl", flush=True)

# ---------- 3. X3 R30 回测 ----------
import prior_check as pc
from design_r30_grid8 import X3Inputs

MB = ("688", "689", "300", "301", "8", "4")
inp = X3Inputs(piv_clean, gate60=-0.15)
dates = inp.dates
first_signal = dates[300]
print(f"首个信号日 (index 300): {first_signal.date()}", flush=True)

res = pc.run_strategy(inp, factor="amihud_60", n=4, rebal=30, take=1.0,
                      stop=None, stop_exec="next", exclude=MB,
                      capital=50_000.0, lot=100, cost_one_way=None, slip=0.002,
                      run_start="2020-01-01",
                      eval_start=first_signal,
                      eval_end=pd.Timestamp("2026-11-10"),
                      phase=0, legacy_grid=False, exposure=1.0,
                      full_liquidate=True)
eq = res.eq
if isinstance(eq, pd.DataFrame):
    eq = eq.iloc[:, 0]
eq = pd.Series(eq).dropna()
eq.to_pickle("results/r30_bt/x3_2020_equity.pkl")
print(f"净值: {eq.index[0].date()} ~ {eq.index[-1].date()}, {len(eq)} 点, "
      f"¥{eq.iloc[0]:,.0f} → ¥{eq.iloc[-1]:,.0f}", flush=True)

# ---------- 4. 按年拆分 ----------
def year_stats(eq):
    rows = []
    years = sorted(set(eq.index.year))
    for y in years:
        seg = eq[eq.index.year == y]
        if len(seg) == 0:
            continue
        prev = eq[eq.index < seg.index[0]]
        start_val = float(prev.iloc[-1]) if len(prev) else float(seg.iloc[0])
        full = pd.concat([pd.Series([start_val]), seg])
        ret = float(seg.iloc[-1] / start_val - 1) * 100
        mdd = float((full / full.cummax() - 1).min()) * 100
        rows.append({"year": y, "days": int(len(seg)),
                     "ret": round(ret, 2), "mdd": round(mdd, 2),
                     "start": str(seg.index[0].date()), "end": str(seg.index[-1].date())})
    return rows

tot = float(eq.iloc[-1] / eq.iloc[0] - 1) * 100
mdd_all = float((eq / eq.cummax() - 1).min()) * 100
print(json.dumps({"full": {"total": round(tot, 2), "mdd": round(mdd_all, 2),
                           "from": str(eq.index[0].date()), "to": str(eq.index[-1].date())}},
                 ensure_ascii=False), flush=True)
for r in year_stats(eq):
    print(json.dumps(r, ensure_ascii=False), flush=True)
print("DONE", flush=True)
