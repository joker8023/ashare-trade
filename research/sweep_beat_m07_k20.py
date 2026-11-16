#!/usr/bin/env python3
"""K20: eval-frequency pilot (daily close eval vs A-grid-signal eval).

Caliber identical to run_m07_final.py / sweep_beat_m07_k2.py except evalfreq
(see research/evalfreq_k20.py): ph0 / RUN_START=2023-01-03 /
EVAL_END=2026-11-12 / 5w / realistic fees + slip 0.002 / round lots /
native amihud_60 both legs / A-B params verbatim M07 / brake + RS60 verbatim.
Only new file besides evalfreq_k20.py; output results/r30_bt/sweep_beat_m07_k20.json
(K2 schema + evalfreq/brake_daily fields).
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))

import pandas as pd

import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, WINDOWS, RUN_START, EVAL_END, MB
from evalfreq_k20 import build_ns_k20

M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05,
       "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
M07_SWITCH = [["2023-06-21", "B"], ["2024-08-15", "A"], ["2026-09-08", "B"]]

piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))

_shadow_cache = {}
_ns_cache = {}


def get_ns(bx, by, bf):
    k = (bx, by, bf)
    if k not in _ns_cache:
        _ns_cache[k] = build_ns_k20(bx, by, bf)
    return _ns_cache[k]


def get_shadows(cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp):
    key = (cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp)
    if key in _shadow_cache:
        return _shadow_cache[key]
    inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=cut_a, max_win=win_a)
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=cut_b, max_win=win_b)
    CA = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=MB,
              capital=50000.0, lot=100, cost_one_way=None, slip=0.002,
              run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END,
              legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=b_n, rebal=30, take=b_take, exposure=b_exp)
    ra = pc.run_strategy(inp_a, n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
    _shadow_cache[key] = (inp_a, inp_b, ra, rb, CA, CFG_B)
    return _shadow_cache[key]


def run_one(tag, cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, stop=0.25,
            a_take=1.2, b_take=0.80, a_n=5, b_n=4, b_exp=0.9, rs=60,
            bx=0.18, by_=0.08, bf=0.6, evalfreq="grid", brake_daily=False):
    inp_a, inp_b, ra, rb, CA, CFG_B = get_shadows(
        cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp)
    KW = dict(n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0,
              inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq,
              rs_lookback=rs, exclude_a=MB, exclude_b=MB,
              evalfreq=evalfreq, brake_daily=brake_daily,
              **{k: v for k, v in CA.items() if k != "exclude"})
    ns = get_ns(bx, by_, bf)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "evalfreq": evalfreq, "brake_daily": bool(brake_daily),
           "total": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
           "mdd": round(_mdd(eq) * 100, 2),
           "trades": len(res.trades),
           "cost": round(float(res.meta["total_cost"]), 0),
           "mode": res.meta["final_mode"],
           "switches": len(res.meta["switch_log"]),
           "brakes": len(res.meta.get("brake_log", [])) // 2,
           "switch_log": [list(x) for x in res.meta["switch_log"]],
           "brake_log": [list(x) for x in res.meta.get("brake_log", [])]}
    for w, d in WINDOWS.items():
        sub = eq.tail(d + 1)
        out[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
        out[w + "_mdd"] = round(_mdd(sub) * 100, 2)
    out["nbeat_m07"] = sum(1 for w in WINDOWS if out[w] > M07[w])
    out["beat_all"] = all(out[w] > M07[w] for w in WINDOWS)
    out["mdd_better"] = out["mdd"] > M07["mdd"]
    out["win_all"] = bool(out["beat_all"] and out["mdd_better"])
    out["switch_same_m07"] = (out["switch_log"] == M07_SWITCH)
    return out


CFGS = [
    dict(tag="base_M07"),
    dict(tag="daily_M07", evalfreq="daily"),
    dict(tag="daily1_M07", evalfreq="daily1"),
    dict(tag="daily_gbf07", evalfreq="daily", by_=0.05, cut_a=0.78, cut_b=0.78, bf=0.7),
    dict(tag="daily1_gbf07", evalfreq="daily1", by_=0.05, cut_a=0.78, cut_b=0.78, bf=0.7),
    dict(tag="daily_M07_brakeD", evalfreq="daily", brake_daily=True),
]

if __name__ == "__main__":
    rows = []
    for cfg in CFGS:
        c = dict(cfg)
        tag = c.pop("tag")
        try:
            r = run_one(tag, **c)
            slim = {k: r[k] for k in ("tag", "evalfreq", "total", "mdd", "trades",
                                      "cost", "switches", "brakes", "1m", "3m",
                                      "6m", "1y", "2y", "3y", "nbeat_m07",
                                      "beat_all", "mdd_better", "switch_same_m07")}
            print(json.dumps(slim, ensure_ascii=False), flush=True)
            rows.append(r)
            if tag == "base_M07":
                cal = {k: r[k] for k in ("total", "mdd", "1m",
                                        "3m", "6m", "1y", "2y", "3y")}
                exp = {k: M07[k] for k in cal}
                assert cal == exp and r["trades"] == 184 and r["cost"] == 50990.0, \
                    "CALIB DIFF base_M07 vs M07_final: %s" % json.dumps(r, ensure_ascii=False)
                assert r["switch_log"] == M07_SWITCH, "CALIB switch_log diff: %s" % r["switch_log"]
                print("CALIB OK base_M07 == M07_final", flush=True)
        except Exception as e:
            print("FAIL %s: %s" % (tag, e), flush=True)
            import traceback
            traceback.print_exc()
    open(ROOT / "results" / "r30_bt" / "sweep_beat_m07_k20.json", "w").write(
        json.dumps(rows, ensure_ascii=False, indent=1))
    print("saved %d rows" % len(rows), flush=True)
