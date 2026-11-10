"""最终组合测试: 最优多头(N=25) + 多空对冲,干净实现"""
import os
os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E, strategy_lab as S, combo_lab as C

p=E.piv(); c=p["close"]
adv20=p["amount"].rolling(20,min_periods=10).mean()
atre=C.get_atr(14); ratio=C.combo_rank("amihud+amount_level")
liquid=(adv20>20000000)&c.notna()
gate=(ratio>=0.75)&liquid
d0=pd.Timestamp("2015-01-01"); idx=c.index[c.index>=d0]; cols=c.columns
def cut(x): return x.reindex(index=idx,columns=cols).where(gate.reindex(index=idx,columns=cols))
buy=(c-0.3*atre).shift(1); sell=buy+0.8*atre.shift(1); stop=buy-10*atre.shift(1)
mkt=C._market_scale(p,15,"000852")

# 多头腿(三种集中度)
for npos,tag in [(50,"N50"),(30,"N30"),(25,"N25")]:
    import strategy_lab as SL
    orig_max = SL.MAX_POS
    SL.MAX_POS = npos
    try:
        eq,tr=S.backtest(p,cut(buy),cut(sell),cut(stop),cost=0.0015,market_scale=mkt,liquidate_on_off=True)
        r=eq.pct_change(fill_method=None).dropna()
        r.to_pickle(f"results/pool/long_{tag}.pkl")
        yrs=len(r)/252; ann=eq.iloc[-1]**(1/yrs)-1; mdd=(eq/eq.cummax()-1).min()
        print(f"多头{tag}: {len(tr)}笔 年化{ann:.1%} 回撤{mdd:.1%} (已存)", flush=True)
    finally:
        SL.MAX_POS = orig_max
print("DONE")
