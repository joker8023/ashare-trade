#!/usr/bin/env python3
"""OPT-V2: phase-2 refinement, 5 configs. Output: results/r30_bt/opt_v2.json."""
import sys, json, gc
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import _mdd, EVAL_END, MB
from switch_ns import build_ns as build_ns_C
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
RUN_START = str(dates[0].date())
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
print("building shadow A ...", flush=True)
inpA = MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=40)
ra = pc.run_strategy(inpA, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
print(f"shadow A ready trades={len(ra.trades)}", flush=True)
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
        out[str(y)+"_mdd"] = round(m,2); out[str(y)+"_bars"] = int(len(sub))
        prev_end = float(sub.iloc[-1])
    return out
def make_inp_b(kind, sel=None):
    if kind == "MAX":
        return MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=20)
    return DInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.70, max_win=20, sel=sel)
_shadow_cache = {}
def shadow_b(kind, sel, cfg_b):
    key = (kind, sel, tuple(sorted(cfg_b.items())))
    if key not in _shadow_cache:
        rb = pc.run_strategy(make_inp_b(kind, sel), phase=0, **{**CA, **cfg_b})
        _shadow_cache[key] = (rb.eq.iloc[:,0] if isinstance(rb.eq, pd.DataFrame) else rb.eq, len(rb.trades))
        print(f"  shadowB trades={len(rb.trades)}", flush=True)
        del rb; gc.collect()
    return _shadow_cache[key]
OUT = ROOT/"results"/"r30_bt"/"opt_v2.json"
def save(rows):
    OUT.write_text(json.dumps({"RUN_START": RUN_START, "EVAL_END": str(EVAL_END), "rows": rows}, ensure_ascii=False, indent=1))
rows = []
if OUT.exists():
    try: rows = json.loads(OUT.read_text()).get("rows", [])
    except Exception as e: print(f"resume failed: {e}", flush=True)
have = set(r["tag"] for r in rows)
CFG = [
 dict(tag="F1H1_h001", fam="F1", kind="MAX", sel=None, cfg_b=dict(n=5, rebal=15, take=0.45, exposure=1.0), ns=(0.15,0.10,0.5,0.01,0,1), rs=60, ef="grid", bd=False),
 dict(tag="F1H2_h0015", fam="F1", kind="MAX", sel=None, cfg_b=dict(n=5, rebal=15, take=0.45, exposure=1.0), ns=(0.15,0.10,0.5,0.015,0,1), rs=60, ef="grid", bd=False),
 dict(tag="F2R75_h003cf2", fam="F2", kind="D", sel="amihud_5", cfg_b=dict(n=4, rebal=30, take=0.8, exposure=0.9), ns=(0.12,0.05,0.4,0.03,0,2), rs=75, ef="grid", bd=False),
 dict(tag="F2R120_h003cf2", fam="F2", kind="D", sel="amihud_5", cfg_b=dict(n=4, rebal=30, take=0.8, exposure=0.9), ns=(0.12,0.05,0.4,0.03,0,2), rs=120, ef="grid", bd=False),
 dict(tag="F4B1_b1508", fam="F4", kind="D", sel="c_a60_a5", cfg_b=dict(n=5, rebal=30, take=0.8, exposure=0.9), ns=(0.15,0.08,0.6,0.0,0,1), rs=13, ef="grid", bd=False),
]
for c in CFG:
    if c["tag"] in have:
        print("SKIP " + c["tag"], flush=True)
        continue
    print("RUN " + c["tag"], flush=True)
    shb = shadow_b(c["kind"], c["sel"], c["cfg_b"])
    nsp = build_ns_C(c["ns"][0], c["ns"][1], c["ns"][2], c["ns"][3], c["ns"][4], c["ns"][5])
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=None, cfg_b=c["cfg_b"], shadow_a=ra.eq, shadow_b=shb[0], rs_lookback=c["rs"], exclude_a=MB, exclude_b=MB, evalfreq=c["ef"], brake_daily=c["bd"], **{k: v for k, v in CA.items() if k != "exclude"})
    KW["inp_b"] = make_inp_b(c["kind"], c["sel"])
    res = nsp["run_strategy_switch"](inpA, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    e2 = eq.dropna()
    tot = float(e2.iloc[-1] / e2.iloc[0] - 1) * 100
    out = {"tag": c["tag"], "fam": c["fam"], "cfg": {"ns": c["ns"], "rs": c["rs"], "ef": c["ef"], "cfg_b": c["cfg_b"]}, "total": round(tot, 2), "mdd": round(float(_mdd(e2)) * 100, 2), "trades": int(len(res.trades)), "cost": round(float(res.meta["total_cost"]), 0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "brakes": len(res.meta.get("brake_log", [])) // 2}
    out.update(annuals(e2))
    rows.append(out)
    save(rows)
    print(json.dumps({"tag": out["tag"], "total": out["total"], "mdd": out["mdd"], "trades": out["trades"], "switches": out["switches"], "y2022": out["2022"], "y2022yoy": out["2022_yoy"], "y2022m": out["2022_mdd"], "y2023": out["2023"], "y2023yoy": out["2023_yoy"], "y2023m": out["2023_mdd"], "y2024": out["2024"], "y2024yoy": out["2024_yoy"], "y2025yoy": out["2025_yoy"], "y2026": out["2026"]}, ensure_ascii=False), flush=True)
    del KW["inp_b"]
    gc.collect()
_shadow_cache.clear()
gc.collect()
print("OPT-V2 DONE rows=" + str(len(rows)), flush=True)
