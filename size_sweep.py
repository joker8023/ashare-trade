import os; os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E
import risk_control as R
midx = R._index_series("000905")
sig = (midx > midx.rolling(20).mean()).shift(1).astype(float)
res=[]
for lo,hi in [(0.03,0.20),(0.03,0.30),(0.05,0.20),(0.05,0.30),(0.05,0.50),(0.10,0.30)]:
    r = E.returns_series("amihud",n_hold=25,rebal=40,size_range=(lo,hi),cost=0.005)
    rr=(r*sig.reindex(r.index).ffill().fillna(0.0)).dropna()
    eq=(1+rr).cumprod(); yrs=len(rr)/252
    ann=eq.iloc[-1]**(1/yrs)-1; mdd=(eq/eq.cummax()-1).min()
    vol=rr.std()*np.sqrt(252); sh=rr.mean()*252/vol
    res.append((lo,hi,ann,mdd,sh,ann/abs(mdd)))
    print(f"size {lo}-{hi}: 年化{ann:.1%} 回撤{mdd:.1%} 夏普{sh:.2f} Calmar{ann/abs(mdd):.2f}", flush=True)
pd.DataFrame(res,columns=["lo","hi","ann","mdd","sharpe","calmar"]).to_csv("results/size_sweep.csv",index=False)
