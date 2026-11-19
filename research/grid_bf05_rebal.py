import sys
from pathlib import Path
ROOT=Path('.').resolve()
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'team'/'audit')); sys.path.insert(0,str(ROOT/'research'))
import pandas as pd
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import RUN_START, EVAL_END, MB
piv=pd.read_pickle(ROOT/'data'/'pivots_2020_clean_realshares_v2.pkl')
dates=piv['close'].index
inpA=MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=20)
inpB=MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=20)
ga=inpA.grid(20,0); gb=inpB.grid(15,0)
print('A grid n=',len(ga))
print('B grid n=',len(gb))
import pandas as pd
run_ts=pd.Timestamp(RUN_START); end_ts=pd.Timestamp(EVAL_END)
ga=[i for i in ga if dates[i]>=run_ts]; gb=[i for i in gb if dates[i]>=run_ts]
print('A grid dates tail<=EVAL:')
for i in ga:
    if dates[i]<=end_ts:
        pass
tailA=[dates[i].date() for i in ga if dates[i]<=end_ts][-6:]
print(tailA)
print('A grid first after EVAL:')
for i in ga:
    if dates[i]>end_ts:
        print(dates[i].date(), 'idx', i)
        break
print('B grid tail<=EVAL:', [dates[i].date() for i in gb if dates[i]<=end_ts][-4:])
# exec is t+1? In switch engine exec_map: exec = signal+1+sig_lag (0) -> next trading day close. Print exec too.
print('--- A last3 sig->exec ---')
ids=[i for i in ga if dates[i]<=end_ts][-3:]
for i in ids:
    print(f"sig {dates[i].date()} -> exec {dates[i+1].date()}")
ni=next(i for i in ga if dates[i]>end_ts)
print(f"NEXT sig {dates[ni].date()} -> exec {dates[ni+1].date() if ni+1<len(dates) else 'need more data'}")
