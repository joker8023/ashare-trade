import os; os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E
import risk_control as R
midx = R._index_series("000905")
sig = (midx > midx.rolling(15).mean()).shift(1).astype(float)
for f in ["amihud_60","turn20","amount_level","size"]:
    try:
        r = E.returns_series(f,n_hold=100,rebal=90,size_range=(0.05,0.30),cost=0.005)
    except Exception as e:
        print(f, "ERR", str(e)[:100], flush=True); continue
    rr=(r*sig.reindex(r.index).ffill().fillna(0.0)).dropna()
    eq=(1+rr).cumprod(); yrs=len(rr)/252
    ann=eq.iloc[-1]**(1/yrs)-1; mdd=(eq/eq.cummax()-1).min()
    vol=rr.std()*np.sqrt(252); sh=rr.mean()*252/vol
    print(f"{f}: 年化{ann:.1%} 回撤{mdd:.1%} 夏普{sh:.2f} Calmar{ann/abs(mdd):.2f}", flush=True)
