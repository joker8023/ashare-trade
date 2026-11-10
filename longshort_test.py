"""多空对冲测试 — 新思路
====================
之前所有策略都是纯多头, 回撤大是因为吃了满满的贝塔。
新思路: long 不流动小盘 + short 高流动性大盘 (或指数),
用空头对冲系统性下跌, 不加杠杆。

测试:
  A. 纯多空: long Amihud top100 / short Amihud bottom100 (等权, 美元中性)
  B. 对冲指数: long 因子组合 - beta * 中证1000
  C. 对冲 + 择时: B 再加 MA15 过滤
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import engine as E
import risk_control as R

BASE = Path(__file__).resolve().parent
SIZE = (0.05, 0.30)
COST = 0.0015
REBAL = 60
NHOLD = 100


def load():
    p = E.piv()
    c = p["close"]
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    seasoned = c.shift(250).notna()
    fac = E.FACTORS["amihud"](p)
    return p, c, adv20, seasoned, fac


def run_longshort(p, c, adv20, seasoned, fac, n=NHOLD, size=SIZE):
    """美元中性: 做多 top-N, 做空 bottom-N, 等权"""
    dates = c.index
    codes = c.columns
    rets = []
    prev_l, prev_s = set(), set()
    for i in range(300, len(dates) - REBAL - 2, REBAL):
        t = dates[i]
        t1, t2 = dates[i + 1], dates[min(i + 1 + REBAL, len(dates) - 1)]
        valid = seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna() & fac.loc[t].notna()
        cap = c.loc[t] * p["shares"]
        lo, hi = cap.quantile(size[0]), cap.quantile(size[1])
        valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
        pool = valid[valid].index
        if len(pool) < 2 * n:
            continue
        fv = fac.loc[t, pool]
        longs = list(fv.nlargest(n).index)
        shorts = list(fv.nsmallest(n).index)
        seg = c.loc[t1:t2, longs + shorts].ffill()
        if len(seg) < 2:
            continue
        rel = seg.div(seg.iloc[0])
        # 多空等权: 多头 +0.5, 空头 -0.5
        rl = rel[longs].mean(axis=1)
        rs = rel[shorts].mean(axis=1)
        pr = 0.5 * rl.pct_change(fill_method=None) - 0.5 * rs.pct_change(fill_method=None)
        pr = pr.dropna()
        # 换手成本 (双边都换)
        cur = (set(longs), set(shorts))
        to = 1.0 if not prev_l else (
            len(set(longs) - prev_l) / n + len(set(shorts) - prev_s) / n) / 2
        if len(pr):
            pr.iloc[0] -= to * 2 * COST
        prev_l, prev_s = set(longs), set(shorts)
        rets.append(pr)
    r = pd.concat(rets).sort_index()
    return r[~r.index.duplicated(keep="first")]


def run_hedged(base_r, hedge="000852", beta=1.0):
    """多头策略收益 - beta * 指数收益 (指数空头对冲)"""
    ref = base_r.index
    idx = R._index_series(hedge).reindex(ref).ffill()
    ir = idx.pct_change(fill_method=None).fillna(0).reindex(ref).fillna(0)
    return base_r - beta * ir


def stats(r, label):
    eq = (1 + r).cumprod()
    yrs = len(r) / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(252)
    mdd = (eq / eq.cummax() - 1).min()
    act = r[r != 0]
    return dict(策略=label, 年化=ann, 波动=vol,
                夏普=r.mean() * 252 / vol if vol > 0 else 0,
                回撤=mdd, Calmar=ann / abs(mdd) if mdd < 0 else 0,
                胜率=(active := (act > 0).mean()) if len(act) else 0,
                天数=len(r))


def main():
    p, c, adv20, seasoned, fac = load()

    # 1. 先拿基准多头 (与之前一致的配置)
    import strategy_lab as S
    import combo_lab as C
    ratio = C.combo_rank("amihud+amount_level")
    d0 = pd.Timestamp("2015-01-01")
    idx = c.index[c.index >= d0]
    buy = (c - 0.3 * C.get_atr(14)).shift(1)
    sell = buy + 0.8 * C.get_atr(14).shift(1)
    stop = buy - 10 * C.get_atr(14).shift(1)
    gate = (ratio >= 0.75) & (adv20 > 20_000_000) & c.notna()
    def cut(x):
        return x.reindex(index=idx, columns=c.columns).where(gate.reindex(index=idx, columns=c.columns))
    eq, tr = S.backtest(p, cut(buy), cut(sell), cut(stop), cost=COST)
    base = eq.pct_change(fill_method=None).dropna()

    rows = [stats(base, "基准:纯多头")]
    # 2. 对冲指数
    for beta, hedge in [(1.0, "000852"), (0.7, "000852"), (0.5, "000852"),
                        (1.0, "000985"), (1.0, "000300")]:
        rows.append(stats(run_hedged(base, hedge, beta), f"对冲{hedge}x{beta}"))
    # 3. 纯多空
    try:
        r = run_longshort(p, c, adv20, seasoned, fac)
        rows.append(stats(r, "纯多空 top100/bottom100"))
    except Exception as e:
        print("纯多空失败:", e)

    df = pd.DataFrame(rows)
    print("=" * 92)
    print("多空对冲 vs 纯多头 (2015-2026, 清洗后数据)")
    print("=" * 92)
    d = df.copy()
    for col in ["年化", "波动", "回撤"]:
        d[col] = d[col].map(lambda x: f"{x:.1%}")
    d["夏普"] = d["夏普"].map(lambda x: f"{x:.2f}")
    d["Calmar"] = d["Calmar"].map(lambda x: f"{x:.2f}")
    d["胜率"] = d["胜率"].map(lambda x: f"{x:.1%}")
    print(d.to_string(index=False))


if __name__ == "__main__":
    main()
