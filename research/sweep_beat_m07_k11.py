#!/usr/bin/env python3
"""K11: joint-rebuild pilot = new switch family (hysteresis + brake-freeze) x new
selector (K10 a60_a5 composite) = 6 new configs + base_M07 calibration.

Baseline = M07 final (ph0). Caliber verbatim run_m07_final.py / K1-K10 except the
switch-mechanism x selector joint (ph0 / RUN_START=2023-01-03 /
EVAL_END=2026-11-12 / 50k / real fee (cost_one_way=None) / slip=0.002 /
lot=100 / legacy_grid=False / full_liquidate=True / stop_exec=next /
MB exclusion / brake bx0.18/by0.08/bf0.6):
M07: A band=(0.02,0.30) gate60=-0.15 cut=0.80 win=40 take=1.2 n=5 rebal=20 exp=1.0;
     B band=(0.05,0.30) gate60=-1.0 cut=0.80 win=20 take=0.8 n=4 rebal=30 exp=0.9;
     stop=0.25; RS trailing (M07 rule ra>=rb->A else B, rs_lookback=60).
K11 dims (6 new configs, all lock_mode=None, no lookahead, no caliber patchwork):
  family k11_hyst_brakefreeze (research/family_k11.py build_ns_k11, fixed traits:
    hysteresis band + freeze switching while brake ON; brake itself verbatim M07)
  x hyst h in {0.02, 0.05, 0.10} (3 param values)
  x legs in B (B-leg only -> K10 a60_a5, A-leg keeps M07 MaxInputs)
            / both (both legs -> K10 a60_a5, per-leg AB params unchanged)
  + base_M07 calibration row (verbatim total 1863.27 / mdd -27.05, six windows).
Dedup: K1-K10 never introduced a hysteresis/brake-freeze switch family; K11 tags
are all k11_ prefixed, no overlap with prior json tags -> 0 skipped, run all.
New configs strictly = 6, within budget (<=8).
Decision: strict > vs M07 ph0 six windows, beat_all and mdd>-27.05 is win_all.
Output: results/r30_bt/sweep_beat_m07_k11.json (K2 schema + family/hyst/brake_freeze).
Repro:
  .venv/bin/python research/sweep_beat_m07_k11.py --check-trailing  # truncation spot-check
  .venv/bin/python research/sweep_beat_m07_k11.py --only base_M07   # base calibration row
  .venv/bin/python research/sweep_beat_m07_k11.py                   # full 6+1 and dump
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
from inputs_k10 import K10Inputs
from family_k11 import build_ns_k11, FAMILY
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
SEL = "a60_a5"
NS_M07 = build_ns(0.18, 0.08, 0.6)
_NS_K11 = {}
def NS_K11(h):
    if h not in _NS_K11:
        _NS_K11[h] = build_ns_k11(hyst=h, brake_freeze=True, bx=0.18, by_=0.08, bf=0.6)
    return _NS_K11[h]
_inp_cache = {}
_shadow_cache = {}


def get_inp(kind, leg):
    key = (kind, leg)
    if key not in _inp_cache:
        P = A_P if leg == "A" else B_P
        if kind == "M07":
            _inp_cache[key] = MaxInputs(piv, **P)
        else:
            _inp_cache[key] = K10Inputs(piv, use_max=True, sel=kind, **P)
    return _inp_cache[key]


def get_shadow(kind, leg, n, rebal, take, exposure):
    key = (kind, leg, n, rebal, take, exposure)
    if key not in _shadow_cache:
        inp = get_inp(kind, leg)
        factor = "amihud_60" if kind == "M07" else kind
        CA = dict(factor=factor, stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
        _shadow_cache[key] = (inp, pc.run_strategy(inp, n=n, rebal=rebal, take=take, exposure=exposure, phase=0, **CA), CA)
    return _shadow_cache[key]


def run_one(tag, combo, legs, hyst=None):
    is_base = (tag == "base_M07")
    a_kind = "M07" if (is_base or legs == "B") else SEL
    b_kind = "M07" if is_base else SEL
    inp_a, ra, CA = get_shadow(a_kind, "A", 5, 20, 1.2, 1.0)
    inp_b, rb, _CB = get_shadow(b_kind, "B", 4, 30, 0.80, 0.9)
    CFG_B = dict(n=4, rebal=30, take=0.80, exposure=0.9)
    # switch engine takes a single factor for both legs: K10 instances bind sel at
    # construction and ignore the passed factor; M07 legs use amihud_60.
    kw_factor = "amihud_60" if (is_base or legs == "B") else SEL
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=60, exclude_a=MB, exclude_b=MB, factor=kw_factor, **{k: v for k, v in CA.items() if k not in ("exclude", "factor")})
    NS = NS_M07 if is_base else NS_K11(hyst)
    res = NS["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "family": ("m07_baseline" if is_base else FAMILY), "selector": ("amihud_60" if is_base else SEL), "legs": legs, "max_filter": "on", "hyst": hyst, "brake_freeze": (None if is_base else True), "combo": combo, "total": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2), "mdd": round(_mdd(eq) * 100, 2), "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]), 0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "brakes": len(res.meta.get("brake_log", [])) // 2, "switch_log": [list(x) for x in res.meta["switch_log"]], "brake_log": [list(x) for x in res.meta.get("brake_log", [])]}
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


CFGS = [dict(tag="base_M07", combo="M07 verbatim calibration row", legs="B", hyst=None)]
for _h in [0.02, 0.05, 0.10]:
    for _legs, _ln in [("B", "single-B"), ("both", "both-legs")]:
        CFGS.append(dict(tag="k11_h%02d_%s" % (round(_h * 100), _legs), combo="hyst %.2f + brake-freeze x a60_a5 + %s + MAX on" % (_h, _ln), legs=_legs, hyst=_h))
assert len([c for c in CFGS if c["tag"] != "base_M07"]) == 6, CFGS


def dedup_check(cfgs):
    seen_tags = set()
    for i in list(range(1, 11)) + ["j04_k1", "j04_k2"]:
        fn = "sweep_beat_m07_k%s.json" % i if isinstance(i, int) else "sweep_beat_%s.json" % i
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
            skipped.append((cfg["tag"], cfg["combo"], "tag seen in K1-K10 json"))
            continue
        kept.append(cfg)
    return kept, skipped


def trailing_check():
    """Truncation cross-check: full-piv instance vs truncated-to-T instance must
    give byte-identical picks on T (covers selector a60_a5 x 2 dates), plus a
    manual recomputation spot-check of amihud5. Any use of t+1-or-later data in
    any matrix/sort would diverge the truncated instance. The switch signal
    itself (_rs via searchsorted right-1 on shadow eq; _brake from pre-rebalance
    t-day mark-to-market) reads t-and-before only by construction.
    """
    TS = [pd.Timestamp("2024-06-03"), pd.Timestamp("2025-09-01")]
    for T in TS:
        assert T in dates, T
    print("piv keys: %s" % sorted(piv.keys()), flush=True)
    ok_all = True
    inp_full = K10Inputs(piv, sel=SEL, **B_P)
    for T in TS:
        piv_tr = {k: (v[v.index <= T] if (hasattr(v, "index") and str(getattr(v.index, "dtype", "")) == "datetime64[ns]") else v)
                  for k, v in piv.items()}
        inp_tr = K10Inputs(piv_tr, sel=SEL, **B_P)
        p_full = inp_full.picks(T, 4, exclude=MB)
        p_tr = inp_tr.picks(T, 4, exclude=MB)
        ok = (p_full == p_tr)
        ok_all &= ok
        print("TRUNC %s %s full=%s trunc=%s %s"
              % (SEL, T.date(), p_full, p_tr, "OK" if ok else "MISMATCH"),
              flush=True)
    T = TS[0]
    inp = K10Inputs(piv, sel=SEL, **B_P)
    code = inp.amihud5.loc[T].dropna().index[0]
    loc = inp.close.index.get_loc(T)
    px = inp.close.iloc[loc-5:loc+1, inp.close.columns.get_loc(code)]
    am = inp.amount.iloc[loc-5:loc+1, inp.amount.columns.get_loc(code)]
    manual = float((px.pct_change(fill_method=None).abs().iloc[1:] / (am.iloc[1:] / 1e8)).mean())
    stored = float(inp.amihud5.loc[T, code])
    ok = abs(manual - stored) < 1e-9
    ok_all &= ok
    print("SPOT amihud5 %s %s manual=%.6f stored=%.6f %s"
          % (code, T.date(), manual, stored, "OK" if ok else "MISMATCH"), flush=True)
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
            r = run_one(cfg["tag"], cfg["combo"], cfg["legs"], cfg["hyst"])
            print(json.dumps(r, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (cfg["tag"], e), flush=True)
            import traceback; traceback.print_exc()
    if not args.only:
        outp = ROOT / "results" / "r30_bt" / "sweep_beat_m07_k11.json"
        outp.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        print("saved %d rows -> %s" % (len(rows), outp), flush=True)
