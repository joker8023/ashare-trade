"""持仓行业集中度分析"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long.pkl")
import engine as E

BASE = Path(__file__).resolve().parent
OUT = BASE / "results"

REBAL, NHOLD = 60, 100
SIZE = (0.05, 0.30)


def main():
    p = E.piv()
    c = p["close"]
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    seasoned = c.shift(250).notna()
    fac = E.FACTORS["amihud"](p)
    ind = E.industry_map()
    dates = c.index

    rows = []
    for i in range(300, len(dates) - REBAL - 2, REBAL):
        t = dates[i]
        valid = seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna() & fac.loc[t].notna()
        cap = c.loc[t] * p["shares"]
        lo, hi = cap.quantile(SIZE[0]), cap.quantile(SIZE[1])
        valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
        pool = valid[valid].index
        if len(pool) < NHOLD:
            continue
        picks = list(fac.loc[t, pool].nlargest(NHOLD).index)
        g = ind.reindex(picks).fillna("UNKNOWN")
        w = g.value_counts(normalize=True)
        hhi = float((w ** 2).sum())
        rows.append({
            "date": t,
            "行业数": int((w > 0).sum()),
            "最大行业占比": float(w.iloc[0]),
            "最大行业": w.index[0],
            "前3行业占比": float(w.head(3).sum()),
            "HHI": hhi,
        })

    df = pd.DataFrame(rows).set_index("date")
    print("=" * 66)
    print(f"Amihud 策略持仓行业集中度 (N={NHOLD}, 60日调仓, {len(df)} 个调仓期)")
    print("=" * 66)
    print(f"  平均持仓行业数      : {df['行业数'].mean():.1f} 个")
    print(f"  最大行业占比 平均   : {df['最大行业占比'].mean():.1%}  "
          f"(最高 {df['最大行业占比'].max():.1%})")
    print(f"  前3行业占比 平均    : {df['前3行业占比'].mean():.1%}  "
          f"(最高 {df['前3行业占比'].max():.1%})")
    print(f"  HHI 平均            : {df['HHI'].mean():.3f}  "
          f"(完全分散=0.008, 全押一个=1.0)")

    # 有效行业数 = 1/HHI
    eff = 1 / df["HHI"]
    print(f"  有效行业数 (1/HHI)  : {eff.mean():.1f} 个")

    print("\n最常出现的最大行业:")
    print(df["最大行业"].value_counts().head(8).to_string())

    print("\n集中度最高的5期:")
    top = df.nlargest(5, "最大行业占比")[["最大行业", "最大行业占比", "前3行业占比", "行业数"]]
    for d, r in top.iterrows():
        print(f"  {d.date()}  {r['最大行业']:<10} {r['最大行业占比']:6.1%}  "
              f"前3={r['前3行业占比']:6.1%}  行业数={r['行业数']}")

    df.to_csv(OUT / "industry_concentration.csv", encoding="utf-8")
    print(f"\n明细: {OUT / 'industry_concentration.csv'}")

    # 图
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS",
                                           "Heiti SC", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
        fig, ax = plt.subplots(figsize=(11, 4.5))
        ax.plot(df.index, df["最大行业占比"] * 100, lw=1.2, color="#c0392b",
                label="最大单一行业占比")
        ax.plot(df.index, df["前3行业占比"] * 100, lw=1.2, color="#2c7fb8",
                label="前3行业占比")
        ax.axhline(10, color="gray", ls="--", lw=0.8, label="完全分散参考线(10%)")
        ax.set_ylabel("权重 (%)")
        ax.set_title("Amihud 策略持仓行业集中度")
        ax.legend(); ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(OUT / "industry_concentration.png", dpi=130)
        print(f"图表: {OUT / 'industry_concentration.png'}")
    except Exception as e:
        print(f"绘图跳过: {e}")


if __name__ == "__main__":
    main()
