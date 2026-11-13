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
RUN_START = '2023-11-10'
EVAL_END = pd.Timestamp('2026-11-12')
piv = pd.read_pickle(BASE / 'data' / 'pivots_2020_clean.pkl')
print('pivots loaded', piv['close'].shape, flush=True)
INPS = {'b': X3Inputs(piv, gate60=-0.15), 'g25': X3Inputs(piv, gate60=-0.25), 'g10': X3Inputs(piv, gate60=-0.10)}
print('inputs built', flush=True)
def win_stats(eq, days):
    sub = eq.tail(days + 1)
    ret = sub.iloc[-1] / sub.iloc[0] - 1
    mdd = (sub / sub.cummax() - 1).min()
    return {'ret': round(float(ret) * 100, 2), 'mdd': round(float(mdd) * 100, 2)}
def summarize(name, res):
    eq = res.eq
    if isinstance(eq, pd.DataFrame): eq = eq.iloc[:, 0]
    eq = pd.Series(eq).dropna()
    return {'tag': name,
        'total': round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
        'mdd': round(float((eq / eq.cummax() - 1).min()) * 100, 2),
        'w': {k: win_stats(eq, d) for k, d in WINDOWS.items()},
        'trades': int(len(res.trades)),
        'cost': round(float(res.meta.get('total_cost', 0.0)), 0)}
BASE_KW = dict(factor='amihud_60', stop_exec='next', exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=pd.Timestamp('2025-02-13'), eval_end=EVAL_END, phase=0, legacy_grid=False, exposure=1.0, full_liquidate=True)
VARIANTS = [
    ('base_TP100_R30', 'b', dict(take=1.0, rebal=30, stop=None, n=4)),
    ('TP45', 'b', dict(take=0.45, rebal=30, stop=None, n=4)),
    ('TP60', 'b', dict(take=0.60, rebal=30, stop=None, n=4)),
    ('TP70', 'b', dict(take=0.70, rebal=30, stop=None, n=4)),
    ('TP80', 'b', dict(take=0.80, rebal=30, stop=None, n=4)),
    ('R15', 'b', dict(take=1.0, rebal=15, stop=None, n=4)),
    ('R20', 'b', dict(take=1.0, rebal=20, stop=None, n=4)),
    ('STOP15', 'b', dict(take=1.0, rebal=30, stop=0.15, n=4)),
    ('STOP20', 'b', dict(take=1.0, rebal=30, stop=0.20, n=4)),
    ('N5', 'b', dict(take=1.0, rebal=30, stop=None, n=5)),
    ('N6', 'b', dict(take=1.0, rebal=30, stop=None, n=6)),
    ('GATE25', 'g25', dict(take=1.0, rebal=30, stop=None, n=4)),
    ('GATE10', 'g10', dict(take=1.0, rebal=30, stop=None, n=4)),
    ('TP70_R20', 'b', dict(take=0.70, rebal=20, stop=None, n=4)),
    ('TP60_R20', 'b', dict(take=0.60, rebal=20, stop=None, n=4)),
    ('TP70_STOP20', 'b', dict(take=0.70, rebal=30, stop=0.20, n=4)),
    ('TP70_R20_STOP20', 'b', dict(take=0.70, rebal=20, stop=0.20, n=4)),
    ('TP60_R20_N5', 'b', dict(take=0.60, rebal=20, stop=None, n=5)),
]
rows = []
for tag, ikey, kw in VARIANTS:
    res = pc.run_strategy(INPS[ikey], n=kw['n'], rebal=kw['rebal'], take=kw['take'], stop=kw['stop'], **BASE_KW)
    row = summarize(tag, res)
    rows.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
    del res
    gc.collect()
with open('results/r30_bt/opt_x3_recent.json', 'w') as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)
print('SAVED results/r30_bt/opt_x3_recent.json', flush=True)