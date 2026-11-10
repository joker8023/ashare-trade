"""动态仓位管理: 回撤加深渐进降仓 + 波动率目标"""
import pandas as pd, numpy as np, os
os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
S = pd.read_pickle("results/wf_blend/blend_series.pkl")
a, b = S["long"].copy(), S["ls30"].copy()
ix = a.index.intersection(b.index); a, b = a.loc[ix], b.loc[ix]
base = 0.35*a + 0.65*b

def stats(r, lb):
    eq=(1+r).cumprod(); yrs=len(r)/252
    ann=eq.iloc[-1]**(1/yrs)-1; vol=r.std()*np.sqrt(252); mdd=(eq/eq.cummax()-1).min()
    sh=r.mean()*252/vol if vol>0 else 0
    return dict(策略=lb, 年化=ann, 回撤=mdd, 夏普=sh, Calmar=ann/abs(mdd) if mdd<0 else 0)

rows=[stats(base,"基准(固定35/65)")]
# 1. 回撤渐进降仓
for dd_lo, floor in [(-0.15,0.3),(-0.12,0.4),(-0.10,0.5)]:
    eq=(1+base).cumprod(); dd=(eq/eq.cummax()-1).shift(1).fillna(0)
    # DD>-5%满仓, DD<dd_lo降到floor, 之间线性
    sc = np.where(dd>-0.05, 1.0, np.where(dd<dd_lo, floor, 1-(1-floor)*(dd+0.05)/(dd_lo+0.05)))
    r = base*pd.Series(sc,index=base.index)
    rows.append(stats(r, f"回撤降仓({dd_lo:.0%}→{floor:.0%})"))
# 2. 波动率目标
for tgt in [0.15, 0.12, 0.10]:
    rv = base.rolling(20).std()*np.sqrt(252)
    sc = (tgt/rv).clip(upper=1.0).shift(1).fillna(1.0)
    r = base*sc
    rows.append(stats(r, f"波动目标{tgt:.0%}"))
# 3. 两者叠加
eq=(1+base).cumprod(); dd=(eq/eq.cummax()-1).shift(1).fillna(0)
sc_dd = np.where(dd>-0.05, 1.0, np.where(dd<-0.15, 0.3, 1-0.7*(dd+0.05)/(-0.10)))
rv = base.rolling(20).std()*np.sqrt(252)
sc_vol = (0.15/rv).clip(upper=1.0).shift(1).fillna(1.0)
r = base*pd.Series(np.minimum(sc_dd,sc_vol.values),index=base.index)
rows.append(stats(r, "回撤降仓+波目标"))

df=pd.DataFrame(rows).sort_values("Calmar",ascending=False)
for c in ["年化","回撤"]:
    df[c]=df[c].map(lambda x:f"{x:.1%}")
df["夏普"]=df["夏普"].map(lambda x:f"{x:.2f}")
df["Calmar"]=df["Calmar"].map(lambda x:f"{x:.2f}")
print(df.to_string(index=False))
