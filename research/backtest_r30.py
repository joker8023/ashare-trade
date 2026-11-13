#!/usr/bin/env python3
"""R30 回测: ashare-trade 仓库 pools_r30.py 的口径 —
Amihud 因子, 30 交易日调仓, 流通市值 5%~30% 分位, 单边成本 0.5%,
持仓数 N = 5/6/7 (仓库 pools_r30.py 的三档)。用 engine.returns_series
在 data/pivots_long.pkl (2023-11-10~2026-11-10) 上跑出逐日收益序列,
再按 1/3/6 月、1/2 年窗口 (锚定数据末端 2026-11-10) 切片算
累计收益与最大回撤。engine 需要 300 日预热, 收益序列实际从约
2025-08 开始, 2 年窗口只能覆盖约 425 个交易日, 结果里如实标注。
"""
import json
import os
import sys

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long.pkl")
sys.path.insert(0, os.path.expanduser("~/workspace/ashare-trade"))
os.chdir(os.path.expanduser("~/workspace/ashare-trade"))

import pandas as pd

import engine as E

OUT = "results/r30_bt"
os.makedirs(OUT, exist_ok=True)

WINDOWS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504}


def stats(r: pd.Series, days: int):
    sub = r.tail(days)
    curve = (1 + sub).cumprod()
    mdd = (curve / curve.cummax() - 1).min()
    return {
        "days": int(len(sub)),
        "start": str(sub.index.min().date()),
        "end": str(sub.index.max().date()),
        "ret_pct": round(float(curve.iloc[-1] - 1) * 100, 2),
        "mdd_pct": round(float(mdd) * 100, 2),
    }


def main():
    summary = {}
    for n in (5, 6, 7):
        r = E.returns_series("amihud", n_hold=n, rebal=30,
                             size_range=(0.05, 0.30), cost=0.005)
        r.to_pickle(f"{OUT}/r30_N{n}_returns.pkl")
        summary[f"N{n}"] = {
            "series_days": int(len(r)),
            "series_start": str(r.index.min().date()),
            "series_end": str(r.index.max().date()),
            "windows": {w: stats(r, d) for w, d in WINDOWS.items()},
        }
        print(f"N{n} done: series {len(r)} days "
              f"{summary[f'N{n}']['series_start']}~{summary[f'N{n}']['series_end']}",
              flush=True)
    with open(f"{OUT}/r30_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
