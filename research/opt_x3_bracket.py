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
KW = dict(factor='amihud_60', stop=None, stop_exec='next', exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start='2023-11-10', eval_start=pd.Timestamp('2025-02-13'), eval_end=pd.Timestamp('2026-11-12'), legacy_grid=False, exposure=1.0, full_liquidate=True, take=1.0, n=5)
rows = []
for tag, rb in [('R18_N5', 18), ('R22_N5', 22), ('R20_N5_ph7', 20)]:
    ph = 7 if tag.endswith('ph7') else 0
    res = pc.run_strategy(INP, rebal=rb, phase=ph, **KW)
    eq = pd.Series(res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq).dropna()
    w = {}
    for k, d in WINDOWS.items():
        sub = eq.tail(d + 1)
        w[k] = {'ret': round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2), 'mdd': round(float((sub / sub.cummax() - 1).min()) * 100, 2)}
    rows.append({'tag': tag, 'total': round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2), 'mdd': round(float((eq / eq.cummax() - 1).min()) * 100, 2), 'w': w, 'trades': int(len(res.trades)), 'cost': round(float(res.meta.get('total_cost', 0.0)), 0)})
    print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    del res; gc.collect()
print('DONE bracket', flush=True)