"""
生成当前实盘持仓清单
====================
按 v3 策略规格, 用最新数据算出现在应该买哪些股票。

输出:
  results/live_holdings.csv   完整清单
  控制台: 摘要 + 风控状态
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long.pkl")
import engine as E
import risk_control as R

BASE = Path(__file__).resolve().parent
OUT = BASE / "results"

NHOLD = 50
SIZE = (0.05, 0.30)
FACTOR = "amihud"
MIN_ADV = 5e6


def main():
    p = E.piv()
    c = p["close"]
    dates = c.index
    t = dates[-1]

    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    seasoned = c.shift(250).notna()
    fac = E.FACTORS[FACTOR](p)
    cap = c.loc[t] * p["shares"]

    valid = seasoned.loc[t] & (adv20.loc[t] > MIN_ADV) & c.loc[t].notna() & fac.loc[t].notna()
    lo, hi = cap.quantile(SIZE[0]), cap.quantile(SIZE[1])
    valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
    pool = valid[valid].index

    print("=" * 72)
    print(f"实盘持仓清单 — 基准日 {t.date()}")
    print("=" * 72)
    print(f"可选股票池: {len(pool)} 只 (市值 {lo/1e8:.1f}亿 ~ {hi/1e8:.1f}亿, 日成交额>{MIN_ADV/1e4:.0f}万)")

    # 风控状态
    try:
        s = R._index_series("000852")
        ma20 = s.rolling(20).mean()
        last = s.iloc[-1]
        m = ma20.iloc[-1]
        above = last > m
        pos = 1.0 if above else 0.5
        print(f"\n风控状态: 中证1000 {last:.1f} vs MA20 {m:.1f} → "
              f"{'在均线上方, 满仓' if above else '在均线下方, 半仓'}")
        print(f"建议总仓位: {pos:.0%}")
    except Exception as e:
        print(f"\n风控状态获取失败: {e}")
        pos = 1.0

    picks = list(fac.loc[t, pool].nlargest(NHOLD).index)
    ind = E.industry_map()
    uni = pd.read_pickle(BASE / "data" / "universe.pkl").set_index("code")

    # 最新价
    last_px = c.loc[t]
    rows = []
    for i, code in enumerate(picks, 1):
        rows.append({
            "序号": i,
            "代码": code,
            "名称": uni["name"].get(code, ""),
            "行业": ind.get(code, ""),
            "最新价": round(float(last_px[code]), 2),
            "流通市值(亿)": round(float(cap[code]) / 1e8, 2),
            "日均成交额(万)": round(float(adv20.loc[t, code]) / 1e4, 0),
            "Amihud值": round(float(fac.loc[t, code]), 4),
            "建议权重": f"{1/NHOLD:.1%}",
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "live_holdings.csv", index=False, encoding="utf-8-sig")

    print(f"\n=== 持仓 {NHOLD} 只 ===")
    print(df.head(20).to_string(index=False))
    print(f"... 共 {len(df)} 只, 完整清单见 results/live_holdings.csv")

    print(f"\n=== 组合特征 ===")
    print(f"  市值中位数      : {df['流通市值(亿)'].median():.1f} 亿")
    print(f"  日成交额中位数  : {df['日均成交额(万)'].median():.0f} 万")
    print(f"  覆盖行业数      : {df['行业'].nunique()} 个")
    print(f"  按单只权重      : {1/NHOLD:.1%}")

    print(f"\n=== 不同资金的实际下单量 ===")
    for capital in [1e5, 5e5, 1e6, 5e6, 1e7]:
        per = capital / NHOLD * pos
        pct = per / (df['日均成交额(万)'].median() * 1e4)
        print(f"  {capital/1e4:>6.0f}万 → 每只 {per/1e4:>6.2f}万, "
              f"占日成交额中位数 {pct:>6.2%}")

    # 行业分布
    print(f"\n=== 行业分布 (前10) ===")
    vc = df["行业"].value_counts().head(10)
    for k, v in vc.items():
        print(f"  {k:<14} {v:>2} 只  ({v/NHOLD:.0%})")

    print(f"\n清单已保存: {OUT / 'live_holdings.csv'}")


if __name__ == "__main__":
    main()
