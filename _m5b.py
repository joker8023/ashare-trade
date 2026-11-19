import pandas as pd
piv = pd.read_pickle("data/pivots_2020_clean_realshares_v2.pkl")
close = piv["close"]
print(close.shape)
