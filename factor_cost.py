import os
os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E, risk_control as R
p=E.piv()
idx = R._index_series("000852"); ma = idx.rolling(15).mean()
sig = (idx > ma).shift(1).astype(float)
for fac in ["amihud", "amount_level", "size"]:
    print(f"=== {fac} ===")
    for cost in [0.0015, 0.003, 0.005, 0.008, 0.01]:
        r = E.returns_series(fac, n_hold=50, rebal=60, size_range=(0.05,0.30), cost=cost)
        on = sig.reindex(r.index).ffill().fillna(0.0)
        for label, rr in [("无择时",r), ("+MA15",r*on)]:
            eq=(1+rr).cumprod(); yrs=len(rr)/252
            ann=eq.iloc[-1]**(1/yrs)-1; vol=rr.std()*np.sqrt(252); mdd=(eq/eq.cummax()-1).min()
            print(f"  成本{cost*100:4.2f}% {label:8s} 年化{ann:6.1%} 回撤{mdd:7.1%} 夏普{rr.mean()*252/vol if vol>0 else 0:5.2f}")
    print()
