"""
分层回测 (Decile Analysis)
==========================
把股票池按 Amihud 因子分成 10 组, 看每组的收益是否单调。
如果是真因子, 应该从第1组到第10组收益递增。
如果只有第10组好、中间杂乱, 说明收益来自噪音/极端值, 不可靠。
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long.pkl")
import engine as E

BASE = Path(__file__).resolve().parent
OUT = BASE / "results"
REBAL = 60
COST = 0.005
SIZE = None  # 不限制市值, 看全市场的因子单调性


def main():
    p = E.piv()
    c = p["close"]
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    seasoned = c.shift(250).notna()
    fac = E.FACTORS["amihud"](p)
    dates = c.index

    n_bins = 10
    rets = {i: [] for i in range(n_bins)}
    counts = {i: [] for i in range(n_bins)}

    for i in range(300, len(dates) - REBAL - 2, REBAL):
        t, t1 = dates[i], dates[i + 1]
        t2 = dates[min(i + 1 + REBAL, len(dates) - 1)]
        valid = seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna() & fac.loc[t].notna()
        pool = valid[valid].index
        if len(pool) < 500:
            continue
        f = fac.loc[t, pool]
        # 按因子分10层 (0=流动性最好, 9=最不流动)
        try:
            grp = pd.qcut(f.rank(method="first"), n_bins, labels=False)
        except Exception:
            continue
        for g in range(n_bins):
            codes = grp[grp == g].index
            if len(codes) < 10:
                continue
            seg = c.loc[t1:t2, codes].ffill()
            if len(seg) < 2:
                continue
            pr = seg.div(seg.iloc[0]).mean(axis=1).pct_change(fill_method=None).dropna()
            if len(pr):
                pr.iloc[0] -= 2 * COST
            rets[g].append(pr)
            counts[g].append(len(codes))

    print("=" * 70)
    print("Amihud 因子十分层回测 (2011-2026, 60日调仓, 单边0.5%)")
    print("第1层=流动性最好, 第10层=最不流动")
    print("=" * 70)
    print(f"{'层':>4} {'年化':>8} {'夏普':>7} {'回撤':>8} {'波动':>8} {'平均股票数':>10}")
    print("-" * 70)

    anns = []
    for g in range(n_bins):
        if not rets[g]:
            continue
        r = pd.concat(rets[g]).sort_index()
        r = r[~r.index.duplicated(keep="first")]
        eq = (1 + r).cumprod()
        yrs = len(r) / 252
        ann = eq.iloc[-1] ** (1 / yrs) - 1
        vol = r.std() * np.sqrt(252)
        mdd = (eq / eq.cummax() - 1).min()
        anns.append(ann)
        print(f"{g+1:>4} {ann:>7.1%} {r.mean()*252/vol:>7.2f} {mdd:>7.1%} "
              f"{vol:>7.1%} {np.mean(counts[g]):>10.0f}")

    print("-" * 70)
    if len(anns) >= 10:
        # 单调性检验
        mono = sum(1 for i in range(len(anns) - 1) if anns[i + 1] >= anns[i])
        corr = np.corrcoef(range(len(anns)), anns)[0, 1]
        print(f"单调递增的层数: {mono}/9")
        print(f"层序与收益的相关系数: {corr:.3f}")
        print(f"第10层 - 第1层 年化差: {anns[-1]-anns[0]:+.1%}")
        print(f"多空组合(第10层 - 第1层)年化: {anns[-1]-anns[0]:+.1%}")

    # 图
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS",
                                           "Heiti SC", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
        fig, ax = plt.subplots(figsize=(9, 5))
        colors = ["#2c7fb8"] * (len(anns) - 1) + ["#c0392b"]
        ax.bar(range(1, len(anns) + 1), [a * 100 for a in anns], color=colors)
        for i, a in enumerate(anns):
            ax.text(i + 1, a * 100 + (2.5 if a >= 0 else -5.5), f"{a*100:.0f}%",
                    ha="center", fontsize=9)
        ax.set_xlabel("Amihud 分位组 (1=流动性最好, 10=最不流动)")
        ax.set_ylabel("年化收益 (%)")
        ax.set_title("因子十分层单调性检验 — Amihud 非流动性")
        ax.axhline(0, color="black", lw=0.8)
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(OUT / "decile_amihud.png", dpi=130)
        print(f"\n图表: {OUT / 'decile_amihud.png'}")
    except Exception as e:
        print(f"绘图跳过: {e}")


if __name__ == "__main__":
    main()
