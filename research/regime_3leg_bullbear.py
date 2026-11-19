#!/usr/bin/env python3
"""3-leg bull/bear/side regime specialists on OLD pivots (combo/M07 caliber).
BULL=A MAX40 N5 R20 TP1.2 exp1.0 | SIDE=B MAX20 N4 R30 TP0.8 exp0.9 | BEAR=C defensive variants.
RS switching via switch_ns3.build_ns3 (trailing-only), costs slip0.002 stop0.25 next-day.
RUN_START 2023-01-03, EVAL_END 2026-11-12. Benchmark combo_w70 1624.33/-22.61.
"""
import sys, json, gc
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import _mdd, WINDOWS, RUN_START, EVAL_END, MB
from switch_ns3 import build_ns3
print("RUN_START", RUN_START, "EVAL_END", EVAL_END, flush=True)
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
print("first_sig", first_sig, "n", len(dates), flush=True)
CA0 = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)

def mk_max(band, gate, cut, win):
    return MaxInputs(piv, band=band, gate60=gate, max_cut=cut, max_win=win)
def mk_d(sel, band=(0.05,0.30), gate=-1.0, cut=0.80, win=20):
    return DInputs(piv, band=band, gate60=gate, max_cut=cut, max_win=win, sel=sel)

# leg cfgs
CFG_A = dict(n=5, rebal=20, take=1.2, exposure=1.0)   # BULL aggressive
CFG_B = dict(n=4, rebal=30, take=0.8, exposure=0.9)   # SIDE balanced
# BEAR candidates
CFG_C1 = dict(n=4, rebal=30, take=0.8, exposure=0.4)  # same selector, low exposure
CFG_C2 = dict(n=3, rebal=30, take=0.6, exposure=0.7)   # concentrated, quick take
CFG_C3 = dict(n=3, rebal=30, take=0.8, exposure=1.0)   # vol-based DInputs
CFG_C4 = dict(n=4, rebal=30, take=0.8, exposure=0.9)   # tight stop (stop_c=0.15)
CFG_C5 = dict(n=3, rebal=30, take=0.8, exposure=0.6)   # pure vol20 defensive

_sh = {}
def shadow(inp, cfg, stop=0.25, tag=""):
    key = (tag, tuple(sorted(cfg.items())), stop)
    if key not in _sh:
        CA = dict(CA0); CA["stop"] = stop
        r = pc.run_strategy(inp, phase=0, **{**CA, **cfg})
        eq = r.eq.iloc[:,0] if isinstance(r.eq, pd.DataFrame) else r.eq
        _sh[key] = (eq, len(r.trades))
        print(f"  shadow {tag} cfg={cfg} stop={stop} trades={len(r.trades)}", flush=True)
        del r; gc.collect()
    return _sh[key]

def run_variant(tag, inpA, inpB, inpC, cfgA, cfgB, cfgC, ns, rs=60, ef="grid", stop_c=None, extra=""):
    sha = shadow(inpA, cfgA, 0.25, tag+"_A")[0]
    shb = shadow(inpB, cfgB, 0.25, tag+"_B")[0]
    shc = shadow(inpC, cfgC, stop_c if stop_c is not None else 0.25, tag+"_C")[0]
    nsp = build_ns3(*ns) if isinstance(ns, tuple) else ns
    KW = dict(n=cfgA["n"], rebal=cfgA["rebal"], take=cfgA["take"], exposure=cfgA["exposure"],
              phase=0, inp_b=inpB, cfg_b=cfgB, inp_c=inpC, cfg_c=cfgC,
              shadow_a=sha, shadow_b=shb, shadow_c=shc, rs_lookback=rs,
              exclude_a=MB, exclude_b=MB, exclude_c=MB, evalfreq=ef, brake_daily=False,
              **{k:v for k,v in CA0.items() if k != "exclude"})
    if stop_c is not None:
        KW["stop_c"] = stop_c
    res = nsp["run_strategy_switch"](inpA, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2),
           "mdd": round(float(_mdd(eq))*100,2), "trades": int(len(res.trades)),
           "cost": round(float(res.meta["total_cost"]),0), "mode": res.meta["final_mode"],
           "switches": len(res.meta["switch_log"]),
           "switch_log": [list(x) for x in res.meta["switch_log"]],
           "brakes": len(res.meta.get("brake_log",[])),
           "extra": extra}
    for w,d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
        out[w+"_mdd"] = round(float(_mdd(sub))*100,2)
    # annual
    for y in [2023,2024,2025,2026]:
        m = eq[eq.index.year==y]
        if len(m)>1:
            out[f"ann_{y}"] = round(float(m.iloc[-1]/m.iloc[0]-1)*100,2)
    eq.to_pickle(ROOT/"results"/"r30_bt"/f"REG3_{tag}_equity.pkl")
    del res; gc.collect()
    return out, eq

