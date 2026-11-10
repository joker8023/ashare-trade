#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""batch_025 2024窗口审计: U4/U5/U6 + Y1基准 (warmup 2022-01-01).
独立主线: 审计员自写引擎 (stop=None, warmup 2022-01-01).
U4 exempt / U6 staged 不支持→用同参plain版本重算并以harness差值定量机制效应.
用法: .venv/bin/python team/audit/batch_025/audit_2025.py [--out team/audit/out/batch_025_audit.json]
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
EVAL_S, EVAL_E, BASE_D = pd.Timestamp('2024-01-01'), pd.Timestamp('2024-12-31'), pd.Timestamp('2023-12-31')
CFG = {'Y1': dict(n=4, rebal=30, take=0.45, exposure=0.9, label='b024_Y1_R30_base_2024'),
       'U4': dict(n=2, rebal=7, take=0.45, exposure=0.9, label='b025_U4_N2_exempt_2024'),
       'U5': dict(n=3, rebal=7, take=0.45, exposure=0.9, label='b025_U5_N3_base_2024'),
       'U6': dict(n=2, rebal=7, take=0.45, exposure=0.9, label='b025_U6_N2_staged_2024')}

def run_one(n, rebal, take, exposure, phase=0, cost_one_way=None):
    kw = dict(factor='amihud_60', n=n, rebal=rebal, take=take, exposure=exposure,
              capital=CAP, lot=100, slip=0.002, run_start='2022-01-01',
              phase=phase, legacy_grid=False, stop_exec='next',
              exclude=MB, cost_one_way=cost_one_way)
    kw['stop'] = None
    return pc.run_strategy(pc.get_inputs(), **kw)

def enrich(label, res, save=True):
    m = pc.metrics(res, eval_start=EVAL_S, eval_end=EVAL_E, base_date=BASE_D)
    tr = res.trades
    ev = tr[(tr.exit_date >= EVAL_S) & (tr.exit_date <= EVAL_E)] if len(tr) else tr
    pnl = ev.groupby('code')['net_pnl'].sum().sort_values(ascending=False) if len(ev) else pd.Series(dtype=float)
    tot = float(pnl.sum()) if len(pnl) else 0.0
    w = res.exposure.loc[EVAL_S:EVAL_E]
    _mm = res.eq.loc[EVAL_S:EVAL_E].resample('ME').last().pct_change().dropna()
    _wm = f"{int((_mm>0).sum())}/{int(len(_mm))}"
    _monthly = {str(k.date()): round(float(v),6) for k,v in _mm.items()}
    reasons = ev['reason'].value_counts().to_dict() if len(ev) and 'reason' in ev.columns else {}
    out = dict(label=label, total=m['total_2026'], mdd=m['mdd_2026'],
        wp=m['win_period'], n_periods=m['n_periods'], wt=m['win_trade'], n_trades=m['n_trades'],
        trade_win_n=m['trade_win_n'], wm=(float((_mm>0).mean()) if len(_mm) else float('nan')), wm_n=_wm, monthly=_monthly,
        top1_share=float(pnl.iloc[0]/tot) if len(pnl) and tot else float('nan'),
        top3_share=float(pnl.head(3).sum()/tot) if len(pnl) and tot else float('nan'),
        top3_codes=list(pnl.index[:3]), n_codes=int(len(pnl)),
        cost_total=float(res.meta.get('total_cost',0.0)),
        skipped_lot=int(res.meta.get('skipped_lot',0)),
        stale_buys=int(res.meta.get('stale_buys',0)), stale_sells=int(res.meta.get('stale_sells',0)),
        n_rebalances=int(res.meta.get('n_rebalances',0)),
        reasons={str(k): int(v) for k,v in reasons.items()},
        end_equity=m['end_equity'], base_equity=m['base_equity'])
    kk = int(round(m['win_period']*m['n_periods'])) if m['n_periods'] else 0
    z = 1.96
    def _w(k_, n_):
        if n_ == 0: return [float('nan'), float('nan')]
        p = k_/n_; d = 1+z*z/n_; c_ = (p+z*z/(2*n_))/d
        hh = z*((p*(1-p)/n_+z*z/(4*n_*n_))**0.5)/d
        return [c_-hh, c_+hh]
    out['wilson_wp'] = list(_w(kk, m['n_periods']))
    out['wilson_wt'] = list(_w(m['trade_win_n'], m['n_trades']))
    try:
        ab = _wm.split('/')
        out['wilson_wm'] = list(_w(int(ab[0]), int(ab[1])))
    except Exception:
        out['wilson_wm'] = [float('nan'), float('nan')]
    if save:
        res.trades.to_csv(os.path.join(ROOT, 'team', 'audit', 'out', f'b025_{label.lower()}_trades.csv'), index=False)
        res.eq.to_csv(os.path.join(ROOT, 'team', 'audit', 'out', f'b025_{label.lower()}_equity.csv'))
    return out, m, res

