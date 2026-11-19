"""T40 six-window trailing backtest (exact filed config)."""
import sys, json, gc
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import _mdd, EVAL_END, MB
from switch_ns3 import build_ns3
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
RUN_START = str(dates[0].date())
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
print(f"RUN_START={RUN_START} first_sig={first_sig.date()} EVAL_END={EVAL_END} bars={len(dates)}", flush=True)
CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
def make_inp(sel):
    return DInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.70, max_win=20, sel=sel)
A3 = dict(n=3, rebal=30, take=0.8, exposure=1.0); B6 = dict(n=6, rebal=30, take=0.8, exposure=1.0); C4 = dict(n=4, rebal=30, take=0.8, exposure=1.0)
_sh = {}
def shadow(sel, cfg):
    key = (sel, tuple(sorted(cfg.items())))
    if key not in _sh:
        rb = pc.run_strategy(make_inp(sel), phase=0, **{**CA, **cfg})
        _sh[key] = (rb.eq.iloc[:,0] if isinstance(rb.eq, pd.DataFrame) else rb.eq, len(rb.trades))
        print(f"  shadow {sel} trades={len(rb.trades)}", flush=True)
        del rb; gc.collect()
    return _sh[key]
sha = shadow("c_a60_vol", A3); shb = shadow("c_a60_turn", B6); shc = shadow("amihud_5", C4)
nsT = build_ns3(0.12, 0.05, 0.4, 0.02, 0, 1, hyst_a=0.005, hyst_b=0.005, hyst_c=0.08)
inpA = make_inp("c_a60_vol")
KW = dict(n=A3["n"], rebal=A3["rebal"], take=A3["take"], exposure=1.0, phase=0, inp_b=make_inp("c_a60_turn"), cfg_b=B6, inp_c=make_inp("amihud_5"), cfg_c=C4, shadow_a=sha[0], shadow_b=shb[0], shadow_c=shc[0], rs_lookback=90, exclude_a=MB, exclude_b=MB, exclude_c=MB, evalfreq="grid", brake_daily=False, **{k: v for k, v in CA.items() if k != "exclude"})
print("RUN T40 switch...", flush=True)
res = nsT["run_strategy_switch"](inpA, lock_mode=None, **KW)
eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
eq = eq.dropna()
print(f"eq {eq.index[0].date()} -> {eq.index[-1].date()} n={len(eq)}", flush=True)
eq.to_pickle(ROOT/"results"/"r30_bt"/"T40_equity.pkl")
WINDOWS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}
out = {"tag": "T40_asym00508", "end": str(eq.index[-1].date()), "start": str(eq.index[0].date()), "nbars": int(len(eq)), "total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), "full_mdd": round(float(_mdd(eq))*100,2), "trades": int(len(res.trades)), "cost": round(float(res.meta["total_cost"]),0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "brakes": len(res.meta.get("brake_log", []))//2}
for w, d in WINDOWS.items():
    sub = eq.tail(d+1)
    out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
    out[w+"_mdd"] = round(float(_mdd(sub))*100,2)
    out[w+"_start"] = str(sub.index[0].date())
def calwin(days):
    cutoff = eq.index[-1] - pd.Timedelta(days=days)
    sub = eq[eq.index > cutoff]
    return dict(ret=round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2), mdd=round(float(_mdd(sub))*100,2), start=str(sub.index[0].date()), bars=int(len(sub)))
for k, dd in [("m1",31),("m3",93),("m6",182),("y1",365),("y2",730),("y3",1095)]:
    out["cal_"+k] = calwin(dd)
for y in [2021,2022,2023,2024,2025,2026]:
    sub = eq[eq.index.year==y]
    if len(sub)>1:
        out["ann_"+str(y)] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
        out["ann_"+str(y)+"_mdd"] = round(float(_mdd(sub))*100,2)
print(json.dumps(out, ensure_ascii=False, indent=1))
open(ROOT/"results"/"r30_bt"/"T40_trail6.json","w").write(json.dumps(out, ensure_ascii=False, indent=1))
print("saved results/r30_bt/T40_trail6.json + T40_equity.pkl", flush=True)
