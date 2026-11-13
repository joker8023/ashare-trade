import os, sys, json
ROOT=os.getcwd()
sys.path.insert(0, os.path.join(ROOT, "team","audit"))
import pandas as pd
import prior_check as pc
MB=("688","689","300","301","8","4")
WINDOWS={"1m":21,"3m":63,"6m":126,"1y":252,"2y":504}
class X3Inputs(pc.Inputs):
    def __init__(self, piv, band=(0.02,0.30), gate60=-0.20, min_adv=5e6):
        super().__init__(piv)
        self.band,self.gate60,self.min_adv=band,gate60,min_adv
        self.ret60=self.close/self.close.shift(60)-1.0
        self.ret10=self.close/self.close.shift(10)-1.0
    def picks(self, t, n, size_range=None, min_adv=None, exclude=(), factor="amihud"):
        if t not in self.close.index: return []
        sr=self.band if size_range is None else size_range
        ma=self.min_adv if min_adv is None else min_adv
        fac=self.amihud60 if factor=="amihud_60" else self.amihud
        valid=(self.seasoned.loc[t] & (self.adv20.loc[t] > ma) & self.close.loc[t].notna() & fac.loc[t].notna())
        valid &= ~((self.ret60.loc[t] < self.gate60) & (self.ret10.loc[t] < 0)).fillna(False)
        cap_t=self.cap.loc[t]
        lo,hi=cap_t.quantile(sr[0]),cap_t.quantile(sr[1])
        valid &= ((cap_t >= lo) & (cap_t <= hi)).fillna(False)
        if exclude:
            valid &= ~pd.Series(list(valid.index), index=valid.index).str.startswith(exclude)
        return list(fac.loc[t][valid].sort_values(ascending=False).head(n).index)
def win(eq, days):
    sub=eq.tail(days+1)
    ret=float(sub.iloc[-1]/sub.iloc[0]-1)*100
    mdd=float((sub/sub.cummax()-1).min())*100
    return {"ret": round(ret,2), "mdd": round(mdd,2), "start": str(sub.index[0].date()), "end": str(sub.index[-1].date())}
def metrics(eq):
    eq=eq.dropna()
    tot=round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2)
    mdd=round(float((eq/eq.cummax()-1).min())*100,2)
    return {"total": tot, "mdd": mdd, "from": str(eq.index[0].date()), "to": str(eq.index[-1].date()), "ndays": int(len(eq)), "w": {k: win(eq,d) for k,d in WINDOWS.items()}}
print("loading pivots", flush=True)
piv=pd.read_pickle("data/pivots_long_clean.pkl")
print(f"pivots {piv['close'].shape} {piv['close'].index[0].date()}~{piv['close'].index[-1].date()}", flush=True)
base_inp=pc.get_inputs()
print(f"base inp dates {base_inp.dates[-1].date()} n={len(base_inp.dates)}", flush=True)
# X3 det: gate -0.15, e1.0, TP100, R30, N4
print("run X3", flush=True)
x3inp=X3Inputs(piv, gate60=-0.15)
rx=pc.run_strategy(x3inp, factor="amihud_60", n=4, rebal=30, take=1.0, stop=None, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start="2023-11-10", eval_start=pd.Timestamp("2025-02-13"), eval_end=pd.Timestamp("2026-11-12"), phase=0, legacy_grid=False, exposure=1.0, full_liquidate=True)
eqx=rx.eq.dropna()
mx=metrics(eqx)
print("X3 done", flush=True)
print("run N4", flush=True)
rn=pc.run_strategy(base_inp, factor="amihud_60", n=4, rebal=30, take=0.45, stop=None, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start="2023-11-10", eval_start=pd.Timestamp("2025-02-13"), eval_end=pd.Timestamp("2026-11-12"), phase=0, legacy_grid=False, exposure=0.9)
eqn=rn.eq.dropna()
mn=metrics(eqn)
print("N4 done", flush=True)
out={"X3_TP100_e100_gate15": {**mx, "trades": int(len(rx.trades)), "cost": round(float(rx.meta.get("total_cost",0)),0)}, "N4_TP45_e09": {**mn, "trades": int(len(rn.trades)), "cost": round(float(rn.meta.get("total_cost",0)),0)}}
with open("results/_compare_x3_n4_1112.json","w",encoding="utf-8") as f: json.dump(out,f,ensure_ascii=False,indent=1)
eqx.to_pickle("results/_eq_x3_1112.pkl")
eqn.to_pickle("results/_eq_n4_1112.pkl")
print(json.dumps(out, ensure_ascii=False, indent=1))
