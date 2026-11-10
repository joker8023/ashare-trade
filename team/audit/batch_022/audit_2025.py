#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""batch_022 2025窗口审计: T1/T2/C3 + C2(高收益验证) + W1基准.
完全独立复算 (prior_check 审计员自写引擎, 未调用 harness):
  warmup 2024-01-01 连续跑 + pc.metrics(eval 2025-01-01~2025-12-31, base 2024-12-31).
用法: .venv/bin/python team/audit/batch_022/audit_2025.py [--out team/audit/out/batch_022_audit.json]
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
EVAL_S, EVAL_E, BASE_D = pd.Timestamp('2025-01-01'), pd.Timestamp('2025-12-31'), pd.Timestamp('2024-12-31')

def wilson(k, n, z=1.96):
    if n == 0: return (float('nan'), float('nan'))
    p = k / n; d = 1 + z*z/n; c = (p + z*z/(2*n))/d
    h = z*((p*(1-p)/n + z*z/(4*n*n))**0.5)/d
    return (c-h, c+h)

def enrich_2025(label, res, save=True):
    m = pc.metrics(res, eval_start=EVAL_S, eval_end=EVAL_E, base_date=BASE_D)
    tr = res.trades
    ev = tr[(tr.exit_date >= EVAL_S) & (tr.exit_date <= EVAL_E)] if len(tr) else tr
    pnl = ev.groupby('code')['net_pnl'].sum().sort_values(ascending=False) if len(ev) else pd.Series(dtype=float)
    tot = float(pnl.sum()) if len(pnl) else 0.0
    w = res.exposure.loc[EVAL_S:EVAL_E]
    reasons = ev['reason'].value_counts().to_dict() if len(ev) and 'reason' in ev.columns else {}
    out = dict(label=label, total=m['total_2026'], mdd=m['mdd_2026'],
        wp=m['win_period'], n_periods=m['n_periods'], period_rets=m['period_rets'],
        wm=m['win_month'], wm_n=m['win_month_n'], monthly=m['monthly_rets'],
        wt=m['win_trade'], n_trades=m['n_trades'], trade_win_n=m['trade_win_n'],
        top1_share=float(pnl.iloc[0]/tot) if len(pnl) and tot else float('nan'),
        top3_share=float(pnl.head(3).sum()/tot) if len(pnl) and tot else float('nan'),
        top3_codes=list(pnl.index[:3]), n_codes=int(len(pnl)),
        cost_total=float(res.meta.get('total_cost',0.0)),
        skipped_lot=int(res.meta.get('skipped_lot',0)),
        stale_buys=int(res.meta.get('stale_buys',0)), stale_sells=int(res.meta.get('stale_sells',0)),
        n_rebalances=int(res.meta.get('n_rebalances',0)),
        reasons={str(k): int(v) for k,v in reasons.items()},
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
        res.trades.to_csv(os.path.join(ROOT, 'team', 'audit', 'out', f'b022_{tag_or_label(label)}_trades.csv'), index=False)
        res.eq.to_csv(os.path.join(ROOT, 'team', 'audit', 'out', f'b022_{tag_or_label(label)}_equity.csv'))
    return out, m, res

def tag_or_label(label):
    return {'W1':'w1','T1':'t1','T2':'t2','C3':'c3','C2':'c2','C1':'c1'}.get(label, label)

def bootstrap_daily(res, base, n_iter=1000, seed=7):
    rng = np.random.default_rng(seed)
    win = res.eq.loc[EVAL_S:EVAL_E]
    dret = win.pct_change(); dret.iloc[0] = win.iloc[0]/base - 1.0
    r = dret.to_numpy(dtype=float)
    sims = np.empty(n_iter)
    for i in range(n_iter):
        sims[i] = float(np.prod(1.0+rng.choice(r, size=len(r), replace=True))-1.0)
    return dict(p5=float(np.quantile(sims,0.05)), p50=float(np.quantile(sims,0.5)),
                p_neg=float((sims<0).mean()), mean=float(sims.mean()), n_iter=n_iter, seed=seed)

def spread_bootstrap(res_c, base_c, res_b, base_b, n_iter=5000, seed=11):
    rng = np.random.default_rng(seed)
    wc = res_c.eq.loc[EVAL_S:EVAL_E]
    wb = res_b.eq.loc[EVAL_S:EVAL_E]
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

KW = dict(factor='amihud_60', exclude=MB)  # size_range/min_adv 用引擎默认(与spec一致: 5-30%/5e6)
Cfgs = {
    'W1':  dict(n=4, rebal=30, take=0.45, exposure=0.9),
    'T1':  dict(n=4, rebal=7, take=0.70, exposure=1.0),
    'T2':  dict(n=4, rebal=7, take=0.90, exposure=1.0),
    'C3':  dict(n=6, rebal=7, take=0.45, exposure=0.9),
    'C2':  dict(n=2, rebal=7, take=0.45, exposure=0.9),
    'C1':  dict(n=1, rebal=7, take=0.45, exposure=0.9),
}

def run_one(n, rebal, take, exposure, phase=0, cost_one_way=None, sig_lag=0):
    kw = dict(KW, n=n, rebal=rebal, take=take, exposure=exposure,
              capital=CAP, lot=100, slip=0.002, run_start='2024-01-01',
              phase=phase, legacy_grid=False, stop_exec='next',
              cost_one_way=cost_one_way, sig_lag=sig_lag, stop=None)  # spec无止损: 必须显式关闭引擎默认0.12跟踪止损
    return pc.run_strategy(pc.get_inputs(), **kw)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default='team/audit/out/batch_022_audit.json')
    a = ap.parse_args()
    inp = pc.get_inputs()
    out = {}
    df = pd.read_csv(os.path.join(ROOT, 'team', 'runs', 'batch_022_results.csv'))
    idmap = {'W1':'b020_W1_R30_base_2025','T1':'b022_T1_TP70','T2':'b022_T2_TP90',
             'C3':'b022_C3_trueN6','C2':'b022_C2_trueN2','C1':'b022_C1_trueN1'}
    df20 = pd.read_csv(os.path.join(ROOT, 'team', 'runs', 'batch_020_results.csv'))
    res = {}
    for label, cfg in Cfgs.items():
        r = run_one(**cfg)
        e, m, rr = enrich_2025(label, r)
        e['bootstrap'] = bootstrap_daily(rr, m['base_equity'])
        out[label] = e
        res[label] = (e, m, rr)
        sid = idmap[label]
        _df = df if not sid.startswith('b020') else df20
        h = _df[_df['id']==sid].iloc[0]
        out[label+':harness'] = dict(total_2025=float(h['total_2025']), mdd_2025=float(h['mdd_2025']),
            wt_2025=float(h['win_trade_2025']), ntr_2025=float(h['n_trades_2025']))
        out[label+':delta_pp'] = (e['total']-float(h['total_2025']))*100.0
        out[label+':delta_mdd_pp'] = (e['mdd']-float(h['mdd_2025']))*100.0
    # spread vs W1
    _ew1, _mw1, _rw1 = res['W1']
    for label in ('T1','C3','C2'):
        e, m, r = res[label]
        out[f'spread:{label}_vs_W1'] = spread_bootstrap(r, m['base_equity'], _rw1, _mw1['base_equity'])
    # phase 0-3 for T1, C3, W1
    for label in ('T1','C3','W1'):
        cfg = Cfgs[label]
        ph = {}
        for p in (0, 1, 2, 3):
            rr = run_one(cfg['n'], cfg['rebal'], cfg['take'], cfg['exposure'], phase=p)
            mm = pc.metrics(rr, eval_start=EVAL_S, eval_end=EVAL_E, base_date=pd.Timestamp('2024-12-31'))
            ph[str(p)] = dict(total_2025=mm['total_2026'], mdd_2025=mm['mdd_2026'])
        out[f'phase:{label}'] = ph
    # T1 vs T2 identity (my engine)
    out['T1_T2_identity_mine'] = bool(abs(out['T1']['total']-out['T2']['total'])<1e-9)
    # C2 engine-anomaly guard: concentration + monthly
    e2 = out['C2']
    out['C2:guard'] = dict(n_trades=e2['n_trades'], wt=e2['wt'], top1=e2['top1_share'],
        top3=e2['top3_share'], monthly=e2['monthly'], cost_total=e2['cost_total'])
    op = os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, 'w') as f:
        json.dump(out, f, indent=1, default=float)
    for label in Cfgs:
        print(f"[{label}] mine {out[label]['total']*100:.2f}% harness {out[label+':harness']['total_2025']*100:.2f}% delta={out[label+':delta_pp']:+.3f}pp mdd {out[label]['mdd']*100:.2f}")
    for k in sorted(out):
        if k.startswith('spread'):
            print(k, {kk:(f"{vv*100:.2f}%" if isinstance(vv,float) else vv) for kk,vv in out[k].items()})
    for k in sorted(out):
        if k.startswith('phase'):
            print(k, {p:(f"{v['total_2025']*100:.2f}%" if isinstance(v['total_2025'],float) else v) for p,v in out[k].items()})
    print('C2 guard:', out['C2:guard'])
    print('wrote', op)

if __name__ == '__main__':
    main()
