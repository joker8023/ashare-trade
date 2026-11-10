"""
策略组合优化 — 目标: 年化40%+ / 回撤~10%
=====================================
1. 分析策略间相关性
2. 随机权重搜索最大化 Calmar
3. 计算加杠杆后能否达到 40%/10%
4. 诚实报告可达前沿
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
POOL = BASE / "results" / "pool"
OUT = BASE / "results" / "portfolio"
OUT.mkdir(parents=True, exist_ok=True)

MARGIN_COST = 0.06


def stats(r):
    eq = (1 + r).cumprod()
    yrs = len(r) / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(252)
    mdd = (eq / eq.cummax() - 1).min()
    return dict(ann=ann, vol=vol, mdd=mdd,
                sharpe=r.mean() * 252 / vol if vol > 0 else 0,
                calmar=ann / abs(mdd) if mdd < 0 else 0)


def main():
    data = pd.read_pickle(POOL / "series.pkl")
    data = data.dropna(how="all")
    print(f"策略池: {data.shape[1]} 条, {data.shape[0]} 个交易日 "
          f"({data.index[0].date()} ~ {data.index[-1].date()})")

    # ---------- 相关性 ----------
    top = []
    for k in data.columns:
        s = stats(data[k].dropna())
        if s["calmar"] > 0.4:
            top.append(k)
    print(f"\nCalmar>0.4 的策略: {len(top)} 个")
    corr = data[top].corr()
    iu = np.triu_indices(len(top), 1)
    print(f"平均相关系数: {corr.values[iu].mean():.3f}")
    print(f"最低相关: {corr.values[iu].min():.3f}  最高: {corr.values[iu].max():.3f}")

    # ---------- 随机权重搜索 ----------
    sub = data[top].dropna()
    R = sub.values
    n = R.shape[1]
    rng = np.random.default_rng(42)

    best = None
    results = []
    for it in range(30000):
        if it < 3000:
            w = np.zeros(n); w[rng.integers(0, n, 1)[0]] = 1.0   # 单策略
        elif it < 12000:
            k = rng.integers(2, min(6, n) + 1)
            idx = rng.choice(n, k, replace=False)
            w = np.zeros(n); w[idx] = rng.dirichlet(np.ones(k))
        else:
            w = rng.dirichlet(np.ones(n) * 0.5)
        r = R @ w
        eq = np.cumprod(1 + r)
        yrs = len(r) / 252
        ann = eq[-1] ** (1 / yrs) - 1
        peak = np.maximum.accumulate(eq)
        mdd = (eq / peak - 1).min()
        cal = ann / abs(mdd) if mdd < 0 else 0
        results.append((cal, ann, mdd, w.copy()))
        if best is None or cal > best[0]:
            best = (cal, ann, mdd, w.copy())

    print(f"\n=== 最优组合 (Calmar {best[0]:.2f}) ===")
    print(f"  年化 {best[1]:.1%}  回撤 {best[2]:.1%}")
    w = best[3]
    for i in np.argsort(-w)[:8]:
        if w[i] > 0.01:
            print(f"    {w[i]:5.1%}  {top[i]}")

    # ---------- 可达前沿 ----------
    df = pd.DataFrame(results, columns=["calmar", "ann", "mdd", "w"])
    # 对每个回撤档位, 找最大年化
    print("\n" + "=" * 72)
    print("可达前沿: 不同回撤约束下的最高年化 (1倍杠杆, 无融资)")
    print("=" * 72)
    print(f"{'回撤上限':>10}{'最高年化':>12}{'Calmar':>9}{'策略数':>8}")
    print("-" * 72)
    for cap in [0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25]:
        sub_df = df[df["mdd"] >= -cap]
        if len(sub_df) == 0:
            print(f"{cap:>9.0%}       无可行解")
            continue
        b = sub_df.loc[sub_df["ann"].idxmax()]
        nz = int((b["w"] > 0.01).sum())
        print(f"{-cap:>9.0%}{b['ann']:>12.1%}{b['ann']/cap:>9.2f}{nz:>8}")

    # ---------- 杠杆分析 ----------
    print("\n" + "=" * 72)
    print("加杠杆能否达到 40% 年化 / 10% 回撤?")
    print("=" * 72)
    # 取在 10% 回撤约束下年化最高的组合, 加杠杆
    sub10 = df[df["mdd"] >= -0.10]
    if len(sub10):
        b = sub10.loc[sub10["ann"].idxmax()]
        base_ann, base_mdd = b["ann"], b["mdd"]
        print(f"无杠杆最优 (回撤≤10%): 年化 {base_ann:.1%}, 回撤 {base_mdd:.1%}")
        for lev in [1.0, 1.5, 2.0, 3.0, 4.0]:
            r_lev = R @ b["w"] * lev - (lev - 1) * MARGIN_COST / 252
            s = stats(pd.Series(r_lev, index=sub.index))
            print(f"  {lev:.1f}倍杠杆: 年化 {s['ann']:6.1%}  回撤 {s['mdd']:7.1%}  "
                  f"{'✅ 达标' if s['ann']>=0.40 and s['mdd']>=-0.10 else ''}")
    else:
        print("没有回撤≤10%的解")

    # 反推: 要达到 40% 年化需要多少杠杆, 回撤会是多少
    print(f"\n反推: 达到 40% 年化所需杠杆 → 对应回撤")
    b = df.loc[df["ann"].idxmax()]
    if b["ann"] > 0:
        lev_needed = 0.40 / b["ann"]
        r_lev = R @ b["w"] * lev_needed - (lev_needed - 1) * MARGIN_COST / 252
        s = stats(pd.Series(r_lev, index=sub.index))
        print(f"  最佳组合年化 {b['ann']:.1%} → 需要 {lev_needed:.2f}倍杠杆")
        print(f"  此时回撤 {s['mdd']:.1%} (目标 -10%)")

    df[["calmar", "ann", "mdd"]].to_csv(OUT / "frontier.csv", index=False, encoding="utf-8")
    print(f"\n结果: {OUT / 'frontier.csv'}")


if __name__ == "__main__":
    main()
