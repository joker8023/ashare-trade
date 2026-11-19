#!/usr/bin/env python3
"""Sensitivity: split-adjusted shares (audit batch_054_m07rs).
Naive realshares matrix multiplies ADJUSTED close by RAW contemporaneous shares,
so pre-split mcap is understated by the split factor (exact-ratio jumps prove
prices are split-adjusted: e.g. 000661 2020-06-09 ratio exactly 2.0, gap 1.0008).
This script scales pre-split history up by the cumulative forward split factor
(mcap-continuous lineage; non-exact 解禁/回购 jumps untouched) and reruns M07/J04.
No new files outside this dir (matrix adjusted in memory).
"""
import sys, json, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))
import numpy as np
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
assert RUN_START == "2023-01-03"
assert str(EVAL_END)[:10] == "2026-11-12"
piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean_realshares.pkl")
raw = piv["shares"]
CANON = [1.1, 1.2, 1.25, 1.3, 1.4, 1.5, 1.6, 2.0, 3.0]
adj = raw.copy()
split_events = []
for code in raw.columns:
    v = raw[code].to_numpy(dtype="float64")
    chg = np.where(pd.Series(v).ne(pd.Series(v).shift()))[0]
    fac = np.ones(len(v))
    for i in chg:
        if i > 0 and v[i - 1] == v[i - 1] and v[i - 1] != 0:
            r = v[i] / v[i - 1]
            for c in CANON:
                if abs(r - c) / c < 1e-6:
                    fac[i] = c
                    split_events.append((code, str(raw.index[i].date()), c))
                    break
    cum = np.ones(len(v))
    acc = 1.0
    for i in range(len(v) - 1, -1, -1):
        cum[i] = acc
        acc *= fac[i]
    col = v * cum
    col[np.isnan(v)] = np.nan
    adj[code] = col.astype("float32")
print("split events detected: %d" % len(split_events), flush=True)
piv_adj = dict(piv)
piv_adj["shares"] = adj
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
_cache = {}
def get_shadows(p, cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp):
    key = (id(p), cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp)
    if key not in _cache:
        ia = MaxInputs(p, band=(0.02, 0.30), gate60=-0.15, max_cut=cut_a, max_win=win_a)
        ib = MaxInputs(p, band=(0.05, 0.30), gate60=-1.0, max_cut=cut_b, max_win=win_b)
        CA = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
        CB = dict(n=b_n, rebal=30, take=b_take, exposure=b_exp)
        ra = pc.run_strategy(ia, n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0, **CA)
        rb = pc.run_strategy(ib, phase=0, **{**CA, **CB})
        _cache[key] = (ia, ib, ra, rb, CA, CB)
    return _cache[key]
def run_grid(p, tag, cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, stop=0.25, a_take=1.2, b_take=0.80, a_n=5, b_n=4, b_exp=0.9, rs=60, bx=0.18, by_=0.08, bf=0.6):
    ia, ib, ra, rb, CA, CB = get_shadows(p, cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp)
    KW = dict(n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0, inp_b=ib, cfg_b=CB, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB, **{k: v for k, v in CA.items() if k != "exclude"})
    res = build_ns(bx, by_, bf)["run_strategy_switch"](ia, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "total": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2), "mdd": round(_mdd(eq) * 100, 2), "trades": len(res.trades), "switches": len(res.meta["switch_log"]), "switch_log": [list(x) for x in res.meta["switch_log"]]}
    for w, d in WINDOWS.items():
        sub = eq.tail(d + 1)
        out[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
    return out
t0 = time.time()
m07 = run_grid(piv_adj, "M07_adj")
print("DONE M07_adj total=%.2f (%.0fs)" % (m07["total"], time.time() - t0), flush=True)
j04 = run_grid(piv_adj, "J04_adj", win_b=40, b_n=5)
print("DONE J04_adj total=%.2f (%.0fs)" % (j04["total"], time.time() - t0), flush=True)
w = ["1m", "3m", "6m", "1y", "2y", "3y"]
nbeat = sum(1 for k in w if m07[k] > j04[k])
OUT = ROOT / "team" / "audit" / "batch_054_m07rs" / "part_054_rssensitivity.json"
OUT.write_text(json.dumps({"n_split_events": len(split_events), "M07_adj": m07, "J04_adj": j04, "nbeat_M07_over_J04": nbeat, "mdd_M07_better": bool(m07["mdd"] > j04["mdd"]), "seconds": round(time.time() - t0, 1)}, ensure_ascii=False, indent=1))
print("nbeat=%d/6 mdd_better=%s saved %s" % (nbeat, bool(m07["mdd"] > j04["mdd"]), str(OUT)), flush=True)
