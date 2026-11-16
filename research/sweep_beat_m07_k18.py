#!/usr/bin/env python3
"""K18: rank-weight pilot -- sorting-weighted intra-leg sizing (NEW dimension).

Background: K1-K17 (170 new configs, beat_all=0) all held EQUAL weight within
each leg (alloc = equity*exposure/N). Never tested: splitting the leg budget
by signal-day sort order. K18 pilots 2 of 3 schemes (linear-rank vs
Amihud-value-proportional; sqrt-rank skipped as the interpolant, see
research/weight_k18.py) on the g_bf07 seat (the only 5/6-window config:
total 2128.41/mdd -24.28; 1m -0.01pp, rest +0.01/+0.30/+0.85/+13.53/+197.95pp)
plus B-leg single-leg weighted rows (same seat, same weights).

Caliber verbatim M07 ph0 (RUN_START=2023-01-03 / EVAL_END=2026-11-12 / 50k /
real fee (cost_one_way=None) / slip=0.002 / lot=100 / legacy_grid=False /
full_liquidate=True / stop_exec=next / MB exclusion / native amihud_60 legs /
A band=(0.02,0.30) gate60=-0.15 cut=0.80/0.78 win=40 take=1.2 n=5 rebal=20
exp=1.0; B band=(0.05,0.30) gate60=-1.0 cut=0.80/0.78 win=20 take=0.8 n=4
rebal=30 exp=0.9; RS trailing-60 shadow / brake M07 bx0.18/by0.08/bf0.6,
g_bf07 bx0.15/by0.05/bf0.7) EXCEPT intra-leg weights under test:
  alloc_i = equity_now * leg_exposure * w_i, sum w = 1, lot-rounded with the
  verbatim cash-fallback chain. Weights use signal-day (t) factor snapshot
  only; execution stays t+1. Shadow curves are re-run with the SAME weighting
  (no equal-weight shadow mismatch); RS stays trailing-60 raw-return compare.
  Long-only, no leverage.

Rows (2 calib + 4 new <= 6 new):
  base_M07 / base_gbf07 : verbatim equal-weight calibration rows
  k18_ranklin_gbf07     : g_bf07 switch x rank_linear, both legs weighted
  k18_amiprop_gbf07     : g_bf07 switch x amihud_prop, both legs weighted
  k18_ranklin_B         : single-leg B (g_bf07 B params) x rank_linear
  k18_amiprop_B         : single-leg B (g_bf07 B params) x amihud_prop

Output: results/r30_bt/sweep_beat_m07_k18.json (K14 schema + weight field).
Repro:
  .venv/bin/python research/sweep_beat_m07_k18.py
  .venv/bin/python research/sweep_beat_m07_k18.py --only k18_ranklin_gbf07
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
from weight_k18 import get_single_ns, K18_PILOT_MODES
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB

M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05, "2y": 1474.08,
       "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
K3_GBF07 = {"total": 2128.41, "mdd": -24.28}
M07_SWITCH = [["2023-06-21", "B"], ["2024-08-15", "A"], ["2026-09-08", "B"]]
assert RUN_START == "2023-01-03", RUN_START
assert str(EVAL_END)[:10] == "2026-11-12", EVAL_END
assert WINDOWS == {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}, WINDOWS
assert set(K18_PILOT_MODES) == {"rank_linear", "amihud_prop"}, K18_PILOT_MODES

piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))

A_M07 = dict(band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
B_M07 = dict(band=(0.05, 0.30), gate60=-1.0, max_cut=0.80, max_win=20)
A_GBF07 = dict(band=(0.02, 0.30), gate60=-0.15, max_cut=0.78, max_win=40)
B_GBF07 = dict(band=(0.05, 0.30), gate60=-1.0, max_cut=0.78, max_win=20)
MBX, MBY, MBF = 0.18, 0.08, 0.6
GBX, GBY, GBF = 0.15, 0.05, 0.7

_inp_cache = {}
_shadow_cache = {}

def get_inp(seat, leg):
    key = (seat, leg)
    if key not in _inp_cache:
        P = {"M07": A_M07 if leg == "A" else B_M07,
             "gbf07": A_GBF07 if leg == "A" else B_GBF07}[seat]
        _inp_cache[key] = MaxInputs(piv, **P)
    return _inp_cache[key]

CA_BASE = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB,
               capital=50000.0, lot=100, cost_one_way=None, slip=0.002,
               run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END,
               legacy_grid=False, full_liquidate=True)

def get_shadow(seat, leg, weight=None):
    key = (seat, leg, weight)
    if key not in _shadow_cache:
        inp = get_inp(seat, leg)
        n, rebal, take, expo = (5, 20, 1.2, 1.0) if leg == "A" else (4, 30, 0.80, 0.9)
        if weight is None:
            r = pc.run_strategy(inp, n=n, rebal=rebal, take=take,
                                exposure=expo, phase=0, **CA_BASE)
        else:
            ns = get_single_ns(weight)
            r = ns["run_strategy"](inp, n=n, rebal=rebal, take=take,
                                   exposure=expo, phase=0, **CA_BASE)
        _shadow_cache[key] = (inp, r, CA_BASE)
    return _shadow_cache[key]

def _finish(tag, base, family, mech, legs, combo, eq, res, weight, extra=None):
    eq = eq.dropna()
    out = {"tag": tag, "base": base, "family": family, "mechanism": mech,
           "selector": "amihud_60", "legs": legs, "weight": weight,
           "max_filter": "on", "thresh": None, "direction": None, "combo": combo,
           "total": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
           "mdd": round(_mdd(eq) * 100, 2),
           "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]), 0),
           "mode": res.meta.get("final_mode", "B"),
           "switches": len(res.meta.get("switch_log", [])),
           "brakes": len(res.meta.get("brake_log", [])) // 2,
           "switch_log": [list(x) for x in res.meta.get("switch_log", [])],
           "brake_log": [list(x) for x in res.meta.get("brake_log", [])]}
    if extra:
        out.update(extra)
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

def run_switch(tag, seat, weight, combo, family="k18_rankweight"):
    w = None if weight is None else weight
    inp_a, ra, CA = get_shadow(seat, "A", w)
    inp_b, rb, _CB = get_shadow(seat, "B", w)
    CFG_B = dict(n=4, rebal=30, take=0.80, exposure=0.9)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b,
              cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=60,
              exclude_a=MB, exclude_b=MB, factor="amihud_60",
              **{k: v for k, v in CA.items() if k not in ("exclude", "factor")})
    assert weight is None, weight  # weighted switch goes via run_switch_weighted
    bx, by_, bf = (MBX, MBY, MBF) if seat == "M07" else (GBX, GBY, GBF)
    NS = build_ns(bx, by_, bf)
    mech, legs = "baseline", "B(native)"
    res = NS["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    return _finish(tag, seat, family, mech, legs, combo, eq, res, weight)

def run_single_B(tag, seat, weight, combo, family="k18_rankweight"):
    inp_b, rb, _CB = get_shadow(seat, "B", weight)
    eq = rb.eq.iloc[:, 0] if isinstance(rb.eq, pd.DataFrame) else rb.eq
    return _finish(tag, seat, family, "rankWeight", "B(weighted,single)", combo,
                   eq, rb, weight)

def slim(r):
    return {k: r[k] for k in ("tag", "base", "weight", "total", "mdd", "trades",
            "cost", "switches", "1m", "3m", "6m", "1y", "2y", "3y",
            "nbeat_m07", "beat_all", "mdd_better", "win_all")}

CFGS = [
    dict(tag="base_M07", kind="switch", seat="M07", weight=None,
         combo="M07 verbatim calibration row"),
    dict(tag="base_gbf07", kind="switch", seat="gbf07", weight=None,
         combo="g_bf07 verbatim calibration row (K3 row: by05+cut78both+bx15+bf0.7)"),
    dict(tag="k18_ranklin_gbf07", kind="switch", seat="gbf07", weight="rank_linear",
         combo="g_bf07 switch x rank_linear weights, both legs (shadow=live)"),
    dict(tag="k18_amiprop_gbf07", kind="switch", seat="gbf07", weight="amihud_prop",
         combo="g_bf07 switch x amihud-proportional weights, both legs (shadow=live)"),
    dict(tag="k18_ranklin_B", kind="single", seat="gbf07", weight="rank_linear",
         combo="single-leg B (g_bf07 B params) x rank_linear weights"),
    dict(tag="k18_amiprop_B", kind="single", seat="gbf07", weight="amihud_prop",
         combo="single-leg B (g_bf07 B params) x amihud-proportional weights"),
]
assert len([c for c in CFGS if c["tag"] not in ("base_M07", "base_gbf07")]) <= 6, CFGS

def run_one(cfg):
    if cfg["kind"] == "switch" and cfg["weight"] is None:
        return run_switch(cfg["tag"], cfg["seat"], None, cfg["combo"])
    if cfg["kind"] == "switch":
        return run_switch_weighted(cfg)
    return run_single_B(cfg["tag"], cfg["seat"], cfg["weight"], cfg["combo"])

def run_switch_weighted(cfg):
    # Weighted switch: brake params per seat + K18 weights, composed in THIS
    # file from build_ns (brake, verbatim) + weight_k18 patch (weights only).
    import weight_k18 as W
    from sweep_beat_h1_v4 import AA, BB, CC, DD, EE, FF, GG, SIG, PICKLINE
    seat, weight = cfg["seat"], cfg["weight"]
    bx, by_, bf = (MBX, MBY, MBF) if seat == "M07" else (GBX, GBY, GBF)
    src = (ROOT / "research" / "switch_engine.py").read_text()
    def _once(old, new):
        nonlocal src
        assert src.count(old) == 1, (old[:60], src.count(old))
        src = src.replace(old, new)
    add = "\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n    _brake_log: List = []\n    _BRAKE_X = %s\n    _BRAKE_Y = %s\n    _BRAKE_F = %s" % (bx, by_, bf)
    _once(AA, AA + add)
    _once(BB, BB + ", _brake, _brake_trough, _brake_peak, _brake_log")
    brake_eval = "\n        tb_mv_pre = 0.0\n        for tb_cc, tb_p in pos.items():\n            tb_px = px_ffill_or_nan(mark, day, tb_cc)\n            if pd.isna(tb_px):\n                tb_px = tb_p.entry_px\n            tb_mv_pre += tb_p.shares * tb_px\n        tb_eq_pre = cash + tb_mv_pre\n        if tb_eq_pre > _brake_peak:\n            _brake_peak = tb_eq_pre\n        if not _brake and _brake_peak > 0 and (_brake_peak - tb_eq_pre) / _brake_peak >= _BRAKE_X:\n            _brake = True\n            _brake_trough = tb_eq_pre\n            _brake_log.append((str(day.date()), 'ON', round(float((_brake_peak - tb_eq_pre) / _brake_peak) * 100, 2)))\n        elif _brake:\n            if tb_eq_pre < _brake_trough:\n                _brake_trough = tb_eq_pre\n            if _brake_trough > 0 and tb_eq_pre >= _brake_trough * (1.0 + _BRAKE_Y):\n                _brake = False\n                _brake_log.append((str(day.date()), 'OFF', round(float(tb_eq_pre / _brake_trough - 1) * 100, 2)))"
    _once(CC, CC + brake_eval)
    skip_block = "\n        if not switching and set(picks) == set(pos):\n            return False"
    _once(DD, DD + skip_block)
    _once(PICKLINE, "        _ex = (exclude_a if mode == 'A' else exclude_b) if (exclude_a is not None or exclude_b is not None) else exclude\n" + PICKLINE.replace("exclude=exclude", "exclude=_ex"))
    _once(SIG, SIG + "\n    exclude_a=None,\n    exclude_b=None,")
    # brake-scaled exposure: verbatim from build_ns (bf scaling), applied to
    # the WEIGHTED per-code alloc (exposure split first, then weights).
    _once(EE, "        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n" + EE)
    _once(FF, FF + "\n        if (cash + mv) > _brake_peak:\n            _brake_peak = cash + mv")
    _once(GG, "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode, brake_log=_brake_log,")
    # ---- K18 weight patch on top of the braked engine ----
    # NOTE: at this point EE-blockalloc line exists but per-code alloc is still
    # the equal split; replace the split with weights, keeping brake scaling:
    # build_ns inserted "alloc = alloc * bf" BEFORE "for code in picks", so the
    # anchor now reads "alloc = equity.../slots\n        alloc = alloc * ...".
    eq_split = "            alloc = equity_now * state_exposure / slots\n        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n        for code in picks:"
    assert src.count(eq_split) == 1, ("braked alloc anchor", src.count(eq_split))
    wblk = W._weight_block("state_exposure").replace(
        "_w_expo = equity_now * state_exposure",
        "_w_expo = equity_now * state_exposure * (_BRAKE_F if _brake else 1.0)")
    # eq_split's first line sits inside the `else:` body (12sp); re-indent the
    # whole weight block to 12sp so the else-branch stays valid, keeping the
    # trailing `for code in picks:` at 8sp (loop level, as native).
    _wlines = wblk.split("\n")
    assert _wlines[-1] == "        for code in picks:", _wlines[-1]
    wblk12 = "\n".join(("    " + ln) if ln.strip() else ln for ln in _wlines[:-1]) + "\n" + _wlines[-1]
    src = src.replace(eq_split, wblk12)
    assert src.count(W._SW_LOOP_A) == 1
    src = src.replace(W._SW_LOOP_A, "                sh = int(_w_alloc[code] / px // lot) * lot")
    assert src.count(W._SW_LOOP_B) == 1
    src = src.replace(W._SW_LOOP_B, "                sh = _w_alloc[code] / px")
    assert src.count(W._SW_SNAP) == 1
    src = src.replace(W._SW_SNAP,
        "                               alloc_per_slot=float(_w_mean), picked=int(len(picks)), "
        "weight_mode=_w_mode, weights={cd: round(float(_w_alloc[cd]), 4) for cd in picks}))")
    src = src.replace("    switch_log: List[Tuple[str, str]] = []",
        "    switch_log: List[Tuple[str, str]] = []\n    _WEIGHT_MODE = " + repr(weight), 1)
    ns = {}
    exec(compile(src, "switch_engine_k18_%s_%s" % (seat, weight), "exec"), ns)
    inp_a, ra, CA = get_shadow(seat, "A", weight)
    inp_b, rb, _CB = get_shadow(seat, "B", weight)
    CFG_B = dict(n=4, rebal=30, take=0.80, exposure=0.9)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b,
              cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=60,
              exclude_a=MB, exclude_b=MB, factor="amihud_60",
              **{k: v for k, v in CA.items() if k not in ("exclude", "factor")})
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    return _finish(cfg["tag"], "gbf07" if seat == "gbf07" else seat,
                   "k18_rankweight", "rankWeight", "both(weighted)",
                   cfg["combo"], eq, res, weight)

def check_calib(rows):
    m = {r["tag"]: r for r in rows}
    b = m.get("base_M07")
    assert b is not None, "missing base_M07"
    assert abs(b["total"] - M07["total"]) <= 0.01 and abs(b["mdd"] - M07["mdd"]) <= 0.01, ("M07 caliber drift", b["total"], b["mdd"])
    assert b["switch_log"] == M07_SWITCH, b["switch_log"]
    g = m.get("base_gbf07")
    assert g is not None, "missing base_gbf07"
    dt, dm = abs(g["total"] - K3_GBF07["total"]), abs(g["mdd"] - K3_GBF07["mdd"])
    if dt > 0.01 or dm > 0.01:
        print("CALIBER DRIFT: base_gbf07 total=%.2f (K3 2128.41) mdd=%.2f (K3 -24.28); STOP" % (g["total"], g["mdd"]), flush=True)
        raise SystemExit(2)
    print("calib OK: base_M07 total=%.2f mdd=%.2f | base_gbf07 total=%.2f mdd=%.2f" % (b["total"], b["mdd"], g["total"], g["mdd"]), flush=True)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    outp = ROOT / "results" / "r30_bt" / "sweep_beat_m07_k18.json"
    if args.only:
        cfg = next((c for c in CFGS if c["tag"] == args.only), None)
        assert cfg, args.only
        r = run_one(cfg)
        print(json.dumps(slim(r), ensure_ascii=False), flush=True)
        raise SystemExit(0)
    rows = []
    for cfg in CFGS:
        try:
            r = run_one(cfg)
            print(json.dumps(slim(r), ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (cfg["tag"], e), flush=True)
            import traceback; traceback.print_exc()
            raise SystemExit(1)
    check_calib(rows)
    outp.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print("saved %d rows -> %s" % (len(rows), outp), flush=True)
