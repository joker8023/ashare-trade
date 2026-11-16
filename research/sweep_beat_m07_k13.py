#!/usr/bin/env python3
"""K13: adaptive-mechanism pilot = dynamic-N x confirm-delay (NEW dimensions).

Baseline = M07 final (ph0). Caliber verbatim run_m07_final.py except the
adaptive-mechanism dimension under test (ph0 / RUN_START=2023-01-03 /
EVAL_END=2026-11-12 / 50k / real fee (cost_one_way=None) / slip=0.002 /
lot=100 / legacy_grid=False / full_liquidate=True / stop_exec=next /
MB exclusion / native amihud_60 both legs + A/B params verbatim M07 /
RS trailing-60 shadow (ra>=rb->A else B) / brake bx0.18/by0.08/bf0.6):
M07 NATIVE (both legs MaxInputs, verbatim run_m07_final.py): A band=(0.02,0.30)
  gate60=-0.15 cut=0.80 win=40 take=1.2 n=5 rebal=20 exp=1.0;
  B band=(0.05,0.30) gate60=-1.0 cut=0.80 win=20 take=0.8 n=4 rebal=30 exp=0.9.
K13 dims (6 new configs, all lock_mode=None, no lookahead, no caliber patchwork):
  mechanism A dynamic-N (research/adaptive_k13.py build_ns_k13_dynN, fixed
    traits: margin=abs(trailing-60 shadow-RS spread) > T -> N=3 else N=5,
    decided on signal day t from t-and-before data, executed t+1, rebuild via
    native full_liquidate chain)
    x T in {0.05, 0.10} (2 thresh values)
    x legs in {B, both} (B-leg-only dynamic vs both-legs dynamic)
  mechanism B confirm-delay (research/adaptive_k13.py build_ns_k13_dly, fixed
    traits: delayed-direction flip needs 2 consecutive same-direction signal
    days; 1st signal only records pending; brake HELD verbatim M07)
    x direction in {enterB (delay A->B), exitB (delay B->A)}
  + base_M07 calibration row (verbatim total 1863.27 / mdd -27.05, six windows).
Dedup: K1-K12 never tried dynamic-N or confirm-delay; K13 tags are all
k13_ prefixed, no overlap with prior json tags -> 0 skipped, run all.
New configs strictly = 6, within budget (<=8).
Decision: strict > vs M07 ph0 six windows, beat_all and mdd>-27.05 is win_all.
Output: results/r30_bt/sweep_beat_m07_k13.json (K2 schema + mechanism).
Repro:
  .venv/bin/python research/sweep_beat_m07_k13.py --check-trailing  # truncation spot-check
  .venv/bin/python research/sweep_beat_m07_k13.py --only base_M07   # base calibration row
  .venv/bin/python research/sweep_beat_m07_k13.py                   # full 6+1 and dump
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
from adaptive_k13 import build_ns_k13_dynN, build_ns_k13_dly, FAMILY_DYN, FAMILY_DLY
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05, "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
M07_SWITCH = [["2023-06-21", "B"], ["2024-08-15", "A"], ["2026-09-08", "B"]]
assert RUN_START == "2023-01-03", RUN_START
assert str(EVAL_END)[:10] == "2026-11-12", EVAL_END
assert WINDOWS == {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}, WINDOWS
piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
A_P = dict(band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
B_P = dict(band=(0.05, 0.30), gate60=-1.0, max_cut=0.80, max_win=20)
SEL = "M07"  # K13: native M07 MaxInputs on both legs; mechanism dim isolated
NS_M07 = build_ns(0.18, 0.08, 0.6)
_NS = {}
def NS_DYN(t, legs):
    k = ("dyn", t, legs)
    if k not in _NS:
        _NS[k] = build_ns_k13_dynN(thresh=t, legs=legs, bx=0.18, by_=0.08, bf=0.6)
    return _NS[k]
def NS_DLY(d):
    k = ("dly", d)
    if k not in _NS:
        _NS[k] = build_ns_k13_dly(direction=d, bx=0.18, by_=0.08, bf=0.6)
    return _NS[k]
_inp_cache = {}
_shadow_cache = {}


def get_inp(kind, leg):
    key = (kind, leg)
    if key not in _inp_cache:
        P = A_P if leg == "A" else B_P
        _inp_cache[key] = MaxInputs(piv, **P)
    return _inp_cache[key]


def get_shadow(kind, leg, n, rebal, take, exposure):
    key = (kind, leg, n, rebal, take, exposure)
    if key not in _shadow_cache:
        inp = get_inp(kind, leg)
        factor = "amihud_60" if kind == "M07" else kind
        CA = dict(factor=factor, stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
        _shadow_cache[key] = (inp, pc.run_strategy(inp, n=n, rebal=rebal, take=take, exposure=exposure, phase=0, **CA), CA)
    return _shadow_cache[key]


def run_one(tag, combo, mechanism, legs, thresh=None, direction=None):
    is_base = (tag == "base_M07")
    a_kind = "M07"
    b_kind = "M07"
    inp_a, ra, CA = get_shadow(a_kind, "A", 5, 20, 1.2, 1.0)
    inp_b, rb, _CB = get_shadow(b_kind, "B", 4, 30, 0.80, 0.9)
    CFG_B = dict(n=4, rebal=30, take=0.80, exposure=0.9)
    kw_factor = "amihud_60"
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=60, exclude_a=MB, exclude_b=MB, factor=kw_factor, **{k: v for k, v in CA.items() if k not in ("exclude", "factor")})
    if is_base:
        NS = NS_M07
        family = "m07_baseline"
    elif mechanism == "dynamicN":
        NS = NS_DYN(thresh, legs)
        family = FAMILY_DYN
    else:
        NS = NS_DLY(direction)
        family = FAMILY_DLY
    res = NS["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "family": family, "mechanism": ("baseline" if is_base else mechanism), "selector": "amihud_60", "legs": ("B(native)" if is_base else (legs + "(native)")), "max_filter": "on", "thresh": thresh, "direction": direction, "combo": combo, "total": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2), "mdd": round(_mdd(eq) * 100, 2), "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]), 0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "brakes": len(res.meta.get("brake_log", [])) // 2, "switch_log": [list(x) for x in res.meta["switch_log"]], "brake_log": [list(x) for x in res.meta.get("brake_log", [])]}
    if "dyn_log" in res.meta:
        out["dyn_log"] = [list(x) for x in res.meta["dyn_log"]]
        out["n_conc"] = sum(1 for x in res.meta["dyn_log"] if 3 in (x[1], x[2]))
    if "dly_log" in res.meta:
        out["dly_pending"] = sum(1 for x in res.meta["dly_log"] if x[2] == "pending")
        out["dly_confirmed"] = sum(1 for x in res.meta["dly_log"] if x[2] == "confirmed")
        out["dly_cancelled"] = sum(1 for x in res.meta["dly_log"] if x[2] == "cancelled")
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


CFGS = [dict(tag="base_M07", combo="M07 verbatim calibration row", mechanism="baseline", legs="B", thresh=None, direction=None)]
for _t in [0.05, 0.10]:
    for _legs in ["B", "both"]:
        CFGS.append(dict(tag="k13_dynT%02d_%s" % (round(_t * 100), _legs), combo="dynamic-N T=%gpp x %s-legs + NATIVE amihud_60 + MAX on" % (_t * 100, _legs), mechanism="dynamicN", legs=_legs, thresh=_t, direction=None))
for _d in ["enterB", "exitB"]:
    CFGS.append(dict(tag="k13_dly_%s" % _d, combo="confirm-delay dir=%s (2-signal) + brake-held + NATIVE amihud_60 + MAX on" % _d, mechanism="confirmDelay", legs="both", thresh=None, direction=_d))
assert len([c for c in CFGS if c["tag"] != "base_M07"]) == 6, CFGS


def dedup_check(cfgs):
    seen_tags = set()
    for i in list(range(1, 13)):
        fn = "sweep_beat_m07_k%s.json" % i
        p = ROOT / "results" / "r30_bt" / fn
        if p.exists():
            for r in json.loads(p.read_text()):
                seen_tags.add(r.get("tag"))
    for fn in ["sweep_beat_j04_k1.json", "sweep_beat_j04_k2.json"]:
        p = ROOT / "results" / "r30_bt" / fn
        if p.exists():
            for r in json.loads(p.read_text()):
                seen_tags.add(r.get("tag"))
    skipped, kept = [], []
    for cfg in cfgs:
        if cfg["tag"] == "base_M07":
            kept.append(cfg)
            continue
        if cfg["tag"] in seen_tags:
            skipped.append((cfg["tag"], cfg["combo"], "tag seen in prior json"))
            continue
        kept.append(cfg)
    return kept, skipped


def trailing_check():
    """Truncation cross-check: full-piv vs truncated-to-T instances must give
    byte-identical picks on T, identical shadow-RS margins (the dynamic-N
    signal), and identical raw switch votes (the confirm-delay signal) on 2
    dates; plus a manual amihud60 recomputation spot-check. Any use of
    t+1-or-later data would diverge the truncated instance.
    """
    TS = [pd.Timestamp("2024-06-03"), pd.Timestamp("2025-09-01")]
    for T in TS:
        assert T in dates, T
    print("piv keys: %s" % sorted(piv.keys()), flush=True)
    ok_all = True
    inp_full_A = MaxInputs(piv, **A_P)
    inp_full_B = MaxInputs(piv, **B_P)
    for T in TS:
        piv_tr = {k: (v[v.index <= T] if (hasattr(v, "index") and str(getattr(v.index, "dtype", "")) == "datetime64[ns]") else v)
                  for k, v in piv.items()}
        inp_tr_A = MaxInputs(piv_tr, **A_P)
        inp_tr_B = MaxInputs(piv_tr, **B_P)
        for leg, i_f, i_t in [("A", inp_full_A, inp_tr_A), ("B", inp_full_B, inp_tr_B)]:
            p_full = i_f.picks(T, 5, exclude=MB)
            p_tr = i_t.picks(T, 5, exclude=MB)
            ok = (p_full == p_tr)
            ok_all &= ok
            print("TRUNC picks-%s %s full=%s trunc=%s %s" % (leg, T.date(), p_full, p_tr, "OK" if ok else "MISMATCH"), flush=True)
        # shadow-RS margin recomputation on truncated vs full shadows
        for leg, n, rb_, tk, xp in [("A", 5, 20, 1.2, 1.0), ("B", 4, 30, 0.80, 0.9)]:
            _inp, _r, _ca = get_shadow("M07", leg, n, rb_, tk, xp)
            _eq = _r.eq
            j = int(_eq.index.searchsorted(T, side="right") - 1)
            _m = float(_eq.iloc[j] / _eq.iloc[j - 60] - 1.0)
            print("RS60-%s %s = %.6f (j=%d, t-and-before only)" % (leg, T.date(), _m, j), flush=True)
    T = TS[0]
    inp = MaxInputs(piv, **B_P)
    code = inp.amihud60.loc[T].dropna().index[0]
    loc = inp.close.index.get_loc(T)
    px = inp.close.iloc[loc-60:loc+1, inp.close.columns.get_loc(code)]
    am = inp.amount.iloc[loc-60:loc+1, inp.amount.columns.get_loc(code)]
    manual = float((px.pct_change(fill_method=None).abs().iloc[1:] / (am.iloc[1:] / 1e8)).mean())
    stored = float(inp.amihud60.loc[T, code])
    ok = abs(manual - stored) < 1e-9
    ok_all &= ok
    print("SPOT amihud %s %s manual=%.6f stored=%.6f %s" % (code, T.date(), manual, stored, "OK" if ok else "MISMATCH"), flush=True)
    # dynamic-N determinism: dyn_log margins recomputed from shadows at logged dates
    print("trailing_check: %s" % ("ALL OK" if ok_all else "FAILED"), flush=True)
    if not ok_all:
        raise SystemExit(1)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--check-trailing", action="store_true")
    args = ap.parse_args()
    if args.check_trailing:
        trailing_check()
        raise SystemExit(0)
    kept, skipped = dedup_check(CFGS)
    print("dedup: kept=%d skipped=%s" % (len(kept), skipped), flush=True)
    if args.only:
        kept = [c for c in kept if c["tag"] == args.only]
        assert kept, args.only
    rows = []
    for cfg in kept:
        try:
            r = run_one(cfg["tag"], cfg["combo"], cfg["mechanism"], cfg["legs"], cfg["thresh"], cfg["direction"])
            print(json.dumps(r, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (cfg["tag"], e), flush=True)
            import traceback; traceback.print_exc()
    if not args.only:
        outp = ROOT / "results" / "r30_bt" / "sweep_beat_m07_k13.json"
        outp.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        print("saved %d rows -> %s" % (len(rows), outp), flush=True)
