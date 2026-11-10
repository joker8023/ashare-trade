"""状态依赖的动态组合权重"""
import pandas as pd, numpy as np, os
os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import risk_control as R
long_r = pd.read_pickle("results/pool/blend_N25_LS30_best.pkl") if False else None
# 用blend_v3的组件重建:多头+空头
import engine as E, strategy_lab as S, combo_lab as C
p=E.piv(); c=p["close"]
adv20=p["amount"].rolling(20,min_periods=10).mean()
atre=C.get_atr(14); ratio=C.combo_rank("amihud+amount_level")
liquid=(adv20>20000000)&c.notna()
gate=(ratio>=0.75)&liquid
d0=pd.Timestamp("2015-01-01"); idx=c.index[c.index>=d0]; cols=c.columns
def cut(x): return x.reindex(index=idx,columns=cols).where(gate.reindex(index=idx,columns=cols))
buy=(c-0.3*atre).shift(1); sell=buy+0.8*atre.shift(1); stop=buy-10*atre.shift(1)
mkt=C._market_scale(p,15,"000905")
eqL,_=S.backtest(p,cut(buy),cut(sell),cut(stop),cost=0.0015,max_pos=25,market_scale=mkt,liquidate_on_off=True)
rL=eqL.pct_change(fill_method=None).dropna()
# 空头腿(缓存或重算)
import pickle, os
cf="results/pool/ls30_for_regime.pkl"
if os.path.exists(cf):
    rS=pd.read_pickle(cf)
else:
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
    rS.to_pickle(cf)
ix=rL.index.intersection(rS.index); a=rL.loc[ix]; b=rS.loc[ix]
# 状态变量: 中证500相对MA15的偏离度
midx=R._index_series("000905"); ma=midx.rolling(15).mean()
dev=(midx/ma-1).reindex(ix).fillna(0)
def run(w_func, label):
    w = w_func(dev)
    r = w*a.values+(1-w.values)*b.values
    r = pd.Series(r,index=ix)
    eq=(1+r).cumprod(); yrs=len(r)/252
    ann=eq.iloc[-1]**(1/yrs)-1; mdd=(eq/eq.cummax()-1).min()
    vol=r.std()*np.sqrt(252); sh=r.mean()*252/vol if vol>0 else 0
    print(f"{label:28s} 年化{ann:6.1%} 回撤{mdd:7.1%} 夏普{sh:5.2f} Calmar{ann/abs(mdd) if mdd<0 else 0:5.2f}", flush=True)
print("=== 状态依赖权重 vs 固定权重 ===")
run(lambda d: pd.Series(0.5,index=d.index),"固定50/50")
run(lambda d: (0.3+0.4*(d>0).astype(float)),"牛0.7熊0.3(MA上下)")
run(lambda d: (0.2+0.6*((d-d.quantile(0.1))/(d.quantile(0.9)-d.quantile(0.1))).clip(0,1)),"连续偏离度加权")
run(lambda d: (0.35+0.3*np.tanh(d*20)),"tanh平滑切换")
