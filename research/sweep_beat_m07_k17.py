#!/usr/bin/env python3
"""K17: risk-adjusted shadow-RS switch pilot (NEW scale, dedup vs K1-K16).

Background: K1-K16 (167 new configs, beat_all=0) falsified every variant of
the RAW-return trailing-60 shadow-RS comparison (RS30-120 / hysteresis /
bandwidth / confirm-delay). Never tested: changing the comparison SCALE
itself. K17 pilots 3 risk-adjusted scales on the trailing-60 shadow window
(t-and-before data only, A-grid signal days only, flips at t+1 close):

  sharpe   : shadow daily-ret mean / vol  (trailing 60)
  calmar   : trailing-60 point return / trailing-60 max-drawdown depth
  downside : trailing-60 point return / downside deviation

Caliber otherwise verbatim M07 ph0 (RUN_START=2023-01-03 /
EVAL_END=2026-11-12 / 50k / real fee (cost_one_way=None) / slip=0.002 /
lot=100 / legacy_grid=False / full_liquidate=True / stop_exec=next / MB
exclusion / native amihud_60 legs / A+B params verbatim M07 / brake verbatim
M07). Engine code: research/riskadj_k17.py build_ns_k17 (this file only
composes it; no edit to switch_engine.py).

Pilot plan (<=6 new + base_M07 calibration):
  phase 1: 3 scales x native-M07 seat (k17_<metric>_M07).
  phase 2: for each scale with nbeat_m07>=3 (priority sharpe>calmar>
           downside), add the same scale x g_bf07 seat (K3 row: cut 0.78
           both legs + brake bx0.15/by0.05/bf0.7), keeping TOTAL rows <= 6
           (base_M07 counts toward the 6).
Output: results/r30_bt/sweep_beat_m07_k17.json (K2 schema + rs_metric).
Repro:
  .venv/bin/python research/sweep_beat_m07_k17.py              # calib + pilot (+phase2 iff gate)
  .venv/bin/python research/sweep_beat_m07_k17.py --only k17_sharpe_M07
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from riskadj_k17 import build_ns_k17, metric_k17
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB

M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05, "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
M07_SWITCH = [["2023-06-21", "B"], ["2024-08-15", "A"], ["2026-09-08", "B"]]
assert RUN_START == "2023-01-03", RUN_START
assert str(EVAL_END)[:10] == "2026-11-12", EVAL_END
assert WINDOWS == {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}, WINDOWS

A_M07 = dict(band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
B_M07 = dict(band=(0.05, 0.30), gate60=-1.0, max_cut=0.80, max_win=20)
A_GBF07 = dict(band=(0.02, 0.30), gate60=-0.15, max_cut=0.78, max_win=40)
B_GBF07 = dict(band=(0.05, 0.30), gate60=-1.0, max_cut=0.78, max_win=20)
MBX, MBY, MBF = 0.18, 0.08, 0.6
GBX, GBY, GBF = 0.15, 0.05, 0.7
METRICS = ("sharpe", "calmar", "downside")

piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))

_inp_cache = {}
_shadow_cache = {}
_ns_cache = {}

def get_inp(seat, leg):
    key = (seat, leg)
    if key not in _inp_cache:
        P = {"M07": A_M07 if leg == "A" else B_M07,
             "gbf07": A_GBF07 if leg == "A" else B_GBF07}[seat]
        _inp_cache[key] = MaxInputs(piv, **P)
    return _inp_cache[key]

def get_shadow(seat, leg):
    key = (seat, leg)
    if key not in _shadow_cache:
        inp = get_inp(seat, leg)
        n, rebal, take, expo = (5, 20, 1.2, 1.0) if leg == "A" else (4, 30, 0.80, 0.9)
        CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB,
                  capital=50000.0, lot=100, cost_one_way=None, slip=0.002,
                  run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END,
                  legacy_grid=False, full_liquidate=True)
        _shadow_cache[key] = (inp, pc.run_strategy(inp, n=n, rebal=rebal, take=take,
                                                   exposure=expo, phase=0, **CA), CA)
    return _shadow_cache[key]

def get_ns(seat, metric):
    key = (seat, metric)
    if key not in _ns_cache:
        if metric == "raw":
            bx, by_, bf = (MBX, MBY, MBF) if seat == "M07" else (GBX, GBY, GBF)
            _ns_cache[key] = build_ns(bx, by_, bf)
        else:
            bx, by_, bf = (MBX, MBY, MBF) if seat == "M07" else (GBX, GBY, GBF)
            _ns_cache[key] = build_ns_k17(metric, bx, by_, bf)
    return _ns_cache[key]

def run_one(tag, seat, metric, combo):
    inp_a, ra, CA = get_shadow(seat, "A")
    inp_b, rb, _CB = get_shadow(seat, "B")
    CFG_B = dict(n=4, rebal=30, take=0.80, exposure=0.9)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b,
              cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=60,
              exclude_a=MB, exclude_b=MB, factor="amihud_60",
              **{k: v for k, v in CA.items() if k not in ("exclude", "factor")})
    NS = get_ns(seat, metric)
    res = NS["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "base": seat, "family": "k17_riskadj_rs",
           "mechanism": ("baseline" if metric == "raw" else "riskadj_rs"),
           "selector": "amihud_60", "rs_metric": metric,
           "legs": "B(native)", "max_filter": "on", "combo": combo,
           "total": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
           "mdd": round(_mdd(eq) * 100, 2),
           "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]), 0),
           "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]),
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

def truncation_check():
    """No-lookahead audit: score at signal day t from the FULL shadow series
    (iloc slice <= j) must equal metric_k17 on the shadow TRUNCATED at t."""
    import numpy as np
    sig_idx = sorted(set(
        [i for i in range(300, len(dates), 20)
         if dates[i] >= pd.Timestamp(RUN_START)]) )
    picks = []
    for seat in ("M07", "gbf07"):
        _, ra, _ = get_shadow(seat, "A")
        _, rb, _ = get_shadow(seat, "B")
        eqa = ra.eq.iloc[:, 0] if isinstance(ra.eq, pd.DataFrame) else ra.eq
        eqb = rb.eq.iloc[:, 0] if isinstance(rb.eq, pd.DataFrame) else rb.eq
        found = []
        for si in sig_idx:
            t = dates[si]
            if len(eqa.loc[:t]) >= 61 and len(eqb.loc[:t]) >= 61:
                found.append(si)
        assert len(found) >= 2, (seat, len(found))
        picks.append((seat, found[0]))
        picks.append((seat, found[len(found)//2]))
    n = 0
    for seat, si in picks:
        t = dates[si]
        for leg in ("A", "B"):
            _, rsh, _ = get_shadow(seat, leg)
            full = rsh.eq.iloc[:, 0] if isinstance(rsh.eq, pd.DataFrame) else rsh.eq
            trunc = full.loc[:t]
            assert len(trunc) >= 61, (seat, leg, str(t), len(trunc))
            j = int(full.index.searchsorted(t, side="right") - 1)
            assert full.index[j] == trunc.index[-1], (seat, leg, str(t))
            for m in METRICS:
                a = metric_k17(trunc, m)          # truncated-at-t path
                w = full.iloc[j-60:j+1].astype(float)  # full-series slice path (<=j only)
                rr = w.iloc[1:].to_numpy() / w.iloc[:-1].to_numpy() - 1.0
                R = float(w.iloc[-1] / w.iloc[0] - 1.0)
                if m == "sharpe":
                    mm, ss = float(np.mean(rr)), float(np.std(rr, ddof=1))
                    b = (1e9 if mm > 0 else (-1e9 if mm < 0 else 0.0)) if ss < 1e-12 else mm / ss
                elif m == "calmar":
                    dd = float((w / w.cummax() - 1.0).min()); aa = -dd
                    b = (1e9 if R > 0 else (0.0 if R == 0 else -1e9)) if aa < 1e-12 else R / aa
                else:
                    dd = float(np.sqrt(np.mean(np.minimum(rr, 0.0) ** 2)))
                    b = (1e9 if R > 0 else (0.0 if R == 0 else -1e9)) if dd < 1e-12 else R / dd
                assert abs(a - b) < 1e-9, (seat, leg, m, str(t), a, b)
                n += 1
    print("truncation_check PASS: %d (seat,leg,metric,t) combos, full==truncated" % n, flush=True)

def slim(r):
    return {k: r[k] for k in ("tag", "base", "rs_metric", "total", "mdd", "trades",
            "cost", "switches", "1m", "3m", "6m", "1y", "2y", "3y",
            "nbeat_m07", "beat_all", "mdd_better", "win_all", "switch_same_m07")}

CFGS_PILOT = [
    dict(tag="k17_sharpe_M07", seat="M07", metric="sharpe",
         combo="native-M07 seat x Sharpe-RS switch (trailing-60 mean/vol)"),
    dict(tag="k17_calmar_M07", seat="M07", metric="calmar",
         combo="native-M07 seat x Calmar-RS switch (trailing-60 ret/mdd)"),
    dict(tag="k17_downside_M07", seat="M07", metric="downside",
         combo="native-M07 seat x downside-RS switch (trailing-60 ret/downvol)"),
]

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    outp = ROOT / "results" / "r30_bt" / "sweep_beat_m07_k17.json"
    pool = [dict(tag="base_M07", seat="M07", metric="raw",
                 combo="M07 verbatim calibration row")] + CFGS_PILOT
    if args.only:
        cfg = next((c for c in pool if c["tag"] == args.only), None)
        assert cfg, args.only
        truncation_check()
        r = run_one(cfg["tag"], cfg["seat"], cfg["metric"], cfg["combo"])
        print(json.dumps(slim(r), ensure_ascii=False), flush=True)
        raise SystemExit(0)
    rows = []
    base = run_one("base_M07", "M07", "raw", "M07 verbatim calibration row")
    print(json.dumps(slim(base), ensure_ascii=False), flush=True)
    assert abs(base["total"] - M07["total"]) <= 0.01 and abs(base["mdd"] - M07["mdd"]) <= 0.01, \
        ("M07 caliber drift", base["total"], base["mdd"])
    assert base["switch_log"] == M07_SWITCH, base["switch_log"]
    print("calib OK: base_M07 total=%.2f mdd=%.2f switches=%d" % (
        base["total"], base["mdd"], base["switches"]), flush=True)
    rows.append(base)
    truncation_check()
    for cfg in CFGS_PILOT:
        r = run_one(cfg["tag"], cfg["seat"], cfg["metric"], cfg["combo"])
        print(json.dumps(slim(r), ensure_ascii=False), flush=True)
        rows.append(r)
    # phase 2: qualifying metric (nbeat>=3) x g_bf07 seat, priority
    # sharpe > calmar > downside, TOTAL rows <= 6 (base counts).
    qual = [r for r in rows if r["tag"].startswith("k17_") and r["nbeat_m07"] >= 3]
    pri = {"sharpe": 0, "calmar": 1, "downside": 2}
    qual = sorted(qual, key=lambda r: pri[r["rs_metric"]])
    added = []
    for q in qual:
        if len(rows) >= 6:
            print("cap: total rows=6 reached, skip g_bf07 x %s (priority cutoff)" % q["rs_metric"], flush=True)
            continue
        m = q["rs_metric"]
        r = run_one("k17_%s_gbf07" % m, "gbf07", m,
                    "g_bf07 seat (K3 row) x %s-RS switch" % m)
        print(json.dumps(slim(r), ensure_ascii=False), flush=True)
        rows.append(r)
        added.append(r["tag"])
    if not qual:
        print("phase2 SKIPPED with note: no pilot metric reached nbeat>=3", flush=True)
    outp.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print("saved %d rows -> %s | phase2 added: %s" % (
        len(rows), outp, added if added else "none"), flush=True)
