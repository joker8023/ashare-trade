import os, itertools
os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E
import longshort_test as L

p,c,adv20,seasoned,fac = L.load()
import strategy_lab as S
import combo_lab as C

def run_ls(n_hold=100, rebal=60, size=(0.05,0.30), use_timing=False):
    dates=c.index; codes=c.columns
    rets=[]; prev_l=set(); prev_s=set()
    for i in range(300, len(dates)-rebal-2, rebal):
        t=dates[i]; t1=dates[i+1]; t2=dates[min(i+1+rebal,len(dates)-1)]
        valid=seasoned.loc[t]&(adv20.loc[t]>5e6)&c.loc[t].notna()&fac.loc[t].notna()
        cap=c.loc[t]*p["shares"]
        lo,hi=cap.quantile(size[0]),cap.quantile(size[1])
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
        to=1.0 if not prev_l else (len(set(longs)-prev_l)/n_hold+len(set(shorts)-prev_s)/n_hold)/2
        if len(pr): pr.iloc[0]-=to*2*0.0015
        prev_l,prev_s=set(longs),set(shorts)
        rets.append(pr)
    r=pd.concat(rets).sort_index(); r=r[~r.index.duplicated(keep=False)]
    if use_timing:
        idx=R_idx(); sig=(idx>idx.rolling(20).mean()).shift(1).astype(float)
        m=sig.reindex(r.index).ffill().fillna(0).values
        r=r*m
    return r

def R_idx():
    import risk_control as R
    return R._index_series("000852")

def st(r,lb):
    eq=(1+r).cumprod(); yrs=len(r)/252
    ann=eq.iloc[-1]**(1/yrs)-1; vol=r.std()*np.sqrt(252); mdd=(eq/eq.cummax()-1).min()
    sh=r.mean()*252/vol if vol>0 else 0
    print(f"{lb:28s} 年化{ann:6.1%} 回撤{mdd:7.1%} 夏普{sh:5.2f} Calmar{ann/abs(mdd) if mdd<0 else 0:5.2f}")
    return ann,mdd

print("=== 集中度 × 择时 ===")
for n in [100,50,30]:
    for timing in [False,True]:
        r=run_ls(n_hold=n,use_timing=timing)
        st(r,f"N={n} 择时={'开' if timing else '关'}")
