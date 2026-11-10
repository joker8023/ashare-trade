import os
os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E, risk_control as R
p = E.piv()
idx = R._index_series("000852")
ma = idx.rolling(15).mean()
sig = (idx > ma).shift(1).astype(float)
for n in [10, 15, 20]:
    try:
        r = E.returns_series("amihud", n_hold=n, rebal=40, size_range=(0.05,0.30), cost=0.005)
        on = sig.reindex(r.index).ffill().fillna(0)
        rr = (r*on).dropna()
        eq=(1+rr).cumprod(); yrs=len(rr)/252
        ann=eq.iloc[-1]**(1/yrs)-1; vol=rr.std()*np.sqrt(252); mdd=(eq/eq.cummax()-1).min()
        sh=rr.mean()*252/vol if vol>0 else 0
        print(f"N={n:<3} 年化{ann:6.1%} 回撤{mdd:7.1%} 夏普{sh:5.2f} Calmar{ann/abs(mdd) if mdd<0 else 0:5.2f}", flush=True)
    except Exception as e:
        print(n, "失败", str(e)[:50])
