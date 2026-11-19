import pathlib, pandas as pd
print(list(pathlib.Path("data").iterdir())[:40])
# check hourly, minute, etc?
# check pivots close sample
piv=pd.read_pickle("data/pivots_2020_clean_realshares_v2.pkl")
close=piv["close"]
print(close.shape)
# market proxy: equal weight mean normalized?
# compute daily market return as median stock return?
rets=close.pct_change()
# median daily
mmed=rets.median(axis=1)
print(mmed.head(10).to_string())
print(mmed.describe().to_string())
# MA60 of cumulative market index?
midx=(1+mmed.fillna(0)).cumprod()
print(midx.head(10).to_string())
print(midx.tail(10).to_string())
# save?
# check amount/volume for regime vol
