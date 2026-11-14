"""Fresh-1: long-hold + trailing-stop family, 2020 caliber ph0.
N2-N5 x stop 8/12/15%, R60, no TP, Amihud60 topN, band 5-30%, MB.
Compares six windows vs H1 (TB18-ph0)."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'team'/'audit')); sys.path.insert(0, str(ROOT/'research'))
import pandas as pd
import prior_check as pc
from design_r30_grid8 import X3Inputs
WINDOWS = {'1m': 21, '3m': 63, '6m': 126, '1y': 252, '2y': 504, '3y': 756}
RUN_START = '2023-01-03'
EVAL_END = pd.Timestamp('2026-11-12')
MB = ('688', '689', '300', '301', '8', '4')
BASE_W = {'1m': -4.98, '3m': 14.07, '6m': 32.01, '1y': 150.80, '2y': 1334.68, '3y': 1321.51}
def _mdd(s):
    return float((s / s.cummax() - 1).min())
def main():
    piv = pd.read_pickle(ROOT/'data'/'pivots_2020_clean.pkl')
    dates = piv['close'].index
    grid_dates = [dates[i] for i in range(300, len(dates), 30)]
    first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
    inp = X3Inputs(piv, band=(0.05, 0.30), gate60=-0.15)
    cfgs = []
    for n in [2, 3, 4, 5]:
        for st in [0.08, 0.12, 0.15]:
            cfgs.append(dict(tag='f1_N%d_s%d' % (n, int(st*100)), n=n, stop=st))
    rows = []
    for cfg in cfgs:
        try:
            res = pc.run_strategy(inp, factor='amihud_60', n=cfg['n'], rebal=60, take=None, stop=cfg['stop'], stop_exec='next', exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, phase=0, legacy_grid=False, full_liquidate=True, exposure=1.0)
            eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
            eq = eq.dropna()
            out = {'tag': cfg['tag'], 'total': round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), 'mdd': round(_mdd(eq)*100,2), 'trades': len(res.trades), 'cost': round(float(res.meta['total_cost']),0)}
            for w, d in WINDOWS.items():
                sub = eq.tail(d+1)
                out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
            out['gap'] = round(out['3y']-out['2y'],2)
            out['nbeat'] = sum(1 for w in WINDOWS if out[w] > BASE_W[w])
            print(json.dumps(out, ensure_ascii=False), flush=True)
            rows.append(out)
        except Exception as e:
            print('FAIL %s: %s' % (cfg['tag'], e), flush=True)
    open(ROOT/'results'/'r30_bt'/'fresh1_hold.json', 'w').write(json.dumps(rows, ensure_ascii=False, indent=1))
    print('saved %d rows' % len(rows), flush=True)
if __name__ == '__main__':
    main()