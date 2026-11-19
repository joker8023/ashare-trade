import sys, json
from pathlib import Path
ROOT=Path('.').resolve()
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'team'/'audit')); sys.path.insert(0,str(ROOT/'research'))
import pandas as pd
from sweep_beat_h1_v4 import _mdd
import search_C_stage2 as S
WINDOWS={'1m':21,'3m':63,'6m':126,'1y':252,'2y':504,'3y':756}
TAGS=[('C2_grid_mh0_bx0.15_by0.1_bf0.5',dict(rs=60,bx=0.15,by_=0.1,bf=0.5,hyst=0.0,mh=0,evalfreq='grid',brake_daily=False)),('C2_daily_h0.03_mh0_bx0.15_by0.05_bf0.5_bd',dict(rs=60,bx=0.15,by_=0.05,bf=0.5,hyst=0.03,mh=0,evalfreq='daily',brake_daily=True)),('C2_daily_h0.03_mh10_bx0.15_by0.05_bf0.5_bd',dict(rs=60,bx=0.15,by_=0.05,bf=0.5,hyst=0.03,mh=10,evalfreq='daily',brake_daily=True)),('C2_daily_h0.02_mh10_bx0.15_by0.1_bf0.5_bg',dict(rs=60,bx=0.15,by_=0.1,bf=0.5,hyst=0.02,mh=10,evalfreq='daily',brake_daily=False)),('C2_grid_mh0_bx0.15_by0.1_bf0.7',dict(rs=60,bx=0.15,by_=0.1,bf=0.7,hyst=0.0,mh=0,evalfreq='grid',brake_daily=False))]
rows=[]
for tag,kw in TAGS:
    o,e=S.run_one(tag,**kw)
    eq=e.dropna() if isinstance(e,pd.Series) else e.iloc[:,0].dropna()
    r={'tag':tag}
    for w,d in WINDOWS.items():
        sub=eq.tail(d+1)
        r[w]=round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
        r[w+'_mdd']=round(_mdd(sub)*100,2)
        r[w+'_bars']=int(len(sub))
    r['total']=o['total']; r['mdd']=o['mdd']
    rows.append(r)
    print(json.dumps(r,ensure_ascii=False))
open('results/r30_bt/C5_windows.json','w').write(json.dumps(rows,ensure_ascii=False,indent=1))
print('saved results/r30_bt/C5_windows.json')
