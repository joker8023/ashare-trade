import os; os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E
import risk_control as R
midx = R._index_series("000905")
sig = (midx > midx.rolling(15).mean()).shift(1).astype(float)
df = pd.read_pickle('data/bond_511880.pkl')
b = df.set_index(pd.to_datetime(df['date'])).sort_index()['close'].astype(float)
rb = (b.pct_change() + 0.03/252)
for n,reb in [(25,20),(25,30)]:
    r = E.returns_series("amihud",n_hold=n,rebal=reb,size_range=(0.05,0.30),cost=0.005)
    e = sig.reindex(r.index).ffill().fillna(0.0)
    off = rb.reindex(r.index).ffill().fillna(0.0)
    rr = r*e + off*(1-e) - e.diff().abs().fillna(0)*0.003
    eq=(1+rr).cumprod(); yrs=len(rr)/252
    ann=eq.iloc[-1]**(1/yrs)-1; mdd=(eq/eq.cummax()-1).min()
    vol=rr.std()*np.sqrt(252); sh=rr.mean()*252/vol
    print(f"N={n} R={reb}+债券: 年化{ann:.1%} 回撤{mdd:.1%} 夏普{sh:.2f} Calmar{ann/abs(mdd):.2f}", flush=True)
