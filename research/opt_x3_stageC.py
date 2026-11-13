import gc, json, os, sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / 'team' / 'audit'))
sys.path.insert(0, str(BASE / 'research'))
os.chdir(BASE)
import pandas as pd
import prior_check as pc
from design_r30_grid8 import X3Inputs
MB = ('688', '689', '300', '301', '8', '4')
WINDOWS = {'1m': 21, '3m': 63, '6m': 126, '1y': 252, '2y': 504}
piv = pd.read_pickle(BASE / 'data' / 'pivots_2020_clean.pkl')
INPS = {'b': X3Inputs(piv, gate60=-0.15), 'g10': X3Inputs(piv, gate60=-0.10), 'g25': X3Inputs(piv, gate60=-0.25), 'b225': X3Inputs(piv, gate60=-0.15, band=(0.02, 0.25)), 'b235': X3Inputs(piv, gate60=-0.15, band=(0.02, 0.35)), 'a10m': X3Inputs(piv, gate60=-0.15, min_adv=1e7)}
print('inputs ready', flush=True)
def win_stats(eq, days):
    sub = eq.tail(days + 1)
    return {'ret': round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2), 'mdd': round(float((sub / sub.cummax() - 1).min()) * 100, 2)}
def summarize(name, res):
    eq = pd.Series(res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq).dropna()
    return {'tag': name, 'total': round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2), 'mdd': round(float((eq / eq.cummax() - 1).min()) * 100, 2), 'w': {k: win_stats(eq, d) for k, d in WINDOWS.items()}, 'trades': int(len(res.trades)), 'cost': round(float(res.meta.get('total_cost', 0.0)), 0)}
KW = dict(stop_exec='next', exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start='2023-11-10', eval_start=pd.Timestamp('2025-02-13'), eval_end=pd.Timestamp('2026-11-12'), phase=0, legacy_grid=False, exposure=1.0)
V = [
    ('TP70_R20_N5', 'b', dict(take=0.70, rebal=20, n=5)),
    ('TP80_R20_N5', 'b', dict(take=0.80, rebal=20, n=5)),
    ('TP55_R20_N5', 'b', dict(take=0.55, rebal=20, n=5)),
    ('GATE10_R20_N5', 'g10', dict(take=1.0, rebal=20, n=5)),
    ('GATE25_R20_N5', 'g25', dict(take=1.0, rebal=20, n=5)),
    ('BAND0225_R20_N5', 'b225', dict(take=1.0, rebal=20, n=5)),
    ('BAND0235_R20_N5', 'b235', dict(take=1.0, rebal=20, n=5)),
    ('AMI20_R20_N5', 'b', dict(take=1.0, rebal=20, n=5, factor='amihud')),
    ('ADV10M_R20_N5', 'a10m', dict(take=1.0, rebal=20, n=5)),
    ('N7_R20', 'b', dict(take=1.0, rebal=20, n=7)),
    ('LAG1_R20_N5', 'b', dict(take=1.0, rebal=20, n=5, sig_lag=1)),
    ('LAG2_R20_N5', 'b', dict(take=1.0, rebal=20, n=5, sig_lag=2)),
    ('TP60_R20_N6', 'b', dict(take=0.60, rebal=20, n=6)),
    ('NOFULLLIQ_R20_N5', 'b', dict(take=1.0, rebal=20, n=5, full_liquidate=False)),
]
rows = []
for tag, ik, kw in V:
    base = dict(KW); base.update({'factor': 'amihud_60', 'full_liquidate': True, 'sig_lag': 0})
    base.update(kw)
    res = pc.run_strategy(INPS[ik], n=base.pop('n', 4) if False else kw['n'], rebal=kw['rebal'], take=kw['take'], **{k: v for k, v in base.items() if k not in ('n', 'rebal', 'take')})
    row = summarize(tag, res)
    rows.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
    del res; gc.collect()
with open('results/r30_bt/opt_x3_stageC.json', 'w') as f: json.dump(rows, f, ensure_ascii=False, indent=1)
print('SAVED stageC', flush=True)