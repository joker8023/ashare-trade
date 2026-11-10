import os; os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E
import risk_control as R
p = E.piv(); c = p["close"]
adv20 = p["amount"].rolling(20,min_periods=10).mean()
seasoned = c.shift(250).notna(); fac = E.FACTORS["amihud"](p)
dates = c.index
midx = R._index_series("000905")
sig = (midx > midx.rolling(20).mean()).shift(1).astype(float)
for minadv in [2e6, 5e6, 1e7, 2e7]:
    rets=[]; prev=set()
    for i in range(300, len(dates)-40-2, 40):
        t,t1 = dates[i], dates[i+1]; t2 = dates[min(i+41,len(dates)-1)]
        valid = seasoned.loc[t]&(adv20.loc[t]>minadv)&c.loc[t].notna()&fac.loc[t].notna()
        cap = c.loc[t]*p["shares"]; lo,hi = cap.quantile(0.05),cap.quantile(0.30)
        valid &= ((cap>=lo)&(cap<=hi)).fillna(False)
        pool = valid[valid].index
        if len(pool)<25: continue
        picks = list(fac.loc[t,pool].nlargest(25).index)
        seg = c.loc[t1:t2,picks].ffill()
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
    print(f"min_adv={minadv/1e6:.0f}M: 年化{ann:.1%} 回撤{mdd:.1%} 夏普{sh:.2f} Calmar{ann/abs(mdd):.2f}", flush=True)
