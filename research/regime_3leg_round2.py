#!/usr/bin/env python3
"""Round2: fine-tune V1 (C exp0.4, M07 brake) to get mdd<=-25 keep total>1624."""
import sys, json, gc
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, WINDOWS, RUN_START, EVAL_END, MB
from switch_ns3 import build_ns3
print("RUN_START", RUN_START, "EVAL_END", EVAL_END, flush=True)
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
CA0 = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
CFG_A = dict(n=5, rebal=20, take=1.2, exposure=1.0)
CFG_B = dict(n=4, rebal=30, take=0.8, exposure=0.9)
CFG_C1 = dict(n=4, rebal=30, take=0.8, exposure=0.4)
CFG_C7 = dict(n=4, rebal=30, take=0.8, exposure=0.3)
def mk_max(band, gate, cut, win):
    return MaxInputs(piv, band=band, gate60=gate, max_cut=cut, max_win=win)
inpA0 = mk_max((0.02,0.30), -0.15, 0.80, 40)
inpB0 = mk_max((0.05,0.30), -1.0, 0.80, 20)
inpC0 = mk_max((0.05,0.30), -1.0, 0.80, 20)
print("running shadows once...", flush=True)
ra = pc.run_strategy(inpA0, phase=0, **{**CA0, **CFG_A})
rb = pc.run_strategy(inpB0, phase=0, **{**CA0, **CFG_B})
rc1 = pc.run_strategy(inpC0, phase=0, **{**CA0, **CFG_C1})
rc7 = pc.run_strategy(mk_max((0.05,0.30), -1.0, 0.80, 20), phase=0, **{**CA0, **CFG_C7})
sha = ra.eq.iloc[:,0] if isinstance(ra.eq, pd.DataFrame) else ra.eq
shb = rb.eq.iloc[:,0] if isinstance(rb.eq, pd.DataFrame) else rb.eq
shc1 = rc1.eq.iloc[:,0] if isinstance(rc1.eq, pd.DataFrame) else rc1.eq
shc7 = rc7.eq.iloc[:,0] if isinstance(rc7.eq, pd.DataFrame) else rc7.eq
print(f"shadows done A={len(ra.trades)} B={len(rb.trades)} C1={len(rc1.trades)} C7={len(rc7.trades)}", flush=True)

def run_switch(tag, shc, cfgC, inpC, bx=0.18, by_=0.08, bf=0.6, hyst=0.0, ha=None, hb=None, hc=None, rs=60, mh=0, cf=1):
    nsp = build_ns3(bx, by_, bf, hyst, mh, cf, hyst_a=ha, hyst_b=hb, hyst_c=hc)
    KW = dict(n=CFG_A["n"], rebal=CFG_A["rebal"], take=CFG_A["take"], exposure=CFG_A["exposure"],
              phase=0, inp_b=inpB0, cfg_b=CFG_B, inp_c=inpC, cfg_c=cfgC,
              shadow_a=sha, shadow_b=shb, shadow_c=shc, rs_lookback=rs,
              exclude_a=MB, exclude_b=MB, exclude_c=MB, evalfreq="grid", brake_daily=False,
              **{k:v for k,v in CA0.items() if k != "exclude"})
    res = nsp["run_strategy_switch"](inpA0, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2),
           "mdd": round(float(_mdd(eq))*100,2), "trades": int(len(res.trades)),
           "cost": round(float(res.meta["total_cost"]),0), "mode": res.meta["final_mode"],
           "switches": len(res.meta["switch_log"]),
           "switch_log": [list(x) for x in res.meta["switch_log"]],
           "brakes": len(res.meta.get("brake_log",[]))}
    for w,d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
    for y in [2023,2024,2025,2026]:
        m = eq[eq.index.year==y]
        if len(m)>1: out[f"ann_{y}"] = round(float(m.iloc[-1]/m.iloc[0]-1)*100,2)
    eq.to_pickle(ROOT/"results"/"r30_bt"/f"REG3_{tag}_equity.pkl")
    del res; gc.collect()
    return out

rows = []
rows.append(run_switch("W1_hyst001", shc1, CFG_C1, inpC0, hyst=0.01))
print(json.dumps({k:rows[-1][k] for k in ["tag","total","mdd","switches","mode"]}), flush=True)
rows.append(run_switch("W2_hyst002", shc1, CFG_C1, inpC0, hyst=0.02))
print(json.dumps({k:rows[-1][k] for k in ["tag","total","mdd","switches","mode"]}), flush=True)
rows.append(run_switch("W3_stickyBear", shc1, CFG_C1, inpC0, hyst=0.0, ha=0.005, hb=0.005, hc=0.08))
print(json.dumps({k:rows[-1][k] for k in ["tag","total","mdd","switches","mode"]}), flush=True)
rows.append(run_switch("W4_RS90", shc1, CFG_C1, inpC0, rs=90))
print(json.dumps({k:rows[-1][k] for k in ["tag","total","mdd","switches","mode"]}), flush=True)
rows.append(run_switch("W5_RS90_sticky", shc1, CFG_C1, inpC0, rs=90, ha=0.005, hb=0.005, hc=0.08))
print(json.dumps({k:rows[-1][k] for k in ["tag","total","mdd","switches","mode"]}), flush=True)
rows.append(run_switch("W6_bf05", shc1, CFG_C1, inpC0, bf=0.5))
print(json.dumps({k:rows[-1][k] for k in ["tag","total","mdd","switches","mode"]}), flush=True)
rows.append(run_switch("W7_Cexp03", shc7, CFG_C7, mk_max((0.05,0.30), -1.0, 0.80, 20)))
print(json.dumps({k:rows[-1][k] for k in ["tag","total","mdd","switches","mode"]}), flush=True)
rows.append(run_switch("W8_minHold2", shc1, CFG_C1, inpC0, mh=2))
print(json.dumps({k:rows[-1][k] for k in ["tag","total","mdd","switches","mode"]}), flush=True)
open(ROOT/"results"/"r30_bt"/"REG3_round2.json","w").write(json.dumps(rows, ensure_ascii=False, indent=1))
print("SAVED REG3_round2 rows="+str(len(rows)), flush=True)
