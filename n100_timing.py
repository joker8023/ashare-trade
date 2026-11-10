import os; os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E
import risk_control as R
r = E.returns_series("amihud",n_hold=100,rebal=90,size_range=(0.05,0.30),cost=0.005)
r.to_pickle("results/pool/long_N100_R90_05.pkl")
print("leg saved", flush=True)
for code, ma in [("000905",10),("000905",15),("000905",20),("000852",15),("000852",20)]:
    midx = R._index_series(code)
    sig = (midx > midx.rolling(ma).mean()).shift(1).astype(float)
    rr=(r*sig.reindex(r.index).ffill().fillna(0.0)).dropna()
    eq=(1+rr).cumprod(); yrs=len(rr)/252
    ann=eq.iloc[-1]**(1/yrs)-1; mdd=(eq/eq.cummax()-1).min()
    vol=rr.std()*np.sqrt(252); sh=rr.mean()*252/vol
    print(f"{code} MA{ma}: 年化{ann:.1%} 回撤{mdd:.1%} 夏普{sh:.2f} Calmar{ann/abs(mdd):.2f}", flush=True)
