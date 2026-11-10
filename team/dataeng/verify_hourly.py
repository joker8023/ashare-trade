import pandas as pd, json, os
OUT='data/hourly_60m'
mani=pd.read_csv(f'{OUT}/manifest.csv')
print('stocks manifest', mani.shape, 'total', mani['bars'].sum())
print('missing:', (mani['bars']==0).sum())
# append index rows
rows=[]
for c in ['510300','510500','159915']:
    d=pd.read_csv(f'{OUT}/{c}.csv')
    rows.append(dict(code=c, bs=c, bars=len(d), start=str(d['datetime'].min()), end=str(d['datetime'].max()), source='resample-5m', note='from data/minute_etf 5m'))
idx=pd.DataFrame(rows)
full=pd.concat([mani, idx], ignore_index=True)
full.to_csv(f'{OUT}/manifest.csv', index=False)
print('merged manifest', full.shape)
# verify all pool codes have files with right cols
pool=pd.read_csv('team/dataeng/pool_list.csv', dtype=str)
import glob
files=sorted(glob.glob(f'{OUT}/*.csv'))
print('n files in hourly_60m:', len(files))
bad=[]
for c in pool['code'].str.zfill(6):
    p=f'{OUT}/{c}.csv'
    if not os.path.exists(p): bad.append((c,'miss')); continue
    d=pd.read_csv(p)
    if list(d.columns)!=['datetime','open','high','low','close','volume','amount']: bad.append((c,'cols:'+str(list(d.columns))))
print('bad stock files:', bad)
# date range + missing rate estimate: expected ~2748 bars (687d*4); suspensions cause small shortfall
all_bars=mani['bars'].sum()
print('stock bars total', all_bars, 'avg per stock', all_bars/len(mani))
print(mani['bars'].describe().to_dict())
print(mani.sort_values('bars').head(8).to_string())
# progress
prog=json.load(open(f'{OUT}/progress.json'))
print('progress entries', len(prog), 'done', sum(1 for v in prog.values() if v.get('status')=='done'))
