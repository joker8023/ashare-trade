import os, sys; os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
sys.argv = ["x", "None"]
import importlib.util
spec = importlib.util.spec_from_file_location("led", "ledger_10k.py")
led = importlib.util.module_from_spec(spec)
# 手动跑：改STOP
led.STOP = None
import pandas as pd
rows=[]
for n,reb in [(2,30),(3,30),(4,30),(5,30),(2,40),(3,40),(4,40),(5,40),(2,60),(3,60),(4,60),(5,60)]:
    spec.loader.exec_module(led) if False else None
    cash, ret, mdd, trades, paid = led.run(n, reb, "none", 15)
    import glob
    f = f"results/signals/ledger_N{n}_STOPNone.csv"
    eq = pd.read_csv(f, index_col=0, parse_dates=True)["eq"]
    segs=[eq.iloc[i:i+40] for i in range(0,len(eq),40)]
    wr=sum(s.iloc[-1]/s.iloc[0]-1>0 for s in segs)
    rows.append((n,reb,round(float(ret),4),round(float(mdd),4),wr,len(segs),trades,round(float(paid),1)))
    print(f"N={n} R={reb}: 收益{ret:.1%} 回撤{mdd:.1%} 胜率{wr}/{len(segs)}", flush=True)
pd.DataFrame(rows,columns=["n","reb","ann","mdd","wins","nseg","trades","fees"]).to_csv("results/newgoal_noleverage.csv",index=False)
