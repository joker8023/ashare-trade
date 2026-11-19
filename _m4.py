import pandas as pd
piv=pd.read_pickle("data/pivots_2020_clean_realshares_v2.pkl")
close=piv["close"]; shares=piv["shares"]
mcap=close*shares
# cap-weighted daily return: total mcap return
tot=mcap.sum(axis=1)
mret=tot.pct_change()
print(mret.describe().to_string())
midx=(1+mret.fillna(0)).cumprod()
print(midx.tail(20).to_string())
# MA60, slope, vol
ma60=midx.rolling(60).mean()
ma20=midx.rolling(20).mean()
print(pd.DataFrame({"midx":midx,"ma60":ma60,"ma20":ma20}).tail(30).to_string())
# breadth: % above MA60 per stock?
ma60_stock=close.rolling(60).mean()
above=(close>ma60_stock).mean(axis=1)
print(above.tail(30).to_string())
# vol: 20d std of mret
vol=mret.rolling(20).std()
print(vol.tail(20).to_string())
