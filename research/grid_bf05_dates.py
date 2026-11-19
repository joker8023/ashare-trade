import sys, json
from pathlib import Path
ROOT=Path('.').resolve()
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'team'/'audit')); sys.path.insert(0,str(ROOT/'research'))
import pandas as pd
from sweep_beat_h1_v4 import RUN_START, EVAL_END
piv=pd.read_pickle(ROOT/'data'/'pivots_2020_clean_realshares_v2.pkl')
dates=piv['close'].index
print('dates range:', dates[0].date(), '->', dates[-1].date(), 'n=', len(dates))
print('EVAL_END:', EVAL_END)
grid30=[dates[i] for i in range(300,len(dates),30)]
print('grid30 n=', len(grid30), 'first=', grid30[0].date(), 'last=', grid30[-1].date())
first_sig=next(d for d in grid30 if d>=pd.Timestamp(RUN_START))
print('first_sig:', first_sig.date())
# filed switch/brake for grid_bf05
d=json.load(open('results/r30_bt/search_C_stage2.json'))
for r in d:
    if r['tag']=='C2_grid_mh0_bx0.15_by0.1_bf0.5':
        print('switch_log:', r['switch_log'])
        print('brake_log:', r.get('brake_log'))
        break
# recent grid signals <= EVAL_END and next after
sigs=[d for d in grid30 if d>=pd.Timestamp(first_sig) and d<=pd.Timestamp(EVAL_END)]
print('nsig<=EVAL:', len(sigs))
print('last 5 sigs:', [str(x.date()) for x in sigs[-5:]])
# execution is t+1 close: exec date = next trading date after sig
for s in sigs[-5:]:
    i=dates.get_loc(s)
    ex=dates[i+1] if i+1<len(dates) else None
    print(f"sig {s.date()} -> exec {ex.date() if ex is not None else None}")
after=[d for d in grid30 if d>pd.Timestamp(EVAL_END)]
print('grid sigs after EVAL_END:', [str(x.date()) for x in after[:5]])
if after:
    s=after[0]; i=dates.get_loc(s)
    ex=dates[i+1] if i+1<len(dates) else None
    print(f"NEXT sig {s.date()} -> exec {ex.date() if ex is not None else None}")
# also last 3 A-leg rebal? mode A since 2026-05-18, rebal=20 for A? B rebal=15. Grid evalfreq=grid uses sig_a (A grid?). Just report grid30.
