#!/usr/bin/env python3
"""Round4: fixed switch grid RS60 (same as X1), BEAR-leg only sweep for 6win+mdd all-win vs combo_w70."""
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
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
CA0 = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
CFG_A = dict(n=5, rebal=20, take=1.2, exposure=1.0)
CFG_B = dict(n=4, rebal=30, take=0.8, exposure=0.9)
BENCH = {"1m": -2.38, "3m": 17.84, "6m": 39.86, "1y": 165.34, "2y": 1335.20, "3y": 1528.63, "mdd": -22.61}
def mkmax():
    return MaxInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.80, max_win=20)
mkA = MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=40)
mkB = mkmax()
print("shadows A/B...", flush=True)
ra = pc.run_strategy(mkA, phase=0, **{**CA0, **CFG_A})
rb = pc.run_strategy(mkB, phase=0, **{**CA0, **CFG_B})
sha = ra.eq.iloc[:,0] if isinstance(ra.eq, pd.DataFrame) else ra.eq
shb = rb.eq.iloc[:,0] if isinstance(rb.eq, pd.DataFrame) else rb.eq
print("A trades=%d B trades=%d" % (len(ra.trades), len(rb.trades)), flush=True)
del ra, rb; gc.collect()
_sh = {}
def bear_shadow(kind, cfg, stop=0.25, tag=""):
    key = (kind, tag, tuple(sorted(cfg.items())), stop)
    if key not in _sh:
        if kind == "max":
            inp = mkmax()
            r = pc.run_strategy(inp, phase=0, **{**dict(CA0, stop=stop), **cfg})
        elif kind == "vol":
            inp = DInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.80, max_win=20, sel="c_a60_vol")
            r = pc.run_strategy(inp, phase=0, **{**dict(CA0, stop=stop), **cfg})
        elif kind == "turn":
            inp = DInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.80, max_win=20, sel="c_a60_turn")
            r = pc.run_strategy(inp, phase=0, **{**dict(CA0, stop=stop), **cfg})
        else:
            raise ValueError(kind)
        eq = r.eq.iloc[:,0] if isinstance(r.eq, pd.DataFrame) else r.eq
        _sh[key] = (eq, inp, len(r.trades))
        print("  bear shadow %s %s stop=%s trades=%d" % (tag, cfg, stop, len(r.trades)), flush=True)
        del r; gc.collect()
    return _sh[key]
def run_switch(tag, shc, inpC, cfgC, bx=0.18, by_=0.08, bf=0.5, rs=60, stop_c=None):
    nsp = build_ns3(bx, by_, bf, 0.0, 0, 1)
    KW = dict(n=CFG_A["n"], rebal=CFG_A["rebal"], take=CFG_A["take"], exposure=CFG_A["exposure"], phase=0, inp_b=mkB, cfg_b=CFG_B, inp_c=inpC, cfg_c=cfgC, shadow_a=sha, shadow_b=shb, shadow_c=shc, rs_lookback=rs, exclude_a=MB, exclude_b=MB, exclude_c=MB, evalfreq="grid", brake_daily=False, **{k:v for k,v in CA0.items() if k != "exclude"})
    if stop_c is not None:
        KW["stop_c"] = stop_c
    res = nsp["run_strategy_switch"](mkA, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), "mdd": round(float(_mdd(eq))*100,2), "trades": int(len(res.trades)), "cost": round(float(res.meta["total_cost"]),0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "switch_log": [list(x) for x in res.meta["switch_log"]], "brakes": len(res.meta.get("brake_log",[]))}
    for w,d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
        out[w+"_mdd"] = round(float(_mdd(sub))*100,2)
    for y in [2023,2024,2025,2026]:
        m = eq[eq.index.year==y]
        if len(m)>1:
            out["ann_"+str(y)] = round(float(m.iloc[-1]/m.iloc[0]-1)*100,2)
            out["ann_"+str(y)+"_mdd"] = round(float(_mdd(m))*100,2)
    wins = [w for w in WINDOWS if out[w] > BENCH[w]]
    out["nbeat"] = len(wins)
    out["beats_mdd"] = bool(out["mdd"] > BENCH["mdd"])
    out["allwin"] = bool(len(wins) == 6 and out["beats_mdd"])
    eq.to_pickle(ROOT/("results/r30_bt/REG3_R4_"+tag+"_equity.pkl"))
    del res; gc.collect()
    return out
