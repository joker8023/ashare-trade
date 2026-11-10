import os
os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E, risk_control as R, strategy_lab as S, combo_lab as C
p=E.piv(); c=p["close"]
adv20=p["amount"].rolling(20,min_periods=10).mean()
idx=R._index_series("000852"); ma=idx.rolling(15).mean()
msig=(idx>ma).shift(1).astype(float)
COST=0.005
def stat(r,lb):
    eq=(1+r).cumprod(); yrs=len(r)/252
    ann=eq.iloc[-1]**(1/yrs)-1; vol=r.std()*np.sqrt(252); mdd=(eq/eq.cummax()-1).min()
    sh=r.mean()*252/vol if vol>0 else 0
    return dict(策略=lb,年化=ann,回撤=mdd,夏普=sh,Calmar=ann/abs(mdd) if mdd<0 else 0)
rows=[]
# 因子策略
for f in ["amihud","amount_level","size","size_rev","rev60","turn20","vol20","max20"]:
    try:
        r=E.returns_series(f,n_hold=50,rebal=60,size_range=(0.05,0.30),cost=COST)
        on=msig.reindex(r.index).ffill().fillna(0)
        rows.append(stat(r*on, f"因子:{f}+MA15"))
    except Exception as e: print(f, "失败", str(e)[:50])
# 价位策略(宽止盈降换手)
atr=C.get_atr(14); ratio=C.combo_rank("amihud+amount_level")
liquid=(adv20>20000000)&c.notna()
gate=(ratio>=0.75)&liquid
d0=pd.Timestamp("2015-01-01"); idx2=c.index[c.index>=d0]; cols=c.columns
def cut(x): return x.reindex(index=idx2,columns=cols).where(gate.reindex(index=idx2,columns=cols))
ms=C._market_scale(p,15,"000905")
for name,fn in [("价位:固定回调+8%",lambda: S.s03_fixed(p,0.03,0.08)),
                ("价位:网格±3%",lambda: S.s01_grid(p,0.03)),
                ("价位:均线回踩+6%",lambda: S.s05_ma_pullback(p,20,0.06))]:
    try:
        buy,sell,stop=fn()
        eq,tr=S.backtest(p,cut(buy),cut(sell),cut(stop),cost=COST,market_scale=ms,liquidate_on_off=True)
        r=eq.pct_change(fill_method=None).dropna()
        rows.append(stat(r,name))
        print(f"{name} 完成 {len(tr)}笔")
    except Exception as e: print(name,"失败",str(e)[:80])
df=pd.DataFrame(rows).sort_values("Calmar",ascending=False)
for c_ in ["年化","回撤"]:
    df[c_]=df[c_].map(lambda x:f"{x:.1%}")
df["夏普"]=df["夏普"].map(lambda x:f"{x:.2f}")
df["Calmar"]=df["Calmar"].map(lambda x:f"{x:.2f}")
print("\n=== 现实成本(0.5%)下的10个策略排名 ===")
print(df.to_string(index=False))
df.to_csv("results/final10_realistic.csv",index=False,encoding="utf-8")
