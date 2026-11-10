"""
策略普适性检验
1. 分年度收益: 靠某几年还是每年都赚
2. 样本外验证: 前半段选参数, 后半段验证; 反向再验一次
3. 起点敏感性: 换不同起始日期看结论是否稳定
"""
import itertools
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
OUT = BASE / "results"
COST = 0.0015

COMBOS = list(itertools.product([20, 50, 100], [10, 20, 40],
                                [(0.10, 0.50), (0.05, 0.30), (0.10, 0.30)]))
DEFAULT = dict(n_hold=100, rebal=20, lo=0.05, hi=0.30)


def load():
    close, amount, shares = pd.read_pickle(DATA / "pivots.pkl")
    return close, amount, shares


def run(close, amount, shares, n_hold, rebal, lo, hi):
    dates = close.index
    codes = [c for c in close.columns if c in shares.index]
    cl = close[codes]; sh = shares[codes]
    ret20 = cl / cl.shift(20) - 1
    adv20 = amount[codes].rolling(20, min_periods=10).mean()
    seasoned = cl.shift(250).notna()

    rets, prev = [], set()
    for i in range(300, len(dates), rebal):
        t = dates[i]; t1 = dates[min(i + rebal, len(dates) - 1)]
        r = ret20.loc[t]; cap = cl.loc[t] * sh
        valid = r.notna() & cap.notna() & (adv20.loc[t] > 5e6) & seasoned.loc[t]
        cv = cap[valid]
        if len(cv) < 200:
            continue
        a, b = cv.quantile(lo), cv.quantile(hi)
        pool = cv[(cv >= a) & (cv <= b)].index
        picks = list(r.loc[pool].nsmallest(n_hold).index)
        if not picks:
            continue
        seg = cl.loc[t:t1, picks].ffill()
        if len(seg) < 2:
            continue
        pr = seg.div(seg.iloc[0]).mean(axis=1).pct_change().dropna()
        cur = set(picks)
        to = 1.0 if not prev else len(cur - prev) / max(len(cur), 1)
        if len(pr):
            pr.iloc[0] -= to * 2 * COST
        prev = cur
        rets.append(pr)
    r = pd.concat(rets).sort_index()
    return r[~r.index.duplicated(keep="first")]


def stat(r):
    eq = (1 + r).cumprod()
    yrs = len(eq) / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(252)
    mdd = (eq / eq.cummax() - 1).min()
    return dict(ann=ann, sharpe=r.mean() * 252 / vol if vol > 0 else 0,
                mdd=mdd, total=eq.iloc[-1] - 1, vol=vol)


def main():
    close, amount, shares = load()

    # ---------- 1. 分年度 ----------
    r = run(close, amount, shares, **{"n_hold": DEFAULT["n_hold"], "rebal": DEFAULT["rebal"],
                                      "lo": DEFAULT["lo"], "hi": DEFAULT["hi"]})
    print("=== 1. 分年度收益 (N=100, R=20d, 5%-30%) ===")
    yr = r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)
    for y, v in yr.items():
        flag = "  ← 亏损年" if v < 0 else ""
        print(f"  {y}: {v:+7.1%}{flag}")
    pos_years = (yr > 0).sum()
    print(f"  盈利年份 {pos_years}/{len(yr)}, 最差年 {yr.min():.1%}, 最好年 {yr.max():.1%}")

    # ---------- 2. 样本外 ----------
    print("\n=== 2. 样本外检验 ===")
    dates = close.index
    split = "2024-01-01"

    for train_end, label in [(split, "训练=2021~2023 → 测试=2024~2026"),
                             ("2025-01-01", "训练=2021~2024 → 测试=2025~2026")]:
        train_close = close[close.index < train_end]
        test_close = close[close.index >= train_end]
        # 训练集选最优
        best = None
        for n_hold, rebal, (lo, hi) in COMBOS:
            try:
                rt = run(train_close, amount.loc[train_close.index],
                         shares, n_hold, rebal, lo, hi)
                if len(rt) < 100:
                    continue
                s = stat(rt)["sharpe"]
                if best is None or s > best[0]:
                    best = (s, n_hold, rebal, lo, hi)
            except Exception:
                continue
        if best is None:
            print(f"  {label}: 训练失败")
            continue
        _, n_hold, rebal, lo, hi = best
        # 测试集验证 (注意: 需要训练集数据算 warmup, 用全量再截取)
        r_all = run(close, amount, shares, n_hold, rebal, lo, hi)
        r_test = r_all[r_all.index >= train_end]
        r_def = r[r.index >= train_end]
        st = stat(r_test) if len(r_test) > 20 else None
        sd = stat(r_def) if len(r_def) > 20 else None
        if st:
            print(f"  {label}")
            print(f"    训练最优参数: N={n_hold} R={rebal} 市值{lo:.0%}-{hi:.0%}")
            print(f"    样本外: 年化{st['ann']:+7.1%} 夏普{st['sharpe']:5.2f} 回撤{st['mdd']:7.1%}")
            print(f"    基准配置样本外: 年化{sd['ann']:+7.1%} 夏普{sd['sharpe']:5.2f} 回撤{sd['mdd']:7.1%}")

    # ---------- 3. 起点敏感性 ----------
    print("\n=== 3. 起点敏感性 (同样参数, 不同起始日) ===")
    for start in ["2021-04-01", "2022-01-01", "2023-01-01", "2024-01-01"]:
        seg = r[r.index >= start]
        if len(seg) < 60:
            continue
        s = stat(seg)
        print(f"  {start} 起: 年化{s['ann']:+7.1%}  夏普{s['sharpe']:5.2f}  "
              f"回撤{s['mdd']:7.1%}  区间{seg.index[0].date()}~{seg.index[-1].date()}")

    # ---------- 4. 滚动3年窗口 ----------
    print("\n=== 4. 滚动3年窗口年化 (检验稳定性) ===")
    windows = []
    for y in range(2021, 2027):
        s, e = f"{y}-01-01", f"{y}-12-31"
        seg = r[(r.index >= s) & (r.index <= e)]
        if len(seg) > 200:
            windows.append((y, stat(seg)["ann"]))
    for y, a in windows:
        bar = "█" * max(int(abs(a) * 50), 1)
        print(f"  {y}: {a:+7.1%} {'+' if a > 0 else '-'}{bar}")


if __name__ == "__main__":
    main()
