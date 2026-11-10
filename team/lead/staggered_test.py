import os; os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import numpy as np, pandas as pd, engine as E
p=E.piv(); c=p["close"]; dates=c.index
adv20=p["amount"].rolling(20,min_periods=10).mean(); seasoned=c.shift(250).notna(); cap=c*p["shares"]
fac=E.FACTORS["amihud_60"](p)
STAR=set(x for x in c.columns if x.startswith(("688","689","4","8","92")))
def sleeve_returns(N,REB,retail,off,cost=0.005):
    rows=[]; prev=set()
    for i in range(300+off,len(dates)-1,REB):
        t,t1=dates[i],dates[i+1]; t2=dates[min(i+1+REB,len(dates)-1)]
        if t2<pd.Timestamp("2025-06-01"): continue
        v=seasoned.loc[t]&(adv20.loc[t]>5e6)&c.loc[t].notna()&fac.loc[t].notna()
        lo,hi=cap.loc[t].quantile(.05),cap.loc[t].quantile(.30)
        v&=((cap.loc[t]>=lo)&(cap.loc[t]<=hi)).fillna(False)
        pool=[x for x in v[v].index if (not retail) or x not in STAR]
        if len(pool)<N: continue
        picks=list(fac.loc[t,pool].nlargest(N).index)
        seg=c.loc[t1:t2,picks].ffill(); nav=seg.div(seg.iloc[0]).mean(axis=1)
        ret=nav.pct_change(fill_method=None).dropna(); cur=set(picks)
        to=1.0 if not prev else len(cur-prev)/max(len(cur),1)
        if len(ret): ret.iloc[0]-=to*2*cost
        rows.append(pd.DataFrame({"date":ret.index,"ret":ret.values})); prev=cur
    d=pd.concat(rows).sort_values("date"); d=d[~d["date"].duplicated()].set_index("date")["ret"]
    return d

def combine(rets_list):
    # 等资金 sleeve，各自复利后平均
    base=pd.Timestamp("2026-01-05")
    eqs=[]
    for r in rets_list:
        e=(1+r).cumprod(); eqs.append(e)
    df=pd.concat(eqs,axis=1).ffill().dropna()
    eq=df.mean(axis=1)
    # 用 2025-12-31 为基
    pre=eq[eq.index<base]; eq0=pre.iloc[-1] if len(pre) else 1.0
    s=eq[eq.index>=base]; s=s/eq0
    tot=s.iloc[-1]-1; mdd=(s/s.cummax()-1).min()
    m=s.resample("ME").last().pct_change().dropna(); m.iloc[0]=s[s.index.month==1].iloc[-1]-1
    # 30 日非重叠块
    idx=list(s.index); blocks=[]
    for k in range(0,len(idx),30):
        b=s.iloc[k:min(k+30,len(idx))]
        if len(b)>=20: blocks.append(b.iloc[-1]/b.iloc[0]-1)
    # 30 日滚动
    roll=(s.shift(-30)/s-1).dropna()
    return dict(total=tot,mdd=mdd,win_month=(m>0).mean(),n_month=len(m),
                block_wr=np.mean([x>0 for x in blocks]),n_block=len(blocks),
                roll_wr=(roll>0).mean())

for N in [5,8]:
    for ns in [1,3,5]:
        step=30//ns
        offs=[-(k*step) for k in range(ns)]
        rets=[sleeve_returns(N,30,True,o) for o in offs]
        m=combine(rets)
        print(f"amihud_60 N{N} R30 retail staggered {ns} sleeves offsets {offs}: total {m['total']:+.1%} mdd {m['mdd']:.1%} mon {m['win_month']:.0%} block {m['block_wr']:.0%}({m['n_block']}) roll30 {m['roll_wr']:.0%}")
    print()
