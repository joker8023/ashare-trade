import pandas as pd
piv=pd.read_pickle("data/pivots_2020_clean_realshares_v2.pkl")
close=piv["close"]; shares=piv["shares"]
mcap=close*shares
tot=mcap.sum(axis=1)
mret=tot.pct_change()
midx=(1+mret.fillna(0)).cumprod()
ma20=midx.rolling(20).mean()
ma60=midx.rolling(60).mean()
vol20=mret.rolling(20).std()
# grid same as T40: every 30 from idx300
dates=piv["close"].index
grid30=[dates[i] for i in range(300,len(dates),30)]
# RUN_START = dates[0]
import pandas as pd
RUN_START=str(dates[0].date())
first_sig=next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
print("RUN_START",RUN_START,"first",first_sig.date(),"ngrid",len(grid30))
# regime per grid
def regime(d):
    px=midx.loc[d]; a20=ma20.loc[d]; a60=ma60.loc[d]
    if pd.isna(a60) or pd.isna(a20): return "NA"
    if px>a60 and a20>a60: return "BULL"
    if px<a60 and a20<a60: return "BEAR"
    return "SIDE"
from collections import Counter
regs=[(str(d.date()),regime(d)) for d in grid30 if d>=pd.Timestamp("2023-01-03")]
print(Counter(r for _,r in regs))
for d,r in regs:
    print(d,r)
# also check eval window 2023-01-19 start?
print("--- vol stats ---")
print(vol20.describe().to_string())
