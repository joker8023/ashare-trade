#!/usr/bin/env python3
"""Independent recompute of rerun_realshares_b1 5 configs (audit batch_054_m07rs).
Frozen engines only (prior_check / fresh2_max.MaxInputs / sweep_beat_h1_v4.build_ns /
 sweep_beat_m07_k21.build_ns_k21); own run_one port on data/pivots_2020_clean_realshares.pkl.
Compares every reported field to results/r30_bt/rerun_realshares_b1.json.
"""
import sys, json, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
from sweep_beat_m07_k21 import build_ns_k21
assert RUN_START == "2023-01-03", RUN_START
assert str(EVAL_END)[:10] == "2026-11-12"
assert WINDOWS == {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}
NEW_PIV = ROOT / "data" / "pivots_2020_clean_realshares.pkl"
piv = pd.read_pickle(NEW_PIV)
print("piv: %d days x %d codes shares=%s" % (piv["close"].shape[0], piv["close"].shape[1], type(piv["shares"]).__name__), flush=True)
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
print("first_sig:", first_sig.date(), flush=True)
_shadow_cache = {}
_ns_cache = {}
_ns_k21_cache = {}
def get_ns(bx, by_, bf):
    k = (bx, by_, bf)
    if k not in _ns_cache:
        _ns_cache[k] = build_ns(bx, by_, bf)
    return _ns_cache[k]
def get_ns_k21(bx, by_, bf, hyst):
    k = (bx, by_, bf, hyst)
    if k not in _ns_k21_cache:
        _ns_k21_cache[k] = build_ns_k21(bx, by_, bf, hyst)
    return _ns_k21_cache[k]
def get_shadows(cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp, gate_a=-0.15, band_a_lo=0.02):
    key = (cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp, gate_a, band_a_lo)
    if key in _shadow_cache:
        return _shadow_cache[key]
    inp_a = MaxInputs(piv, band=(band_a_lo, 0.30), gate60=gate_a, max_cut=cut_a, max_win=win_a)
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=cut_b, max_win=win_b)
    CA = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=b_n, rebal=30, take=b_take, exposure=b_exp)
    ra = pc.run_strategy(inp_a, n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
    _shadow_cache[key] = (inp_a, inp_b, ra, rb, CA, CFG_B)
    return _shadow_cache[key]
def finish(tag, res, extra=None):
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag}
    if extra:
        out.update(extra)
    out.update({"total": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2), "mdd": round(_mdd(eq) * 100, 2), "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]), 0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "switch_log": [list(x) for x in res.meta["switch_log"]], "brake_log": [list(x) for x in res.meta.get("brake_log", [])]})
    for w, d in WINDOWS.items():
        sub = eq.tail(d + 1)
        out[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
        out[w + "_mdd"] = round(_mdd(sub) * 100, 2)
    return out
def run_grid(tag, cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, stop=0.25, a_take=1.2, b_take=0.80, a_n=5, b_n=4, b_exp=0.9, rs=60, bx=0.18, by_=0.08, bf=0.6, gate_a=-0.15, band_a_lo=0.02):
    inp_a, inp_b, ra, rb, CA, CFG_B = get_shadows(cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp, gate_a, band_a_lo)
    KW = dict(n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB, **{k: v for k, v in CA.items() if k != "exclude"})
    ns = get_ns(bx, by_, bf)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    return finish(tag, res)
def run_k21(tag, cut_a=0.78, cut_b=0.78, win_a=40, win_b=20, stop=0.25, a_take=1.2, b_take=0.80, a_n=5, b_n=4, b_exp=0.9, rs=60, bx=0.15, by_=0.05, bf=0.7, hyst=0.03):
    inp_a, inp_b, ra, rb, CA, CFG_B = get_shadows(cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp)
    KW = dict(n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB, evalfreq="daily", brake_daily=False, **{k: v for k, v in CA.items() if k != "exclude"})
    ns = get_ns_k21(bx, by_, bf, hyst)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    return finish(tag, res, {"evalfreq": "daily", "hyst": hyst, "rs": rs, "bx": bx, "by": by_, "bf": bf})
CFGS = [
    ("M07", {}, {}),
    ("J04", {"win_b": 40, "b_n": 5}, {}),
    ("g_bf07", {"by_": 0.05, "cut_a": 0.78, "cut_b": 0.78, "bx": 0.15, "bf": 0.7}, {}),
    ("g_bf07_winA30", {"win_a": 30, "by_": 0.05, "cut_a": 0.78, "cut_b": 0.78, "bx": 0.15, "bf": 0.7}, {}),
]
KEYS = ["total", "mdd", "trades", "cost", "switches", "1m", "3m", "6m", "1y", "2y", "3y"]
WKEYS = KEYS + ["1m_mdd", "3m_mdd", "6m_mdd", "1y_mdd", "2y_mdd", "3y_mdd"]
EXPECTED = {r["tag"]: r for r in json.loads((ROOT / "results" / "r30_bt" / "rerun_realshares_b1.json").read_text())["rows"]}
t0 = time.time()
results = {}
for tag, kw, _ in CFGS:
    r = run_grid(tag, **kw)
    results[tag] = r
    print("DONE %s total=%.2f mdd=%.2f trades=%d (%.0fs)" % (tag, r["total"], r["mdd"], r["trades"], time.time() - t0), flush=True)
r = run_k21("k21_daily_hyst003_gbf07")
results["k21_daily_hyst003_gbf07"] = r
print("DONE k21 total=%.2f mdd=%.2f trades=%d (%.0fs)" % (r["total"], r["mdd"], r["trades"], time.time() - t0), flush=True)
report = {}
for tag, r in results.items():
    e = EXPECTED[tag]
    diffs = {}
    for k in WKEYS:
        d = round(r[k] - e[k], 4)
        if d != 0:
            diffs[k] = d
    sl = (r["switch_log"] == [list(x) for x in e["switch_log"]])
    bl = (r["brake_log"] == [list(x) for x in e["brake_log"]])
    mode_ok = (r["mode"] == e["mode"])
    ok = (not diffs) and sl and bl and mode_ok
    report[tag] = {"match": bool(ok), "num_diffs": diffs, "switch_log_equal": bool(sl), "brake_log_equal": bool(bl), "mode_equal": bool(mode_ok), "recomputed": {k: r[k] for k in KEYS}}
    print(("PASS " if ok else "FAIL ") + tag + " diffs=" + json.dumps(diffs, ensure_ascii=False), flush=True)
OUT = ROOT / "team" / "audit" / "batch_054_m07rs" / "part_054_rsrecompute.json"
OUT.write_text(json.dumps({"meta": {"seconds": round(time.time() - t0, 1)}, "report": report}, ensure_ascii=False, indent=1))
print("saved " + str(OUT), flush=True)
