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
INP = X3Inputs(piv, gate60=-0.15)
print('inputs ready', flush=True)
def win_stats(eq, days):
    sub = eq.tail(days + 1)
    return {'ret': round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2), 'mdd': round(float((sub / sub.cummax() - 1).min()) * 100, 2)}
def summarize(name, eq, trades_n=0, cost=0):
    eq = pd.Series(eq.iloc[:, 0] if isinstance(eq, pd.DataFrame) else eq).dropna()
    return {'tag': name, 'total': round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2), 'mdd': round(float((eq / eq.cummax() - 1).min()) * 100, 2), 'w': {k: win_stats(eq, d) for k, d in WINDOWS.items()}, 'trades': trades_n, 'cost': cost}
KW = dict(factor='amihud_60', stop=None, stop_exec='next', exclude=MB, lot=100, cost_one_way=None, slip=0.002, run_start='2023-11-10', eval_start=pd.Timestamp('2025-02-13'), eval_end=pd.Timestamp('2026-11-12'), legacy_grid=False, exposure=1.0, full_liquidate=True)
def leg(take, rebal, n, cap, phase=0):
    res = pc.run_strategy(INP, n=n, rebal=rebal, take=take, capital=cap, phase=phase, **KW)
    eq = pd.Series(res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq).dropna()
    t = (int(len(res.trades)), round(float(res.meta.get('total_cost', 0.0)), 0))
    del res; gc.collect()
    return eq, t
rows = []
eq, t = leg(0.55, 20, 5, 50000.0, 0)
rows.append(summarize('TP55_R20_N5', eq, t[0], t[1]))
print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
eq1, t1 = leg(0.55, 20, 4, 25000.0, 0)
eq2, t2 = leg(1.0, 20, 5, 25000.0, 0)
rows.append(summarize('ENS_TP55R20_R20N5', eq1 + eq2, t1[0] + t2[0], t1[1] + t2[1]))
print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
eq1, t1 = leg(0.60, 20, 4, 25000.0, 0)
eq2, t2 = leg(1.0, 20, 5, 25000.0, 0)
rows.append(summarize('ENS_TP60R20_R20N5', eq1 + eq2, t1[0] + t2[0], t1[1] + t2[1]))
print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
eq1, t1 = leg(1.0, 20, 5, 25000.0, 0)
eq2, t2 = leg(1.0, 20, 5, 25000.0, 10)
rows.append(summarize('R20N5_P0P10', eq1 + eq2, t1[0] + t2[0], t1[1] + t2[1]))
print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
with open('results/r30_bt/opt_x3_stageD.json', 'w') as f: json.dump(rows, f, ensure_ascii=False, indent=1)
print('SAVED stageD', flush=True)