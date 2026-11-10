import os
os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E, strategy_lab as S, combo_lab as C, risk_control as R
p=E.piv(); c=p["close"]
adv20=p["amount"].rolling(20,min_periods=10).mean()
atre=C.get_atr(14); ratio=C.combo_rank("amihud+amount_level")
liquid=(adv20>20000000)&c.notna()
gate=(ratio>=0.75)&liquid
d0=pd.Timestamp("2015-01-01"); idx=c.index[c.index>=d0]; cols=c.columns
buy=(c-0.3*atre).shift(1); sell=buy+0.8*atre.shift(1); stop=buy-10*atre.shift(1)
def cut(x): return x.reindex(index=idx,columns=cols).where(gate.reindex(index=idx,columns=cols))
mkt=C._market_scale(p,15,"000905")
for cost in [0.0015, 0.003, 0.005, 0.008, 0.01]:
    eq,tr=S.backtest(p,cut(buy),cut(sell),cut(stop),cost=cost,market_scale=mkt,liquidate_on_off=True)
    r=eq.pct_change(fill_method=None).dropna()
    yrs=len(r)/252; ann=eq.iloc[-1]**(1/yrs)-1
    vol=r.std()*np.sqrt(252); mdd=(eq/eq.cummax()-1).min()
    print(f"单边成本{cost*100:4.2f}%  年化{ann:6.1%} 回撤{mdd:7.1%} 夏普{r.mean()*252/vol if vol>0 else 0:5.2f} 交易{len(tr)}")