# Build inputs (fresh instances per leg to avoid shared-state confusion)
def fresh_legs(selC="c1"):
    A = mk_max((0.02,0.30), -0.15, 0.80, 40)
    B = mk_max((0.05,0.30), -1.0, 0.80, 20)
    if selC=="c1": C = mk_max((0.05,0.30), -1.0, 0.80, 20)
    elif selC=="c2": C = mk_max((0.05,0.30), -1.0, 0.80, 20)
    elif selC=="c3": C = mk_d("c_a60_vol")
    elif selC=="c4": C = mk_max((0.05,0.30), -1.0, 0.80, 20)
    elif selC=="c5": C = mk_d("vol20")
    elif selC=="c6": C = mk_d("amihud_5")
    else: raise ValueError(selC)
    return A,B,C

NS_M07 = (0.18,0.08,0.6,0.0,0,1)     # M07 brake, no hyst
NS_T40 = (0.12,0.05,0.4,0.02,0,1)    # T40-style brake + hyst 0.02

rows = []
# V1: C1 low-exposure bear, M07 brake
A,B,C = fresh_legs("c1")
out,eq = run_variant("V1_Cexp04_M07brk", A,B,C, CFG_A, CFG_B, CFG_C1, NS_M07, rs=60, ef="grid", extra="BEAR=MAX20 N4 exp0.4, brake 0.18/0.08/0.6")
rows.append(out); print(json.dumps({k:out[k] for k in ["tag","total","mdd","trades","cost","mode","switches","ann_2023","ann_2024","ann_2025","ann_2026"]}, ensure_ascii=False), flush=True)

# V2: C1 low-exposure bear, T40 brake+hyst
A,B,C = fresh_legs("c1")
out,eq = run_variant("V2_Cexp04_T40brk", A,B,C, CFG_A, CFG_B, CFG_C1, NS_T40, rs=60, ef="grid", extra="BEAR=MAX20 N4 exp0.4, brake 0.12/0.05/0.4 hyst0.02")
rows.append(out); print(json.dumps({k:out[k] for k in ["tag","total","mdd","trades","cost","mode","switches","ann_2023","ann_2024","ann_2025","ann_2026"]}, ensure_ascii=False), flush=True)

# V3: C3 vol-N3 bear (DInputs c_a60_vol), M07 brake
A,B,C = fresh_legs("c3")
out,eq = run_variant("V3_CvolN3_M07brk", A,B,C, CFG_A, CFG_B, CFG_C3, NS_M07, rs=60, ef="grid", extra="BEAR=DInputs c_a60_vol N3 TP0.8 exp1.0")
rows.append(out); print(json.dumps({k:out[k] for k in ["tag","total","mdd","trades","cost","mode","switches","ann_2023","ann_2024","ann_2025","ann_2026"]}, ensure_ascii=False), flush=True)

# V4: C4 tight-stop bear (stop_c 0.15), M07 brake
A,B,C = fresh_legs("c4")
out,eq = run_variant("V4_Ctight15_M07brk", A,B,C, CFG_A, CFG_B, CFG_C4, NS_M07, rs=60, ef="grid", stop_c=0.15, extra="BEAR=MAX20 N4 exp0.9 stop_c0.15")
rows.append(out); print(json.dumps({k:out[k] for k in ["tag","total","mdd","trades","cost","mode","switches","ann_2023","ann_2024","ann_2025","ann_2026"]}, ensure_ascii=False), flush=True)

# V5: C2 concentrated N3 bear, M07 brake
A,B,C = fresh_legs("c2")
out,eq = run_variant("V5_CN3_M07brk", A,B,C, CFG_A, CFG_B, CFG_C2, NS_M07, rs=60, ef="grid", extra="BEAR=MAX20 N3 TP0.6 exp0.7")
rows.append(out); print(json.dumps({k:out[k] for k in ["tag","total","mdd","trades","cost","mode","switches","ann_2023","ann_2024","ann_2025","ann_2026"]}, ensure_ascii=False), flush=True)

# V6: C5 pure vol20 N3 low-exp bear, M07 brake
A,B,C = fresh_legs("c5")
out,eq = run_variant("V6_Cpurevol_M07brk", A,B,C, CFG_A, CFG_B, CFG_C5, NS_M07, rs=60, ef="grid", extra="BEAR=DInputs vol20 N3 TP0.8 exp0.6")
rows.append(out); print(json.dumps({k:out[k] for k in ["tag","total","mdd","trades","cost","mode","switches","ann_2023","ann_2024","ann_2025","ann_2026"]}, ensure_ascii=False), flush=True)

open(ROOT/"results"/"r30_bt"/"REG3_bullbear_variants.json","w").write(json.dumps(rows, ensure_ascii=False, indent=1))
print("SAVED REG3_bullbear_variants.json rows="+str(len(rows)), flush=True)
