import pandas as pd
piv = pd.read_pickle("data/pivots_2020_clean_realshares_v2.pkl")
close = piv["close"]
shares = piv["shares"]
cap = close * shares
rets = close.pct_change(fill_method=None)
eq_idx = (1 + rets.mean(axis=1, skipna=True).fillna(0)).cumprod()
print(eq_idx.tail(5).to_string())
