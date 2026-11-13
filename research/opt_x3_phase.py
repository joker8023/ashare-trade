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
WINDOWS = {'3m': 63, '6m': 126, '1y': 252}
piv = pd.read_pickle(BASE / 'data' / 'pivots_2020_clean.pkl')
INP = X3Inputs(piv, gate60=-0.15)
print('inputs ready', flush=True)
def summ(res):
    eq = pd.Series(res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq).dropna()
    w = {}
    for k, d in WINDOWS.items():
        sub = eq.tail(d + 1)
        w[k] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
    return {'total': round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2), 'mdd': round(float((eq / eq.cummax() - 1).min()) * 100, 2), 'w3m': w['3m'], 'w6m': w['6m'], 'w1y': w['1y'], 'trades': int(len(res.trades))}
CANDS = [('TP55_R20', dict(take=0.55, rebal=20, n=4)), ('TP50_R20', dict(take=0.50, rebal=20, n=4)), ('R20_N5', dict(take=1.0, rebal=20, n=5))]
KW = dict(factor='amihud_60', stop=None, stop_exec='next', exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start='2023-11-10', eval_start=pd.Timestamp('2025-02-13'), eval_end=pd.Timestamp('2026-11-12'), legacy_grid=False, exposure=1.0, full_liquidate=True)
out = {}
for tag, kw in CANDS:
    rows = []
    for ph in range(30):
        res = pc.run_strategy(INP, n=kw['n'], rebal=kw['rebal'], take=kw['take'], phase=ph, **KW)
        r = summ(res); r['phase'] = ph
        rows.append(r)
        del res; gc.collect()
    out[tag] = rows
    df = pd.DataFrame(rows)
    stat = {c: {'mean': round(float(df[c].mean()), 1), 'min': round(float(df[c].min()), 1), 'med': round(float(df[c].median()), 1), 'std': round(float(df[c].std()), 1)} for c in ['total', 'mdd', 'w3m', 'w6m', 'w1y']}
    print(tag + ' ' + json.dumps(stat, ensure_ascii=False), flush=True)
with open('results/r30_bt/opt_x3_phase.json', 'w') as f: json.dump(out, f, ensure_ascii=False, indent=1)
print('SAVED phase', flush=True)