#!/usr/bin/env python3
"""batch_045 T-line for k17_calmar_M07 (best K17 row, nbeat=2):
leg1 independent recompute (ph0 verbatim) | leg2 cross-phase ph0/5/7/10/14/15
vs phase-matched raw M07 | leg3 ex-top3 | leg4 slip x2 | leg5 full-decision-set
lookahead equivalence (engine-slice vs metric_k17 on t-truncated series).
Only writes team/audit/batch_045_m07k17/tline_k17_calmar_out.json"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from riskadj_k17 import build_ns_k17, metric_k17
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB

M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05, "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
A_M07 = dict(band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
B_M07 = dict(band=(0.05, 0.30), gate60=-1.0, max_cut=0.80, max_win=20)
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
NS_CAL = build_ns_k17("calmar", 0.18, 0.08, 0.6)
NS_RAW = build_ns(0.18, 0.08, 0.6)
def _s(x):
    return x.iloc[:, 0] if isinstance(x, pd.DataFrame) else x

def shadows(ph, slip=0.002):
    ia = MaxInputs(piv, **A_M07); ib = MaxInputs(piv, **B_M07)
    CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0,
              lot=100, cost_one_way=None, slip=slip, run_start=RUN_START, eval_start=first_sig,
              eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    ra = pc.run_strategy(ia, n=5, rebal=20, take=1.2, exposure=1.0, phase=ph, **CA)
    rb = pc.run_strategy(ib, n=4, rebal=30, take=0.80, exposure=0.9, phase=ph, **CA)
    return ia, ib, ra, rb, CA

def run_switch(ia, ib, ra, rb, CA, ns, ph):
    CFG_B = dict(n=4, rebal=30, take=0.80, exposure=0.9)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=ph, inp_b=ib, cfg_b=CFG_B,
              shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=60, exclude_a=MB, exclude_b=MB,
              factor="amihud_60", **{k: v for k, v in CA.items() if k not in ("exclude", "factor")})
    res = ns["run_strategy_switch"](ia, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100, 2), "mdd": round(_mdd(eq)*100, 2),
           "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]), 0),
           "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]),
           "switch_log": [list(x) for x in res.meta["switch_log"]]}
    for w, d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100, 2)
    return out, res

out = {}
# leg1: verbatim recompute
ia, ib, ra, rb, CA = shadows(0)
cal, res = run_switch(ia, ib, ra, rb, CA, NS_CAL, 0)
row = json.loads((ROOT/"results"/"r30_bt"/"sweep_beat_m07_k17.json").read_text())
js = next(r for r in row if r["tag"] == "k17_calmar_M07")
out["leg1_recompute"] = {"mine": cal,
    "match_total": abs(cal["total"]-js["total"]) < 1e-9, "match_mdd": abs(cal["mdd"]-js["mdd"]) < 1e-9,
    "match_trades": cal["trades"] == js["trades"], "match_cost": cal["cost"] == js["cost"],
    "match_switch": cal["switch_log"] == js["switch_log"],
    "nbeat_m07": sum(1 for w in WINDOWS if cal[w] > M07[w])}
# leg3: ex-top3 on recompute trades
tr = res.trades; pnl = tr["net_pnl"].fillna(0); top3 = pnl.nlargest(3).sum()
eq0 = float(_s(res.eq).dropna().iloc[0])
out["leg3_extop3"] = {"calmar_extop3_total": round(float((eq0+pnl.sum()-top3)/eq0-1)*100, 2),
    "m07_extop3_total": 1351.75}
# leg2: cross-phase
out["leg2_xphase"] = []
for ph in [0, 5, 7, 10, 14, 15]:
    ia2, ib2, ra2, rb2, CA2 = shadows(ph)
    c, _ = run_switch(ia2, ib2, ra2, rb2, CA2, NS_CAL, ph)
    m, _ = run_switch(ia2, ib2, ra2, rb2, CA2, NS_RAW, ph)
    out["leg2_xphase"].append({"ph": ph,
        "calmar_total": c["total"], "raw_total": m["total"],
        "nbeat_phase_matched": sum(1 for w in WINDOWS if c[w] > m[w])})
# leg4: slip x2
ia4, ib4, ra4, rb4, CA4 = shadows(0, slip=0.004)
c4, _ = run_switch(ia4, ib4, ra4, rb4, CA4, NS_CAL, 0)
out["leg4_slipx2"] = {"total": c4["total"], "mdd": c4["mdd"],
    "nbeat_vs_stdM07": sum(1 for w in WINDOWS if c4[w] > M07[w]),
    "delta_total_vs_ph0": round(c4["total"]-cal["total"], 2)}
# leg5: full decision-set lookahead equivalence (every A-grid signal day, both legs, 3 metrics)
import numpy as np
full_a, full_b = _s(ra.eq), _s(rb.eq)
sig_days = [d for d in grid_dates if d >= pd.Timestamp(RUN_START)]
n = 0; mx = 0.0
for t in sig_days:
    for full in (full_a, full_b):
        if t not in full.index: continue
        trunc = full.loc[:t]
        if len(trunc) < 61: continue
        j = int(full.index.searchsorted(t, side="right") - 1)
        if full.index[j] != trunc.index[-1]:
            out["leg5_index_mismatch"] = str(t); continue
        w = full.iloc[j-60:j+1].astype(float)
        rr = w.iloc[1:].to_numpy()/w.iloc[:-1].to_numpy()-1.0
        R = float(w.iloc[-1]/w.iloc[0]-1.0)
        for m in ("sharpe", "calmar", "downside"):
            a = metric_k17(trunc, m)
            if m == "sharpe":
                mm, ss = float(np.mean(rr)), float(np.std(rr, ddof=1))
                b = (1e9 if mm > 0 else (-1e9 if mm < 0 else 0.0)) if ss < 1e-12 else mm/ss
            elif m == "calmar":
                dd = float((w/w.cummax()-1.0).min()); aa = -dd
                b = (1e9 if R > 0 else (0.0 if R == 0 else -1e9)) if aa < 1e-12 else R/aa
            else:
                dd = float(np.sqrt(np.mean(np.minimum(rr, 0.0)**2)))
                b = (1e9 if R > 0 else (0.0 if R == 0 else -1e9)) if dd < 1e-12 else R/dd
            mx = max(mx, abs(a-b)); n += 1
out["leg5_lookahead"] = {"combos": n, "max_abs_diff": mx}
(ROOT/"team"/"audit"/"batch_045_m07k17"/"tline_k17_calmar_out.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps({"leg1": out["leg1_recompute"], "leg3": out["leg3_extop3"], "leg2": out["leg2_xphase"], "leg4": out["leg4_slipx2"], "leg5": out["leg5_lookahead"]}, ensure_ascii=False, indent=1))
