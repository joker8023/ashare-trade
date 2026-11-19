#!/usr/bin/env python3
"""SCAN2: harvest-leg variants (stop/gate/cut-win/R). Output results/r30_bt/scan2_5y.json."""
import sys, json, gc, itertools
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import _mdd, EVAL_END, MB
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
RUN_START = str(dates[0].date())
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
CA0 = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
print(f"RUN_START={RUN_START} first_sig={first_sig.date()}", flush=True)
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
OUT = ROOT/"results"/"r30_bt"/"scan2_5y.json"
def save(rows):
    OUT.write_text(json.dumps({"RUN_START": RUN_START, "rows": rows}, ensure_ascii=False, indent=1))
rows = []
if OUT.exists():
    try: rows = json.loads(OUT.read_text()).get("rows", [])
    except Exception as e: print(f"resume failed: {e}", flush=True)
have = set(r["tag"] for r in rows)
BASE = [
 ("vN4R30T08", "c_a60_vol", 4, 30, 0.8),
 ("tN6R30T08", "c_a60_turn", 6, 30, 0.8),
 ("a5N4R30T08", "c_a60_a5", 4, 30, 0.8),
 ("aN6R30T08", "amihud", 6, 30, 0.8),
 ("a5N4R15T045", "amihud", 4, 15, 0.45),
]
VAR = [
 ("s15", dict(stop=0.15)),
 ("s15tp15", dict(stop=0.15, tp=0.15)),
 ("g-015", dict(gate=-0.15)),
 ("c08w40", dict(cut=0.8, win=40)),
 ("R45", dict(R=45)),
 ("N2", dict(n=2)),
]
plan = []
for bn, sel, n, R, tp in BASE:
    for vn, ov in VAR:
        nn = ov.get("n", n); RR = ov.get("R", R); tt = ov.get("tp", tp)
        plan.append(dict(tag=f"S2_{bn}_{vn}", sel=sel, n=nn, R=RR, tp=tt, stop=ov.get("stop", 0.25), gate=ov.get("gate", -1.0), cut=ov.get("cut", 0.70), win=ov.get("win", 20)))
print(f"plan={len(plan)} have={len(have)}", flush=True)
for c in plan:
    if c["tag"] in have: continue
    try:
        CA = dict(CA0); CA["stop"] = c["stop"]
        inp = DInputs(piv, band=(0.05,0.30), gate60=c["gate"], max_cut=c["cut"], max_win=c["win"], sel=c["sel"])
        res = pc.run_strategy(inp, n=c["n"], rebal=c["R"], take=c["tp"], exposure=1.0, phase=0, **{**CA, "factor": "amihud_60"})
        eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
        e2 = eq.dropna()
        tot = float(e2.iloc[-1]/e2.iloc[0]-1)*100
        out = {"tag": c["tag"], "total": round(tot,2), "mdd": round(float(_mdd(e2))*100,2), "trades": int(len(res.trades)), "cost": round(float(res.meta["total_cost"]),0)}
        out.update(annuals(e2))
        rows.append(out); save(rows)
        print(json.dumps({"tag": out["tag"], "y22": out.get("2022"), "y22m": out.get("2022_mdd"), "y23": out.get("2023"), "y23m": out.get("2023_mdd"), "y24": out.get("2024"), "y24m": out.get("2024_mdd"), "y25": out.get("2025_yoy"), "y26": out.get("2026"), "tot": out["total"], "mdd": out["mdd"]}, ensure_ascii=False), flush=True)
    except Exception as e:
        print("FAIL " + c["tag"] + " " + str(e)[:200], flush=True)
    finally:
        gc.collect()
print("SCAN2 DONE rows=" + str(len(rows)), flush=True)