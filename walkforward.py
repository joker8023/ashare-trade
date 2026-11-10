"""
滚动样本外验证 (Walk-Forward)
==============================
每年年初, 只用「历史至今」的数据挑参数, 然后用选中的参数跑这一年。
不允许任何未来信息进入参数选择。

如果滚动样本外仍然有效 → 策略是真的, 不是数据挖掘
如果滚动样本外失效 → 之前的好看数字是参数挑选出来的幻觉
"""
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

import engine as E

BASE = Path(__file__).resolve().parent
OUT = BASE / "results"

CANDIDATES = list(itertools.product(
    ["amihud", "amihud_60", "turn_std", "amount_level"],
    [50, 100],           # n_hold
    [20, 60],            # rebal
))
SIZE = (0.05, 0.30)
COST = 0.005


def sharpe(r):
    if len(r) < 60:
        return -9
    v = r.std() * np.sqrt(252)
    return r.mean() * 252 / v if v > 0 else -9


def ann(r):
    if len(r) == 0:
        return 0.0
    return (1 + r).prod() ** (252 / len(r)) - 1


def main():
    print(f"候选参数组合: {len(CANDIDATES)} 种")
    print("正在计算每个组合的收益序列 (一次性)...")

    series = {}
    for f, n, reb in CANDIDATES:
        try:
            series[(f, n, reb)] = E.returns_series(
                f, n_hold=n, rebal=reb, size_range=SIZE, cost=COST)
            print(f"  {f:14s} N={n:3d} R={reb:2d}  完成 ({len(series[(f,n,reb)])}天)")
        except Exception as e:
            print(f"  {f} N={n} R={reb} 失败: {e}")

    # 统一时间轴
    all_idx = sorted(set().union(*[set(s.index) for s in series.values()]))
    years = sorted({d.year for d in all_idx})

    print("\n" + "=" * 72)
    print("滚动样本外: 每年只用过去的年数据选参数")
    print("=" * 72)

    oos_parts = []
    rows = []
    for y in years:
        train_end = pd.Timestamp(f"{y}-01-01")
        test_start = pd.Timestamp(f"{y}-01-01")
        test_end = pd.Timestamp(f"{y}-12-31")

        # --- 只用 y 年之前的数据选参数 ---
        best, best_s = None, -9
        for k, s in series.items():
            tr = s[s.index < train_end]
            sc = sharpe(tr)
            if sc > best_s:
                best_s, best = sc, k
        if best is None:
            continue

        # --- 用选中参数跑 y 年 ---
        s = series[best]
        te = s[(s.index >= test_start) & (s.index <= test_end)]
        if len(te) < 40:
            continue
        a = ann(te)
        oos_parts.append(te)
        rows.append({
            "年份": y,
            "选中参数": f"{best[0]}|N={best[1]}|R={best[2]}",
            "训练期夏普": round(best_s, 2),
            "当年收益": round(a, 4),
            "当年夏普": round(sharpe(te), 2),
            "交易日": len(te),
        })

    df = pd.DataFrame(rows)
    print(df.to_string(index=False))

    oos = pd.concat(oos_parts).sort_index() if oos_parts else pd.Series(dtype=float)
    oos = oos[~oos.index.duplicated(keep="first")]
    eq = (1 + oos).cumprod()
    mdd = (eq / eq.cummax() - 1).min()

    print("\n" + "-" * 72)
    print(f"滚动样本外整体: 年化 {ann(oos):.1%}   夏普 {sharpe(oos):.2f}   "
          f"最大回撤 {mdd:.1%}   累计 {eq.iloc[-1]-1:.1%}")
    print(f"盈利年份: {(df['当年收益'] > 0).sum()}/{len(df)}")
    print("-" * 72)

    # 对比: 全样本固定用最优参数 (这是有偏的基准)
    fixed = series.get(("amihud", 100, 60))
    if fixed is not None:
        fx = fixed[(fixed.index >= pd.Timestamp(f"{years[2]}-01-01"))] if len(years) > 2 else fixed
        print(f"\n对照 (全样本固定 amihud/N=100/R=60, 知道未来才选得出): "
              f"年化 {ann(fx):.1%}  夏普 {sharpe(fx):.2f}")
        print(f"滚动样本外 vs 固定最优 的差额 = 真实的数据挖掘损耗")

    df.to_csv(OUT / "walkforward.csv", index=False, encoding="utf-8")
    pd.DataFrame({"ret": oos, "equity": eq}).to_csv(
        OUT / "walkforward_daily.csv", encoding="utf-8")
    print(f"\n结果: {OUT / 'walkforward.csv'}")


if __name__ == "__main__":
    main()
