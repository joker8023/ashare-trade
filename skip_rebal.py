import os; os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E
import risk_control as R
p = E.piv(); c = p["close"]
adv20 = p["amount"].rolling(20,min_periods=10).mean()
seasoned = c.shift(250).notna(); fac = E.FACTORS["amihud"](p)
dates = c.index
midx = R._index_series("000905")
sig = (midx > midx.rolling(15).mean()).shift(1)
N, REB = 100, 90
rets=[]; holds=None; cash=False
for i in range(300, len(dates)-2):
    t = dates[i]
    if (i-300) % REB == 0 and i < len(dates)-REB-2:
        s = sig.loc[t] if t in sig.index else 1.0
        if s == 1.0 or holds is None:
            valid = seasoned.loc[t]&(adv20.loc[t]>5e6)&c.loc[t].notna()&fac.loc[t].notna()
            cap = c.loc[t]*p["shares"]; lo,hi = cap.quantile(0.05),cap.quantile(0.30)
            valid &= ((cap>=lo)&(cap<=hi)).fillna(False)
            pool = valid[valid].index
            if len(pool)>=N:
                new = set(fac.loc[t,pool].nlargest(N).index)
                to = 1.0 if holds is None else len(new-holds)/N
                holds = new
            else:
                to = 0.0
        else:
            to = 0.0  # 信号为0时跳过调仓,不交易
        t1 = dates[i+1]
    if holds is None: continue
    s = sig.loc[t] if t in sig.index else 1.0
    dayret = (c.loc[dates[i+1], list(holds)]/c.loc[t, list(holds)]-1).mean() if s==1.0 else 0.0
    rets.append((dates[i+1], dayret, to if (i-300)%REB==0 and i < len(dates)-REB-2 else 0.0))
df = pd.DataFrame(rets, columns=["date","ret","to"]).set_index("date")
df["ret"] = df["ret"] - df["to"]*0.005
# 切换成本:持仓↔现金
e = sig.reindex(df.index).ffill().fillna(0.0)
df["ret"] = df["ret"] - e.diff().abs().fillna(0)*0.003
r = df["ret"].dropna()
eq=(1+r).cumprod(); yrs=len(r)/252
ann=eq.iloc[-1]**(1/yrs)-1; mdd=(eq/eq.cummax()-1).min()
vol=r.std()*np.sqrt(252); sh=r.mean()*252/vol
print(f"跳过熊市调仓: 年化{ann:.1%} 回撤{mdd:.1%} 夏普{sh:.2f} Calmar{ann/abs(mdd):.2f}", flush=True)
print(f"调仓次数: {(df['to']>0).sum()}, 总换手成本: {(df['to']*0.005).sum():.2%}", flush=True)
