#!/usr/bin/env python3
"""DIAG: monthly mode vs leg shadows for T08/T40 chassis. Output printed only."""
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
def make_inp(sel):
    return DInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.70, max_win=20, sel=sel)
specs = {"A": ("c_a60_vol", dict(n=3, rebal=30, take=0.8, exposure=1.0)), "B": ("c_a60_turn", dict(n=6, rebal=30, take=0.8, exposure=1.0)), "C": ("amihud_5", dict(n=4, rebal=30, take=0.8, exposure=1.0))}
sh = {}
for leg, (sel, cfg) in specs.items():
    rb = pc.run_strategy(make_inp(sel), phase=0, **{**CA0, **cfg})
    sh[leg] = rb.eq.iloc[:,0] if isinstance(rb.eq, pd.DataFrame) else rb.eq
    del rb; gc.collect()
nsp = build_ns3(0.12, 0.05, 0.4, 0.02, 0, 1)
inpA = make_inp("c_a60_vol")
KW = dict(n=3, rebal=30, take=0.8, exposure=1.0, phase=0, inp_b=make_inp("c_a60_turn"), cfg_b=specs["B"][1], inp_c=make_inp("amihud_5"), cfg_c=specs["C"][1], shadow_a=sh["A"], shadow_b=sh["B"], shadow_c=sh["C"], rs_lookback=90, exclude_a=MB, exclude_b=MB, exclude_c=MB, evalfreq="grid", brake_daily=False, **{k: v for k, v in CA0.items() if k != "exclude"})
res = nsp["run_strategy_switch"](inpA, lock_mode=None, **KW)
eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
eq = eq.dropna()
sw = [(str(d), m) for d, m in res.meta["switch_log"]]
print("switches:", json.dumps(sw), flush=True)
cur = "A"
swd = {d: m for d, m in sw}
for (y, m) in [(2022, i) for i in range(1,13)] + [(2023, i) for i in range(1,13)] + [(2024, i) for i in range(1,13)]:
    sub = eq[(eq.index.year==y) & (eq.index.month==m)]
    if len(sub) < 2: continue
    r = float(sub.iloc[-1]/sub.iloc[0]-1)*100
    legs = {}
    for leg in "ABC":
        s2 = sh[leg][(sh[leg].index.year==y) & (sh[leg].index.month==m)]
        legs[leg] = round(float(s2.iloc[-1]/s2.iloc[0]-1)*100,1) if len(s2)>1 else None
    la = legs["A"]; lb = legs["B"]; lc = legs["C"]
    print(f"{y}-{m:02d} sw={r:+.1f}% A={la} B={lb} C={lc}", flush=True)