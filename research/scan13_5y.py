#!/usr/bin/env python3
"""SCAN13: TURNxAMR15 long-RS double-pass attempt. Output results/r30_bt/scan13_5y.json."""
import sys, json, gc
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import _mdd, EVAL_END, MB
from switch_ns import build_ns as build_ns_C
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
RUN_START = str(dates[0].date())
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
CA0 = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
def annuals(eq):
    eq = eq.dropna()
    out = {}
    prev_end = None
    for y in range(int(eq.index[0].year), 2027):
        sub = eq[eq.index.year==y]
        if len(sub)==0: continue
        sret = float(sub.iloc[-1]/sub.iloc[0]-1)*100
        yoy = float(sub.iloc[-1]/prev_end-1)*100 if prev_end is not None else sret
        m = float((sub/sub.cummax()-1).min())*100
        out[str(y)] = round(sret,2); out[str(y)+"_yoy"] = round(yoy,2)
        out[str(y)+"_mdd"] = round(m,2)
        prev_end = float(sub.iloc[-1])
    return out
def make_inp(sel):
    return DInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.70, max_win=20, sel=sel)
A = ("c_a60_turn", dict(n=6, rebal=30, take=0.8, exposure=1.0))
B = ("amihud", dict(n=4, rebal=15, take=0.45, exposure=1.0))
OUT = ROOT/"results"/"r30_bt"/"scan13_5y.json"
def save(rows):
    OUT.write_text(json.dumps({"RUN_START": RUN_START, "rows": rows}, ensure_ascii=False, indent=1))
rows = []
if OUT.exists():
    try: rows = json.loads(OUT.read_text()).get("rows", [])
    except Exception as e: print(f"resume failed: {e}", flush=True)
have = set(r["tag"] for r in rows)
_sh = {}
def shadow(sel, cfg):
    key = (sel, tuple(sorted(cfg.items())))
    if key not in _sh:
        rb = pc.run_strategy(make_inp(sel), phase=0, **{**CA0, **cfg})
        _sh[key] = (rb.eq.iloc[:,0] if isinstance(rb.eq, pd.DataFrame) else rb.eq, len(rb.trades))
        del rb; gc.collect()
    return _sh[key]
for tag, rs in [("S13_TAxAM_rs90", 90), ("S13_TAxAM_rs120", 120)]:
    if tag in have:
        print("SKIP " + tag, flush=True)
        continue
    ask_, acfg = A
    bsk, bcfg = B
    sha = shadow(ask_, acfg)
    shb = shadow(bsk, bcfg)
    nsp = build_ns_C(0.12, 0.05, 0.4, 0.02, 0, 1)
    KW = dict(n=acfg["n"], rebal=acfg["rebal"], take=acfg["take"], exposure=1.0, phase=0, inp_b=None, cfg_b=bcfg, shadow_a=sha[0], shadow_b=shb[0], rs_lookback=rs, exclude_a=MB, exclude_b=MB, evalfreq="grid", brake_daily=False, **{k: v for k, v in CA0.items() if k != "exclude"})
    KW["inp_b"] = make_inp(bsk)
    inpA = make_inp(ask_)
    res = nsp["run_strategy_switch"](inpA, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
    e2 = eq.dropna()
    out = {"tag": tag, "total": round(float(e2.iloc[-1]/e2.iloc[0]-1)*100,2), "mdd": round(float(_mdd(e2))*100,2), "trades": int(len(res.trades)), "cost": round(float(res.meta["total_cost"]),0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"])}
    out.update(annuals(e2))
    rows.append(out); save(rows)
    print(json.dumps({"tag": tag, "tot": out["total"], "mdd": out["mdd"], "sw": out["switches"], "y22": out.get("2022"), "y23": out.get("2023"), "y24": out.get("2024"), "y24m": out.get("2024_mdd"), "y25": out.get("2025_yoy"), "y26": out.get("2026")}, ensure_ascii=False), flush=True)
    del KW["inp_b"], inpA; gc.collect()
print("SCAN13 DONE rows=" + str(len(rows)), flush=True)