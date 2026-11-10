#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""batch_008 独立审计: R7冠军 vs N4基线.
禁调 team/harness.py; 只用 data/pivots_long_clean.pkl + team/audit/prior_check.py(审计员自写引擎).
口径: fresh 2026-01-05空仓起步, 现实费率(佣金0.025%最低5元+印花0.05%+过户0.001%+滑点0.2%/边),
5万/100股整手, t信号t+1收盘执行, TP t收盘触发t+1收盘卖(next), 主板池, amihud_60, size5-30%, adv>5e6.
用法: .venv/bin/python team/audit/batch_008/audit_r7.py [--out team/audit/out/batch_008_audit.json]
"""
from __future__ import annotations
import argparse, json, math, os, sys
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import prior_check as pc
ROOT = pc.ROOT
MB = ('688', '689', '300', '301', '8', '4')
CAP = 50000.0
CHAMP_ID = 'b008_G1_N4_TPnone_exp100'
BASE_ID = 'b008_G3_BASELINE_N4R30TP45e09'
CHAMP_KW = dict(factor='amihud_60', n=4, rebal=7, stop=None, take=None,
                 capital=CAP, lot=100, cost_one_way=None, slip=0.002,
                 run_start='2026-01-05', phase=0, legacy_grid=False,
                 stop_exec='next', exclude=MB, exposure=1.0)
BASE_KW = dict(factor='amihud_60', n=4, rebal=30, stop=None, take=0.45,
                capital=CAP, lot=100, cost_one_way=None, slip=0.002,
                run_start='2026-01-05', phase=0, legacy_grid=False,
                stop_exec='next', exclude=MB, exposure=0.9)

def wilson(k, n, z=1.96):
    if n == 0: return (float('nan'), float('nan'))
    p = k / n; d = 1 + z*z/n; c = (p + z*z/(2*n))/d
    h = z*((p*(1-p)/n + z*z/(4*n*n))**0.5)/d
    return (c-h, c+h)

def enrich(label, res):
    m = pc.metrics(res)
    tr = res.trades
    ev = tr[(tr.exit_date >= pc.EVAL_START) & (tr.exit_date <= pc.EVAL_END)] if len(tr) else tr
    pnl = ev.groupby('code')['net_pnl'].sum().sort_values(ascending=False) if len(ev) else pd.Series(dtype=float)
    tot = float(pnl.sum()) if len(pnl) else 0.0
    w = res.exposure.loc[pc.EVAL_START:pc.EVAL_END]
    out = dict(label=label, fresh_total=m['total_2026'], fresh_ann=m['ann_2026'],
        mdd=m['mdd_2026'], wp=m['win_period'], n_periods=m['n_periods'],
        period_rets=m['period_rets'], last_partial_ret=m['last_partial_ret'],
        wm=m['win_month'], wm_n=m['win_month_n'], monthly=m['monthly_rets'],
        wt=m['win_trade'], n_trades=m['n_trades'], trade_win_n=m['trade_win_n'],
        avg_win=m['avg_win'], avg_loss=m['avg_loss'], profit_factor=m['profit_factor'],
        vol=m['vol'], sharpe=m['sharpe'], calmar_total_over_mdd=(m['total_2026']/abs(m['mdd_2026']) if m['mdd_2026']<0 else float('nan')),
        exposure_mean=float(w.mean()), exposure_min=float(w.min()),
        top1_share=float(pnl.iloc[0]/tot) if len(pnl) and tot else float('nan'),
        top3_share=float(pnl.head(3).sum()/tot) if len(pnl) and tot else float('nan'),
        top3_codes=list(pnl.index[:3]), n_codes=int(len(pnl)),
        cost_total=float(res.meta.get('total_cost',0.0)),
        cost_pct_cap=float(res.meta.get('total_cost',0.0))/m['base_equity'],
        cost_by_year=res.meta.get('cost_by_year',{}),
        skipped_lot=int(res.meta.get('skipped_lot',0)),
        stale_buys=int(res.meta.get('stale_buys',0)), stale_sells=int(res.meta.get('stale_sells',0)),
        limitup_buys=int(res.meta.get('limitup_buys',0)), limitdown_sells=int(res.meta.get('limitdown_sells',0)),
        stop_sells=int(res.meta.get('stop_sells',0)), rebal_sells=int(res.meta.get('rebal_sells',0)),
        n_rebalances=int(res.meta.get('n_rebalances',0)), end_equity=m['end_equity'], base_equity=m['base_equity'])
    k = int(round(m['win_period']*m['n_periods'])) if m['n_periods'] else 0
    out['wilson_wp'] = list(wilson(k, m['n_periods']))
    out['wilson_wt'] = list(wilson(m['trade_win_n'], m['n_trades']))
    try:
        a,b = m['win_month_n'].split('/')
        out['wilson_wm'] = list(wilson(int(a), int(b)))
    except Exception:
        out['wilson_wm'] = [float('nan'), float('nan')]
    return out, m, res

def bootstrap_daily(res, base, n_iter=1000, seed=7):
    rng = np.random.default_rng(seed)
    win = res.eq.loc[pc.EVAL_START:pc.EVAL_END]
    dret = win.pct_change(); dret.iloc[0] = win.iloc[0]/base - 1.0
    r = dret.to_numpy(dtype=float)
    sims = np.empty(n_iter)
    for i in range(n_iter):
        s = rng.choice(r, size=len(r), replace=True)
        sims[i] = float(np.prod(1.0+s)-1.0)
    return dict(p5=float(np.quantile(sims,0.05)), p50=float(np.quantile(sims,0.5)),
                p_neg=float((sims<0).mean()), mean=float(sims.mean()), n_iter=n_iter, seed=seed)

def oos_2025(kw):
    k2 = dict(kw); k2['run_start'] = '2024-01-01'
    res = pc.run_strategy(pc.get_inputs(), **k2)
    eq = res.eq
    seg = eq.loc['2025-01-01':'2025-12-31']
    b = eq.loc[:'2024-12-31']
    base = float(b.iloc[-1]) if len(b) else CAP
    total = float(seg.iloc[-1]/base-1); mdd = float((seg/seg.cummax()-1).min())
    per = res.periods
    p = per[(per.start>=pd.Timestamp('2025-01-01'))&(per.end<=pd.Timestamp('2025-12-31'))&per.complete.fillna(False).astype(bool)] if len(per) else per
    tr = res.trades
    t = tr[(tr.exit_date>=pd.Timestamp('2025-01-01'))&(tr.exit_date<=pd.Timestamp('2025-12-31'))] if len(tr) else tr
    mm = eq.loc[:'2025-12-31'].resample('ME').last()
    allm = pd.concat([pd.Series([base], index=[pd.Timestamp('2024-12-31')]), mm.loc['2025-01-01':]])
    allm = allm[~allm.index.duplicated(keep='last')].sort_index()
    mr = allm.pct_change().dropna()
    wm = f"{int((mr>0).sum())}/{int(len(mr))}"
    return dict(total=total, mdd=mdd, wp=float((p.ret>0).mean()) if len(p) else float('nan'),
                n_periods=int(len(p)), wt=float((t.net_ret>0).mean()) if len(t) else float('nan'),
                n_trades=int(len(t)), wm=wm)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default='team/audit/out/batch_008_audit.json')
    a = ap.parse_args()
    inp = pc.get_inputs()
    out = {'champ_id': CHAMP_ID, 'base_id': BASE_ID}
    # harness对照
    df = pd.read_csv(os.path.join(ROOT, 'team', 'runs', 'batch_008_results.csv'))
    for sid in (CHAMP_ID, BASE_ID):
        row = df[df['id']==sid].iloc[0]
        out[sid+':harness'] = dict(fresh_total=float(row['fresh_total']), fresh_mdd=float(row['fresh_mdd']),
            fresh_win_period=float(row['fresh_win_period']), fresh_win_month=str(row['fresh_win_month']),
            fresh_win_trade=float(row['fresh_win_trade']), fresh_n_trades=float(row['fresh_n_trades']),
            fresh_top3=float(row['fresh_top3_pnl_share']), fresh_exposure=float(row['fresh_exposure']),
            fresh_cost_paid_pct=float(row['fresh_cost_paid_pct']), total_2025=float(row['total_2025']),
            win_period_2025=float(row['win_period_2025']))
    # (1)独立复算
    for label, kw, sid in (('champ', CHAMP_KW, CHAMP_ID), ('base', BASE_KW, BASE_ID)):
        res = pc.run_strategy(inp, **kw)
        e, m, r = enrich(label, res)
        h = out[sid+':harness']
        e['delta_pp_vs_harness'] = (e['fresh_total']-h['fresh_total'])*100.0
        e['delta_mdd_pp'] = (e['mdd']-h['fresh_mdd'])*100.0
        e['bootstrap'] = bootstrap_daily(r, m['base_equity'])
        out[label] = e
        out[label+':trades_n'] = int(len(res.trades))
        res.trades.to_csv(os.path.join(ROOT, 'team', 'audit', 'out', f'b008_{label}_trades.csv'), index=False)
        res.eq.to_csv(os.path.join(ROOT, 'team', 'audit', 'out', f'b008_{label}_equity.csv'))
    # (2)成本0.8%/边
    for label, kw in (('champ', CHAMP_KW), ('base', BASE_KW)):
        k2 = dict(kw); k2['cost_one_way'] = 0.008
        e, m, r = enrich(label+':cost08', pc.run_strategy(inp, **k2))
        out[label+':cost08'] = {k: e[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades','cost_total','cost_pct_cap')}
    # (3)phase五档
    for label, kw in (('champ', CHAMP_KW), ('base', BASE_KW)):
        ph = {}
        for p in (-10, -5, 0, 5, 10):
            k2 = dict(kw); k2['phase'] = p
            e, m, r = enrich(f'{label}:ph{p}', pc.run_strategy(inp, **k2))
            ph[str(p)] = {k: e[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades','wm','wm_n')}
        out[label+':phase'] = ph
    # (4)OOS 2025
    for label, kw in (('champ', CHAMP_KW), ('base', BASE_KW)):
        out[label+':oos2025'] = oos_2025(kw)
    # (5)剔Top3
    for label, kw in (('champ', CHAMP_KW), ('base', BASE_KW)):
        top3 = out[label]['top3_codes']
        k2 = dict(kw); k2['exclude'] = tuple(kw['exclude']) + tuple(top3)
        e, m, r = enrich(label+':exTop3', pc.run_strategy(inp, **k2))
        base_tot = out[label]['fresh_total']
        out[label+':exTop3'] = {k: e[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades')} | \
            {'retention': (e['fresh_total']/base_tot if base_tot else float('nan')), 'excluded': top3}
    # (6)前视+1日
    for label, kw in (('champ', CHAMP_KW), ('base', BASE_KW)):
        k2 = dict(kw); k2['sig_lag'] = 1
        e, m, r = enrich(label+':lag1', pc.run_strategy(inp, **k2))
        out[label+':lag1'] = {k: e[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades')}
    op = os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, 'w') as f:
        json.dump(out, f, indent=1, default=float)
    for label in ('champ', 'base'):
        e = out[label]; h = out[out['champ_id' if label=='champ' else 'base_id']+':harness']
        print(f"[{label}] mine fresh={e['fresh_total']*100:.4f}% harness={h['fresh_total']*100:.4f}% delta={e['delta_pp_vs_harness']:+.4f}pp mdd_mine={e['mdd']*100:.2f}% mdd_h={h['fresh_mdd']*100:.2f}% n={e['n_trades']}/{h['fresh_n_trades']} wt={e['wt']*100:.1f}/{h['fresh_win_trade']*100:.1f} top3={e['top3_share']*100:.1f}/{h['fresh_top3']*100:.1f}")
    print('wrote', op)

if __name__ == '__main__':
    main()
