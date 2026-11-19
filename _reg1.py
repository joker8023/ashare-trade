import pandas as pd
piv=pd.read_pickle("data/pivots_2020_clean_realshares_v2.pkl")
close=piv["close"]; shares=piv["shares"]
tot=(close*shares).sum(axis=1)
mret=tot.pct_change()
midx=(1+mret.fillna(0)).cumprod()
ma60=midx.rolling(60).mean()
dates=piv["close"].index
grid30=[dates[i] for i in range(300,len(dates),30)]
grid=[d for d in grid30 if d>=pd.Timestamp("2023-01-03")]
for thr in [0.01,0.02,0.03,0.05]:
    def reg(d):
        t=float(midx.loc[d]/ma60.loc[d]-1)
        if t>thr: return "BULL"
        if t<-thr: return "BEAR"
        return "SIDE"
    from collections import Counter
    c=Counter(reg(d) for d in grid)
    print(f"thr={thr}",dict(c))
# also try MA20-MA60 gap
ma20=midx.rolling(20).mean()
for thr in [0.01,0.02]:
    def reg2(d):
        g=float(ma20.loc[d]/ma60.loc[d]-1)
        if g>thr: return "BULL"
        if g<-thr: return "BEAR"
        return "SIDE"
    from collections import Counter
    c=Counter(reg2(d) for d in grid)
    print(f"gap thr={thr}",dict(c))
    for d in grid:
        print(" ",str(d.date()),round(float(ma20.loc[d]/ma60.loc[d]-1)*100,2),reg2(d))
    print()
