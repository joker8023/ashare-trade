"""最强多头(N=25,中证500MA15) + 多空对冲"""
import os
os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E, strategy_lab as S, combo_lab as C, risk_control as R
p=E.piv(); c=p["close"]
adv20=p["amount"].rolling(20,min_periods=10).mean()
atre=C.get_atr(14); ratio=C.combo_rank("amihud+amount_level")
liquid=(adv20>20000000)&c.notna()
gate=(ratio>=0.75)&liquid
d0=pd.Timestamp("2015-01-01"); idx=c.index[c.index>=d0]; cols=c.columns
def cut(x): return x.reindex(index=idx,columns=cols).where(gate.reindex(index=idx,columns=cols))
buy=(c-0.3*atre).shift(1); sell=buy+0.8*atre.shift(1); stop=buy-10*atre.shift(1)
mkt=R._index_series("000905"); ma=mkt.rolling(15).mean()
sig=(mkt>ma).shift(1).astype(float)
# 多头 N=25
eqL,trL=S.backtest(p,cut(buy),cut(sell),cut(stop),cost=0.0015,max_pos=25,market_scale=sig,liquidate_on_off=True)
rL=eqL.pct_change(fill_method=None).dropna()
print(f"多头N=25(中证500MA15): {len(trL)}笔", flush=True)
# 空头腿 N=30
seasoned=c.shift(250).notna(); fac=E.FACTORS["amihud"](p)
rets=[]; prev_l=set(); prev_s=set()
for i in range(300,len(c.index)-60-2,60):
    t=c.index[i]; t1=c.index[i+1]; t2=c.index[min(i+61,len(c.index)-1)]
    valid=seasoned.loc[t]&(adv20.loc[t]>5e6)&c.loc[t].notna()&fac.loc[t].notna()
    cap=c.loc[t]*p["shares"]; lo,hi=cap.quantile(0.05),cap.quantile(0.30)
    valid &= ((cap>=lo)&(cap<=hi)).fillna(False)
    pool=valid[valid].index
    if len(pool)<60: continue
    fv=fac.loc[t,pool]
    longs=list(fv.nlargest(30).index); shorts=list(fv.nsmallest(30).index)
    seg=c.loc[t1:t2,longs+shorts].ffill()
    if len(seg)<2: continue
    rel=seg.div(seg.iloc[0])
    pr=0.5*rel[longs].mean(axis=1).pct_change(fill_method=None)-0.5*rel[shorts].mean(axis=1).pct_change(fill_method=None)
    pr=pr.dropna()
    to=1.0 if not prev_l else (len(set(longs)-prev_l)/30+len(set(shorts)-prev_s)/30)/2
    if len(pr): pr.iloc[0]-=to*0.0015
    prev_l,prev_s=set(longs),set(shorts)
    rets.append(pr)
rS=pd.concat(rets).sort_index(); rS=rS[~rS.index.duplicated(keep=False)]
print(f"空头N=30: 完成", flush=True)
rS.to_pickle("results/pool/ls30_v2.pkl")
ix=rL.index.intersection(rS.index); a=rL.loc[ix]; b=rS.loc[ix]
print(f"相关系数: {a.corr(b):.3f}")
print(f"{'w多头':>6}{'年化':>8}{'回撤':>8}{'夏普':>7}{'Calmar':>7}")
best=None
for w in [0.3,0.4,0.5,0.6,0.7,0.8,1.0]:
    r=w*a+(1-w)*b
    eq=(1+r).cumprod(); yrs=len(r)/252
    ann=eq.iloc[-1]**(1/yrs)-1; mdd=(eq/eq.cummax()-1).min()
    vol=r.std()*np.sqrt(252); sh=r.mean()*252/vol if vol>0 else 0
    cal=ann/abs(mdd) if mdd<0 else 0
    print(f"{w:>6.2f}{ann:>8.1%}{mdd:>8.1%}{sh:>7.2f}{cal:>7.2f}", flush=True)
    if best is None or cal>best[0]: best=(cal,w,ann,mdd,sh)
print(f"最优: w={best[1]:.2f} Calmar{best[0]:.2f} 年化{best[2]:.1%} 回撤{best[3]:.1%} 夏普{best[4]:.2f}")
pd.DataFrame({"ret":w*a+(1-w)*b for w in [best[1]]}).to_csv("results/pool/blend_v4_best.csv")
