import os; os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import numpy as np, pandas as pd
import engine as E, risk_control as R
p=E.piv(); c=p["close"]; dates=c.index
adv20=p["amount"].rolling(20,min_periods=10).mean(); seasoned=c.shift(250).notna()
cap=c*p["shares"]
# 2026 daily universe equal weight (seasoned, adv>5m, size 5-30%)
d0=pd.Timestamp("2026-01-05")
rows=[]
for t in dates[dates>=d0]:
    v=seasoned.loc[t]&(adv20.loc[t]>5e6)&c.loc[t].notna()
    lo,hi=cap.loc[t].quantile(.05),cap.loc[t].quantile(.30)
    v&=((cap.loc[t]>=lo)&(cap.loc[t]<=hi)).fillna(False)
    r=c.loc[t].pct_change(fill_method=None) if False else None
    rows.append((t,v.sum()))
npool=pd.Series(dict(rows)); print("pool size 2026: min/med/max",npool.min(),npool.median(),npool.max())
# market equal-weight daily return using previous day's pool
rets={}
for i in range(1,len(dates)):
    t=dates[i]; tp=dates[i-1]
    if t<d0: continue
    v=seasoned.loc[tp]&(adv20.loc[tp]>5e6)&c.loc[tp].notna()
    lo,hi=cap.loc[tp].quantile(.05),cap.loc[tp].quantile(.30)
    v&=((cap.loc[tp]>=lo)&(cap.loc[tp]<=hi)).fillna(False)
    pool=v[v].index
    r=(c.loc[t,pool]/c.loc[tp,pool]-1).replace([np.inf,-np.inf],np.nan).dropna()
    if len(r)>50: rets[t]=r.mean()
ew=pd.Series(rets).sort_index()
eq=(1+ew).cumprod()
m=eq.resample("ME").last().pct_change().dropna()
m.iloc[0]=eq[eq.index.month==1].iloc[-1]-1
print("\n2026 等权小微盘月收益 %:")
print((m*100).round(2).to_string())
print("2026 total %.2f%% mdd %.2f%%"%( (eq.iloc[-1]-1)*100, ((eq/eq.cummax()-1).min())*100))
# 30-day non-overlap blocks aligned to first trading day of 2026
print("\n2026 等权小微盘 30 日块收益 (从1月第1个交易日对齐):")
idx=list(eq.index)
for k in range(0,len(idx),30):
    blk=eq.iloc[k:min(k+30,len(idx))]
    print(idx[k].date(), "->", idx[min(k+30,len(idx))-1].date(), "%.2f%%"%((blk.iloc[-1]/blk.iloc[0]-1)*100) if len(blk)>1 else "")
# 中证1000/500 2026
for code in ["000852","000905"]:
    s=R._index_series(code).reindex(eq.index).ffill()
    mm=s.resample("ME").last().pct_change().dropna()
    print("\n%s 2026 月收益:"%code, (mm*100).round(2).to_dict())
    print("%s 2026 total %.2f%%"%(code,(s.iloc[-1]/s.iloc[0]-1)*100))
