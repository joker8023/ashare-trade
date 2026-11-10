import os
os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E, strategy_lab as S, combo_lab as C, risk_control as R
p=E.piv(); c=p["close"]
adv20=p["amount"].rolling(20,min_periods=10).mean()
atre=C.get_atr(14); ratio=C.combo_rank("amihud+amount_level")
d0=pd.Timestamp("2015-01-01"); idx=c.index[c.index>=d0]; cols=c.columns
def run(tp, min_adv, cost, label):
    gate=(ratio>=0.75)&(adv20>min_adv)&c.notna()
    buy=(c-0.3*atre).shift(1); sell=buy+tp*atre.shift(1); stop=buy-10*atre.shift(1)
    def cut(x): return x.reindex(index=idx,columns=cols).where(gate.reindex(index=idx,columns=cols))
    mkt=C._market_scale(p,15,"000905")
    eq,tr=S.backtest(p,cut(buy),cut(sell),cut(stop),cost=cost,market_scale=mkt,liquidate_on_off=True)
    r=eq.pct_change(fill_method=None).dropna()
    yrs=len(r)/252; ann=eq.iloc[-1]**(1/yrs)-1
    vol=r.std()*np.sqrt(252); mdd=(eq/eq.cummax()-1).min()
    print(f"{label:32s} 年化{ann:6.1%} 回撤{mdd:7.1%} 夏普{r.mean()*252/vol if vol>0 else 0:5.2f} 交易{len(tr):5d}")
print("=== 缓解方案: 更宽止盈 + 更高流动性门槛 ===")
for tp,adv,cost,lb in [(0.8,20_000_000,0.003,"TP0.8 ADV20M cost0.3%"),
 (1.5,20_000_000,0.003,"TP1.5 ADV20M cost0.3%"),
 (0.8,50_000_000,0.003,"TP0.8 ADV50M cost0.3%"),
 (1.5,50_000_000,0.003,"TP1.5 ADV50M cost0.3%"),
 (1.5,50_000_000,0.005,"TP1.5 ADV50M cost0.5%"),
 (2.0,50_000_000,0.005,"TP2.0 ADV50M cost0.5%")]:
    run(tp,adv,cost,lb)
