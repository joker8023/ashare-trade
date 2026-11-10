"""检查动态权重是否存在未来函数:对比不shift(错误) vs shift(1)(正确)"""
import pandas as pd, numpy as np, os
os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import risk_control as R
from combo_lab import get_atr, combo_rank
import engine as E, strategy_lab as S
p=E.piv(); c=p["close"]
adv20=p["amount"].rolling(20,min_periods=10).mean()
atre=get_atr(14); ratio=combo_rank("amihud+amount_level")
liquid=(adv20>20000000)&c.notna()
gate=(ratio>=0.75)&liquid
d0=pd.Timestamp("2015-01-01"); idx=c.index[c.index>=d0]; cols=c.columns
def cut(x): return x.reindex(index=idx,columns=cols).where(gate.reindex(index=idx,columns=cols))
buy=(c-0.3*atre).shift(1); sell=buy+0.8*atre.shift(1); stop=buy-10*atre.shift(1)
mkt=R._index_series("000905"); ma=mkt.rolling(15).mean()
sig=(mkt>ma).astype(float)
eqL,_=S.backtest(p,cut(buy),cut(sell),cut(stop),cost=0.0015,max_pos=25,market_scale=sig,liquidate_on_off=True)
rL=eqL.pct_change(fill_method=None).dropna()
# 空头腿(缓存或快速重算N=30,简化版:用已存)
import glob
rS=pd.read_pickle("results/pool/ls_N30.pkl") if False else None
# 用blend_v3的空头逻辑快速构建
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
ix=rL.index.intersection(rS.index); a=rL.loc[ix]; b=rS.loc[ix]
dev=(mkt/mkt.rolling(15).mean()-1).reindex(ix).fillna(0)
def show(w,lb):
    r=(w*a.values+(1-w.values)*b.values); r=pd.Series(r,index=ix)
    eq=(1+r).cumprod(); yrs=len(r)/252
    ann=eq.iloc[-1]**(1/yrs)-1; mdd=(eq/eq.cummax()-1).min()
    vol=r.std()*np.sqrt(252); sh=r.mean()*252/vol if vol>0 else 0
    print(f"{lb:28s} 年化{ann:6.1%} 回撤{mdd:7.1%} 夏普{sh:5.2f} Calmar{ann/abs(mdd) if mdd<0 else 0:5.2f}", flush=True)
print("=== 有未来函数(错误版, w用当日信号) ===")
show((0.2+0.6*((dev-dev.quantile(0.1))/(dev.quantile(0.9)-dev.quantile(0.1))).clip(0,1)),"连续偏离度(未shift)")
print("=== 修正版(信号shift一天) ===")
dev_s=dev.shift(1).fillna(0)
show((0.2+0.6*((dev_s-dev_s.quantile(0.1))/(dev_s.quantile(0.9)-dev_s.quantile(0.1))).clip(0,1)),"连续偏离度(shift1)")
show(pd.Series(np.where(dev_s>0,0.7,0.3),index=ix),"牛0.7熊0.3(shift1)")

print("\n=== 彻底修正版(分位数也只用历史数据) ===")
# 用expanding分位数: 每天只用当天及以前的数据算分位
exp_q10 = dev_s.expanding(min_periods=252).quantile(0.1)
exp_q90 = dev_s.expanding(min_periods=252).quantile(0.9)
norm = ((dev_s - exp_q10) / (exp_q90 - exp_q10)).clip(0, 1).fillna(0.5)
w_dyn = 0.2 + 0.6 * norm
r = (w_dyn.values * a.values + (1 - w_dyn.values) * b.values)
r = pd.Series(r, index=ix)
eq = (1 + r).cumprod(); yrs = len(r) / 252
ann = eq.iloc[-1] ** (1 / yrs) - 1; mdd = (eq / eq.cummax() - 1).min()
vol = r.std() * np.sqrt(252); sh = r.mean() * 252 / vol if vol > 0 else 0
print(f"动态权重(无未来函数) 年化{ann:.1%} 回撤{mdd:.1%} 夏普{sh:.2f} Calmar{ann/abs(mdd) if mdd<0 else 0:.2f}")
# 分段验证
for label, s in [("前半", r[r.index < "2021-01-01"]), ("后半", r[r.index >= "2021-01-01"])]:
    eq2 = (1 + s).cumprod(); yrs2 = len(s) / 252
    a2 = eq2.iloc[-1] ** (1 / yrs2) - 1; m2 = (eq2 / eq2.cummax() - 1).min()
    print(f"  {label}: 年化{a2:.1%} 回撤{m2:.1%}")
