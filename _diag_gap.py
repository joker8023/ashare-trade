import pandas as pd
piv = pd.read_pickle("data/pivots_2020_clean_realshares_v2.pkl")
close = piv["close"]
shares = piv["shares"]
rets = close.pct_change(fill_method=None)
eq_idx = (1 + rets.mean(axis=1, skipna=True).fillna(0)).cumprod()
tot = (close * shares).sum(axis=1)
mret = tot.pct_change(fill_method=None)
midx = (1 + mret.fillna(0)).cumprod()
medcap = (close * shares).median(axis=0)
small_cols = medcap.nsmallest(1500).index
small_idx = (1 + rets[small_cols].mean(axis=1, skipna=True).fillna(0)).cumprod()
dates = close.index
for s in ["2026-06-15", "2026-07-28", "2026-09-08", "2026-10-28", "2026-11-12", "2025-07-30", "2024-11-04"]:
    d = pd.Timestamp(s)
    cg = float(midx.loc[d] / midx.rolling(60).mean().loc[d] - 1) * 100
    eg = float(eq_idx.loc[d] / eq_idx.rolling(60).mean().loc[d] - 1) * 100
    sg = float(small_idx.loc[d] / small_idx.rolling(60).mean().loc[d] - 1) * 100
    print(s + " cap=" + str(round(cg,2)) + " eq=" + str(round(eg,2)) + " small=" + str(round(sg,2)))
