import os; os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import numpy as np, pandas as pd, engine as E, risk_control as R
p=E.piv(); c=p["close"]; dates=c.index
adv20=p["amount"].rolling(20,min_periods=10).mean(); seasoned=c.shift(250).notna(); cap=c*p["shares"]
fac=E.FACTORS["amihud_60"](p)
STAR=set(x for x in c.columns if x.startswith(("688","689","4","8","92")))
idx=R._index_series("000852").reindex(dates).ffill()
def run(N=5,REB=30,timing="none",param=20,ddtrig=None,cost=0.005):
    rows=[]; prev=set(); eq=1.0; peak=1.0; state=1.0; rets=[]
    segs=[]
    for i in range(300,len(dates)-1,REB):
        t,t1=dates[i],dates[i+1]; t2=dates[min(i+1+REB,len(dates)-1)]
        if t1<pd.Timestamp("2025-06-01"): continue
        on=True
        if timing=="ma":
            on=bool(idx.loc[t] > idx.rolling(param).mean().loc[t])  # t close known, exec t+1
        if timing=="lastret" and len(segs)>0:
            on=segs[-1]["ret"] > -0.05
        if timing=="dd" and ddtrig is not None:
            dd=eq/peak-1
            if state and dd<=-ddtrig: state=0
            elif (not state) and dd>=-ddtrig/2: state=1
            on=bool(state)
        v=seasoned.loc[t]&(adv20.loc[t]>5e6)&c.loc[t].notna()&fac.loc[t].notna()
        lo,hi=cap.loc[t].quantile(.05),cap.loc[t].quantile(.30)
        v&=((cap.loc[t]>=lo)&(cap.loc[t]<=hi)).fillna(False)
        pool=[x for x in v[v].index if x not in STAR]
        picks=list(fac.loc[t,pool].nlargest(N).index) if on and len(pool)>=N else []
        if picks:
            seg=c.loc[t1:t2,picks].ffill(); nav=seg.div(seg.iloc[0]).mean(axis=1)
            ret=nav.pct_change(fill_method=None).dropna(); cur=set(picks)
            to=1.0 if not prev else len(cur-prev)/max(len(cur),1)
            if len(ret): ret.iloc[0]-=to*2*cost
            prev=cur
        else:
            ret=pd.Series(0.0,index=c.loc[t1:t2].index)
            prev=set()
        for d,x in ret.items():
            pass
        segs.append(dict(t1=t1,t2=ret.index[-1],ret=(1+ret).prod()-1,on=on))
        rows.append(pd.DataFrame({"date":ret.index,"ret":ret.values}))
        eq=(1+ret).reindex(ret.index).cumprod().iloc[-1]*0+ (1+ret).prod()  # placeholder
    d=pd.concat(rows).sort_values("date"); d=d[~d["date"].duplicated()].set_index("date")["ret"]
    # proper equity
    e=(1+d).cumprod(); pre=e[e.index<=pd.Timestamp("2025-12-31")]; eq0=pre.iloc[-1] if len(pre) else 1.0
    s=e[e.index>=pd.Timestamp("2026-01-05")]/eq0
    tot=s.iloc[-1]-1; mdd=(s/s.cummax()-1).min()
    m=s.resample("ME").last().pct_change().dropna(); m.iloc[0]=s[s.index.month==1].iloc[-1]-1
    seg26=[x for x in segs if x["t1"]>=pd.Timestamp("2026-01-05") and x["t1"]<=pd.Timestamp("2026-11-04")]
    comp=[x for x in seg26 if len(d[(d.index>=x["t1"])&(d.index<=x["t2"])])>=REB*0.8]
    wp=np.mean([x["ret"]>0 for x in comp])
    print(f"N{N} R{REB} timing={timing}{param if timing=='ma' else ''}{ddtrig or ''}: total {tot:+.1%} mdd {mdd:.1%} mon {(m>0).sum()}/{len(m)} winp {wp:.0%} ({sum(x['ret']>0 for x in comp)}/{len(comp)})")
for param in [10,15,20,30]:
    run(timing="ma",param=param)
for dd in [0.05,0.08,0.10,0.12]:
    run(timing="dd",ddtrig=dd)
run(timing="lastret")
run(timing="none")
