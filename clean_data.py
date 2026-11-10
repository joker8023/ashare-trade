"""
价格数据清洗
============
AKShare 的前复权(qfq)数据在部分股票上会算崩, 产生 0.01 这种占位价格。
A股有涨跌停 (±10%/±20%/±30%), 单日涨跌超过一定幅度物理上不可能。

清洗规则:
  1. 价格 < 0.30 元 → 视为无效 (A股低于1元已面临退市, 内部不会出现 0.01)
  2. 单日涨跌 > 25% → 该日价格置 NaN (覆盖创业板20% + IPO首日, 已留足余量)
  3. 单日涨跌 > 25% 的连续段, 整段置 NaN
  4. 记录清洗统计
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long.pkl")

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"

MIN_PRICE = 0.30
MAX_DAILY = 0.25


def clean_pivots(piv, min_price=MIN_PRICE, max_daily=MAX_DAILY, verbose=True):
    """返回清洗后的 piv (不修改原对象)"""
    piv = {k: (v.copy() if isinstance(v, pd.DataFrame) else v) for k, v in piv.items()}
    close = piv["close"]

    stats = {}
    # --- 规则1: 价格过低 ---
    bad_low = close < min_price
    stats["低价(<%.2f元)记录"] = int(bad_low.sum().sum())
    stats["涉及股票"] = int(bad_low.any().sum())

    # --- 规则2/3: 异常日涨跌 ---
    ret = close.pct_change(fill_method=None)
    bad_ret = ret.abs() > max_daily
    stats["异常日涨跌(>%.0f%%)记录"] = int(bad_ret.sum().sum())
    stats["涉及股票_涨跌"] = int(bad_ret.any().sum())

    # 合并脏点
    dirty = bad_low | bad_ret.fillna(False)

    # 对每个字段, 把脏日置 NaN
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        if col in piv and isinstance(piv[col], pd.DataFrame):
            df = piv[col]
            piv[col] = df.where(~dirty)

    # 清洗后再检查一次 (清洗可能暴露新的异常跳变)
    ret2 = piv["close"].pct_change(fill_method=None)
    still = ret2.abs() > max_daily
    stats["清洗后剩余异常"] = int(still.sum().sum())

    if verbose:
        print("=== 数据清洗 ===")
        for k, v in stats.items():
            print(f"  {k}: {v:,}")
    return piv, stats


def main():
    p = pd.read_pickle(DATA / "pivots_long.pkl")
    print(f"原始: {p['close'].shape[0]} 交易日 × {p['close'].shape[1]} 只")
    pc, stats = clean_pivots(p)

    # 清洗前后对比
    c0, c1 = p["close"], pc["close"]
    r0, r1 = c0.pct_change(fill_method=None), c1.pct_change(fill_method=None)
    print(f"\n{'指标':<28}{'清洗前':>14}{'清洗后':>14}")
    print("-" * 56)
    for th in [0.21, 0.50, 1.00]:
        print(f"  |日收益|>{th*100:.0f}% 的记录数   "
              f"{(r0.abs()>th).sum().sum():>13,}{(r1.abs()>th).sum().sum():>13,}")
    print(f"  收盘价<0.1的股票数        "
          f"{(c0.min()<0.1).sum():>13}{(c1.min()<0.1).sum():>13}")
    print(f"  有效价格占比              "
          f"{c0.notna().mean().mean():>13.2%}{c1.notna().mean().mean():>14.2%}")

    pd.to_pickle(pc, DATA / "pivots_long_clean.pkl")
    print(f"\n已保存: {DATA / 'pivots_long_clean.pkl'}")


if __name__ == "__main__":
    main()
