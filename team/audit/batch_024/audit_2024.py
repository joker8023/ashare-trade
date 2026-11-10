#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""batch_024 2024窗口审计: Y1/Y2/Y3/Y4 + 相信度 + phase健壺性 + 豁免机制.
独立主线: 审计员自写引擎 (run_start 2024-01-01, eval 2024, base 2023-12-31, stop=None).
辅助验证: harness.run_spec 原样重跑 (022 同一特批模式延续; 仅用于数字复现检查与相位表).
用法: .venv/bin/python team/audit/batch_024/audit_2024.py [--out team/audit/out/batch_024_audit.json]
"""
from __future__ import annotations
import argparse, copy, json, os, sys
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import prior_check as pc
ROOT = pc.ROOT
MB = ('688', '689', '300', '301', '8', '4')
CAP = 50000.0
EVAL_S, EVAL_E, BASE_D = pd.Timestamp('2024-01-01'), pd.Timestamp('2024-12-31'), pd.Timestamp('2023-12-31')
IDS = {'Y1': 'b024_Y1_R30_base_2024', 'Y2': 'b024_Y2_R7_base_2024',
       'Y3': 'b024_Y3_R7_exempt_2024', 'Y4': 'b024_Y4_R7_N2_2024'}
CFG = {'Y1': dict(n=4, rebal=30, take=0.45, exposure=0.9),
       'Y2': dict(n=4, rebal=7, take=0.45, exposure=0.9),
       'Y3': dict(n=4, rebal=7, take=0.45, exposure=0.9),
       'Y4': dict(n=2, rebal=7, take=0.45, exposure=0.9)}

def run_one(n, rebal, take, exposure, phase=0, cost_one_way=None):
    kw = dict(factor='amihud_60', n=n, rebal=rebal, take=take, exposure=exposure,
              capital=CAP, lot=100, slip=0.002, run_start='2022-01-01',  # batch_024 warmup=2022-01-01(勿用2024)
              phase=phase, legacy_grid=False, stop_exec='next',
              exclude=MB, cost_one_way=cost_one_way)
    kw['stop'] = None  # spec无止损, 关闭引擎默认跟踪止损
    return pc.run_strategy(pc.get_inputs(), **kw)

def enrich(label, res, save=True):
    m = pc.metrics(res, eval_start=EVAL_S, eval_end=EVAL_E, base_date=BASE_D)
    tr = res.trades
    ev = tr[(tr.exit_date >= EVAL_S) & (tr.exit_date <= EVAL_E)] if len(tr) else tr
    pnl = ev.groupby('code')['net_pnl'].sum().sort_values(ascending=False) if len(ev) else pd.Series(dtype=float)
    tot = float(pnl.sum()) if len(pnl) else 0.0
    w = res.exposure.loc[EVAL_S:EVAL_E]
    _meq = res.eq.loc[EVAL_S:EVAL_E]
    _mret = _meq.resample('ME').last().pct_change().dropna()
    _wm_n = '%d/%d' % (int((_mret > 0).sum()), int(len(_mret)))
    _wm = float((_mret > 0).mean()) if len(_mret) else float('nan')
    _monthly = dict([(str(k.date()), round(float(v), 6)) for k, v in _mret.items()])
    out = dict(label=label, total=m['total_2026'], mdd=m['mdd_2026'],
        wp=m['win_period'], n_periods=m['n_periods'], wt=m['win_trade'], n_trades=m['n_trades'],
        trade_win_n=m['trade_win_n'], wm=_wm, wm_n=_wm_n, monthly=_monthly,
        top1_share=float(pnl.iloc[0]/tot) if len(pnl) and tot else float('nan'),
        top3_share=float(pnl.head(3).sum()/tot) if len(pnl) and tot else float('nan'),
        top3_codes=list(pnl.index[:3]), n_codes=int(len(pnl)),
        cost_total=float(res.meta.get('total_cost',0.0)),
        skipped_lot=int(res.meta.get('skipped_lot',0)),
        stale_buys=int(res.meta.get('stale_buys',0)), stale_sells=int(res.meta.get('stale_sells',0)),
        n_rebalances=int(res.meta.get('n_rebalances',0)),
        reasons={str(k): int(v) for k,v in (ev['reason'].value_counts().to_dict() if len(ev) and 'reason' in ev.columns else {}).items()},
        end_equity=m['end_equity'], base_equity=m['base_equity'])
    kk = int(round(m['win_period']*m['n_periods'])) if m['n_periods'] else 0
    z = 1.96
    def _w(k_, n_):
        if n_ == 0: return [float('nan'), float('nan')]
        p = k_/n_; d = 1+z*z/n_; c_ = (p+z*z/(2*n_))/d
        hh = z*((p*(1-p)/n_+z*z/(4*n_*n_))**0.5)/d
        return [c_-hh, c_+hh]
    out['wilson_wp'] = _w(kk, m['n_periods'])
    out['wilson_wt'] = _w(m['trade_win_n'], m['n_trades'])
    try:
        ab = _wm_n.split('/')
        out['wilson_wm'] = _w(int(ab[0]), int(ab[1]))
    except Exception:
        out['wilson_wm'] = [float('nan'), float('nan')]
    if save:
        res.trades.to_csv(os.path.join(ROOT, 'team', 'audit', 'out', f'b024_{label.lower()}_trades.csv'), index=False)
        res.eq.to_csv(os.path.join(ROOT, 'team', 'audit', 'out', f'b024_{label.lower()}_equity.csv'))
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
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default='team/audit/out/batch_024_audit.json')
    a = ap.parse_args()
    inp = pc.get_inputs()
    out = {'ids': IDS}
    df = pd.read_csv(os.path.join(ROOT, 'team', 'runs', 'batch_024_results.csv'))
    res = {}
    for label, cfg in CFG.items():
        r = run_one(**cfg)
        e, m, rr = enrich(label, r, save=(label in ('Y1','Y2','Y4')))
        e['bootstrap'] = None
        out[label] = e
        out[label+':mine'] = dict(total=float(e['total']), mdd=float(e['mdd']))
        h = df[df['id'] == IDS[label]].iloc[0]
        out[label+':harness'] = dict(total_2024=float(h['total_2024']), mdd_2024=float(h['mdd_2024']),
            wp=float(h['win_period_2024']), wt=float(h['win_trade_2024']), ntr=float(h['n_trades_2024']),
            wm=str(h['win_month_2024']), top3=float(h['top3_pnl_share']), cost=float(h['cost_paid_pct']),
            n_hold_avg=float(h['n_hold_avg']), n_distinct=float(h['n_distinct_names']),
            turnover=float(h['turnover']), exposure=float(h['exposure']))
        out[label+':delta_pp'] = (float(e['total'])-float(h['total_2024']))*100.0
        out[label+':delta_mdd_pp'] = (float(e['mdd'])-float(h['mdd_2024']))*100.0
        res[label] = (e, m, rr)
    for k in ('Y2','Y3','Y4'):
        out[f'spread:{k}_vs_Y1'] = spread(res[k][2], res[k][1]['base_equity'], res['Y1'][2], res['Y1'][1]['base_equity'])
    for k in ('Y1','Y2','Y4'):
        ph = {}
        for p in (0, 1, 2, 3):
            rr = run_one(CFG[k]['n'], CFG[k]['rebal'], CFG[k]['take'], CFG[k]['exposure'], phase=p)
            mm = pc.metrics(rr, eval_start=EVAL_S, eval_end=EVAL_E, base_date=BASE_D)
            ph[str(p)] = dict(total_2024=mm['total_2026'], mdd_2024=mm['mdd_2026'])
        out[f'phase:{k}'] = ph
    op = os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, 'w') as f:
        json.dump(out, f, indent=1, default=float)
    for k in ('Y1','Y2','Y3','Y4'):
        print(f"[{k}] mine {out[k]['total']*100:.2f}% harness {out[k+':harness']['total_2024']*100:.2f}% delta={out[k+':delta_pp']:+.2f}pp mdd {out[k]['mdd']*100:.1f}/{out[k+':harness']['total_2024']*100:.1f}")
    for k in ('Y2','Y3','Y4'):
        print('spread '+k, {kk:(round(v,3) if isinstance(v,float) else v) for kk,v in out[f'spread:{k}_vs_Y1'].items()})
    for k in ('Y1','Y2','Y4'):
        print('phase '+k, {p:(round(v['total_2024']*100,2), round(v['mdd_2024']*100,2)) for p,v in out[f'phase:{k}'].items()})
    print('wrote', op)

if __name__ == '__main__':
    main()
