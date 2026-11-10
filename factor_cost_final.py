import os
os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E, risk_control as R
p = E.piv()
for idx_code, idx_name in [("000852","中证1000"), ("000905","中证500")]:
    idx = R._index_series(idx_code); ma = idx.rolling(15).mean()
    sig = (idx > ma).shift(1).astype(float)
    print(f"=== amihud N=25 R=40 + {idx_name}MA15 (月频调仓,低换手) ===")
    for cost in [0.0015, 0.003, 0.005, 0.01]:
        r = E.returns_series("amihud", n_hold=25, rebal=40, size_range=(0.05,0.30), cost=cost)
        on = sig.reindex(r.index).ffill().fillna(0)
        rr = (r*on).dropna()
        eq=(1+rr).cumprod(); yrs=len(rr)/252
        ann=eq.iloc[-1]**(1/yrs)-1; vol=rr.std()*np.sqrt(252); mdd=(eq/eq.cummax()-1).min()
        ntrades = "约60(6次/年×10年)"  # 月频调仓,换手率~60%
        print(f"  成本{cost*100:4.2f}% 年化{ann:6.1%} 回撤{mdd:7.1%} 夏普{rr.mean()*252/vol if vol>0 else 0:5.2f}", flush=True)
