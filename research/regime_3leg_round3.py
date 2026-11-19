#!/usr/bin/env python3
"""Round3: combine C exp0.3 (high total) with stronger brake to satisfy mdd<=-25."""
import sys, json, gc
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, WINDOWS, RUN_START, EVAL_END, MB
from switch_ns3 import build_ns3
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
CA0 = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
CFG_A = dict(n=5, rebal=20, take=1.2, exposure=1.0)
CFG_B = dict(n=4, rebal=30, take=0.8, exposure=0.9)
CFGS = {"e04": dict(n=4, rebal=30, take=0.8, exposure=0.4), "e03": dict(n=4, rebal=30, take=0.8, exposure=0.3), "e035": dict(n=4, rebal=30, take=0.8, exposure=0.35)}
def mk():
    return MaxInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.80, max_win=20)
mkA = MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=40)
mkB = mk(); mkC = mk()
print("shadows...", flush=True)
ra = pc.run_strategy(mkA, phase=0, **{**CA0, **CFG_A})
rb = pc.run_strategy(mkB, phase=0, **{**CA0, **CFG_B})
sh = {}
for k, cfg in CFGS.items():
    r = pc.run_strategy(mk(), phase=0, **{**CA0, **cfg})
    eq = r.eq.iloc[:,0] if isinstance(r.eq, pd.DataFrame) else r.eq
    sh[k] = eq
    print(f"  {k} trades={len(r.trades)}", flush=True)
    del r; gc.collect()
sha = ra.eq.iloc[:,0] if isinstance(ra.eq, pd.DataFrame) else ra.eq
shb = rb.eq.iloc[:,0] if isinstance(rb.eq, pd.DataFrame) else rb.eq
def run(tag, ck, bx=0.18, by_=0.08, bf=0.6, hyst=0.0, ha=None, hb=None, hc=None, rs=60):
    nsp = build_ns3(bx, by_, bf, hyst, 0, 1, hyst_a=ha, hyst_b=hb, hyst_c=hc)
    inpC = mk()
    KW = dict(n=CFG_A["n"], rebal=CFG_A["rebal"], take=CFG_A["take"], exposure=CFG_A["exposure"], phase=0, inp_b=mkB, cfg_b=CFG_B, inp_c=inpC, cfg_c=CFGS[ck], shadow_a=sha, shadow_b=shb, shadow_c=sh[ck], rs_lookback=rs, exclude_a=MB, exclude_b=MB, exclude_c=MB, evalfreq="grid", brake_daily=False, **{k:v for k,v in CA0.items() if k != "exclude"})
    res = nsp["run_strategy_switch"](mkA, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), "mdd": round(float(_mdd(eq))*100,2), "trades": int(len(res.trades)), "cost": round(float(res.meta["total_cost"]),0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "switch_log": [list(x) for x in res.meta["switch_log"]], "brakes": len(res.meta.get("brake_log",[]))}
    for w,d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
    for y in [2023,2024,2025,2026]:
        m = eq[eq.index.year==y]
        if len(m)>1: out[f"ann_{y}"] = round(float(m.iloc[-1]/m.iloc[0]-1)*100,2)
    eq.to_pickle(ROOT/"results"/"r30_bt"/f"REG3_{tag}_equity.pkl")
    del res; gc.collect()
    return out
rows=[]
rows.append(run("X1_e03_bf05", "e03", bf=0.5))
print(json.dumps({k:rows[-1][k] for k in ["tag","total","mdd","switches"]}), flush=True)
rows.append(run("X2_e03_bf04", "e03", bf=0.4))
print(json.dumps({k:rows[-1][k] for k in ["tag","total","mdd","switches"]}), flush=True)
rows.append(run("X3_e035_bf05", "e035", bf=0.5))
print(json.dumps({k:rows[-1][k] for k in ["tag","total","mdd","switches"]}), flush=True)
rows.append(run("X4_e04_bf04", "e04", bf=0.4))
print(json.dumps({k:rows[-1][k] for k in ["tag","total","mdd","switches"]}), flush=True)
rows.append(run("X5_e03_bf05_sticky", "e03", bf=0.5, ha=0.005, hb=0.005, hc=0.08))
print(json.dumps({k:rows[-1][k] for k in ["tag","total","mdd","switches"]}), flush=True)
rows.append(run("X6_e04_bf05_rs90", "e04", bf=0.5, rs=90))
print(json.dumps({k:rows[-1][k] for k in ["tag","total","mdd","switches"]}), flush=True)
open(ROOT/"results"/"r30_bt"/"REG3_round3.json","w").write(json.dumps(rows, ensure_ascii=False, indent=1))
print("SAVED round3", flush=True)
