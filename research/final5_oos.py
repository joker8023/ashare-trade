"""
F1~F5 五策略 TRAIN/TEST/OOS 复现脚本（正式版）
============================================
口径（与 docs/strategy/README.md + VERIFY.md 一致）：
- 数据：data/pivots_long_clean.pkl（2010-2026，前复权），ASHARE_PIVOTS 环境变量可覆盖
- 引擎：engine.returns_series（t+1 收盘建仓，等权，单边成本 0.5%）
- 择时：risk_control.apply_index_filter，中证1000（000852）收盘 < MA15 -> 20% 仓位，否则 100%
- 区间：TRAIN 2020-01-01~2023-06-30 / TEST 2023-07-01~2024-12-31 / OOS 2025-01-01~2026-11-12
- 幸存者偏差未修（仅当前上市公司），未建模涨跌停不可成交，现金 0 收益

用法：
    ASHARE_PIVOTS=pivots_long_clean.pkl .venv/bin/python research/final5_oos.py
    ASHARE_PIVOTS=pivots_long_clean.pkl .venv/bin/python research/final5_oos.py --json

输出与 docs/strategy/VERIFY.md 逐位一致（verify-f1~f5 子agent 已独立复现）。
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")

import numpy as np
import pandas as pd

import engine as E
import risk_control as R

SPECS = [
    # (fid, factor, direction, N, R, size_range, 家族)
    ("F1_liq", "amihud_60", "high", 4, 60, (0.02, 0.15)),
    ("F2_intraday", "intraday", "high", 4, 20, (0.02, 0.15)),
    ("F3_position", "high52", "low", 5, 60, (0.02, 0.15)),
    ("F4_reversal", "rev60", "high", 4, 20, (0.05, 0.30)),
    ("F5_lowvol", "vol20", "high", 4, 60, (0.02, 0.15)),
]

WINDOWS = [
    ("TRAIN", "2020-01-01", "2023-06-30"),
    ("TEST", "2023-07-01", "2024-12-31"),
    ("OOS", "2025-01-01", "2026-11-12"),
]

TIMING = {"ma": 15, "cut": 0.2, "index_code": "000852"}
COST = 0.005


def slice_stats(r: pd.Series, start: str, end: str) -> dict:
    rr = r[(r.index >= pd.Timestamp(start)) & (r.index <= pd.Timestamp(end))]
    if len(rr) == 0:
        return {"ann": 0.0, "mdd": 0.0, "sharpe": 0.0, "total": 0.0, "n": 0}
    eq = (1 + rr).cumprod()
    yrs = len(rr) / 252
    ann = float(eq.iloc[-1] ** (1 / yrs) - 1) if yrs > 0 else 0.0
    mdd = float((eq / eq.cummax() - 1).min())
    vol = float(rr.std() * np.sqrt(252))
    sharpe = float(rr.mean() * 252 / vol) if vol > 0 else 0.0
    return {"ann": ann, "mdd": mdd, "sharpe": sharpe, "total": float(eq.iloc[-1] - 1), "n": len(rr)}


def run_one(fid: str, factor: str, direction: str, n: int, rb: int, sz: tuple) -> dict:
    r = E.returns_series(factor, direction=direction, n_hold=n, rebal=rb, size_range=sz, cost=COST)
    r2, _ = R.apply_index_filter(r, ma=TIMING["ma"], cut=TIMING["cut"], index_code=TIMING["index_code"])
    out = {"id": fid, "factor": factor, "direction": direction, "n": n, "rebal": rb, "size": list(sz)}
    for name, s, e in WINDOWS:
        out[name] = slice_stats(r2, s, e)
    bare = E.evaluate(factor, direction, n, rb, size_range=sz, start="2020-01-01", end="2023-06-30", cost=COST, min_adv=5e6)
    out["TRAIN_bare"] = {k: bare.get(k) for k in ("ann", "mdd", "sharpe", "IC", "total")}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="输出 JSON 而不是文本表")
    a = ap.parse_args()
    rows = [run_one(fid, f, d, n, rb, sz) for (fid, f, d, n, rb, sz) in SPECS]
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for row in rows:
        print("=" * 90)
        print(f"{row['id']} {row['factor']} {row['direction']} N{row['n']} R{row['rebal']} {tuple(row['size'])} MA15_0.2")
        for name, _, _ in WINDOWS:
            s = row[name]
            print(f" {name} ann={s['ann']:+.2%} mdd={s['mdd']:.2%} sharpe={s['sharpe']:.2f} total={s['total']:+.2%} n={s['n']}")
        b = row["TRAIN_bare"]
        print(f" TRAIN_bare ann={b['ann']:+.2%} mdd={b['mdd']:.2%} IC={b['IC']}")


if __name__ == "__main__":
    main()
