#!/usr/bin/env python3
"""SCAN6: mdd-trim braked variants, one per adopted strategy. Output results/r30_bt/scan6_mdd.json."""
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
def make_inp(kind, sel=None):
    if kind == "MAX":
        return MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=40)
    if kind == "MAXB":
        return MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=20)
    assert sel is not None, sel
    return DInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.70, max_win=20, sel=sel)
OUT = ROOT/"results"/"r30_bt"/"scan6_mdd.json"
def save(rows):
    OUT.write_text(json.dumps({"RUN_START": RUN_START, "rows": rows}, ensure_ascii=False, indent=1))
rows = []
if OUT.exists():
    try: rows = json.loads(OUT.read_text()).get("rows", [])
    except Exception as e: print(f"resume failed: {e}", flush=True)
have = set(r["tag"] for r in rows)
CFG = [
 dict(tag="M1_F1_b1208", A=("MAXB",None,dict(n=5,rebal=15,take=0.45,exposure=1.0)), B=("MAXB",None,dict(n=5,rebal=15,take=0.45,exposure=1.0)), ns=(0.12,0.08,0.5,0.0,0,1), rs=60, ef="grid"),
 dict(tag="M1_F2_b1005", A=("MAX",None,dict(n=5,rebal=20,take=1.2,exposure=1.0)), B=("D","amihud_5",dict(n=4,rebal=30,take=0.8,exposure=0.9)), ns=(0.10,0.05,0.4,0.03,0,2), rs=90, ef="grid"),
 dict(tag="M1_F4_b1208", A=("MAX",None,dict(n=5,rebal=20,take=1.2,exposure=1.0)), B=("D","c_a60_a5",dict(n=5,rebal=30,take=0.8,exposure=0.9)), ns=(0.12,0.08,0.5,0.0,0,1), rs=13, ef="grid"),
 dict(tag="M1_F5_b1205", A=("MAX",None,dict(n=5,rebal=20,take=1.2,exposure=1.0)), B=("D","c_a60_turn",dict(n=4,rebal=15,take=0.45,exposure=0.9)), ns=(0.12,0.05,0.5,0.04,0,1), rs=42, ef="daily"),
 dict(tag="M1_F7_b1508", A=("MAX",None,dict(n=5,rebal=20,take=1.2,exposure=1.0)), B=("D","c_a60_amt",dict(n=4,rebal=15,take=0.45,exposure=0.78)), ns=(0.15,0.08,0.6,0.035,0,1), rs=47, ef="daily"),
]
_sh = {}
def shadow(kind, sel, cfg):
    key = (kind, sel, tuple(sorted(cfg.items())))
    if key not in _sh:
        mk = "MAX" if kind in ("MAX","MAXB") else "D"
        win = 20 if kind == "MAXB" else 40
        base = MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=win) if kind in ("MAX","MAXB") else make_inp(mk, sel)
        rb = pc.run_strategy(base, phase=0, **{**CA0, **cfg})
        _sh[key] = (rb.eq.iloc[:,0] if isinstance(rb.eq, pd.DataFrame) else rb.eq, len(rb.trades))
        del rb; gc.collect()
    return _sh[key]
for c in CFG:
    if c["tag"] in have:
        print("SKIP " + c["tag"], flush=True)
        continue
    ak, ask_, acfg = c["A"]
    bk, bsk, bcfg = c["B"]
    sha = shadow(ak, ask_, acfg)
    shb = shadow(bk, bsk, bcfg)
    nsp = build_ns_C(c["ns"][0], c["ns"][1], c["ns"][2], c["ns"][3], c["ns"][4], c["ns"][5])
    KW = dict(n=acfg["n"], rebal=acfg["rebal"], take=acfg["take"], exposure=acfg.get("exposure",1.0), phase=0, inp_b=None, cfg_b=bcfg, shadow_a=sha[0], shadow_b=shb[0], rs_lookback=c["rs"], exclude_a=MB, exclude_b=MB, evalfreq=c["ef"], brake_daily=False, **{k: v for k, v in CA0.items() if k != "exclude"})
    KW["inp_b"] = make_inp(bk, bsk)
    inpA = make_inp(ak, ask_)
    res = nsp["run_strategy_switch"](inpA, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
    e2 = eq.dropna()
    out = {"tag": c["tag"], "total": round(float(e2.iloc[-1]/e2.iloc[0]-1)*100,2), "mdd": round(float(_mdd(e2))*100,2), "trades": int(len(res.trades)), "cost": round(float(res.meta["total_cost"]),0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "brakes": len(res.meta.get("brake_log", [])) // 2}
    out.update(annuals(e2))
    rows.append(out); save(rows)
    print(json.dumps({"tag": out["tag"], "tot": out["total"], "mdd": out["mdd"], "sw": out["switches"], "br": out["brakes"], "y22": out.get("2022"), "y22m": out.get("2022_mdd"), "y23": out.get("2023"), "y24": out.get("2024"), "y24m": out.get("2024_mdd"), "y25": out.get("2025_yoy"), "y26": out.get("2026")}, ensure_ascii=False), flush=True)
    del KW["inp_b"], inpA; gc.collect()
print("SCAN6 DONE rows=" + str(len(rows)), flush=True)