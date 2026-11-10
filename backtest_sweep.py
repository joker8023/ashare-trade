"""
小市值+反转 参数扫描 (数据只加载一次)
"""
import os
import itertools
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
OUT = BASE / "results"
OUT.mkdir(exist_ok=True)
COST_ONE_WAY = 0.0015


def load_pivots():
    cache = DATA / "pivots.pkl"
    if cache.exists():
        print("复用透视缓存")
        return pd.read_pickle(cache)
    daily = pd.read_pickle(DATA / "ashare_daily.pkl")
    uni = pd.read_pickle(DATA / "universe.pkl")
    close = daily.pivot_table(index="date", columns="code", values="close").sort_index()
    amount = daily.pivot_table(index="date", columns="code", values="amount").sort_index()
    close = close.where(close > 0)
    last_close = close.iloc[-1]
    shares = (uni.set_index("code")["float_cap"] / last_close).replace([np.inf, -np.inf], np.nan).dropna()
    obj = (close, amount, shares)
    pd.to_pickle(obj, cache)
    return obj


def run(close, amount, shares, n_hold, rebal, size_lo, size_hi):
    dates = close.index
    codes = [c for c in close.columns if c in shares.index]
    cl = close[codes]; sh = shares[codes]
    ret20 = cl / cl.shift(20) - 1
    adv20 = amount[codes].rolling(20, min_periods=10).mean()
    seasoned = cl.shift(250).notna()

    idxs = range(300, len(dates), rebal)
    rets, prev = [], set()
    for i in idxs:
        t = dates[i]; t1 = dates[min(i + rebal, len(dates) - 1)]
        r = ret20.loc[t]; cap = cl.loc[t] * sh
        valid = r.notna() & cap.notna() & (adv20.loc[t] > 5e6) & seasoned.loc[t]
        cv = cap[valid]
        if len(cv) < 200:
            continue
        lo, hi = cv.quantile(size_lo), cv.quantile(size_hi)
        pool = cv[(cv >= lo) & (cv <= hi)].index
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
            pr.iloc[0] -= to * 2 * COST_ONE_WAY
        prev = cur
        rets.append(pr)

    r = pd.concat(rets).sort_index()
    r = r[~r.index.duplicated(keep="first")]
    eq = (1 + r).cumprod()
    n = len(eq); yrs = n / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(252)
    mdd = (eq / eq.cummax() - 1).min()
    act = r[r != 0]
    return dict(年化=ann, 波动=vol, 夏普=r.mean() * 252 / vol, 最大回撤=mdd,
                Calmar=ann / abs(mdd) if mdd < 0 else np.nan,
                总收益=eq.iloc[-1] - 1, 胜率=(act > 0).mean()), r, eq


def main():
    close, amount, shares = load_pivots()
    print(f"数据: {close.shape[0]} 交易日 × {close.shape[1]} 只\n")

    rows = []
    combos = list(itertools.product([20, 50, 100], [10, 20, 40],
                                    [(0.10, 0.50), (0.05, 0.30), (0.10, 0.30)]))
    for n_hold, rebal, (lo, hi) in combos:
        try:
            m, _, _ = run(close, amount, shares, n_hold, rebal, lo, hi)
            rows.append({"持仓数": n_hold, "调仓周期": rebal,
                         "市值区间": f"{lo:.0%}-{hi:.0%}", **m})
            print(f"N={n_hold:3d} R={rebal:2d} {lo:.0%}-{hi:.0%}  "
                  f"年化{m['年化']:6.1%} 夏普{m['夏普']:5.2f} 回撤{m['最大回撤']:7.1%}")
        except Exception as e:
            print(f"N={n_hold} R={rebal} {lo}-{hi} 失败: {e}")

    df = pd.DataFrame(rows).sort_values("夏普", ascending=False)
    df.to_csv(OUT / "smallcap_sweep.csv", index=False, encoding="utf-8")

    print("\n=== 按夏普 Top 8 ===")
    d = df.head(8).copy()
    for c in ["年化", "波动", "最大回撤", "总收益", "胜率"]:
        d[c] = d[c].map(lambda x: f"{x:.1%}")
    for c in ["夏普", "Calmar"]:
        d[c] = d[c].map(lambda x: f"{x:.2f}")
    print(d.to_string(index=False))

    print("\n=== 按年化 Top 5 ===")
    d2 = df.sort_values("年化", ascending=False).head(5).copy()
    for c in ["年化", "波动", "最大回撤", "总收益", "胜率"]:
        d2[c] = d2[c].map(lambda x: f"{x:.1%}")
    for c in ["夏普", "Calmar"]:
        d2[c] = d2[c].map(lambda x: f"{x:.2f}")
    print(d2.to_string(index=False))


if __name__ == "__main__":
    main()
