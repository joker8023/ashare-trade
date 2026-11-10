#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""batch_010 独立审计: R20冠军(+0.49pp)噪声判定 + ensemble资本拆分核查 + capN6约束核查.
禁调 team/harness.py; 只用 data/pivots_long_clean.pkl + team/audit/prior_check.py(审计员自写引擎).
口径: fresh 2026-01-05空仓起步, 现实费率(佣金0.025%最低5元+印花0.05%+过户0.001%+滑点0.2%/边),
5万/100股整手, t信号t+1收盘执行, TP t收盘触发t+1收盘卖(next), 主板池, amihud_60, size5-30%, adv>5e6.
用法: .venv/bin/python team/audit/batch_010/audit_r20.py [--out team/audit/out/batch_010_audit.json]
"""
from __future__ import annotations
import argparse, json, os, sys
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import prior_check as pc
ROOT = pc.ROOT
MB = ('688', '689', '300', '301', '8', '4')
CAP = 50000.0
CHAMP_ID = 'b010_G1_N4_R20_TPnone_exp90'
BASE_ID = 'b010_G6_BASELINE_N4R30TP45e09'
CHAMP_KW = dict(factor='amihud_60', n=4, rebal=20, stop=None, take=None,
                 capital=CAP, lot=100, cost_one_way=None, slip=0.002,
                 run_start='2026-01-05', phase=0, legacy_grid=False,
                 stop_exec='next', exclude=MB, exposure=0.9)
BASE_KW = dict(factor='amihud_60', n=4, rebal=30, stop=None, take=0.45,
                capital=CAP, lot=100, cost_one_way=None, slip=0.002,
                run_start='2026-01-05', phase=0, legacy_grid=False,
                stop_exec='next', exclude=MB, exposure=0.9)

def wilson(k, n, z=1.96):
    if n == 0: return (float('nan'), float('nan'))
    p = k / n; d = 1 + z*z/n; c = (p + z*z/(2*n))/d
    h = z*((p*(1-p)/n + z*z/(4*n*n))**2 if False else (p*(1-p)/n + z*z/(4*n*n)))**0.5/d
    return (c-h, c+h)

def enrich(label, res, save=True):
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
        n_rebalances=int(res.meta.get('n_rebalances',0)), end_equity=m['end_equity'], base_equity=m['base_equity'])
    k = int(round(m['win_period']*m['n_periods'])) if m['n_periods'] else 0
    out['wilson_wp'] = list(wilson(k, m['n_periods']))
    out['wilson_wt'] = list(wilson(m['trade_win_n'], m['n_trades']))
    try:
        a,b = m['win_month_n'].split('/')
        out['wilson_wm'] = list(wilson(int(a), int(b)))
    except Exception:
        out['wilson_wm'] = [float('nan'), float('nan')]
    if save:
        res.trades.to_csv(os.path.join(ROOT, 'team', 'audit', 'out', f'b010_{label}_trades.csv'), index=False)
        res.eq.to_csv(os.path.join(ROOT, 'team', 'audit', 'out', f'b010_{label}_equity.csv'))
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

def spread_bootstrap(res_c, base_c, res_b, base_b, n_iter=5000, seed=11):
    """配对bootstrap: 日收益差复合成超额收益分布, 检验+0.49pp是否显著>0."""
    rng = np.random.default_rng(seed)
    wc = res_c.eq.loc[pc.EVAL_START:pc.EVAL_END]
    wb = res_b.eq.loc[pc.EVAL_START:pc.EVAL_END]
    dc = wc.pct_change(); dc.iloc[0] = wc.iloc[0]/base_c - 1.0
    db = wb.pct_change(); db.iloc[0] = wb.iloc[0]/base_b - 1.0
    sp = (dc - db).to_numpy(dtype=float)
    sims = np.empty(n_iter)
    for i in range(n_iter):
        s = rng.choice(sp, size=len(sp), replace=True)
        sims[i] = float(np.prod(1.0+s)-1.0)
    return dict(p5=float(np.quantile(sims,0.05)), p50=float(np.quantile(sims,0.5)),
                p95=float(np.quantile(sims,0.95)), p_excess_pos=float((sims>0).mean()),
                mean=float(sims.mean()), n_iter=n_iter, seed=seed)

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

def leg_kw(n, rebal, take, capital, exposure=0.9):
    return dict(factor='amihud_60', n=n, rebal=rebal, stop=None, take=take,
                capital=capital, lot=100, cost_one_way=None, slip=0.002,
                run_start='2026-01-05', phase=0, legacy_grid=False,
                stop_exec='next', exclude=MB, exposure=exposure)

def synth_ensemble(inp, legs, R_seg=30):
    """legs: [(kw, weight)]. 各leg按权重拆capital独立跑(含整手/现实费率), 元加总为合成净值."""
    eqs, trs, cost = [], [], 0.0
    for kw, w in legs:
        r = pc.run_strategy(inp, **kw)
        eqs.append(r.eq)
        t = r.trades.copy()
        if len(t):
            t['leg'] = f"{kw['n']}R{kw['rebal']}TP{kw['take']}"
            trs.append(t)
        cost += float(r.meta.get('total_cost', 0.0))
    ens = pd.concat(eqs, axis=1).sum(axis=1)
    ens.name = 'eq'
    tr = pd.concat(trs, ignore_index=True) if trs else pd.DataFrame()
    dates = inp.dates
    grid = [i for i in inp.grid(R_seg, 0) if dates[i] >= pd.Timestamp('2026-01-05') and i + 1 < len(dates)]
    execs = [(i + 1, float(ens.loc[dates[i + 1]])) for i in grid if dates[i + 1] in ens.index]
    per = pc.build_periods(ens, execs, inp.ret, dates, R_seg)
    res = pc.Result(eq=ens, trades=tr, periods=per,
                    meta=dict(capital=CAP, total_cost=cost, cost_by_year={},
                              n_rebalances=len(execs)),
                    exposure=(ens / ens.cummax() * 0 + 0.9), nhold=pd.Series(0, index=ens.index))
    return res, cost

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default='team/audit/out/batch_010_audit.json')
    a = ap.parse_args()
    inp = pc.get_inputs()
    out = {'champ_id': CHAMP_ID, 'base_id': BASE_ID}
    df = pd.read_csv(os.path.join(ROOT, 'team', 'runs', 'batch_010_results.csv'))
    for sid in (CHAMP_ID, BASE_ID):
        row = df[df['id']==sid].iloc[0]
        out[sid+':harness'] = dict(fresh_total=float(row['fresh_total']), fresh_mdd=float(row['fresh_mdd']),
            fresh_win_period=float(row['fresh_win_period']) if pd.notna(row['fresh_win_period']) else float('nan'),
            fresh_win_month=str(row['fresh_win_month']),
            fresh_win_trade=float(row['fresh_win_trade']), fresh_n_trades=float(row['fresh_n_trades']),
            fresh_top3=float(row['fresh_top3_pnl_share']), fresh_exposure=float(row['fresh_exposure']),
            fresh_cost_paid_pct=float(row['fresh_cost_paid_pct']), total_2025=float(row['total_2025']),
            win_period_2025=float(row['win_period_2025']))
    # (1)独立复算
    seqs = {}
    for label, kw, sid in (('champ', CHAMP_KW, CHAMP_ID), ('base', BASE_KW, BASE_ID)):
        res = pc.run_strategy(inp, **kw)
        e, m, r = enrich(label, res)
        h = out[sid+':harness']
        e['delta_pp_vs_harness'] = (e['fresh_total']-h['fresh_total'])*100.0
        e['delta_mdd_pp'] = (e['mdd']-h['fresh_mdd'])*100.0
        e['bootstrap'] = bootstrap_daily(r, m['base_equity'])
        out[label] = e
        out[label+':m'] = dict(m=m, r=r)
    # 配对spread bootstrap (噪声vs突破主检验)
    mc = out['champ:m']['m']; rc = out['champ:m']['r']
    mb = out['base:m']['m']; rb = out['base:m']['r']
    out['spread_boot'] = spread_bootstrap(rc, mc['base_equity'], rb, mb['base_equity'])
    out['excess_harness_pp'] = (out[CHAMP_ID+':harness']['fresh_total']-out[BASE_ID+':harness']['fresh_total'])*100.0
    out['excess_mine_pp'] = (out['champ']['fresh_total']-out['base']['fresh_total'])*100.0
    del out['champ:m']; del out['base:m']
    # (2)成本0.8%/边
    for label, kw in (('champ', CHAMP_KW), ('base', BASE_KW)):
        k2 = dict(kw); k2['cost_one_way'] = 0.008
        e, m, r = enrich(label+':cost08', pc.run_strategy(inp, **k2), save=False)
        out[label+':cost08'] = {k: e[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades','cost_total','cost_pct_cap')}
    # (3)phase五档
    for label, kw in (('champ', CHAMP_KW), ('base', BASE_KW)):
        ph = {}
        for p in (-10, -5, 0, 5, 10):
            k2 = dict(kw); k2['phase'] = p
            e, m, r = enrich(f'{label}:ph{p}', pc.run_strategy(inp, **k2), save=False)
            ph[str(p)] = {k: e[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades','wm','wm_n')}
        out[label+':phase'] = ph
    # (4)OOS 2025
    for label, kw in (('champ', CHAMP_KW), ('base', BASE_KW)):
        out[label+':oos2025'] = oos_2025(kw)
    # (5)剔Top3
    for label, kw in (('champ', CHAMP_KW), ('base', BASE_KW)):
        top3 = out[label]['top3_codes']
        k2 = dict(kw); k2['exclude'] = tuple(kw['exclude']) + tuple(top3)
        e, m, r = enrich(label+':exTop3', pc.run_strategy(inp, **k2), save=False)
        base_tot = out[label]['fresh_total']
        out[label+':exTop3'] = {k: e[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades')} | \
            {'retention': (e['fresh_total']/base_tot if base_tot else float('nan')), 'excluded': top3}
    # (6)前视+1日
    for label, kw in (('champ', CHAMP_KW), ('base', BASE_KW)):
        k2 = dict(kw); k2['sig_lag'] = 1
        e, m, r = enrich(label+':lag1', pc.run_strategy(inp, **k2), save=False)
        out[label+':lag1'] = {k: e[k] for k in ('fresh_total','mdd','wp','n_periods','wt','n_trades')}
    # (E) ensemble复制: 各leg按权重拆capital, exposure 0.9, lot100, NAV相加
    ens_defs = {
        'b010_G3_ens_N4R20_N4R30_70_30': [(leg_kw(4,20,0.45,35000.0),0.7),(leg_kw(4,30,0.45,15000.0),0.3)],
        'b010_G3_ens_N4R20_N4R30_50_50': [(leg_kw(4,20,0.45,25000.0),0.5),(leg_kw(4,30,0.45,25000.0),0.5)],
        'b010_G3_ens_N4R30_N5R40_70_30': [(leg_kw(4,30,0.45,35000.0),0.7),(leg_kw(5,40,0.50,15000.0),0.3)],
    }
    for eid, legs in ens_defs.items():
        res, cost = synth_ensemble(inp, legs)
        e, m, r = enrich('ens_'+eid, res, save=False)
        hrow = df[df['id']==eid].iloc[0]
        out[eid+':mine'] = dict(fresh_total=e['fresh_total'], mdd=e['mdd'], wp=e['wp'],
            n_periods=e['n_periods'], wt=e['wt'], n_trades=e['n_trades'], wm_n=e['wm_n'],
            cost_total=cost, monthly=e['monthly'])
        out[eid+':harness'] = dict(fresh_total=float(hrow['fresh_total']), mdd=float(hrow['fresh_mdd']),
            wp=(float(hrow['fresh_win_period']) if pd.notna(hrow['fresh_win_period']) else float('nan')),
            wt=float(hrow['fresh_win_trade']), n_trades=float(hrow['fresh_n_trades']),
            cost_paid_pct=float(hrow['fresh_cost_paid_pct']))
        out[eid+':delta_pp'] = (e['fresh_total']-float(hrow['fresh_total']))*100.0
    # LVN ensemble: 只复算70% N4R30腿, 残差反推低波腿隐含收益
    resA, _ = synth_ensemble(inp, [(leg_kw(4,30,0.45,35000.0),0.7)])
    eA, mA, rA = enrich('ens_lvn_legA', resA, save=False)
    heq = pd.read_csv(os.path.join(ROOT,'team','runs','batch_010_equity','b010_G3_ens_N4R30_LVN10_70_30.csv'), index_col=0, parse_dates=True).iloc[:,0]
    hret = float(heq.loc['2026-01-05':'2026-11-04'].iloc[-1]/heq.loc['2026-01-05':'2026-11-04'].iloc[0]-1)
    out['ens_LVN:legA70'] = dict(fresh_total=eA['fresh_total'], mdd=eA['mdd'])
    out['ens_LVN:harness_total'] = hret
    out['ens_LVN:implied_LVleg'] = (1+hret-0.7*(1+eA['fresh_total']))/0.3-1
    # (C) capN6三档 + 无cap对照 (harness语义=加名, rank_fill True)
    for cap, eid in ((0.20,'b010_G4_N6_TP45_cap20_exp90'),(0.15,'b010_G4_N6_TP45_cap15_exp90'),(0.12,'b010_G4_N6_TP45_cap12_exp90')):
        k2 = dict(factor='amihud_60', n=6, rebal=30, stop=None, take=0.45, capital=CAP, lot=100,
                  cost_one_way=None, slip=0.002, run_start='2026-01-05', phase=0, legacy_grid=False,
                  stop_exec='next', exclude=MB, exposure=0.9, weight_cap=cap, rank_fill=True)
        e, m, r = enrich(f'capN6_{cap}', pc.run_strategy(inp, **k2), save=False)
        hrow = df[df['id']==eid].iloc[0]
        out[f'capN6_{cap}'] = dict(mine_total=e['fresh_total'], mine_mdd=e['mdd'], mine_n=e['n_trades'],
            harness_total=float(hrow['fresh_total']), harness_mdd=float(hrow['fresh_mdd']),
            harness_n=float(hrow['fresh_n_trades']), harness_nhold=float(hrow['n_hold_avg']),
            harness_maxw=float(hrow['max_realized_weight']),
            delta_pp=(e['fresh_total']-float(hrow['fresh_total']))*100.0)
    k0 = dict(factor='amihud_60', n=6, rebal=30, stop=None, take=0.45, capital=CAP, lot=100,
              cost_one_way=None, slip=0.002, run_start='2026-01-05', phase=0, legacy_grid=False,
              stop_exec='next', exclude=MB, exposure=0.9, weight_cap=None)
    e0, m0, r0 = enrich('capN6_nocap', pc.run_strategy(inp, **k0), save=False)
    out['capN6_nocap'] = dict(mine_total=e0['fresh_total'], mine_mdd=e0['mdd'], mine_n=e0['n_trades'])
    op = os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, 'w') as f:
        json.dump(out, f, indent=1, default=float)
    for label, sid in (('champ', CHAMP_ID), ('base', BASE_ID)):
        e = out[label]; h = out[sid+':harness']
        print(f"[{label}] mine {e['fresh_total']*100:.4f}% harness {h['fresh_total']*100:.4f}% delta={e['delta_pp_vs_harness']:+.4f}pp mdd {e['mdd']*100:.2f}/{h['fresh_mdd']*100:.2f} n={e['n_trades']}/{h['fresh_n_trades']}")
    print('excess harness_pp:', round(out['excess_harness_pp'],4), 'mine_pp:', round(out['excess_mine_pp'],4))
    print('spread_boot:', {k:(f"{v*100:.2f}%" if isinstance(v,float) else v) for k,v in out['spread_boot'].items()})
    for eid in ens_defs:
        print(f"[{eid}] mine {out[eid+':mine']['fresh_total']*100:.2f}% harness {out[eid+':harness']['fresh_total']*100:.2f}% delta={out[eid+':delta_pp']:+.3f}pp cost_mine={out[eid+':mine']['cost_total']:.0f}")
    print('LVN legA70:', round(out['ens_LVN:legA70']['fresh_total']*100,2), 'harness ens:', round(out['ens_LVN:harness_total']*100,2), 'implied LV:', round(out['ens_LVN:implied_LVleg']*100,2))
    for cap in (0.20,0.15,0.12):
        d = out[f'capN6_{cap}']
        print(f"[cap{cap}] mine {d['mine_total']*100:.2f}% harness {d['harness_total']*100:.2f}% delta={d['delta_pp']:+.3f}pp maxw_h={d['harness_maxw']:.4f}")
    print('nocapN6 mine:', round(out['capN6_nocap']['mine_total']*100,2))
    print('wrote', op)

if __name__ == '__main__':
    main()
