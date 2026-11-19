import pandas as pd
piv = pd.read_pickle("data/pivots_2020_clean_realshares_v2.pkl")
close = piv["close"]
shares = piv["shares"]
cap = close * shares
rets = close.pct_change(fill_method=None)
eq_idx = (1 + rets.mean(axis=1, skipna=True).fillna(0)).cumprod()
tot = (close * shares).sum(axis=1)
mret = tot.pct_change(fill_method=None)
midx = (1 + mret.fillna(0)).cumprod()
medcap = cap.median(axis=0)
small_cols = medcap.nsmallest(1500).index
small_rets = rets[small_cols].mean(axis=1, skipna=True)
small_idx = (1 + small_rets.fillna(0)).cumprod()
print("ok")
print(eq_idx.tail(3).to_string())
print(midx.tail(3).to_string())
print(small_idx.tail(3).to_string())
