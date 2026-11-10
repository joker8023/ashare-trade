"""Lead 前沿图：2026 selectors × N × R，含按笔胜率代理 & 零售池(剔688/689/北交所)"""
import os; os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import numpy as np, pandas as pd
import engine as E
p=E.piv(); c=p["close"]; dates=c.index
adv20=p["amount"].rolling(20,min_periods=10).mean(); seasoned=c.shift(250).notna(); cap=c*p["shares"]
FAC={k:E.FACTORS[k](p) for k in ["amihud","amihud_5","amihud_60","vol20","rev20","turn20","size","amount_level","rev_lowvol","triple","quad"]}
STAR=[x for x in c.columns if x.startswith(("688","689","4","8","92"))]

def run(fac,N,REB,retail):
    rows=[]; trade_wins=[]; trade_n=[]; prev=set()
    for i in range(300,len(dates)-1,REB):
        t,t1=dates[i],dates[i+1]; t2=dates[min(i+1+REB,len(dates)-1)]
        if t1<pd.Timestamp("2025-11-01"): continue
        v=seasoned.loc[t]&(adv20.loc[t]>5e6)&c.loc[t].notna()&fac.loc[t].notna()
        lo,hi=cap.loc[t].quantile(.05),cap.loc[t].quantile(.30)
        v&=((cap.loc[t]>=lo)&(cap.loc[t]<=hi)).fillna(False)
        pool=list(v[v].index)
        if retail: pool=[x for x in pool if x not in STAR]
        if len(pool)<N: continue
        picks=list(fac.loc[t,pool].nlargest(N).index)
        seg=c.loc[t1:t2,picks].ffill()
        if len(seg)<2: continue
        nav=seg.div(seg.iloc[0]).mean(axis=1); ret=nav.pct_change(fill_method=None).dropna()
        cur=set(picks); to=1.0 if not prev else len(cur-prev)/max(len(cur),1)
        if len(ret): ret.iloc[0]-=to*2*0.005
        rows.append(pd.DataFrame({"date":ret.index,"ret":ret.values}))
        # per-trade proxy: stock total return over segment
        sret=(seg.iloc[-1]/seg.iloc[0]-1)
        trade_wins.append((sret>0).sum()); trade_n.append(len(sret))
        prev=cur
    df=pd.concat(rows).sort_values("date"); df=df[~df["date"].duplicated()]
    s=df.set_index("date")["ret"]; s=s[s.index>=pd.Timestamp("2026-01-05")]
    base=df.set_index("date")["ret"]; base=base[base.index<=pd.Timestamp("2025-12-31")]
    eq0=(1+base).prod() if len(base) else 1.0
    eq=eq0*(1+s).cumprod(); tot=eq.iloc[-1]/eq0-1; n=len(s)
    ann=(1+tot)**(252/n)-1 if n else np.nan; mdd=(eq/eq.cummax()-1).min()
    m=eq.resample("ME").last().pct_change().dropna()
    fm=eq[eq.index.month==1]
    if len(fm): m.iloc[0]=fm.iloc[-1]/eq0-1
    return dict(total=tot,ann=ann,mdd=mdd,win_month=(m>0).mean(),
                win_trade=sum(trade_wins)/max(sum(trade_n),1),n_trade=sum(trade_n),n_days=n)

out=[]
for name,fac in FAC.items():
    for N in [3,5,8,12,25]:
        for REB in [7,15,30]:
            for retail in [False,True]:
                try:
                    m=run(fac,N,REB,retail); m.update(sel=name,N=N,R=REB,retail=retail); out.append(m)
                except Exception as e: print("ERR",name,N,REB,retail,e,flush=True)
res=pd.DataFrame(out)
res.to_csv("team/lead/frontier_map.csv",index=False)
pd.set_option("display.width",220)
print("=== 2026 total top 25 ===")
print(res.sort_values("total",ascending=False).head(25).to_string(index=False,float_format=lambda x:f"{x:.3f}"))
print("\n=== 同时 total>=0.6, mdd>=-0.15, win_period? (用 win_month 代理) ===")
sel=res[(res.total>=0.6)&(res.mdd>=-0.15)&(res.win_month>=0.8)]
print(sel.sort_values("total",ascending=False).to_string(index=False,float_format=lambda x:f"{x:.3f}"))
print("\n=== 按笔胜率 top 20 (total>=0.3) ===")
print(res[res.total>=0.3].sort_values("win_trade",ascending=False).head(20).to_string(index=False,float_format=lambda x:f"{x:.3f}"))
