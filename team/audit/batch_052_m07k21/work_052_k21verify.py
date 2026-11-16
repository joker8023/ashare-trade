#!/usr/bin/env python3
"""batch_052 K21 T-line verify: independent recompute of nbeat>=4 rows
(k21_daily_hyst003_gbf07 nbeat=5 best + k21_daily_hyst003_M07 nbeat=4) +
cross-phase (5/10/15) + ex-top3 + slipx2 for best row (+slipx2/xphase slim for
runner-up). Import build_ns_k21 only; own shadows/metrics. Outputs
part_052_k21.json (this dir only)."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, WINDOWS, RUN_START, EVAL_END, MB
from sweep_beat_m07_k21 import build_ns_k21

M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05,
       "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
EXP = {r["tag"]: r for r in json.load(open(ROOT/"results"/"r30_bt"/"sweep_beat_m07_k21.json"))}
M07F = json.load(open(ROOT/"results"/"r30_bt"/"M07_final.json"))

piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
_ns_cache = {}
_sh_cache = {}
def get_ns(bx, by_, bf, hyst):
    k = (bx, by_, bf, hyst)
    if k not in _ns_cache: _ns_cache[k] = build_ns_k21(bx, by_, bf, hyst)
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

def run_full(evalfreq="daily", hyst=0.0, rs=60, phase=0, slip=0.002,
             bx=0.18, by_=0.08, bf=0.6, cut_a=0.80, cut_b=0.80,
             win_a=40, win_b=20):
    inp_a, inp_b, ra, rb, CA, CFG_B = get_sh(cut_a, win_a, cut_b, win_b, phase)
    CA = dict(CA, slip=slip)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=phase, inp_b=inp_b, cfg_b=CFG_B,
              shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB,
              evalfreq=evalfreq, brake_daily=False,
              **{k: v for k, v in CA.items() if k != "exclude"})
    ns = get_ns(bx, by_, bf, hyst)
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
    if isinstance(tr, pd.DataFrame):
        pnl = tr["net_pnl"].fillna(0)
    else:
        pnl = pd.Series([float(t.get("net_pnl", 0) or 0) for t in tr])
    top3 = pnl.nlargest(3).sum() if len(pnl) else 0.0
    out["top3_share"] = round(float(top3/pnl.sum())*100, 1) if float(pnl.sum()) else 0.0
    out["extop3_total"] = round(float((eq.iloc[0]+pnl.sum()-top3)/eq.iloc[0]-1)*100, 2)
    return out

def slim(o):
    return {k: o[k] for k in ("total","mdd","trades","cost","switches","1m","3m","6m","1y","2y","3y","nbeat","top3_share","extop3_total")}

BEST = dict(evalfreq="daily", hyst=0.03, rs=60, bx=0.15, by_=0.05, bf=0.7, cut_a=0.78, cut_b=0.78)
RUNNER = dict(evalfreq="daily", hyst=0.03, rs=60)
KEYS = ["total","mdd","trades","cost","switches","1m","3m","6m","1y","2y","3y"]

out = {}
# (a) base calibration recompute
b = run_full(evalfreq="grid", hyst=0.0, rs=60)
e = EXP["base_M07"]
out["base_recompute_exact"] = all(b[k] == e[k] for k in KEYS) and b["switch_log"] == e["switch_log"] and b["brake_log"] == e["brake_log"]
out["base_matches_M07_final"] = all(b[k] == M07F[k] for k in ["total","mdd","1m","3m","6m","1y","2y","3y"]) and b["trades"] == M07F["trades"] and b["cost"] == M07F["cost"] and b["switch_log"] == [list(x) for x in M07F["switch_log"]] and b["brake_log"] == [list(x) for x in M07F["brake_log"]]
out["base_recompute"] = slim(b)
# (b) independent recompute nbeat>=4 rows
for tag, kw in [("k21_daily_hyst003_gbf07", BEST), ("k21_daily_hyst003_M07", RUNNER)]:
    r = run_full(**kw)
    e2 = EXP[tag]
    exact = all(r[k] == e2[k] for k in KEYS) and r["switch_log"] == e2["switch_log"] and r["brake_log"] == e2["brake_log"]
    out[tag+"_recompute_exact"] = exact
    out[tag+"_recompute"] = slim(r)
    out[tag+"_recompute_logs"] = {"switch_log": r["switch_log"], "brake_log": r["brake_log"]}
    out[tag+"_expected"] = {k: e2[k] for k in KEYS}
# (c) cross-phase best + runner-up
out["xphase_best"] = {}
for p in (5, 10, 15):
    out["xphase_best"][str(p)] = slim(run_full(phase=p, **BEST))
out["xphase_runner"] = {}
for p in (5, 10, 15):
    out["xphase_runner"][str(p)] = slim(run_full(phase=p, **RUNNER))
# (d) slipx2 best + runner-up
out["best_slipx2"] = slim(run_full(slip=0.004, **BEST))
out["runner_slipx2"] = slim(run_full(slip=0.004, **RUNNER))
# (e) brake verbatim check across K21 rows
out["brake_verbatim_M07"] = {}
for tag, r in EXP.items():
    out["brake_verbatim_M07"][tag] = (r["brake_log"] == [list(x) for x in M07F["brake_log"]])
json.dump(out, open(ROOT/"team"/"audit"/"batch_052_m07k21"/"part_052_k21.json","w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
