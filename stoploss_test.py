"""
个股层面止损 / 加权方式对比
===========================
组合择时 (指数 MA20) 只能在整体下行时减仓;
个股止损可以在个股崩盘时单独砍掉, 保留其余仓位。

测试:
  1. 等权 (基准)
  2. 个股止损: 持仓期内跌破 -X% 即卖出, 转为现金直到下次调仓
  3. 波动率倒数加权: 给低波股票更高权重
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long.pkl")
import engine as E

BASE = Path(__file__).resolve().parent
OUT = BASE / "results"
REBAL, NHOLD, COST = 60, 100, 0.005
SIZE = (0.05, 0.30)


def build_picks():
    """预计算每个调仓期的持仓"""
    p = E.piv()
    c = p["close"]
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    seasoned = c.shift(250).notna()
    fac = E.FACTORS["amihud"](p)
    vol = c.pct_change(fill_method=None).rolling(20).std()
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
        periods.append((t1, t2, picks, vol.loc[t, picks]))
    return c, periods


def simulate(c, periods, mode="equal", stop=None):
    """mode: equal | invvol ; stop: 个股止损阈值(如 -0.15)"""
    rets, prev = [], set()
    for t1, t2, picks, vols in periods:
        seg = c.loc[t1:t2, picks].ffill()
        if len(seg) < 2:
            continue
        # 剔除建仓日无价格的股票
        ok = seg.iloc[0].notna()
        seg = seg.loc[:, ok]
        if seg.shape[1] < 10:
            continue
        use = [x for x in picks if x in seg.columns]

        if mode == "invvol":
            w = (1.0 / vols.reindex(use).replace(0, np.nan))
            w = w.fillna(w.median())
            w = w / w.sum()
        else:
            w = pd.Series(1.0 / len(use), index=use)

        entry = seg.iloc[0]
        entry = entry.where(entry > 0)
        pos_val = w.copy()          # 每只股票的当前市值(初始权重)
        cash = 0.0
        prev_px = entry.copy()
        vals = [1.0]

        for dt in seg.index[1:]:
            px = seg.loc[dt]
            step = (px / prev_px).replace([np.inf, -np.inf], np.nan).fillna(1.0)
            pos_val = pos_val * step

            if stop is not None:
                drop = px / entry - 1
                hit = (drop < stop) & (pos_val > 0)
                if hit.any():
                    cash += float(pos_val[hit].sum())
                    pos_val[hit] = 0.0

            vals.append(float(pos_val.sum()) + cash)
            prev_px = px.where(px > 0, prev_px)

        ser = pd.Series(vals, index=seg.index)
        pr = ser.pct_change(fill_method=None).dropna()

        cur = set(use)
        to = 1.0 if not prev else len(cur - prev) / max(len(cur), 1)
        if len(pr):
            pr.iloc[0] -= to * 2 * COST
        prev = cur
        rets.append(pr)

    r = pd.concat(rets).sort_index()
    return r[~r.index.duplicated(keep="first")]


def show(label, r):
    eq = (1 + r).cumprod()
    yrs = len(r) / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(252)
    mdd = (eq / eq.cummax() - 1).min()
    return {
        "方案": label,
        "年化": f"{ann:.1%}",
        "波动": f"{vol:.1%}",
        "夏普": f"{r.mean()*252/vol:.2f}",
        "最大回撤": f"{mdd:.1%}",
        "Calmar": f"{ann/abs(mdd):.2f}",
    }


def main():
    c, periods = build_picks()
    print(f"调仓期: {len(periods)}\n")

    rows, series = [], {}
    cfgs = [
        ("等权(基准)", dict(mode="equal", stop=None)),
        ("波动率倒数加权", dict(mode="invvol", stop=None)),
        ("等权 + 止损-10%", dict(mode="equal", stop=-0.10)),
        ("等权 + 止损-15%", dict(mode="equal", stop=-0.15)),
        ("等权 + 止损-20%", dict(mode="equal", stop=-0.20)),
        ("等权 + 止损-30%", dict(mode="equal", stop=-0.30)),
        ("倒波加权 + 止损-15%", dict(mode="invvol", stop=-0.15)),
    ]
    for label, kw in cfgs:
        r = simulate(c, periods, **kw)
        rows.append(show(label, r))
        series[label] = r
        print(f"  {label} 完成")

    print("\n" + "=" * 84)
    print("个股止损 / 加权方式对比 (2011-2026, 60日调仓, 单边0.5%)")
    print("=" * 84)
    print(pd.DataFrame(rows).to_string(index=False))

    # 分年度看止损版 vs 基准
    base_r = series["等权(基准)"]
    best = series["等权 + 止损-15%"]
    yb = base_r.groupby(base_r.index.year).apply(lambda x: (1 + x).prod() - 1)
    ys = best.groupby(best.index.year).apply(lambda x: (1 + x).prod() - 1)
    print("\n分年度 (等权 → 止损-15%):")
    for y in yb.index:
        print(f"  {y}: {yb[y]:+7.1%} → {ys.get(y, 0):+7.1%}")

    pd.DataFrame({k: v for k, v in series.items()}).to_csv(
        OUT / "stoploss_compare.csv", encoding="utf-8")
    print(f"\n明细: {OUT / 'stoploss_compare.csv'}")


if __name__ == "__main__":
    main()
