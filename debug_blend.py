"""定位 blend_v2 零成交原因"""
import os
os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E, combo_lab as C

p = E.piv(); c = p["close"]
adv20 = p["amount"].rolling(20, min_periods=10).mean()
atr = C.get_atr(14)
ratio = C.combo_rank("amihud+amount_level")
liquid = (adv20 > 20000000) & c.notna()
gate = (ratio >= 0.75) & liquid
d0 = pd.Timestamp("2015-01-01")
idx = c.index[c.index >= d0]
cols = c.columns

buy = (c - 0.3 * atr).shift(1)
sell = buy + 0.8 * atr.shift(1)
stop = buy - 10 * atr.shift(1)

b = buy.reindex(index=idx, columns=cols).where(gate.reindex(index=idx, columns=cols))
s = sell.reindex(index=idx, columns=cols).where(gate.reindex(index=idx, columns=cols))

print("买入价有效比例:", float(b.notna().mean().mean()))
print("卖出价有效比例:", float(s.notna().mean().mean()))

# 检查某一天的买入触发数
t = idx[300]
o = p["open"].loc[t]; lo = p["low"].loc[t]; bp = b.loc[t]
trig = (lo <= bp) & bp.notna() & o.notna() & (o > 0)
print(f"{t.date()} 触发买入信号数:", int(trig.sum()))

# 检查 mkt
mkt = C._market_scale(p, 15, "000852")
print("mkt类型:", type(mkt), "长度:", len(mkt))
print("mkt最新5个:", mkt.tail(5).tolist() if hasattr(mkt,'tail') else mkt[-5:])
print("mkt均值:", float(np.nanmean(mkt.values if hasattr(mkt,'values') else mkt)))
