import pickle, pathlib, json
import pandas as pd
def mdd(s):
    return float((s/s.cummax()-1).min())
def metrics(eq):
    eq=eq.dropna()
    tot=float(eq.iloc[-1]/eq.iloc[0]-1)*100
    md=mdd(eq)*100
    out={"total":round(tot,2),"mdd":round(md,2),"start":str(eq.index[0].date()),"end":str(eq.index[-1].date()),"n":len(eq),"last":round(float(eq.iloc[-1]),2)}
    W={"1m":21,"3m":63,"6m":126,"1y":252,"2y":504,"3y":756}
    for k,d in W.items():
        sub=eq.tail(d+1)
        out[k]=round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
    for y in [2020,2021,2022,2023,2024,2025,2026]:
        sub=eq[eq.index.year==y]
        if len(sub)>1:
            out[f"ann_{y}"]=round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
            out[f"ann_{y}_mdd"]=round(mdd(sub)*100,2)
    return out
for name in ["combo_w50_equity","combo_w60_equity","combo_w70_equity","combo_w80_equity","combo_w90_ME_equity","T40_equity","J04_equity","M07_equity"]:
    p=pathlib.Path(f"results/r30_bt/{name}.pkl")
    if not p.exists():
        print(name,"MISSING")
        continue
    eq=pickle.load(open(p,"rb"))
    if isinstance(eq,pd.DataFrame): eq=eq.iloc[:,0]
    print("="*70)
    print(name, metrics(eq))
print("--- pivots ---")
import pathlib as pl
piv=pd.read_pickle("data/pivots_2020_clean_realshares_v2.pkl")
print(type(piv), piv.keys() if isinstance(piv,dict) else "")
for k in list(piv.keys())[:10]:
    v=piv[k]
    print(k, type(v), getattr(v,"shape",None))
    if hasattr(v,"index"):
        print("  idx:",v.index[0],v.index[-1],len(v.index))
        print("  cols:",list(v.columns[:5]))
