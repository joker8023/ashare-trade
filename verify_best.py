import os
os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E, risk_control as R
p = E.piv()
for code, name in [("000852","中证1000"), ("000905","中证500")]:
    idx = R._index_series(code)
    ma = idx.rolling(15).mean()
    sig = (idx > ma).shift(1).astype(float)
    r = E.returns_series("amihud", n_hold=25, rebal=40, size_range=(0.05,0.30), cost=0.005)
    on = sig.reindex(r.index).ffill().fillna(0)
    rr = (r*on).dropna()
    eq=(1+rr).cumprod(); yrs=len(rr)/252
    ann=eq.iloc[-1]**(1/yrs)-1; vol=rr.std()*np.sqrt(252); mdd=(eq/eq.cummax()-1).min()
    print(f"{name} MA15 + amihud N=25 R=40: 年化{ann:.1%} 回撤{mdd:.1%} 夏普{rr.mean()*252/vol if vol>0 else 0:.2f} Calmar{ann/abs(mdd) if mdd<0 else 0:.2f}", flush=True)

print("\n--- 40.2% 版本分段验证 ---")
import engine as E2
p2 = E2.piv()
idx2 = R._index_series("000905")
ma2 = idx2.rolling(15).mean()
sig2 = (idx2 > ma2).shift(1).astype(float)
r2 = E2.returns_series("amihud", n_hold=25, rebal=40, size_range=(0.05,0.30), cost=0.005)
on2 = sig2.reindex(r2.index).ffill().fillna(0)
rr2 = (r2*on2).dropna()
for label, s in [("全样本",rr2),("前半",rr2[rr2.index<"2021-01-01"]),("后半",rr2[rr2.index>="2021-01-01"])]:
    eq=(1+s).cumprod(); yrs=len(s)/252
    ann=eq.iloc[-1]**(1/yrs)-1; vol=s.std()*np.sqrt(252); mdd=(eq/eq.cummax()-1).min()
    print(f"{label:8s} 年化{ann:6.1%} 回撤{mdd:7.1%} 夏普{s.mean()*252/vol if vol>0 else 0:5.2f}", flush=True)
yr = rr2.groupby(rr2.index.year).apply(lambda x:(1+x).prod()-1)
print(f"盈利年份 {(yr>0).sum()}/{len(yr)}, 最差 {yr.min():+.1%}, 最好 {yr.max():+.1%}")
