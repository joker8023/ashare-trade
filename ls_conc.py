import os
os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E
p=E.piv(); c=p["close"]
adv20=p["amount"].rolling(20,min_periods=10).mean()
seasoned=c.shift(250).notna()
fac=E.FACTORS["amihud"](p)
dates=c.index
def run(n_hold,rebal=60):
    rets=[]; pl=set(); ps=set()
    for i in range(300,len(dates)-rebal-2,rebal):
        t=dates[i]; t1=dates[i+1]; t2=dates[min(i+1+rebal,len(dates)-1)]
        valid=seasoned.loc[t]&(adv20.loc[t]>5e6)&c.loc[t].notna()&fac.loc[t].notna()
        cap=c.loc[t]*p["shares"]
        lo,hi=cap.quantile(0.05),cap.quantile(0.30)
        valid &= ((cap>=lo)&(cap<=hi)).fillna(False)
        pool=valid[valid].index
        if len(pool)<2*n_hold: continue
        fv=fac.loc[t,pool]
        longs=list(fv.nlargest(n_hold).index); shorts=list(fv.nsmallest(n_hold).index)
        seg=c.loc[t1:t2,longs+shorts].ffill()
        if len(seg)<2: continue
        rel=seg.div(seg.iloc[0])
        pr=0.5*rel[longs].mean(axis=1).pct_change(fill_method=None)-0.5*rel[shorts].mean(axis=1).pct_change(fill_method=None)
        pr=pr.dropna()
        to=1.0 if not pl else (len(set(longs)-pl)/n_hold+len(set(shorts)-ps)/n_hold)/2
        if len(pr): pr.iloc[0]-=to*2*0.0015
        pl,ps=set(longs),set(shorts)
        rets.append(pr)
    r=pd.concat(rets).sort_index(); r=r[~r.index.duplicated(keep="first")]
    eq=(1+r).cumprod(); yrs=len(r)/252
    ann=eq.iloc[-1]**(1/yrs)-1; vol=r.std()*np.sqrt(252); mdd=(eq/eq.cummax()-1).min()
    sh=r.mean()*252/vol if vol>0 else 0
    print(f"N={n_hold:3d}  年化{ann:6.1%} 回撤{mdd:7.1%} 夏普{sh:5.2f} Calmar{ann/abs(mdd) if mdd<0 else 0:5.2f}")
for n in [100,50,30,20,10]:
    run(n)
