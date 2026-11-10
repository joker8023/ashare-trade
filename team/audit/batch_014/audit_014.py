#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""batch_014 独立审计: G2 R7×staged 冠军 + 隔夜策略证伪核查.
禁调 team/harness.py team/lib; staged 用 team/audit/batch_011/staged_engine.py (审计员自写),
隔夜用 team/audit/batch_014/overnight_engine.py, 日线用 prior_check.
数据: data/pivots_long_clean.pkl (+开盘列用于隔夜).
用法: .venv/bin/python team/audit/batch_014/audit_014.py [--out team/audit/out/batch_014_audit.json]
"""
from __future__ import annotations
import argparse, json, os, sys
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..'))
import prior_check as pc
from batch_011.staged_engine import run_staged
from overnight_engine import run_overnight
ROOT = pc.ROOT
MB = ('688', '689', '300', '301', '8', '4')
CAP = 50000.0
CHAMP_ID = 'b014_G2_N4R7_stg30_50_exp100'
BASE_ID = 'b014_G7_BASELINE_N4R30TP45e09'
ON_ID = 'b014_G5_N4R7_overnight_exp90'
STAGED = [(0.30, 0.3333), (0.50, 0.3333)]
CHAMP_KW = dict(factor='amihud_60', n=4, rebal=7, take=None, capital=CAP, lot=100,
                slip=0.002, run_start='2026-01-05', phase=0, stop_exec='next',
                exclude=MB, exposure=1.0)
BASE_KW = dict(factor='amihud_60', n=4, rebal=30, stop=None, take=0.45, capital=CAP, lot=100,
               cost_one_way=None, slip=0.002, run_start='2026-01-05', phase=0, legacy_grid=False,
               stop_exec='next', exclude=MB, exposure=0.9)
ON_KW = dict(n=4, rebal=7, capital=CAP, lot=100, slip=0.002, run_start='2026-01-05',
              phase=0, exclude=MB, factor='amihud_60', exposure=0.9)

def wilson(k, n, z=1.96):
    if n == 0: return (float('nan'), float('nan'))
    p = k / n; d = 1 + z*z/n; c = (p + z*z/(2*n))/d
    h = z*((p*(1-p)/n + z*z/(4*n*n))**0.5)/d
    return (c-h, c+h)

def enrich(label, res, save=True, tag=None):
    m = pc.metrics(res)
    tr = res.trades
    ev = tr[(tr.exit_date >= pc.EVAL_START) & (tr.exit_date <= pc.EVAL_END)] if len(tr) else tr
    pnl = ev.groupby('code')['net_pnl'].sum().sort_values(ascending=False) if len(ev) else pd.Series(dtype=float)
    tot = float(pnl.sum()) if len(pnl) else 0.0
    w = res.exposure.loc[pc.EVAL_START:pc.EVAL_END]
    reasons = ev['reason'].value_counts().to_dict() if len(ev) and 'reason' in ev.columns else {}
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
        skipped_lot=int(res.meta.get('skipped_lot',0)),
        stale_buys=int(res.meta.get('stale_buys',0)), stale_sells=int(res.meta.get('stale_sells',0)),
        n_rebalances=int(res.meta.get('n_rebalances',0)),
        reasons={str(k): int(v) for k,v in reasons.items()},
        align=getattr(res, 'align', None),
        end_equity=m['end_equity'], base_equity=m['base_equity'])
    k = int(round(m['win_period']*m['n_periods'])) if m['n_periods'] else 0
    out['wilson_wp'] = list(wilson(k, m['n_periods']))
    out['wilson_wt'] = list(wilson(m['trade_win_n'], m['n_trades']))
    try:
        ab = m['win_month_n'].split('/')
        out['wilson_wm'] = list(wilson(int(ab[0]), int(ab[1])))
    except Exception:
        out['wilson_wm'] = [float('nan'), float('nan')]
    if save:
        res.trades.to_csv(os.path.join(ROOT, 'team', 'audit', 'out', f'b014_{tag or label}_trades.csv'), index=False)
        res.eq.to_csv(os.path.join(ROOT, 'team', 'audit', 'out', f'b014_{tag or label}_equity.csv'))
    return out, m, res

def bootstrap_daily(res, base, n_iter=1000, seed=7):
    rng = np.random.default_rng(seed)
    win = res.eq.loc[pc.EVAL_START:pc.EVAL_END]
    dret = win.pct_change(); dret.iloc[0] = win.iloc[0]/base - 1.0
    r = dret.to_numpy(dtype=float)
    sims = np.empty(n_iter)
    for i in range(n_iter):
        sims[i] = float(np.prod(1.0+rng.choice(r, size=len(r), replace=True))-1.0)
    return dict(p5=float(np.quantile(sims,0.05)), p50=float(np.quantile(sims,0.5)),
                p_neg=float((sims<0).mean()), mean=float(sims.mean()), n_iter=n_iter, seed=seed)

def spread_bootstrap(res_c, base_c, res_b, base_b, n_iter=5000, seed=11):
    rng = np.random.default_rng(seed)
    wc = res_c.eq.loc[pc.EVAL_START:pc.EVAL_END]
    wb = res_b.eq.loc[pc.EVAL_START:pc.EVAL_END]
    dc = wc.pct_change(); dc.iloc[0] = wc.iloc[0]/base_c - 1.0
    db = wb.pct_change(); db.iloc[0] = wb.iloc[0]/base_b - 1.0
    idx = dc.index.intersection(db.index)
    sp = (dc.loc[idx] - db.loc[idx]).to_numpy(dtype=float)
    sims = np.empty(n_iter)
    for i in range(n_iter):
        sims[i] = float(np.prod(1.0+rng.choice(sp, size=len(sp), replace=True))-1.0)
    return dict(p5=float(np.quantile(sims,0.05)), p50=float(np.quantile(sims,0.5)),
                p95=float(np.quantile(sims,0.95)), p_excess_pos=float((sims>0).mean()),
                mean=float(sims.mean()), n_iter=n_iter, seed=seed)

def oos_2025_pc(kw):
    k2 = dict(kw); k2['run_start'] = '2024-01-01'
    res = pc.run_strategy(pc.get_inputs(), **k2)
    eq = res.eq
    seg = eq.loc['2025-01-01':'2025-12-31']
    b = eq.loc[:'2024-12-31']
    base = float(b.iloc[-1]) if len(b) else CAP
    per = res.periods
    p = per[(per.start>=pd.Timestamp('2025-01-01'))&(per.end<=pd.Timestamp('2025-12-31'))&per.complete.fillna(False).astype(bool)] if len(per) else per
    return dict(total=float(seg.iloc[-1]/base-1), mdd=float((seg/seg.cummax()-1).min()),
                wp=float((p.ret>0).mean()) if len(p) else float('nan'), n_periods=int(len(p)))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default='team/audit/out/batch_014_audit.json')
    a = ap.parse_args()
    inp = pc.get_inputs()
    out = {'champ_id': CHAMP_ID, 'base_id': BASE_ID, 'on_id': ON_ID}
    df = pd.read_csv(os.path.join(ROOT, 'team', 'runs', 'batch_014_results.csv'))
    for sid in (CHAMP_ID, BASE_ID, ON_ID):
        row = df[df['id']==sid].iloc[0]
        out[sid+':harness'] = dict(fresh_total=float(row['fresh_total']), fresh_mdd=float(row['fresh_mdd']),
            fresh_win_period=float(row['fresh_win_period']) if pd.notna(row['fresh_win_period']) else float('nan'),
            fresh_win_month=str(row['fresh_win_month']),
            fresh_win_trade=float(row['fresh_win_trade']), fresh_n_trades=float(row['fresh_n_trades']),
            fresh_top3=float(row['fresh_top3_pnl_share']) if pd.notna(row['fresh_top3_pnl_share']) else float('nan'),
            fresh_exposure=float(row['fresh_exposure']),
            fresh_cost_paid_pct=float(row['fresh_cost_paid_pct']),
            total_2025=float(row['total_2025']) if pd.notna(row['total_2025']) else float('nan'),
            win_period_2025=float(row['win_period_2025']) if pd.notna(row['win_period_2025']) else float('nan'))
    # (1)独立复算: staged冠军 + 基线 + 隔夜(fresh)
    res_c = run_staged(inp, staged=list(STAGED), **CHAMP_KW)
    res_b = pc.run_strategy(inp, **BASE_KW)
    res_on = run_overnight(inp, **ON_KW)
    e, m, r = enrich('champ', res_c)
    h = out[CHAMP_ID+':harness']
    e['delta_pp_vs_harness'] = (e['fresh_total']-h['fresh_total'])*100.0
    e['bootstrap'] = bootstrap_daily(r, m['base_equity'])
    out['champ'] = e
    e2, m2, r2 = enrich('base', res_b, save=False)
    h2 = out[BASE_ID+':harness']
    e2['delta_pp_vs_harness'] = (e2['fresh_total']-h2['fresh_total'])*100.0
    e2['bootstrap'] = bootstrap_daily(r2, m2['base_equity'])
    out['base'] = e2
    eo, mo, ro = enrich('overnight', res_on)
    ho = out[ON_ID+':harness']
    eo['delta_pp_vs_harness'] = (eo['fresh_total']-ho['fresh_total'])*100.0
    eo['bootstrap'] = bootstrap_daily(ro, mo['base_equity'])
    out['overnight'] = eo
    out['spread_champ_vs_base'] = spread_bootstrap(r, m['base_equity'], r2, m2['base_equity'])
    out['spread_on_vs_base'] = spread_bootstrap(ro, mo['base_equity'], r2, m2['base_equity'])
    out['excess_harness_champ_base_pp'] = (h['fresh_total']-h2['fresh_total'])*100.0
    out['excess_mine_champ_base_pp'] = (e['fresh_total']-e2['fresh_total'])*100.0
    # 隔夜前视专项: 全窗逐笔核 买价==t+1收盘 / 卖价==t+2开盘
    opn = inp.piv['open'].astype('float64')
    chk = []
    for _, t in ro.trades.iterrows():
        if not (pd.Timestamp('2026-01-05') <= t['exit_date'] <= pd.Timestamp('2026-11-04')):
            continue
        c0 = str(t['code'])
        ed, xd = pd.Timestamp(t['entry_date']), pd.Timestamp(t['exit_date'])
        bc = float(inp.close.at[ed, c0]) if c0 in inp.close.columns else float('nan')
        so = float(opn.at[xd, c0]) if c0 in opn.columns else float('nan')
        chk.append(dict(buy_ok=bool(abs(t['entry_px']-bc) < 1e-9) if pd.notna(bc) else None,
                        sell_ok=bool(abs(t['exit_px']-so) < 1e-9) if pd.notna(so) else None,
                        next_day=(xd - ed).days))
    import collections
    gaps = collections.Counter(x['next_day'] for x in chk)
    out['overnight:lookahead'] = dict(n_checked=len(chk),
        buy_match=sum(1 for x in chk if x['buy_ok'] is True), buy_mismatch=sum(1 for x in chk if x['buy_ok'] is False),
        sell_match=sum(1 for x in chk if x['sell_ok'] is True), sell_mismatch=sum(1 for x in chk if x['sell_ok'] is False),
        exit_gap_days={str(k): int(v) for k, v in gaps.items()})
    gross = float((ro.trades['shares']*ro.trades['exit_px'] - ro.trades['shares']*ro.trades['entry_px']).sum()) if len(ro.trades) else 0.0
    out['overnight:gross_net'] = dict(gross_total=round(gross,1),
        cost_total=round(float(ro.meta.get('total_cost',0.0)),1))
    # harness 逐笔同样本核对 (gross/net/cost)
    hh = pd.read_csv(os.path.join(ROOT, 'team', 'runs', 'batch_014_trades', 'b014_G5_N4R7_overnight_exp90.csv'))
    hev = hh[pd.to_datetime(hh['exit_date']) >= '2026-01-05']
    out['overnight:harness_gross_net'] = dict(gross_total=round(float((hev['pnl']+hev['cost']).sum()),1),
        net_total=round(float(hev['pnl'].sum()),1), cost_total=round(float(hev['cost'].sum()),1),
        n_window=len(hev))
    # (2)成本0.8% (3)phase五档 -- 冠军/基线; 隔夜: cost08 + phase三档
    for label, kw, is_staged in (('champ', CHAMP_KW, True), ('base', BASE_KW, False)):
        k2 = dict(kw); k2['cost_one_way'] = 0.008
        rr = run_staged(inp, staged=list(STAGED), **{kk: vv for kk, vv in k2.items()}) if is_staged else pc.run_strategy(inp, **k2)
        ee, mm, _ = enrich(label+':cost08', rr, save=False)
        out[label+':cost08'] = {k: ee[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades','cost_total','cost_pct_cap')}
    for label, kw, is_staged in (('champ', CHAMP_KW, True), ('base', BASE_KW, False)):
        ph = {}
        for p in (-10, -5, 0, 5, 10):
            k2 = dict(kw); k2['phase'] = p
            rr = run_staged(inp, staged=list(STAGED), **{kk: vv for kk, vv in k2.items()}) if is_staged else pc.run_strategy(inp, **k2)
            ee, mm, _ = enrich(f'{label}:ph{p}', rr, save=False)
            ph[str(p)] = {k: ee[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades','wm','wm_n')}
        out[label+':phase'] = ph
    ko = dict(ON_KW); ko['cost_one_way'] = 0.008
    ee, mm, _ = enrich('overnight:cost08', run_overnight(inp, **ko), save=False)
    out['overnight:cost08'] = {k: ee[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades','cost_total','cost_pct_cap')}
    pho = {}
    for p in (-10, 0, 10):
        ko2 = dict(ON_KW); ko2['phase'] = p
        ee, mm, _ = enrich(f'overnight:ph{p}', run_overnight(inp, **ko2), save=False)
        pho[str(p)] = {k: ee[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades','wm','wm_n')}
    out['overnight:phase'] = pho
    # (4)OOS2025
    kc = dict(CHAMP_KW); kc['run_start'] = '2024-01-01'
    rc = run_staged(inp, staged=list(STAGED), **{kk: vv for kk, vv in kc.items()})
    eq = rc.eq; seg = eq.loc['2025-01-01':'2025-12-31']; b = eq.loc[:'2024-12-31']
    bb = float(b.iloc[-1]) if len(b) else CAP
    out['champ:oos2025'] = dict(total=float(seg.iloc[-1]/bb-1), mdd=float((seg/seg.cummax()-1).min()))
    out['base:oos2025'] = oos_2025_pc(BASE_KW)
    ko3 = dict(ON_KW); ko3['run_start'] = '2024-01-01'
    ro2 = run_overnight(inp, **ko3)
    eq2 = ro2.eq; seg2 = eq2.loc['2025-01-01':'2025-12-31']; b2 = eq2.loc[:'2024-12-31']
    bb2 = float(b2.iloc[-1]) if len(b2) else CAP
    out['overnight:oos2025'] = dict(total=float(seg2.iloc[-1]/bb2-1), mdd=float((seg2/seg2.cummax()-1).min()),
        n_trades_2025=int(((ro2.trades['exit_date']>='2025-01-01')&(ro2.trades['exit_date']<='2025-12-31')).sum()) if len(ro2.trades) else 0)
    # (5)剔Top3 (6)前视+1日
    for label, kw, is_staged in (('champ', CHAMP_KW, True), ('base', BASE_KW, False)):
        top3 = out[label]['top3_codes']
        k2 = dict(kw); k2['exclude'] = tuple(kw['exclude']) + tuple(top3)
        rr = run_staged(inp, staged=list(STAGED), **{kk: vv for kk, vv in k2.items()}) if is_staged else pc.run_strategy(inp, **k2)
        ee, mm, _ = enrich(label+':exTop3', rr, save=False)
        base_tot = out[label]['fresh_total']
        out[label+':exTop3'] = {k: ee[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades')} | \
            {'retention': (ee['fresh_total']/base_tot if base_tot else float('nan')), 'excluded': top3}
    for label, kw, is_staged in (('champ', CHAMP_KW, True), ('base', BASE_KW, False)):
        k2 = dict(kw); k2['sig_lag'] = 1
        rr = run_staged(inp, staged=list(STAGED), **{kk: vv for kk, vv in k2.items()}) if is_staged else pc.run_strategy(inp, **k2)
        ee, mm, _ = enrich(label+':lag1', rr, save=False)
        out[label+':lag1'] = {k: ee[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades')}
    ko4 = dict(ON_KW); ko4['phase'] = 1  # 隔夜引擎无sig_lag; 用phase+1近似
    ee, mm, _ = enrich('overnight:lag1', run_overnight(inp, **ko4), save=False)
    out['overnight:lag1'] = {k: ee[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades')}
    out['overnight:lag1_note'] = '隔夜引擎无sig_lag, 以phase+1交易日近似'
    op = os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, 'w') as f:
        json.dump(out, f, indent=1, default=float)
    for label, sid in (('champ', CHAMP_ID), ('base', BASE_ID), ('overnight', ON_ID)):
        e = out[label]; hh = out[sid+':harness']
        print(f"[{label}] mine {e['fresh_total']*100:.4f}% harness {hh['fresh_total']*100:.4f}% delta={e['delta_pp_vs_harness']:+.4f}pp n={e['n_trades']}/{hh['fresh_n_trades']}")
    print('excess champ-base harness/mine:', round(out['excess_harness_champ_base_pp'],4), round(out['excess_mine_champ_base_pp'],4))
    print('overnight lookahead:', out['overnight:lookahead'])
    print('overnight gross/net mine:', out['overnight:gross_net'], 'harness:', out['overnight:harness_gross_net'])
    print('overnight oos:', out['overnight:oos2025'])
    print('wrote', op)

if __name__ == '__main__':
    main()
