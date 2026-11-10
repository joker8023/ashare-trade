import os; os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E
import risk_control as R
p = E.piv(); c = p["close"]
keep = [x for x in c.columns if not str(x).startswith("688")]
c2 = c[keep]; amt2 = p["amount"][keep]; sh2 = p["shares"].reindex(keep)
adv20 = amt2.rolling(20,min_periods=10).mean()
seasoned = c2.shift(250).notna(); fac = E.FACTORS["amihud"]({"close":c2,"amount":amt2})
dates = c2.index
midx = R._index_series("000905")
sig = (midx > midx.rolling(20).mean()).shift(1).astype(float)
rets=[]; prev=set()
for i in range(300, len(dates)-40-2, 40):
    t,t1 = dates[i], dates[i+1]; t2 = dates[min(i+41,len(dates)-1)]
    valid = seasoned.loc[t]&(adv20.loc[t]>5e6)&c2.loc[t].notna()&fac.loc[t].notna()
    cap = c2.loc[t]*sh2; lo,hi = cap.quantile(0.05),cap.quantile(0.30)
    valid &= ((cap>=lo)&(cap<=hi)).fillna(False)
    pool = valid[valid].index
    if len(pool)<25: continue
    picks = list(fac.loc[t,pool].nlargest(25).index)
    seg = c2.loc[t1:t2,picks].ffill()
    if len(seg)<2: continue
    pr = seg.div(seg.iloc[0]).mean(axis=1).pct_change(fill_method=None).dropna()
    cur=set(picks); to=1.0 if not prev else len(cur-prev)/25
    if len(pr): pr.iloc[0]-=to*0.005
    prev=cur; rets.append(pr)
r = pd.concat(rets).sort_index(); r=r[~r.index.duplicated(keep="first")]
rr=(r*sig.reindex(r.index).ffill().fillna(0.0)).dropna()
eq=(1+rr).cumprod(); yrs=len(rr)/252
ann=eq.iloc[-1]**(1/yrs)-1; mdd=(eq/eq.cummax()-1).min()
vol=rr.std()*np.sqrt(252); sh=rr.mean()*252/vol
print(f"剔除科创板纯多头MA20: 年化{ann:.1%} 回撤{mdd:.1%} 夏普{sh:.2f} Calmar{ann/abs(mdd):.2f}", flush=True)
r.to_pickle("results/pool/long_N25_no688_05.pkl")
