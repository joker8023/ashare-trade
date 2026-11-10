#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""batch_013 独立审计: 小时级 H03(trail12) vs 基线 + 小时执行层有无 alpha.
禁调 team/hourly_harness.py; 小时用 team/audit/batch_013/hourly_engine.py (审计员自写),
日线用 team/audit/prior_check.py; 数据: data/pivots_long_clean.pkl + data/hourly_60m/*.csv.
用法: .venv/bin/python team/audit/batch_013/audit_013.py [--out team/audit/out/batch_013_audit.json]
"""
from __future__ import annotations
import argparse, json, os, sys
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..'))
import prior_check as pc
from hourly_engine import run_hourly, load_bars
ROOT = pc.ROOT
MB = ('688', '689', '300', '301', '8', '4')
CAP = 50000.0
CHAMP_ID = 'b013_H03_hourly_trail12'
H09_ID = 'b013_H09_hourly_tp45_exp90'
BASE_ID = 'b013_G0_BASELINE_N4R30TP45e09'
DAILYREF_ID = 'b013_G0_N4R7TP45e90_dailyref'

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
        end_equity=m['end_equity'], base_equity=m['base_equity'],
        align=getattr(res, 'align', None))
    k = int(round(m['win_period']*m['n_periods'])) if m['n_periods'] else 0
    out['wilson_wp'] = list(wilson(k, m['n_periods']))
    out['wilson_wt'] = list(wilson(m['trade_win_n'], m['n_trades']))
    try:
        ab = m['win_month_n'].split('/')
        out['wilson_wm'] = list(wilson(int(ab[0]), int(ab[1])))
    except Exception:
        out['wilson_wm'] = [float('nan'), float('nan')]
    if save:
        res.trades.to_csv(os.path.join(ROOT, 'team', 'audit', 'out', f'b013_{tag or label}_trades.csv'), index=False)
        res.eq.to_csv(os.path.join(ROOT, 'team', 'audit', 'out', f'b013_{tag or label}_equity.csv'))
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

H03_KW = dict(n=4, rebal=7, trail=0.12, tp=None, capital=CAP, lot=100, slip=0.002,
              run_start='2024-01-01', phase=0, exclude=MB, factor='amihud_60', exposure=1.0)
H09_KW = dict(n=4, rebal=7, trail=None, tp=0.45, capital=CAP, lot=100, slip=0.002,
              run_start='2024-01-01', phase=0, exclude=MB, factor='amihud_60', exposure=0.9)
BASE_KW = dict(factor='amihud_60', n=4, rebal=30, stop=None, take=0.45, capital=CAP, lot=100,
               cost_one_way=None, slip=0.002, run_start='2026-01-05', phase=0, legacy_grid=False,
               stop_exec='next', exclude=MB, exposure=0.9)
DREF_KW = dict(factor='amihud_60', n=4, rebal=7, stop=None, take=0.45, capital=CAP, lot=100,
               cost_one_way=None, slip=0.002, run_start='2026-01-05', phase=0, legacy_grid=False,
               stop_exec='next', exclude=MB, exposure=0.9)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default='team/audit/out/batch_013_audit.json')
    a = ap.parse_args()
    inp = pc.get_inputs()
    bars = load_bars(ROOT)
    out = {'champ_id': CHAMP_ID, 'h09_id': H09_ID, 'base_id': BASE_ID, 'dailyref_id': DAILYREF_ID,
           'n_hourly_files': len(bars)}
    df = pd.read_csv(os.path.join(ROOT, 'team', 'runs', 'batch_013_results.csv'))
    for sid in (CHAMP_ID, H09_ID, BASE_ID, DAILYREF_ID):
        row = df[df['id']==sid].iloc[0]
        out[sid+':harness'] = dict(fresh_total=float(row['fresh_total']), fresh_mdd=float(row['fresh_mdd']),
            fresh_win_period=float(row['fresh_win_period']) if pd.notna(row['fresh_win_period']) else float('nan'),
            fresh_win_month=str(row['fresh_win_month']),
            fresh_win_trade=float(row['fresh_win_trade']), fresh_n_trades=float(row['fresh_n_trades']),
            fresh_top3=float(row['fresh_top3_pnl_share']), fresh_exposure=float(row['fresh_exposure']),
            fresh_cost_paid_pct=float(row['fresh_cost_paid_pct']))
        if 'total_2025' in df.columns and pd.notna(row['total_2025']):
            out[sid+':harness']['total_2025'] = float(row['total_2025'])
            out[sid+':harness']['win_period_2025'] = float(row['win_period_2025'])
    # (1)独立复算: H03 + H09 (小时引擎, 连续跑) + 基线/日线参照 (日线引擎, 连续跑)
    res_h03 = run_hourly(inp, bars, **H03_KW)
    res_h09 = run_hourly(inp, bars, **H09_KW)
    res_base = pc.run_strategy(inp, **BASE_KW)
    res_dref = pc.run_strategy(inp, **DREF_KW)
    e, m, r = enrich('champ', res_h03)
    h = out[CHAMP_ID+':harness']
    e['delta_pp_vs_harness'] = (e['fresh_total']-h['fresh_total'])*100.0
    e['bootstrap'] = bootstrap_daily(r, m['base_equity'])
    out['champ'] = e
    e9, m9, r9 = enrich('h09', res_h09)
    h9 = out[H09_ID+':harness']
    e9['delta_pp_vs_harness'] = (e9['fresh_total']-h9['fresh_total'])*100.0
    e9['bootstrap'] = bootstrap_daily(r9, m9['base_equity'])
    out['h09'] = e9
    eb, mb, rb = enrich('base', res_base, save=False)
    eb['bootstrap'] = bootstrap_daily(rb, mb['base_equity'])
    hb = out[BASE_ID+':harness']
    eb['delta_pp_vs_harness'] = (eb['fresh_total']-hb['fresh_total'])*100.0
    out['base'] = eb
    ed, md, rd = enrich('dailyref', res_dref, save=False)
    ed['bootstrap'] = bootstrap_daily(rd, md['base_equity'])
    hd = out[DAILYREF_ID+':harness']
    ed['delta_pp_vs_harness'] = (ed['fresh_total']-hd['fresh_total'])*100.0
    out['dailyref'] = ed
    out['spread_champ_vs_base'] = spread_bootstrap(r, m['base_equity'], rb, mb['base_equity'])
    out['spread_champ_vs_dailyref'] = spread_bootstrap(r, m['base_equity'], rd, md['base_equity'])
    out['spread_h09_vs_dailyref'] = spread_bootstrap(r9, m9['base_equity'], rd, md['base_equity'])
    out['excess_harness_champ_base_pp'] = (h['fresh_total']-hb['fresh_total'])*100.0
    out['excess_mine_champ_base_pp'] = (e['fresh_total']-eb['fresh_total'])*100.0
    out['excess_harness_champ_dref_pp'] = (h['fresh_total']-hd['fresh_total'])*100.0
    out['excess_mine_champ_dref_pp'] = (e['fresh_total']-ed['fresh_total'])*100.0
    # 攻击项 (H03 主体; 基线对照)
    for label, kw, is_h in (('champ', H03_KW, True), ('base', BASE_KW, False)):
        k2 = dict(kw); k2['cost_one_way' if not is_h else 'cost_one_way'] = 0.008
        # 小时引擎 cost_one_way 扁平费; 日线引擎同
        rr = run_hourly(inp, bars, **k2) if is_h else pc.run_strategy(inp, **k2)
        ee, mm, _ = enrich(label+':cost08', rr, save=False)
        out[label+':cost08'] = {k: ee[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades','cost_total','cost_pct_cap')}
    for label, kw, is_h in (('champ', H03_KW, True), ('base', BASE_KW, False)):
        ph = {}
        for p in (-10, -5, 0, 5, 10):
            k2 = dict(kw); k2['phase'] = p
            rr = run_hourly(inp, bars, **k2) if is_h else pc.run_strategy(inp, **k2)
            ee, mm, _ = enrich(f'{label}:ph{p}', rr, save=False)
            ph[str(p)] = {k: ee[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades','wm','wm_n')}
        out[label+':phase'] = ph
    # OOS2025: 连续跑已含暖机, 直接切片 (与 prior_check.oos_2025 同口径)
    def oos_eq(res, cap):
        eq = res.eq
        seg = eq.loc['2025-01-01':'2025-12-31']
        b = eq.loc[:'2024-12-31']
        base = float(b.iloc[-1]) if len(b) else cap
        total = float(seg.iloc[-1]/base-1); mdd = float((seg/seg.cummax()-1).min())
        return dict(total=total, mdd=mdd)
    out['champ:oos2025'] = oos_eq(res_h03, CAP) | dict(note='连续跑切片, 2025段')
    kbc = dict(BASE_KW); kbc['run_start'] = '2024-01-01'
    out['base:oos2025'] = oos_eq(pc.run_strategy(inp, **kbc), CAP)
    kdc = dict(DREF_KW); kdc['run_start'] = '2024-01-01'
    out['dailyref:oos2025'] = oos_eq(pc.run_strategy(inp, **kdc), CAP)
    # exTop3 / lag1
    for label, kw, is_h in (('champ', H03_KW, True), ('base', BASE_KW, False)):
        top3 = out[label]['top3_codes']
        k2 = dict(kw); k2['exclude'] = tuple(kw['exclude']) + tuple(top3)
        rr = run_hourly(inp, bars, **k2) if is_h else pc.run_strategy(inp, **k2)
        ee, mm, _ = enrich(label+':exTop3', rr, save=False)
        base_tot = out[label]['fresh_total']
        out[label+':exTop3'] = {k: ee[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades')} | \
            {'retention': (ee['fresh_total']/base_tot if base_tot else float('nan')), 'excluded': top3}
    for label, kw, is_h in (('champ', H03_KW, True), ('base', BASE_KW, False)):
        k2 = dict(kw); k2['sig_lag'] = 1
        rr = run_hourly(inp, bars, **k2) if is_h else pc.run_strategy(inp, **k2)
        ee, mm, _ = enrich(label+':lag1', rr, save=False)
        out[label+':lag1'] = {k: ee[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades')}
    op = os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, 'w') as f:
        json.dump(out, f, indent=1, default=str)
    for label, sid in (('champ', CHAMP_ID), ('h09', H09_ID), ('base', BASE_ID), ('dailyref', DAILYREF_ID)):
        e = out[label]; hh = out[sid+':harness']
        print(f"[{label}] mine {e['fresh_total']*100:.4f}% harness {hh['fresh_total']*100:.4f}% delta={e['delta_pp_vs_harness']:+.4f}pp n={e['n_trades']}/{hh['fresh_n_trades']}")
    print('align champ:', out['champ']['align'])
    print('align h09:', out['h09']['align'])
    print('excess champ-base harness/mine:', round(out['excess_harness_champ_base_pp'],3), round(out['excess_mine_champ_base_pp'],3))
    print('excess champ-dref harness/mine:', round(out['excess_harness_champ_dref_pp'],3), round(out['excess_mine_champ_dref_pp'],3))
    for k in ('spread_champ_vs_base','spread_champ_vs_dailyref','spread_h09_vs_dailyref'):
        print(k, {kk:(f"{vv*100:.2f}%" if isinstance(vv,float) else vv) for kk,vv in out[k].items()})
    print('wrote', op)

if __name__ == '__main__':
    main()
