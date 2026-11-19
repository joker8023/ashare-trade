#!/usr/bin/env python3
"""All-data re-run for 5 champions: params frozen, only RUN_START moved to data start.
Caliber otherwise identical to filed: 50k, slip 0.002, lot 100, real fees,
stop 0.25 stop_exec next, legacy_grid False, full_liquidate True, long-only exp<=1,
signal t-close / exec t+1-close, RS uses t-and-earlier only.
Output: results/r30_bt/alldata_5.json (incremental after each strategy).
"""
import sys, json, gc
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import _mdd, EVAL_END, MB
from sweep_beat_h1_v4 import build_ns as build_ns_F2
from switch_ns import build_ns as build_ns_C

piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
RUN_START = str(dates[0].date())
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
print(f"RUN_START={RUN_START} EVAL_END={EVAL_END} first_sig={first_sig.date()} n_dates={len(dates)}", flush=True)

CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0,
         lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
         eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)

print("building shadow A M07 N5/R20/T1.2 ...", flush=True)
inpA = MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=40)
ra = pc.run_strategy(inpA, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
print(f"shadow A ready trades={len(ra.trades)}", flush=True)

def annuals(eq):
    eq = eq.dropna()
    out = {}
    prev_end = None
    for y in range(int(eq.index[0].year), 2027):
        sub = eq[eq.index.year==y]
        if len(sub)==0:
            continue
        sret = float(sub.iloc[-1]/sub.iloc[0]-1)*100
        yoy = float(sub.iloc[-1]/prev_end-1)*100 if prev_end is not None else sret
        m = float((sub/sub.cummax()-1).min())*100
        out[str(y)] = round(sret,2)
        out[str(y)+"_yoy"] = round(yoy,2)
        out[str(y)+"_mdd"] = round(m,2)
        out[str(y)+"_bars"] = int(len(sub))
        prev_end = float(sub.iloc[-1])
    return out

def run_one(tag, make_inp_b, cfg_b, ns, rs, evalfreq=None, brake_daily=None):
    print(f"[{tag}] building shadow B ...", flush=True)
    inp_b = make_inp_b()
    rb = pc.run_strategy(inp_b, phase=0, **{**CA, **cfg_b})
    print(f"[{tag}] shadow B ready trades={len(rb.trades)}; switching rs={rs} eval={evalfreq} ...", flush=True)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=cfg_b,
              shadow_a=ra.eq, shadow_b=(rb.eq.iloc[:,0] if isinstance(rb.eq, pd.DataFrame) else rb.eq),
              rs_lookback=rs, exclude_a=MB, exclude_b=MB,
              **{k:v for k,v in CA.items() if k!="exclude"})
    if evalfreq is not None:
        KW["evalfreq"] = evalfreq
    if brake_daily is not None:
        KW["brake_daily"] = brake_daily
    res = ns["run_strategy_switch"](inpA, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    tot = float(eq.iloc[-1]/eq.iloc[0]-1)*100
    md = float(_mdd(eq))*100
    out = {"tag": tag, "total": round(tot,2), "mdd": round(md,2),
           "trades": int(len(res.trades)), "cost": round(float(res.meta["total_cost"]),0),
           "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]),
           "switch_log": [[str(a), str(b)] for a,b in res.meta["switch_log"]],
           "brakes": len(res.meta.get("brake_log", []))//2,
           "eq_start": str(eq.index[0].date()), "eq_end": str(eq.index[-1].date()),
           "eq_len": int(len(eq))}
    out.update(annuals(eq))
    del inp_b, rb, res
    gc.collect()
    return out

OUT = ROOT/"results"/"r30_bt"/"alldata_5.json"
def save(rows):
    OUT.write_text(json.dumps({"RUN_START": RUN_START, "EVAL_END": str(EVAL_END), "first_sig": str(first_sig.date()), "rows": rows}, ensure_ascii=False, indent=1))

rows = []
if OUT.exists():
    try:
        old = json.loads(OUT.read_text())
        rows = old.get("rows", [])
        print(f"resume: loaded {len(rows)} rows", flush=True)
    except Exception as e:
        print(f"resume failed: {e}", flush=True)
have = set(r["tag"] for r in rows)

def need(tag): return tag not in have

# F1
if need("C2_grid_mh0_bx0.15_by0.1_bf0.5"):
    ns1 = build_ns_C(0.15, 0.10, 0.5, 0.0, 0, 1)
    r = run_one("C2_grid_mh0_bx0.15_by0.1_bf0.5",
                lambda: MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=20),
                dict(n=5, rebal=15, take=0.45, exposure=1.0), ns1, 60, "grid", False)
    rows.append(r); save(rows); print(json.dumps({k:r.get(k) for k in ("tag","total","mdd","trades","switches")}, ensure_ascii=False), flush=True)
# F2
if need("famF2_T08_bx012_by005_bf04"):
    ns2 = build_ns_F2(0.12, 0.05, 0.4)
    r = run_one("famF2_T08_bx012_by005_bf04",
                lambda: DInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.70, max_win=20, sel="amihud_5"),
                dict(n=4, rebal=30, take=0.8, exposure=0.9), ns2, 60)
    rows.append(r); save(rows); print(json.dumps({k:r.get(k) for k in ("tag","total","mdd","trades","switches")}, ensure_ascii=False), flush=True)
# F4
if need("F4_c_a60_a5_N5_R30_T08_rs13_b01200605_grid"):
    ns4 = build_ns_C(0.12, 0.06, 0.5, 0.0, 0, 1)
    r = run_one("F4_c_a60_a5_N5_R30_T08_rs13_b01200605_grid",
                lambda: DInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.70, max_win=20, sel="c_a60_a5"),
                dict(n=5, rebal=30, take=0.8, exposure=0.9), ns4, 13, "grid", False)
    rows.append(r); save(rows); print(json.dumps({k:r.get(k) for k in ("tag","total","mdd","trades","switches")}, ensure_ascii=False), flush=True)
# F5
if need("F5s3_rs42_h004_dg"):
    ns5 = build_ns_C(0.18, 0.08, 0.6, 0.04, 0, 1)
    r = run_one("F5s3_rs42_h004_dg",
                lambda: DInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.70, max_win=20, sel="c_a60_turn"),
                dict(n=4, rebal=15, take=0.45, exposure=0.9), ns5, 42, "daily", False)
    rows.append(r); save(rows); print(json.dumps({k:r.get(k) for k in ("tag","total","mdd","trades","switches")}, ensure_ascii=False), flush=True)
# F7
if need("F7sF_rs47_h0035_exp078"):
    ns7 = build_ns_C(0.22, 0.05, 0.5, 0.035, 0, 1)
    r = run_one("F7sF_rs47_h0035_exp078",
                lambda: DInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.70, max_win=20, sel="c_a60_amt"),
                dict(n=4, rebal=15, take=0.45, exposure=0.78), ns7, 47, "daily", False)
    rows.append(r); save(rows); print(json.dumps({k:r.get(k) for k in ("tag","total","mdd","trades","switches")}, ensure_ascii=False), flush=True)
print("ALL DONE rows="+str(len(rows)), flush=True)
