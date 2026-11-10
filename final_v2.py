"""
最终策略 v2 — 加入风控
=======================
基础: Amihud 非流动性选股 (N=100, 60日调仓, 市值5-30%, 成本0.5%)
风控: 中证1000 跌破 MA20 → 仓位降到 50%  (MA20/50% 为参数扫描最优)
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

MA, CUT = 20, 0.5
TARGET = "000852"


def row(label, r):
    eq = (1 + r).cumprod()
    yrs = len(r) / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(252)
    mdd = (eq / eq.cummax() - 1).min()
    return {
        "策略": label,
        "年化": f"{ann:.1%}",
        "波动": f"{vol:.1%}",
        "夏普": f"{r.mean()*252/vol:.2f}",
        "最大回撤": f"{mdd:.1%}",
        "Calmar": f"{ann/abs(mdd):.2f}",
        "累计": f"{eq.iloc[-1]:.1f}x",
    }


def yearly(r):
    return r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)


def main():
    base = R.cached_base("amihud", 100, 60, (0.05, 0.30), 0.005)
    ov, _ = R.apply_index_filter(base, ma=MA, cut=CUT, index_code=TARGET)

    print("=" * 74)
    print("最终策略 v2 — Amihud 流动性 + 指数择时风控")
    print("=" * 74)
    print(f"选股 : 全A沪深, 剔除ST/次新/日均成交额<500万, 取流通市值5-30%分位")
    print(f"       Amihud = mean(|日收益|/成交额) 最高的 100 只, 等权")
    print(f"调仓 : 每60交易日")
    print(f"风控 : 中证1000 收盘 < MA{MA} 时, 仓位降至 {CUT:.0%}")
    print(f"成本 : 单边 0.5%")

    print(f"\n--- 全历史 {base.index[0].date()} ~ {base.index[-1].date()} ---")
    print(pd.DataFrame([
        row("基础(无风控)", base),
        row(f"+ 中证1000 MA{MA} 择时", ov),
    ]).to_string(index=False))

    r21 = base[base.index >= "2021-01-01"]
    o21 = ov[ov.index >= "2021-01-01"]
    print(f"\n--- 近段 2021-01 ~ 2026-10 ---")
    print(pd.DataFrame([
        row("基础(无风控)", r21),
        row(f"+ 中证1000 MA{MA} 择时", o21),
    ]).to_string(index=False))

    # 分年度对比
    yb, yo = yearly(base), yearly(ov)
    print("\n--- 分年度 (基础 → 风控版) ---")
    for y in yb.index:
        a = yb.get(y, 0); b = yo.get(y, 0)
        flag = "  ← 亏损" if a < 0 else ""
        print(f"  {y}: {a:+7.1%} → {b:+7.1%}{flag}")
    print(f"  盈利年: 基础 {(yb>0).sum()}/{len(yb)}   风控 {(yo>0).sum()}/{len(yo)}")

    # 极端环境
    print("\n--- 极端环境对比 ---")
    envs = [("2015-06-12", "2015-09-30", "2015 股灾"),
            ("2016-01-04", "2016-02-29", "2016 熔断"),
            ("2017-01-01", "2017-12-31", "2017 漂亮50"),
            ("2018-01-01", "2018-12-31", "2018 熊市"),
            ("2024-01-01", "2024-02-08", "2024 微盘闪崩")]
    rows = []
    for a, b, lb in envs:
        x = base[(base.index >= a) & (base.index <= b)]
        y = ov[(ov.index >= a) & (ov.index <= b)]
        rows.append({
            "环境": lb,
            "基础收益": f"{(1+x).prod()-1:+.1%}",
            "风控收益": f"{(1+y).prod()-1:+.1%}",
            "基础回撤": f"{((1+x).cumprod()/(1+x).cumprod().cummax()-1).min():.1%}",
            "风控回撤": f"{((1+y).cumprod()/(1+y).cumprod().cummax()-1).min():.1%}",
        })
    print(pd.DataFrame(rows).to_string(index=False))

    # 图
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS",
                                           "Heiti SC", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        eqb, eqo = (1 + base).cumprod(), (1 + ov).cumprod()
        ddb = eqb / eqb.cummax() - 1
        ddo = eqo / eqo.cummax() - 1

        fig = plt.figure(figsize=(14, 10))
        gs = fig.add_gridspec(3, 2, height_ratios=[2.4, 1.2, 1.2], hspace=0.32, wspace=0.18)

        ax = fig.add_subplot(gs[0, :])
        ax.plot(eqb.index, eqb.values, lw=1.1, color="#95a5a6", label="基础 (无风控)")
        ax.plot(eqo.index, eqo.values, lw=1.5, color="#c0392b",
                label=f"Amihud + 中证1000 MA{MA} 择时")
        ax.set_yscale("log"); ax.set_ylabel("净值 (对数)")
        ax.set_title(f"Amihud 流动性策略 + 风控   全历史 2011-2026")
        ax.legend(); ax.grid(alpha=0.3)

        ax2 = fig.add_subplot(gs[1, :])
        ax2.fill_between(ddb.index, ddb.values * 100, 0, color="#95a5a6", alpha=0.35, label="基础")
        ax2.fill_between(ddo.index, ddo.values * 100, 0, color="#c0392b", alpha=0.45, label="风控版")
        ax2.set_ylabel("回撤 (%)"); ax2.legend(fontsize=8); ax2.grid(alpha=0.3)

        ax3 = fig.add_subplot(gs[2, :])
        x = np.arange(len(yb)); w = 0.38
        ax3.bar(x - w/2, yb.values * 100, w, color="#95a5a6", label="基础")
        ax3.bar(x + w/2, yo.reindex(yb.index).values * 100, w, color="#c0392b", label="风控")
        ax3.set_xticks(x); ax3.set_xticklabels(yb.index, rotation=45)
        ax3.axhline(0, color="black", lw=0.8)
        ax3.set_ylabel("年度收益 (%)"); ax3.legend(fontsize=8); ax3.grid(axis="y", alpha=0.3)

        fig.savefig(OUT / "final_v2_equity.png", dpi=125, bbox_inches="tight")
        print(f"\n图表: {OUT / 'final_v2_equity.png'}")
    except Exception as e:
        print(f"绘图跳过: {e}")

    pd.DataFrame({"base": base, "overlay": ov}).to_csv(
        OUT / "final_v2_daily.csv", encoding="utf-8")
    print(f"明细: {OUT / 'final_v2_daily.csv'}")


if __name__ == "__main__":
    main()
