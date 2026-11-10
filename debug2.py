import os
os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E, combo_lab as C, strategy_lab as S
p=E.piv(); c=p["close"]
adv20=p["amount"].rolling(20,min_periods=10).mean()
atre=C.get_atr(14); ratio=C.combo_rank("amihud+amount_level")
liquid=(adv20>20000000)&c.notna(); gate=(ratio>=0.75)&liquid
d0=pd.Timestamp("2015-01-01"); idx=c.index[c.index>=d0]; cols=c.columns
def cut(x): return x.reindex(index=idx,columns=cols).where(gate.reindex(index=idx,columns=cols))
buy=(c-0.3*atre).shift(1); sell=buy+0.8*atre.shift(1); stop=buy-10*atre.shift(1)
print("=== A: 无择时 ===")
eq,tr=S.backtest(p,cut(buy),cut(sell),cut(stop),cost=0.0015)
print(f"交易数: {len(tr)}, 最终净值: {eq.iloc[-1]:.2f}" if len(eq)>0 else "无净值")
print("=== B: 有择时 ===")
mkt=C._market_scale(p,15,"000852")
eq2,tr2=S.backtest(p,cut(buy),cut(sell),cut(stop),cost=0.0015,market_scale=mkt,liquidate_on_off=True)
print(f"交易数: {len(tr2)}, 最终净值: {eq2.iloc[-1]:.2f}" if len(eq2)>0 else "无净值")
