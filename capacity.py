"""
资金容量 / 滑点敏感性
====================
用平方根冲击模型估算不同资金规模下的净收益:
    冲击成本 ≈ k * sqrt(本次交易额 / 该股日均成交额)
k 取 0.1 (A股小盘股的经验值, 偏保守)

同时给出: 不同规模下每只股票占日成交额的比例 (流动性安全检查)
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long.pkl")
import engine as E

BASE = Path(__file__).resolve().parent
OUT = BASE / "results"
REBAL, NHOLD = 60, 50
SIZE = (0.05, 0.30)
BASE_COST = 0.00075      # 佣金0.025% + 印花税0.05% (卖出单边) ≈ 0.075% 单边摊薄
IMPACT_K = 0.10


def build_periods():
    p = E.piv()
    c = p["close"]
    amt = p["amount"]
    adv20 = amt.rolling(20, min_periods=10).mean()
    seasoned = c.shift(250).notna()
    fac = E.FACTORS["amihud"](p)
    dates = c.index

    periods = []
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
        t1 = dates[i + 1]
        t2 = dates[min(i + 1 + REBAL, len(dates) - 1)]
        periods.append((t1, t2, picks, adv20.loc[t, picks]))
    return c, periods


def simulate(c, periods, capital):
    """capital: 总资金(元). 返回净收益序列"""
    per_stock = capital / NHOLD
    rets, prev = [], set()
    penalties = []
    for t1, t2, picks, advs in periods:
        seg = c.loc[t1:t2, picks].ffill()
        if len(seg) < 2:
            continue
        ok = seg.iloc[0].notna()
        seg = seg.loc[:, ok]
        use = [x for x in picks if x in seg.columns]
        if len(use) < 10:
            continue
        adv = advs.reindex(use).fillna(1e6)

        # 换手比例
        cur = set(use)
        to = 1.0 if not prev else len(cur - prev) / max(len(cur), 1)

        # 单只股票的单边冲击成本
        participation = (per_stock * to) / adv
        impact = IMPACT_K * np.sqrt(participation.clip(0, 1))
        cost_per_stock = BASE_COST + impact
        cost = float(cost_per_stock.mean()) * 2 * to

        pr = seg.div(seg.iloc[0]).mean(axis=1).pct_change(fill_method=None).dropna()
        if len(pr):
            pr.iloc[0] -= cost
        prev = cur
        rets.append(pr)
        penalties.append(float(participation.mean()))

    r = pd.concat(rets).sort_index()
    r = r[~r.index.duplicated(keep="first")]
    return r, float(np.mean(penalties))


def st(r):
    eq = (1 + r).cumprod()
    yrs = len(r) / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(252)
    mdd = (eq / eq.cummax() - 1).min()
    return ann, r.mean() * 252 / vol, mdd


def main():
    c, periods = build_periods()
    print(f"调仓期 {len(periods)}, 每次 {NHOLD} 只\n")

    # 持仓流动性画像
    adv_all = np.concatenate([a.values for _, _, _, a in periods])
    print("=== 持仓流动性画像 ===")
    for q in [10, 25, 50, 75, 90]:
        print(f"  日成交额 P{q}: {np.percentile(adv_all, q)/1e4:8.0f} 万元")
    print(f"  平均日成交额: {adv_all.mean()/1e4:.0f} 万元")

    print("\n=== 不同资金规模下的净表现 ===")
    print(f"{'资金':>10} {'单只建仓':>10} {'占日成交额':>10} {'年化':>8} {'夏普':>7} {'回撤':>8}")
    print("-" * 62)
    rows = []
    for cap in [1e5, 5e5, 1e6, 5e6, 1e7, 3e7, 5e7, 1e8, 3e8]:
        r, part = simulate(c, periods, cap)
        a, s, m = st(r)
        rows.append({"资金": cap, "年化": a, "夏普": s, "回撤": m, "参与率": part})
        unit = f"{cap/1e4:.0f}万"
        print(f"{unit:>10} {cap/NHOLD/1e4:>9.1f}万 {part:>9.2%} {a:>7.1%} {s:>7.2f} {m:>7.1%}")

    pd.DataFrame(rows).to_csv(OUT / "capacity.csv", index=False, encoding="utf-8")

    # 加风控后的容量
    print("\n=== 加 MA20 风控后的容量 ===")
    import risk_control as R
    print(f"{'资金':>10} {'年化':>8} {'夏普':>7} {'回撤':>8}")
    print("-" * 40)
    for cap in [1e6, 1e7, 5e7, 1e8]:
        r, _ = simulate(c, periods, cap)
        ov, _ = R.apply_index_filter(r, ma=20, cut=0.5, index_code="000852")
        a, s, m = st(ov)
        print(f"{cap/1e4:>9.0f}万 {a:>7.1%} {s:>7.2f} {m:>7.1%}")

    print(f"\n明细: {OUT / 'capacity.csv'}")


if __name__ == "__main__":
    main()
