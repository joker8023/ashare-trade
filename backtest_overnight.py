# -*- coding: utf-8 -*-
"""Overnight arbitrage backtest, daily proxy version."""
import argparse
import numpy as np
import pandas as pd
from pathlib import Path

BASE = Path('/Users/joker/coding/ashare-trade')
DATA = BASE / 'data'
OUT = BASE / 'results'
OUT.mkdir(exist_ok=True)

MAIN_PREFIX = ('000', '001', '002', '003', '600', '601', '603', '605')


def load():
    return pd.read_pickle(DATA / 'pivots_2020_clean_realshares_v2.pkl')


def compute_signals(p, use_enhanced=True):
    o, h, l, c = p['open'], p['high'], p['low'], p['close']
    vol, shares = p['volume'], p['shares']
    ret = c / c.shift(1) - 1
    vol_ma5 = vol.shift(1).rolling(5, min_periods=5).mean()
    vol_ratio = vol / vol_ma5
    turnover = vol * 100.0 / shares
    mktcap = c * shares
    gene = ret.shift(1).rolling(20, min_periods=20).max()
    codes = c.columns
    is_main = np.array([str(x)[:3] in MAIN_PREFIX for x in codes])
    main_mask = pd.DataFrame(np.repeat(is_main[None, :], len(c), axis=0), index=c.index, columns=codes)
    seasoned = c.shift(30).notna()
    base = (seasoned & main_mask & (ret >= 0.03) & (ret <= 0.05)
            & (gene > 0.095) & (vol_ratio > 1.0)
            & (turnover >= 0.05) & (turnover <= 0.10)
            & (mktcap >= 5e9) & (mktcap <= 2e10))
    if not use_enhanced:
        return {'base': base, 'ret': ret, 'vol_ratio': vol_ratio}
    mkt_med = ret.median(axis=1, skipna=True)
    beat_mkt = ret.gt(mkt_med, axis=0)
    high5 = h.shift(1).rolling(5, min_periods=5).max()
    newhigh = h >= high5
    rng = (h - l).replace(0, np.nan)
    pos = (c - l) / rng
    pullback = (c < h) & (pos > 0.5)
    enhanced = base & (c > o) & beat_mkt & newhigh & pullback
    return {'base': base, 'enhanced': enhanced, 'ret': ret, 'vol_ratio': vol_ratio}


def backtest_one(c, o, sig, cost):
    dates = c.index
    open_next = o.shift(-1)
    gross_mat = open_next / c - 1
    trades = []
    daily = pd.Series(0.0, index=dates)
    counts = pd.Series(0, index=dates)
    for i in range(len(dates) - 1):
        t = dates[i]
        row = sig.loc[t]
        if not bool(row.any()):
            continue
        codes = row[row].index.tolist()
        g = gross_mat.loc[t, codes].dropna()
        if len(g) == 0:
            continue
        for code, gv in g.items():
            trades.append((t, code, float(gv)))
        daily.loc[t] = float(g.mean()) - 2 * cost
        counts.loc[t] = len(g)
    tr = pd.DataFrame(trades, columns=['date_T', 'code', 'gross'])
    if len(tr):
        tr['net'] = tr['gross'] - 2 * cost
    return tr, daily, counts


def stats(eq):
    r = eq.pct_change().fillna(0)
    ann = eq.iloc[-1] ** (252 / max(len(eq), 1)) - 1 if len(eq) and eq.iloc[-1] > 0 else float('nan')
    sharpe = (r.mean() / r.std() * (252 ** 0.5)) if r.std() > 0 else float('nan')
    dd = eq / eq.cummax() - 1
    return ann, sharpe, dd.min()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cost', type=float, default=0.0015)
    ap.add_argument('--start', default='2020-01-01')
    ap.add_argument('--end', default='2026-11-16')
    a = ap.parse_args()
    p = load()
    sig = compute_signals(p, True)
    c, o = p['close'], p['open']
    mask = (c.index >= pd.Timestamp(a.start)) & (c.index <= pd.Timestamp(a.end))
    c, o = c.loc[mask], o.loc[mask]
    base = sig['base'].loc[mask]
    enh = sig['enhanced'].loc[mask]
    for name, s in [('BASE-6filters', base), ('ENHANCED-plus-intraday-proxy', enh)]:
        tr, daily, counts = backtest_one(c, o, s, a.cost)
        eq = (1 + daily).cumprod()
        ann, sharpe, mdd = stats(eq)
        n = len(tr)
        win = (tr['net'] > 0).mean() if n else float('nan')
        avg = tr['net'].mean() if n else float('nan')
        med = tr['net'].median() if n else float('nan')
        p3 = (tr['net'] >= 0.03).mean() if n else float('nan')
        nz = int((counts > 0).sum())
        print('=' * 70)
        print(name, a.start, a.end, 'cost', a.cost)
        print('trades:', n, 'active_days:', nz, '/', len(c))
        print('win: %.3f avg: %.4f med: %.4f p_plus3: %.3f' % (win, avg, med, p3))
        print('equity_end: %.3f ann: %.3f sharpe: %.2f maxdd: %.3f' % (float(eq.iloc[-1]), ann, sharpe, mdd))
        if n:
            tr['year'] = pd.to_datetime(tr['date_T']).dt.year
            g = tr.groupby('year')['net'].agg(['count', 'mean', lambda x: (x > 0).mean()])
            print(g.to_string())
    tr, daily, counts = backtest_one(c, o, enh, a.cost)
    tr.to_csv(OUT / 'overnight_trades.csv', index=False)
    daily.rename('daily_net').to_csv(OUT / 'overnight_daily.csv')
    print('saved results/overnight_trades.csv results/overnight_daily.csv')


if __name__ == '__main__':
    main()
