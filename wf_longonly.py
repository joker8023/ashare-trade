import os; os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E
import risk_control as R
midx = R._index_series("000905")
sig = (midx > midx.rolling(15).mean()).shift(1).astype(float)
cfgs = {}
for n,reb,lb in [(25,40,"N25R40"),(50,60,"N50R60"),(100,90,"N100R90")]:
    try:
        r = pd.read_pickle(f"results/pool/long_N{n}_R{reb}_05.pkl")
    except Exception:
        r = E.returns_series("amihud",n_hold=n,rebal=reb,size_range=(0.05,0.30),cost=0.005)
        r.to_pickle(f"results/pool/long_N{n}_R{reb}_05.pkl")
    rr=(r*sig.reindex(r.index).ffill().fillna(0.0)).dropna()
    cfgs[lb]=rr
    print(lb, "ready", len(rr), flush=True)
import pandas as pd
ix = None
for v in cfgs.values(): ix = v.index if ix is None else ix.intersection(v.index)
years = sorted(set(ix.year))
picks=[]; reps=[]
for y in years[1:]:
    best=None
    for lb,rr in cfgs.items():
        past = rr[rr.index.year<y]
        eq=(1+past).cumprod(); yrs=len(past)/252
        ann=eq.iloc[-1]**(1/yrs)-1; mdd=(eq/eq.cummax()-1).min(); ca=ann/abs(mdd)
        if best is None or ca>best[0]: best=(ca,lb)
    picks.append((y,best[1]))
    reps.append(cfgs[best[1]][cfgs[best[1]].index.year==y])
print("picks:", picks, flush=True)
oos = pd.concat(reps).sort_index()
eq=(1+oos).cumprod(); yrs=len(oos)/252
ann=eq.iloc[-1]**(1/yrs)-1; mdd=(eq/eq.cummax()-1).min()
vol=oos.std()*np.sqrt(252); sh=oos.mean()*252/vol
print(f"WF-OOS 只做多头: 年化{ann:.1%} 回撤{mdd:.1%} 夏普{sh:.2f} Calmar{ann/abs(mdd):.2f}", flush=True)
yr = oos.groupby(oos.index.year).apply(lambda x:(1+x).prod()-1)
print(f"盈利 {(yr>0).sum()}/{len(yr)} 最差{yr.min():+.1%}", flush=True)
