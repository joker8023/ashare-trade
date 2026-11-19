#!/usr/bin/env python3
"""COMBO-5Y: A/B harvest+trend switch sweep + braked lockB. Output results/r30_bt/combo_5y.json."""
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
print(f"RUN_START={RUN_START} first_sig={first_sig.date()}", flush=True)
def make_inp(kind, sel=None):
    if kind == "MAX":
        return MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=40)
    if kind == "MAXB":
        return MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=20)
    return DInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.70, max_win=20, sel=sel)
def leg_shadow(kind, sel, cfg):
    rb = pc.run_strategy(make_inp(kind, sel), phase=0, **{**CA, **cfg})
    eq = rb.eq.iloc[:,0] if isinstance(res_eq(rb), pd.DataFrame) else rb.eq
    return eq, len(rb.trades)
def res_eq(rb):
    return rb.eq
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
A_M07 = ("MAX", None, dict(n=5, rebal=20, take=1.2, exposure=1.0))
A_VOL = ("D", "c_a60_vol", dict(n=4, rebal=30, take=0.8, exposure=1.0))
B_VOL = ("D", "c_a60_vol", dict(n=4, rebal=30, take=0.8, exposure=1.0))
B_TURN = ("D", "c_a60_turn", dict(n=6, rebal=30, take=0.8, exposure=1.0))
B_A5S = ("D", "c_a60_a5", dict(n=4, rebal=30, take=0.15, exposure=1.0))
B_AMT = ("D", "amount", dict(n=6, rebal=30, take=0.15, exposure=1.0))
PLAN = [
 dict(tag="C01_M07xVOL_rs60", A=A_M07, B=B_VOL, ns=(0.12,0.05,0.4,0.02,0,1), rs=60, lock=None),
 dict(tag="C02_M07xVOL_rs90", A=A_M07, B=B_VOL, ns=(0.12,0.05,0.4,0.02,0,1), rs=90, lock=None),
 dict(tag="C03_M07xTURN_rs60", A=A_M07, B=B_TURN, ns=(0.12,0.05,0.4,0.02,0,1), rs=60, lock=None),
 dict(tag="C04_M07xTURN_rs90", A=A_M07, B=B_TURN, ns=(0.12,0.05,0.4,0.02,0,1), rs=90, lock=None),
 dict(tag="C05_M07xA5S_rs60", A=A_M07, B=B_A5S, ns=(0.12,0.05,0.4,0.02,0,1), rs=60, lock=None),
 dict(tag="C06_M07xA5S_rs90", A=A_M07, B=B_A5S, ns=(0.12,0.05,0.4,0.02,0,1), rs=90, lock=None),
 dict(tag="C07_VOLxTURN_rs60", A=A_VOL, B=B_TURN, ns=(0.12,0.05,0.4,0.02,0,1), rs=60, lock=None),
 dict(tag="C08_VOLxTURN_rs90", A=A_VOL, B=B_TURN, ns=(0.12,0.05,0.4,0.02,0,1), rs=90, lock=None),
 dict(tag="C09_M07xAMT_rs60", A=A_M07, B=B_AMT, ns=(0.12,0.05,0.4,0.02,0,1), rs=60, lock=None),
 dict(tag="C10_M07xAMT_rs90", A=A_M07, B=B_AMT, ns=(0.12,0.05,0.4,0.02,0,1), rs=90, lock=None),
 dict(tag="C11_lockVOL_bd", A=A_M07, B=B_VOL, ns=(0.12,0.05,0.4,0.0,0,1), rs=60, lock="B"),
 dict(tag="C12_lockTURN_bd", A=A_M07, B=B_TURN, ns=(0.12,0.05,0.4,0.0,0,1), rs=60, lock="B"),
 dict(tag="C13_lockA5S_bd", A=A_M07, B=B_A5S, ns=(0.12,0.05,0.4,0.0,0,1), rs=60, lock="B"),
 dict(tag="C14_lockAMT_bd", A=A_M07, B=B_AMT, ns=(0.12,0.05,0.4,0.0,0,1), rs=60, lock="B"),
]
OUT = ROOT/"results"/"r30_bt"/"combo_5y.json"
def save(rows):
    OUT.write_text(json.dumps({"RUN_START": RUN_START, "rows": rows}, ensure_ascii=False, indent=1))
rows = []
if OUT.exists():
    try: rows = json.loads(OUT.read_text()).get("rows", [])
    except Exception as e: print(f"resume failed: {e}", flush=True)
have = set(r["tag"] for r in rows)
_sh = {}
def shadow(kind, sel, cfg):
    key = (kind, sel, tuple(sorted(cfg.items())))
    if key not in _sh:
        rb = pc.run_strategy(make_inp(kind, sel), phase=0, **{**CA, **cfg})
        _sh[key] = (rb.eq.iloc[:,0] if isinstance(rb.eq, pd.DataFrame) else rb.eq, len(rb.trades))
        print(f"  shadow {key} trades={len(rb.trades)}", flush=True)
        del rb; gc.collect()
    return _sh[key]
for c in PLAN:
    if c["tag"] in have:
        print("SKIP " + c["tag"], flush=True)
        continue
    print("RUN " + c["tag"], flush=True)
    ak, ask_, acfg = c["A"]
    bk, bsk, bcfg = c["B"]
    sha = shadow(ak, ask_, acfg)
    shb = shadow(bk, bsk, bcfg)
    nsp = build_ns_C(c["ns"][0], c["ns"][1], c["ns"][2], c["ns"][3], c["ns"][4], c["ns"][5])
    KW = dict(n=acfg["n"], rebal=acfg["rebal"], take=acfg["take"], exposure=acfg.get("exposure", 1.0), phase=0, inp_b=None, cfg_b=bcfg, shadow_a=sha[0], shadow_b=shb[0], rs_lookback=c["rs"], exclude_a=MB, exclude_b=MB, evalfreq="grid", brake_daily=False, **{k: v for k, v in CA.items() if k != "exclude"})
    KW["inp_b"] = make_inp(bk, bsk)
    inpA = make_inp(ak, ask_)
    res = nsp["run_strategy_switch"](inpA, lock_mode=c["lock"], **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
    e2 = eq.dropna()
    tot = float(e2.iloc[-1]/e2.iloc[0]-1)*100
    out = {"tag": c["tag"], "total": round(tot,2), "mdd": round(float(_mdd(e2))*100,2), "trades": int(len(res.trades)), "cost": round(float(res.meta["total_cost"]),0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "brakes": len(res.meta.get("brake_log", [])) // 2}
    out.update(annuals(e2))
    rows.append(out); save(rows)
    print(json.dumps({"tag": out["tag"], "tot": out["total"], "mdd": out["mdd"], "sw": out["switches"], "br": out["brakes"], "y22": out.get("2022"), "y22m": out.get("2022_mdd"), "y23": out.get("2023"), "y23m": out.get("2023_mdd"), "y24": out.get("2024"), "y24m": out.get("2024_mdd"), "y25": out.get("2025_yoy"), "y25m": out.get("2025_mdd"), "y26": out.get("2026"), "y26m": out.get("2026_mdd")}, ensure_ascii=False), flush=True)
    del KW["inp_b"], inpA; gc.collect()
print("COMBO DONE rows=" + str(len(rows)), flush=True)