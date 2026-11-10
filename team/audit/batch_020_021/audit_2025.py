#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""batch_020/021 2025窗口审计: W1/W2/W5 + V1/V2/V3/V6 重跑验证 + 显著性 + phase稳健性.
Lead 明示用 team/harness.run_spec 重跑验证 (本次特批, 仅限 batch_020/021 的 2025 窗口数字复现检查).
用法: .venv/bin/python team/audit/batch_020_021/audit_2025.py [--out team/audit/out/batch_020_021_audit.json]
"""
from __future__ import annotations
import argparse, copy, json, os, sys
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..'))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
import importlib.util
_HH_SPEC = importlib.util.spec_from_file_location(
    'audit_harness_copy', os.path.join(ROOT, 'team', 'harness.py'))
HH = importlib.util.module_from_spec(_HH_SPEC)
_HH_SPEC.loader.exec_module(HH)

IDS_020 = ['b020_W1_R30_base_2025', 'b020_W2_R7_base_2025', 'b020_W5_R7_N2_2025']
IDS_021 = ['b021_V1_TP60', 'b021_V2_TP80', 'b021_V3_staged', 'b021_V6_N6']

def wilson(k, n, z=1.96):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (c - h, c + h)

def spread_bootstrap(eq_c, eq_b, start='2025-01-01', end='2025-12-31', n_iter=5000, seed=11):
    rng = np.random.default_rng(seed)
    wc = eq_c.loc[start:end]
    wb = eq_b.loc[start:end]
    dc = wc.pct_change(); dc.iloc[0] = 0.0
    db = wb.pct_change(); db.iloc[0] = 0.0
    idx = dc.index.intersection(wb.index)
    sp = (dc.loc[idx] - db.loc[idx]).to_numpy(dtype=float)
    sims = np.empty(n_iter)
    for i in range(n_iter):
        sims[i] = float(np.prod(1.0 + rng.choice(sp, size=len(sp), replace=True)) - 1.0)
    return dict(p5=float(np.quantile(sims, 0.05)), p50=float(np.quantile(sims, 0.5)),
                p95=float(np.quantile(sims, 0.95)), p_excess_pos=float((sims > 0).mean()),
                mean=float(sims.mean()), n_iter=n_iter, seed=seed)

def monthly_wins(eq, year=2025):
    seg = eq.loc[f'{year}-01-01':f'{year}-12-31']
    mret = seg.resample('ME').last().pct_change().dropna()
    return dict(wm=f"{int((mret > 0).sum())}/{int(len(mret))}",
                monthly={str(k.date()): round(float(v), 6) for k, v in mret.items()})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='team/audit/out/batch_020_021_audit.json')
    a = ap.parse_args()
    s20 = {s['id']: s for s in json.load(open(os.path.join(ROOT, 'team', 'specs', 'batch_020.json')))}
    s21 = {s['id']: s for s in json.load(open('team/specs/batch_021.json'))} if os.path.exists('team/specs/batch_021.json') else {}
    if not s21:
        import glob
        cand = glob.glob(os.path.join(ROOT, 'team', 'specs', 'batch_021*.json'))
        print('batch021 spec candidates:', cand)
        s21 = {s['id']: s for s in json.load(open(cand[0]))}
    specs = {}
    for i in IDS_020:
        specs[i] = s20[i]
    for i in IDS_021:
        specs[i] = s21[i]
    df20 = pd.read_csv(os.path.join(ROOT, 'team', 'runs', 'batch_020_results.csv'))
    df21 = pd.read_csv(os.path.join(ROOT, 'team', 'runs', 'batch_021_results.csv'))
    out = {}
    # (0) spec 同一性检查
    import hashlib
    def norm(s):
        d = dict(s)
        d.pop('id', None); d.pop('notes', None); d.pop('group', None)
        return json.dumps(d, sort_keys=True, ensure_ascii=False)
    out['spec_identity'] = {i: hashlib.md5(norm(specs[i]).encode()).hexdigest() for i in specs}
    # (1) run_spec 重跑 (detail=True 取交易明细)
    rerun = {}
    for i, s in specs.items():
        row, eq, tr = HH.run_spec(copy.deepcopy(s), detail=True, variants=())
        rerun[i] = dict(row=row, eq=eq, tr=tr)
        hrow = (df20 if i.startswith('b020') else df21)
        hrow = hrow[hrow['id'] == i].iloc[0]
        out[i+':harness'] = dict(total_2025=float(hrow['total_2025']), mdd_2025=float(hrow['mdd_2025']),
            wp_2025=(float(hrow['win_period_2025']) if pd.notna(hrow['win_period_2025']) else float('nan')),
            wt_2025=float(hrow['win_trade_2025']), ntr_2025=float(hrow['n_trades_2025']),
            wm_2025=str(hrow['win_month_2025']))
        out[i+':mine'] = dict(total_2025=float(row['total_2025']), mdd_2025=float(row['mdd_2025']),
            wp_2025=(float(row['win_period_2025']) if row.get('win_period_2025') is not None and not (isinstance(row.get('win_period_2025'), float) and np.isnan(row.get('win_period_2025'))) else float('nan')),
            wt_2025=float(row['win_trade_2025']), ntr_2025=float(row['n_trades_2025']),
            wm_2025=str(row['win_month_2025']))
        out[i+':delta_pp'] = (float(row['total_2025']) - float(hrow['total_2025'])) * 100.0
        out[i+':delta_mdd_pp'] = (float(row['mdd_2025']) - float(hrow['mdd_2025'])) * 100.0
        out[i+':monthly'] = monthly_wins(eq.set_index('date')['equity'] if 'date' in eq.columns else eq.iloc[:, 1])
    # (2) W2 vs W5 vs V6 交易序列同一性
    def seqkey(tr):
        if tr is None or len(tr) == 0:
            return []
        t = tr.copy()
        return sorted(zip(t['code'].astype(str), pd.to_datetime(t['entry_date']).dt.strftime('%Y-%m-%d'),
                          pd.to_datetime(t['exit_date']).dt.strftime('%Y-%m-%d'), t['shares'].astype(float).round(2)))
    seqs = {i: seqkey(rerun[i]['tr']) for i in ['b020_W2_R7_base_2025', 'b020_W5_R7_N2_2025', 'b021_V6_N6']}
    out['seq_identity_W2_W5'] = (seqs['b020_W2_R7_base_2025'] == seqs['b020_W5_R7_N2_2025'])
    out['seq_identity_W2_V6'] = (seqs['b020_W2_R7_base_2025'] == seqs['b021_V6_N6'])
    out['seq_lengths'] = {k: len(v) for k, v in seqs.items()}
    # 首个持仓抽查: 2025 第一个调仓执仓
    picks = {}
    for i in ['b020_W2_R7_base_2025', 'b021_V6_N6']:
        tr = rerun[i]['tr']
        t = tr[pd.to_datetime(tr['entry_date']) < '2025-03-01'].sort_values('entry_date').head(8)
        picks[i] = t[['code', 'entry_date', 'shares']].to_dict('records')
    out['first_picks'] = {k: [{kk: str(vv) for kk, vv in r.items()} for r in v] for k, v in picks.items()}
    # (3) 显著性: spread bootstrap vs W1
    eqs = {}
    for i in list(specs.keys()):
        e = rerun[i]['eq']
        eq = e.set_index('date')['equity'] if 'date' in e.columns else e.iloc[:, 1]
        eq.index = pd.to_datetime(eq.index)
        eqs[i] = eq
    base = eqs['b020_W1_R30_base_2025']
    for i in ['b020_W2_R7_base_2025', 'b021_V1_TP60', 'b021_V2_TP80', 'b021_V3_staged', 'b021_V6_N6']:
        if i in eqs:
            out[f'spread:{i}_vs_W1'] = spread_bootstrap(eqs[i], base)
    # (4) phase 健壮性 0-3
    for i in ['b020_W1_R30_base_2025', 'b020_W2_R7_base_2025', 'b021_V1_TP60', 'b021_V2_TP80', 'b021_V3_staged']:
        ph = {}
        for p in (0, 1, 2, 3):
            s = copy.deepcopy(specs[i])
            s['phase'] = p
            row = HH.run_spec(s, detail=False, variants=())
            ph[str(p)] = dict(total_2025=float(row['total_2025']), mdd_2025=float(row['mdd_2025']))
        out[f'phase:{i}'] = ph
    op = os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, 'w') as f:
        json.dump(out, f, indent=1, default=str)
    for i in list(specs.keys()):
        print(f"[{i}] mine {out[i+':mine']['total_2025']*100:.2f}% harness {out[i+':harness']['total_2025']*100:.2f}% delta={out[i+':delta_pp']:+.3f}pp")
    print('spec md5:', out['spec_identity'])
    print('W2==W5 trades:', out['seq_identity_W2_W5'], 'W2==V6 trades:', out['seq_identity_W2_V6'], out['seq_lengths'])
    for k in [k for k in out if k.startswith('spread')]:
        print(k, {kk: (f"{vv*100:.2f}%" if isinstance(vv, float) else vv) for kk, vv in out[k].items()})
    for k in [k for k in out if k.startswith('phase')]:
        print(k, {p: f"{v['total_2025']*100:.2f}%" for p, v in out[k].items()})
    print('wrote', op)

if __name__ == '__main__':
    main()
