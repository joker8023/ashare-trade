#!/usr/bin/env python3
"""Trailing windows for T40/S9/T24 (exact filed configs). Output results/r30_bt/trail_3extra.json."""
import sys, json, gc
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import _mdd, EVAL_END, MB
from switch_ns import build_ns as build_ns_old
from switch_ns3 import build_ns3 as build_ns_new
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
RUN_START = str(dates[0].date())
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
def make_inp_D(sel):
    return DInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.70, max_win=20, sel=sel)
def trail(eq):
    end = eq.index[-1]
    def win(days):
        cutoff = end - pd.Timedelta(days=days)
        sub = eq[eq.index > cutoff]
        if len(sub)==0: return None
        r = float(sub.iloc[-1]/sub.iloc[0]-1)*100
        m = float((sub/sub.cummax()-1).min())*100
        return dict(ret=round(r,2), mdd=round(m,2), start=str(sub.index[0].date()), bars=int(len(sub)))
    return {"end": str(end.date()), "m1": win(31), "m3": win(93), "m6": win(182), "y1": win(365), "y2": win(730), "full_ret": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), "full_mdd": round(float(_mdd(eq))*100,2)}
_sh = {}
def shadow(cls, sel, cfg):
    key = (cls, sel, tuple(sorted(cfg.items())))
    if key not in _sh:
        inp = make_inp_D(sel) if cls == "D" else MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=20)
        rb = pc.run_strategy(inp, phase=0, **{**CA, **cfg})
        _sh[key] = rb.eq.iloc[:,0] if isinstance(rb.eq, pd.DataFrame) else rb.eq
        print(f"  shadow {sel} {tuple(sorted(cfg.items()))} trades={len(rb.trades)}", flush=True)
        del rb, inp; gc.collect()
    return _sh[key]
def run3(tag, asel, acfg, sha, inpb, cfgb, shb, inpc, cfgc, shc, rs, ef, bd, ns, extra=None):
    kwa = dict(n=acfg["n"], rebal=acfg["rebal"], take=acfg["take"], exposure=acfg.get("exposure", 1.0), phase=0)
    inpA = make_inp_D(asel)
    print("RUN " + tag, flush=True)
    KW = dict(n=kwa["n"], rebal=kwa["rebal"], take=kwa["take"], exposure=1.0, phase=0, inp_b=inpb, cfg_b=cfgb, inp_c=inpc, cfg_c=cfgc, shadow_a=sha, shadow_b=shb, shadow_c=shc, rs_lookback=rs, exclude_a=MB, exclude_b=MB, exclude_c=MB, evalfreq=ef, brake_daily=bd, **{k: v for k, v in CA.items() if k != "exclude"})
    if extra: KW.update(extra)
    res = ns["run_strategy_switch"](inpA, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
    return eq.dropna()
A3 = dict(n=3, rebal=30, take=0.8, exposure=1.0); B6 = dict(n=6, rebal=30, take=0.8, exposure=1.0); C4 = dict(n=4, rebal=30, take=0.8, exposure=1.0)
A4 = dict(n=4, rebal=30, take=0.8, exposure=1.0)
out = {}
# T40: 3-leg asym grid rs90
nsT = build_ns_new(0.12, 0.05, 0.4, 0.02, 0, 1, hyst_a=0.005, hyst_b=0.005, hyst_c=0.08)
eqT = run3("T40", "c_a60_vol", A3, shadow("D","c_a60_vol",A3), make_inp_D("c_a60_turn"), B6, shadow("D","c_a60_turn",B6), make_inp_D("amihud_5"), C4, shadow("D","amihud_5",C4), 90, "grid", False, nsT)
out["T40_asym00508"] = trail(eqT); del eqT; gc.collect()
# S9: 2-leg classic grid rs30
nsS = build_ns_old(0.12, 0.05, 0.3, 0.02, 0, 1)
print("RUN S9", flush=True);
KW = dict(n=3, rebal=30, take=0.8, exposure=1.0, phase=0, inp_b=make_inp_D("c_a60_a5"), cfg_b=A4, shadow_a=shadow("D","c_a60_vol",A3), shadow_b=shadow("D","c_a60_a5",A4), rs_lookback=30, exclude_a=MB, exclude_b=MB, evalfreq="grid", brake_daily=False, **{k: v for k, v in CA.items() if k != "exclude"})
resS = nsS["run_strategy_switch"](make_inp_D("c_a60_vol"), lock_mode=None, **KW)
eqS = resS.eq.iloc[:,0] if isinstance(resS.eq, pd.DataFrame) else resS.eq
out["S9_VN3xA5_rs30_b120503"] = trail(eqS.dropna()); del eqS, resS; gc.collect()
# T24: 3-leg daily rs90 sym
nsD = build_ns_new(0.18, 0.08, 0.6, 0.02, 0, 1)
eqD = run3("T24", "c_a60_vol", A3, shadow("D","c_a60_vol",A3), make_inp_D("c_a60_turn"), B6, shadow("D","c_a60_turn",B6), make_inp_D("amihud_5"), C4, shadow("D","amihud_5",C4), 90, "daily", False, nsD)
out["T24_drs90h2"] = trail(eqD); del eqD; gc.collect()
open(ROOT/"results"/"r30_bt"/"trail_3extra.json","w").write(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out, ensure_ascii=False, indent=1))