def spread(res_c, base_c, res_b, base_b, n_iter=5000, seed=11):
    rng = np.random.default_rng(seed)
    wc = res_c.eq.loc[EVAL_S:EVAL_E]
    wb = res_b.eq.loc[EVAL_S:EVAL_E]
    dc = wc.pct_change(); dc.iloc[0] = wc.iloc[0]/base_c - 1.0
    db = wb.pct_change(); db.iloc[0] = wb.iloc[0]/base_b - 1.0
    idx = dc.index.intersection(wb.index)
    sp = (dc.loc[idx] - db.loc[idx]).dropna().to_numpy(dtype=float)
    sims = np.empty(n_iter)
    for i in range(n_iter):
        sims[i] = float(np.prod(1.0 + rng.choice(sp, size=len(sp), replace=True)) - 1.0)
    return dict(p5=float(np.quantile(sims,.05)), p50=float(np.quantile(sims,.5)),
                p95=float(np.quantile(sims,.95)), p_excess_pos=float((sims>0).mean()),
                mean=float(sims.mean()), n_iter=n_iter, seed=seed, n_days=int(len(sp)))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default='team/audit/out/batch_025_audit.json')
    a = ap.parse_args()
    df = pd.read_csv(os.path.join(ROOT, 'team', 'runs', 'batch_025_results.csv'))
    Y1ID = 'b024_Y1_R30_base_2024'
    out = {}
    res = {}
    for label, cfg in CFG.items():
        kw = dict(cfg); kw.pop('label', None)
        r = run_one(**kw)
        e, m, rr = enrich(label, r)
        e['bootstrap'] = None
        sid = CFG[label].get('label') or label
        # harness row
        import glob
        hid = {'Y1': Y1ID, 'U4': 'b025_U4_N2_exempt_2024', 'U5': 'b025_U5_N3_base_2024', 'U6': 'b025_U6_N2_staged_2024'}[label]
        _df = df if not label.startswith('Y1') else pd.read_csv(os.path.join(ROOT, 'team', 'runs', 'batch_024_results.csv'))
        h = _df[_df['id']==hid].iloc[0]
        out[label] = e
        out[label+':harness'] = dict(total=float(h['total_2024']), mdd=float(h['mdd_2024']),
            wp=float(h['win_period_2024']), wt=float(h['win_trade_2024']), ntr=float(h['n_trades_2024']),
            wm=str(h['win_month_2024']), top3=float(h['top3_pnl_share']))
        if label not in ('Y1',):
            out[label+':delta_pp'] = (float(e['total'])-float(h['total_2024']))*100.0
        else:
            out[label+':delta_pp'] = (float(e['total'])-float(h['total_2024']))*100.0
        res[label] = (e, m, rr)
    for k in ('U4','U5','U6'):
        out[f'spread:{k}_vs_Y1'] = spread(res[k][2], res[k][1]['base_equity'], res['Y1'][2], res['Y1'][1]['base_equity'])
    for k in ('Y1','U4','U5','U6'):
        ph = {}
        for p in (0, 1, 2, 3):
            rr = run_one(CFG[k]['n'], CFG[k]['rebal'], CFG[k]['take'], CFG[k]['exposure'], phase=p)
            mm = pc.metrics(rr, eval_start=EVAL_S, eval_end=EVAL_E, base_date=BASE_D)
            ph[str(p)] = dict(total_2024=mm['total_2026'], mdd_2024=mm['mdd_2026'])
        out[f'phase:{k}'] = ph
    # U4 exempt effect (mine plain-N2 vs harness exempt-N2) + cost decomposition
    out['exempt_effect'] = dict(mine_plain_U4=float(out['U4']['total']),
        harness_exempt=float(out['U4:harness']['total']))
    op = os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, 'w') as f:
        json.dump(out, f, indent=1, default=float)
    for k in ('Y1','U4','U5','U6'):
        print(f"[{k}] mine {out[k]['total']*100:.2f}% harness {out[k+':harness']['total_2024']*100:.2f}% delta={out[k+':delta_pp']:+.2f}pp mdd {out[k]['mdd']*100:.1f} n={out[k]['n_trades']}")
    for k in ('U4','U5','U6'):
        print('spread '+k, {kk:(round(vv,2) if isinstance(vv,float) else vv) for kk,vv in out[f'spread:{k}_vs_Y1'].items()})
    for k in ('Y1','U4','U5','U6'):
        print('phase '+k, {p:(round(v['total_2024']*100,2), round(v['mdd_2024']*100,2)) for p,v in out['phase:'+k].items()})
    print('wrote', op)

if __name__ == '__main__':
    main()
