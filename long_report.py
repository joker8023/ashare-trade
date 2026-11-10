"""
长历史 (2010起) 压力测试报告
重点: 股灾/熔断/漂亮50/熊市 这些 2021 年后没有的极端环境
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long.pkl")
import engine as E

BASE = Path(__file__).resolve().parent
OUT = BASE / "results"

CFG = dict(factor="amihud", n_hold=100, rebal=60, size_range=(0.05, 0.30), cost=0.005)


def ann(r):
    if len(r) == 0:
        return 0.0
    return (1 + r).prod() ** (252 / len(r)) - 1


def shp(r):
    v = r.std() * np.sqrt(252)
    return r.mean() * 252 / v if v > 0 else 0


def seg(r, a, b, label):
    s = r[(r.index >= a) & (r.index <= b)]
    if len(s) < 5:
        return None
    eq = (1 + s).cumprod()
    return {
        "区间": label,
        "起止": f"{s.index[0].date()}~{s.index[-1].date()}",
        "收益": f"{eq.iloc[-1]-1:+.1%}",
        "回撤": f"{(eq/eq.cummax()-1).min():.1%}",
        "天数": len(s),
    }


def main():
    r = E.returns_series(CFG["factor"], n_hold=CFG["n_hold"], rebal=CFG["rebal"],
                         size_range=CFG["size_range"], cost=CFG["cost"])
    eq = (1 + r).cumprod()
    dd = eq / eq.cummax() - 1

    print("=" * 70)
    print("Amihud 流动性策略 — 长历史压力测试 (2011-2026)")
    print("=" * 70)
    print(f"区间 {r.index[0].date()} ~ {r.index[-1].date()}   {len(r)} 交易日")
    print(f"年化 {ann(r):.1%}   夏普 {shp(r):.2f}   最大回撤 {dd.min():.1%}   "
          f"累计 {eq.iloc[-1]-1:.1%}")

    # --- 分年度 ---
    yr = r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)
    print("\n分年度收益:")
    for y, v in yr.items():
        mark = "  ← 亏损" if v < 0 else ""
        bar = ("+" if v > 0 else "-") + "█" * min(int(abs(v) * 25), 40)
        print(f"  {y}: {v:+8.1%} {bar}{mark}")
    print(f"  盈利 {(yr>0).sum()}/{len(yr)} 年, 最差 {yr.min():+.1%}, 最好 {yr.max():+.1%}")
    print(f"  收益集中度: 最好的3年合计 {(1+yr.nlargest(3)).prod()-1:+.0%}, "
          f"占全期累计的 {(1+yr.nlargest(3)).prod()/eq.iloc[-1]:.0%}")

    # --- 最大回撤区间 ---
    print("\n最大5次回撤:")
    d = dd.copy()
    episodes = []
    in_dd = False
    peak_date = None
    for dt, v in d.items():
        if v <= -0.10 and not in_dd:
            in_dd = True
            peak_date = dt
        elif v >= -0.005 and in_dd:
            in_dd = False
            seg_dd = d.loc[peak_date:dt]
            trough = seg_dd.idxmin()
            episodes.append((seg_dd.min(), peak_date, trough, dt))
    episodes.sort()
    for dep, pk, tr, rc in episodes[:5]:
        days = (rc - pk).days
        print(f"  {dep:7.1%}   峰{pk.date()} → 底{tr.date()} → 收复{rc.date()}  ({days}天)")

    # --- 极端时期 ---
    print("\n极端环境表现:")
    periods = [
        ("2015-06-12", "2015-09-30", "2015 股灾 (千股跌停)"),
        ("2016-01-04", "2016-02-29", "2016 熔断"),
        ("2017-01-01", "2017-12-31", "2017 漂亮50/小盘熊"),
        ("2018-01-01", "2018-12-31", "2018 单边熊市"),
        ("2013-01-01", "2015-06-12", "2013-2015 小盘泡沫"),
        ("2019-01-01", "2020-12-31", "2019-2020 结构牛"),
        ("2021-01-01", "2021-12-31", "2021 小盘强势"),
        ("2024-01-01", "2024-02-10", "2024 微盘闪崩"),
    ]
    rows = []
    for a, b, lb in periods:
        s = seg(r, a, b, lb)
        if s:
            rows.append(s)
    print(pd.DataFrame(rows).to_string(index=False))

    # --- 前后半段 ---
    mid = r.index[len(r) // 2]
    print(f"\n前后半段对比 (以 {mid.date()} 为界):")
    for lb, s in [("前半段", r[r.index < mid]), ("后半段", r[r.index >= mid])]:
        eqs = (1 + s).cumprod()
        print(f"  {lb}: 年化 {ann(s):6.1%}  夏普 {shp(s):5.2f}  "
              f"回撤 {(eqs/eqs.cummax()-1).min():7.1%}")

    # --- 分组图 ---
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS",
                                           "Heiti SC", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        fig = plt.figure(figsize=(14, 9))
        gs = fig.add_gridspec(3, 2, height_ratios=[2.2, 1, 1.1], hspace=0.35, wspace=0.2)

        ax1 = fig.add_subplot(gs[0, :])
        ax1.plot(eq.index, eq.values, lw=1.4, color="#c0392b")
        ax1.set_yscale("log")
        ax1.set_title(f"Amihud 流动性策略 长历史 2011-2026  "
                      f"年化{ann(r):.1%}  夏普{shp(r):.2f}  回撤{dd.min():.1%}")
        ax1.set_ylabel("净值 (对数)"); ax1.grid(alpha=0.3)

        ax2 = fig.add_subplot(gs[1, :])
        ax2.fill_between(dd.index, dd.values * 100, 0, color="#c0392b", alpha=0.4)
        ax2.set_ylabel("回撤 (%)"); ax2.grid(alpha=0.3)

        ax3 = fig.add_subplot(gs[2, :])
        cols = ["#c0392b" if v < 0 else "#2c7fb8" for v in yr.values]
        ax3.bar(yr.index.astype(str), yr.values * 100, color=cols)
        ax3.axhline(0, color="black", lw=0.8)
        ax3.set_ylabel("年度收益 (%)")
        ax3.tick_params(axis="x", rotation=45)
        ax3.grid(axis="y", alpha=0.3)

        fig.savefig(OUT / "long_history_equity.png", dpi=125, bbox_inches="tight")
        print(f"\n图表: {OUT / 'long_history_equity.png'}")
    except Exception as e:
        print(f"绘图跳过: {e}")

    pd.DataFrame({"ret": r, "equity": eq, "dd": dd}).to_csv(
        OUT / "long_history_daily.csv", encoding="utf-8")


if __name__ == "__main__":
    main()
