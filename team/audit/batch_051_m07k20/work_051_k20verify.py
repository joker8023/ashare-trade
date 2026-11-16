#!/usr/bin/env python3
"""batch_051 K20 T-line verify: independent recompute of daily_M07/daily_gbf07 +
brakeD-identity + cross-phase (5/10/15) + ex-top3 + slipx2. Outputs part_051_k20.json (this dir only)."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, WINDOWS, RUN_START, EVAL_END, MB
from evalfreq_k20 import build_ns_k20

M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05, "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
EXP = json.load(open(ROOT/"results"/"r30_bt"/"sweep_beat_m07_k20.json"))
EXP = {r["tag"]: r for r in EXP}

piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
_ns_cache = {}
_sh_cache = {}
def get_ns(bx, by, bf):
    k = (bx, by, bf)
    if k not in _ns_cache: _ns_cache[k] = build_ns_k20(bx, by, bf)
    return _ns_cache[k]
def get_sh(cut_a, win_a, cut_b, win_b, phase):
    key = (cut_a, win_a, cut_b, win_b, phase)
    if key in _sh_cache: return _sh_cache[key]
    inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=cut_a, max_win=win_a)
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=cut_b, max_win=win_b)
    CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0,
              lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
              eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=4, rebal=30, take=0.80, exposure=0.9)
    ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=phase, **CA)
    rb = pc.run_strategy(inp_b, phase=phase, **{**CA, **CFG_B})
    _sh_cache[key] = (inp_a, inp_b, ra, rb, CA, CFG_B)
    return _sh_cache[key]

def run_full(evalfreq, phase=0, brake_daily=False, slip=0.002, bx=0.18, by_=0.08, bf=0.6,
             cut_a=0.80, cut_b=0.78 if False else 0.80, win_a=40, win_b=20):
    inp_a, inp_b, ra, rb, CA, CFG_B = get_sh(cut_a, win_a, cut_b, win_b, phase)
    CA = dict(CA, slip=slip)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=phase, inp_b=inp_b, cfg_b=CFG_B,
              shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=60, exclude_a=MB, exclude_b=MB,
              evalfreq=evalfreq, brake_daily=brake_daily,
              **{k: v for k, v in CA.items() if k != "exclude"})
    ns = get_ns(bx, by_, bf)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {}
    out["total"] = round(float(eq.iloc[-1]/eq.iloc[0]-1)*100, 2)
    out["mdd"] = round(_mdd(eq)*100, 2)
    for w, d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100, 2)
        out[w+"_mdd"] = round(_mdd(sub)*100, 2)
    out["trades"] = len(res.trades)
    out["cost"] = round(float(res.meta["total_cost"]), 0)
    out["switches"] = len(res.meta["switch_log"])
    out["switch_log"] = [list(x) for x in res.meta["switch_log"]]
    out["brake_log"] = [list(x) for x in res.meta.get("brake_log", [])]
    out["nbeat"] = sum(1 for w in WINDOWS if out[w] > M07[w])
    tr = res.trades
    pnl = tr["net_pnl"].fillna(0)
    top3 = pnl.nlargest(3).sum()
    out["top3_share"] = round(float(top3/pnl.sum())*100, 1)
    out["extop3_total"] = round(float((eq.iloc[0]+pnl.sum()-top3)/eq.iloc[0]-1)*100, 2)
    return out

def slim(o):
    return {k: o[k] for k in ("total","mdd","trades","cost","switches","1m","3m","6m","1y","2y","3y","nbeat","top3_share","extop3_total")}

out = {}
# (b) independent recompute ph0
for tag, kw in [("daily_M07", dict(evalfreq="daily")),
                ("daily_gbf07", dict(evalfreq="daily", by_=0.05, cut_a=0.78, cut_b=0.78, bf=0.7))]:
    r = run_full(**kw)
    e = EXP[tag]
    keys = ["total","mdd","trades","cost","switches","1m","3m","6m","1y","2y","3y"]
    exact = all(r[k] == e[k] for k in keys) and r["switch_log"] == e["switch_log"] and r["brake_log"] == e["brake_log"]
    out[tag+"_recompute_exact"] = exact
    out[tag+"_recompute"] = slim(r)
    out[tag+"_expected"] = {k: e[k] for k in keys}
# (c) brakeD identity
rb = run_full(evalfreq="daily", brake_daily=True)
rd = run_full(evalfreq="daily", brake_daily=False)
keys = ["total","mdd","trades","cost","switches","1m","3m","6m","1y","2y","3y"]
out["brakeD_identical_daily"] = all(rb[k] == rd[k] for k in keys) and rb["brake_log"] == rd["brake_log"]
out["brakeD_matches_json"] = all(rb[k] == EXP["daily_M07_brakeD"][k] for k in keys)
# (d) cross-phase daily_M07 (candidate phase p vs M07 ph0)
out["xphase_daily_M07"] = {}
for p in (5, 10, 15):
    r = run_full(evalfreq="daily", phase=p)
    out["xphase_daily_M07"][str(p)] = slim(r)
# (e/f) slipx2
for tag, kw in [("daily_M07", dict(evalfreq="daily")),
                ("daily_gbf07", dict(evalfreq="daily", by_=0.05, cut_a=0.78, cut_b=0.78, bf=0.7))]:
    r = run_full(slip=0.004, **kw)
    out[tag+"_slipx2"] = slim(r)
json.dump(out, open(ROOT/"team"/"audit"/"batch_051_m07k20"/"part_051_k20.json","w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
