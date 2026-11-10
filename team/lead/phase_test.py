import os; os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import numpy as np, pandas as pd, engine as E
p=E.piv(); c=p["close"]; dates=c.index
adv20=p["amount"].rolling(20,min_periods=10).mean(); seasoned=c.shift(250).notna(); cap=c*p["shares"]
fac=E.FACTORS["amihud_60"](p)
STAR=set(x for x in c.columns if x.startswith(("688","689","4","8","92")))
def run(N,REB,retail,off,cost=0.005):
    segs=[]; prev=set(); daily=[]
    for i in range(300+off,len(dates)-1,REB):
        t,t1=dates[i],dates[i+1]; t2=dates[min(i+1+REB,len(dates)-1)]
        if t1<pd.Timestamp("2025-12-01"): continue
        v=seasoned.loc[t]&(adv20.loc[t]>5e6)&c.loc[t].notna()&fac.loc[t].notna()
        lo,hi=cap.loc[t].quantile(.05),cap.loc[t].quantile(.30)
        v&=((cap.loc[t]>=lo)&(cap.loc[t]<=hi)).fillna(False)
        pool=[x for x in v[v].index if (not retail) or x not in STAR]
        picks=list(fac.loc[t,pool].nlargest(N).index)
        seg=c.loc[t1:t2,picks].ffill(); nav=seg.div(seg.iloc[0]).mean(axis=1)
        ret=nav.pct_change(fill_method=None).dropna(); cur=set(picks)
        to=1.0 if not prev else len(cur-prev)/max(len(cur),1)
        if len(ret): ret.iloc[0]-=to*2*cost
        daily.append(pd.DataFrame({"date":ret.index,"ret":ret.values}))
        segs.append(dict(t1=t1,t2=seg.index[-1],ret=nav.iloc[-1]-1))
        prev=cur
    d=pd.concat(daily).sort_values("date"); d=d[~d["date"].duplicated()].set_index("date")["ret"]
    base=d[d.index<=pd.Timestamp("2025-12-31")]; s=d[d.index>=pd.Timestamp("2026-01-05")]
    eq0=(1+base).prod(); eq=eq0*(1+s).cumprod(); tot=eq.iloc[-1]/eq0-1
    mdd=(eq/eq.cummax()-1).min(); n=len(s); ann=(1+tot)**(252/n)-1
    m=eq.resample("ME").last().pct_change().dropna(); m.iloc[0]=eq[eq.index.month==1].iloc[-1]/eq0-1
    seg26=[x for x in segs if x["t1"]>=pd.Timestamp("2026-01-05") and x["t1"]<=pd.Timestamp("2026-11-04")]
    comp=[x for x in seg26 if len(d[(d.index>=x["t1"])&(d.index<=x["t2"])])>=REB*0.8]
    wp=sum(x['ret']>0 for x in comp)/len(comp) if comp else np.nan
    return tot,ann,mdd,(m>0).sum(),len(m),wp,len(comp)
print("phase  total   ann    mdd   mon  wp   n")
for N in [3,5,8]:
    for REB in [15,30]:
        for off in [-10,-5,0,5,10]:
            tot,ann,mdd,wm,nm,wp,np_=run(N,REB,True,off)
            print(f"amihud_60 N{N} R{REB} off{off:+3d}  {tot:+.1%} {ann:+.1%} {mdd:.1%} {wm}/{nm} {wp:.0%} {np_}")
    print()