PLAN = [
    ("R4_cash00", "max", dict(n=4, rebal=30, take=0.8, exposure=0.0), 0.25, 0.18, 0.08, 0.5),
    ("R4_exp02", "max", dict(n=4, rebal=30, take=0.8, exposure=0.2), 0.25, 0.18, 0.08, 0.5),
    ("R4_X1repro", "max", dict(n=4, rebal=30, take=0.8, exposure=0.3), 0.25, 0.18, 0.08, 0.5),
    ("R4_exp05", "max", dict(n=4, rebal=30, take=0.8, exposure=0.5), 0.25, 0.18, 0.08, 0.5),
    ("R4_N2exp03", "max", dict(n=2, rebal=30, take=0.8, exposure=0.3), 0.25, 0.18, 0.08, 0.5),
    ("R4_N2exp05", "max", dict(n=2, rebal=30, take=0.8, exposure=0.5), 0.25, 0.18, 0.08, 0.5),
    ("R4_TP05exp03", "max", dict(n=4, rebal=30, take=0.5, exposure=0.3), 0.25, 0.18, 0.08, 0.5),
    ("R4_TP05exp05", "max", dict(n=4, rebal=30, take=0.5, exposure=0.5), 0.25, 0.18, 0.08, 0.5),
    ("R4_stop15", "max", dict(n=4, rebal=30, take=0.8, exposure=0.3), 0.15, 0.18, 0.08, 0.5),
    ("R4_stop15exp05", "max", dict(n=4, rebal=30, take=0.8, exposure=0.5), 0.15, 0.18, 0.08, 0.5),
    ("R4_volN3", "vol", dict(n=3, rebal=30, take=0.8, exposure=0.3), 0.25, 0.18, 0.08, 0.5),
    ("R4_turnN6", "turn", dict(n=6, rebal=30, take=0.8, exposure=0.3), 0.25, 0.18, 0.08, 0.5),
    ("R4_bx10", "max", dict(n=4, rebal=30, take=0.8, exposure=0.3), 0.25, 0.10, 0.08, 0.5),
    ("R4_bx12bf04", "max", dict(n=4, rebal=30, take=0.8, exposure=0.3), 0.25, 0.12, 0.08, 0.4),
    ("R4_bx15bf03", "max", dict(n=4, rebal=30, take=0.8, exposure=0.3), 0.25, 0.15, 0.08, 0.3),
    ("R4_exp02bf04", "max", dict(n=4, rebal=30, take=0.8, exposure=0.2), 0.25, 0.18, 0.08, 0.4),
]
rows = []
for tag, kind, cfg, stop, bx, by_, bf in PLAN:
    print("RUN " + tag, flush=True)
    shc, inpC, ntr = bear_shadow(kind, cfg, stop, tag)
    out = run_switch(tag, shc, inpC, cfg, bx=bx, by_=by_, bf=bf, rs=60, stop_c=(stop if stop != 0.25 else None))
    rows.append(out)
    print(tag + " total=" + str(out["total"]) + " mdd=" + str(out["mdd"]) + " nbeat=" + str(out["nbeat"]) + "/" + str(6) + " mddwin=" + str(out["beats_mdd"]) + " sw=" + str(out["switches"]), flush=True)
open(ROOT/"results/r30_bt/REG3_round4.json","w").write(json.dumps(rows, ensure_ascii=False, indent=1))
print("SAVED round4 n=" + str(len(rows)), flush=True)
