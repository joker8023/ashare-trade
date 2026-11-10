import os
os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E
p=E.piv(); c=p["close"]
adv20=p["amount"].rolling(20,min_periods=10).mean()
seasoned=c.shift(250).notna()
fac=E.FACTORS["amihud"](p)
dates=c.index

def run_ls(n_hold=100, long_size=(0.05,0.30), short_size=None, rebal=60, label=""):
    rets=[]; prev_l=set(); prev_s=set()
    for i in range(300, len(dates)-rebal-2, rebal):
        t=dates[i]; t1=dates[i+1]; t2=dates[min(i+1+rebal,len(dates)-1)]
        valid=seasoned.loc[t]&(adv20.loc[t]>5e6)&c.loc[t].notna()&fac.loc[t].notna()
        cap=c.loc[t]*p["shares"]
        lo,hi=cap.quantile(long_size[0]),cap.quantile(long_size[1])
        lv=valid&((cap>=lo)&(cap<=hi)).fillna(False)
        pool=lv[lv].index
        if len(pool)<n_hold: continue
        longs=list(fac.loc[t,pool].nlargest(n_hold).index)
        # 空头池
        if short_size is None:
            sv=valid
        else:
            a,b=cap.quantile(short_size[0]),cap.quantile(short_size[1])
            sv=valid&((cap>=a)&(cap<=b)).fillna(False)
        spool=sv[sv].index
        if len(spool)<n_hold: continue
        shorts=list(fac.loc[t,spool].nsmallest(n_hold).index)
        seg=c.loc[t1:t2,longs+shorts].ffill()
        if len(seg)<2: continue
        rel=seg.div(seg.iloc[0])
        pr=0.5*rel[longs].mean(axis=1).pct_change(fill_method=None)-0.5*rel[shorts].mean(axis=1).pct_change(fill_method=None)
        pr=pr.dropna()
        to=1.0 if not prev_l else (len(set(longs)-prev_l)/n_hold+len(set(shorts)-prev_s)/n_hold)/2
        if len(pr): pr.iloc[0]-=to*2*0.0015
        prev_l,prev_s=set(longs),set(shorts)
        rets.append(pr)
    r=pd.concat(rets).sort_index(); r=r[~r.index.duplicated(keep=False)]
    eq=(1+r).cumprod(); yrs=len(r)/252
    ann=eq.iloc[-1]**(1/yrs)-1; vol=r.std()*np.sqrt(252); mdd=(eq/eq.cummax()-1).min()
    print(f"{label:44s} 年化{ann:6.1%} 回撤{mdd:7.1%} 夏普{r.mean()*252/vol if vol>0 else 0:5.2f} Calmar{ann/abs(mdd) if mdd<0 else 0:5.2f}")
    return r

print("=== 空头池对比 (多头固定:小盘不流动) ===")
run_ls(100,(0.05,0.30),None,60,"空头=同池最流动")
run_ls(100,(0.05,0.30),(0.70,1.0),60,"空头=大盘股市值70-100%最流动")
run_ls(100,(0.05,0.30),(0.50,1.0),60,"空头=大盘股市值50-100%最流动")
run_ls(50,(0.05,0.30),None,60,"N=50 空头=同池最流动")
run_ls(50,(0.05,0.30),(0.70,1.0),60,"N=50 空头=大盘股最流动")
