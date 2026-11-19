#!/usr/bin/env python3
"""3LEG11: T40 2024-gap assault. Output results/r30_bt/three_leg11.json."""
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
A_VOL3 = ("c_a60_vol", dict(n=3, rebal=30, take=0.8, exposure=1.0))
B_TURN6 = ("c_a60_turn", dict(n=6, rebal=30, take=0.8, exposure=1.0))
C_A5 = ("amihud_5", dict(n=4, rebal=30, take=0.8, exposure=1.0))
OUT = ROOT/"results"/"r30_bt"/"three_leg11.json"
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
PLAN = [
 dict(tag="T51_rs60", rs=60, ha=0.005, hb=0.005, hc=0.08, mh=0, ns=(0.12,0.05,0.4,0.02,0,1)),
 dict(tag="T52_rs45", rs=45, ha=0.005, hb=0.005, hc=0.08, mh=0, ns=(0.12,0.05,0.4,0.02,0,1)),
 dict(tag="T53_rs75", rs=75, ha=0.005, hb=0.005, hc=0.08, mh=0, ns=(0.12,0.05,0.4,0.02,0,1)),
 dict(tag="T54_hc015", rs=90, ha=0.005, hb=0.005, hc=0.15, mh=0, ns=(0.12,0.05,0.4,0.02,0,1)),
 dict(tag="T55_hc012", rs=90, ha=0.005, hb=0.005, hc=0.12, mh=0, ns=(0.12,0.05,0.4,0.02,0,1)),
 dict(tag="T56_mh3", rs=90, ha=0.005, hb=0.005, hc=0.08, mh=3, ns=(0.12,0.05,0.4,0.02,3,1)),
]
for c in PLAN:
    if c["tag"] in have:
        print("SKIP " + c["tag"], flush=True)
        continue
    ask_, acfg = A_VOL3
    bsk, bcfg = B_TURN6
    csk, ccfg = C_A5
    sha = shadow(ask_, acfg)
    shb = shadow(bsk, bcfg)
    shc = shadow(csk, ccfg)
    nsp = build_ns3(c["ns"][0], c["ns"][1], c["ns"][2], c["ns"][3], c["ns"][4], c["ns"][5], hyst_a=c["ha"], hyst_b=c["hb"], hyst_c=c["hc"])
    KW = dict(n=acfg["n"], rebal=acfg["rebal"], take=acfg["take"], exposure=1.0, phase=0, inp_b=None, cfg_b=bcfg, inp_c=None, cfg_c=ccfg, shadow_a=sha[0], shadow_b=shb[0], shadow_c=shc[0], rs_lookback=c["rs"], exclude_a=MB, exclude_b=MB, exclude_c=MB, evalfreq="grid", brake_daily=False, **{k: v for k, v in CA0.items() if k != "exclude"})
    KW["inp_b"] = make_inp(bsk)
    KW["inp_c"] = make_inp(csk)
    inpA = make_inp(ask_)
    res = nsp["run_strategy_switch"](inpA, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
    e2 = eq.dropna()
    out = {"tag": c["tag"], "total": round(float(e2.iloc[-1]/e2.iloc[0]-1)*100,2), "mdd": round(float(_mdd(e2))*100,2), "trades": int(len(res.trades)), "cost": round(float(res.meta["total_cost"]),0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "brakes": len(res.meta.get("brake_log", [])) // 2}
    out.update(annuals(e2))
    rows.append(out); save(rows)
    print(json.dumps({"tag": out["tag"], "tot": out["total"], "mdd": out["mdd"], "sw": out["switches"], "y22": out.get("2022"), "y22m": out.get("2022_mdd"), "y23": out.get("2023"), "y24": out.get("2024"), "y24m": out.get("2024_mdd"), "y25": out.get("2025_yoy"), "y26": out.get("2026"), "y26m": out.get("2026_mdd")}, ensure_ascii=False), flush=True)
    del KW["inp_b"], KW["inp_c"], inpA; gc.collect()
print("3LEG11 DONE rows=" + str(len(rows)), flush=True)