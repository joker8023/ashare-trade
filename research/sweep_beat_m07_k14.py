#!/usr/bin/env python3
"""K14: g_bf07 peak x K13 adaptive-mechanism stacking (NEW = superposition only).

Baseline refs: M07 final (ph0 total 1863.27 / mdd -27.05) and K3 g_bf07 peak
(M07 + by05 + cutBOTH 0.78 + bx0.15 + bf0.7, total 2128.41 / mdd -24.28,
nbeat_m07=5). K13 best on NAKED M07 was dynT10_both (nbeat=3, no beat_all).
The superposition was never tested -- this is the gap K14 closes.

Caliber verbatim M07 ph0 (RUN_START=2023-01-03 / EVAL_END=2026-11-12 / 50k /
real fee (cost_one_way=None) / slip=0.002 / lot=100 / legacy_grid=False /
full_liquidate=True / stop_exec=next / MB exclusion / native amihud_60 legs /
RS trailing-60 shadow (ra>=rb->A else B)) EXCEPT the g_bf07 seat, which is
verbatim the K3 g_bf07 CFGS row:
  A: band=(0.02,0.30) gate60=-0.15 cut=0.78 win=40 take=1.2 n=5 rebal=20 exp=1.0
  B: band=(0.05,0.30) gate60=-1.0 cut=0.78 win=20 take=0.8 n=4 rebal=30 exp=0.9
  brake bx=0.15 / by=0.05 / bf=0.7; stop=0.25; rs_lookback=60.
K14 dims (<=4 new configs, all lock_mode=None, no lookahead):
  1. k14_dynT10_both  = g_bf07 x dynamic-N (T=0.10, both legs)
  2. k14_dynT05_both  = g_bf07 x dynamic-N (T=0.05, both legs)
  3. k14_dly_exitB    = g_bf07 x confirm-delay exitB (delay B->A only)
  4. k14_triple_T10xB = g_bf07 x dynamic-N(T10,both) + confirm-delay exitB
     (triple stack; ONLY run if configs 1-3 all fail beat_all, else skipped
     with a note; never exceeds 4 new configs).
Mechanism code is reused verbatim from research/adaptive_k13.py
(build_ns_k13_dynN / build_ns_k13_dly, called here with the g_bf07 brake
params). The triple engine is composed in THIS file only from adaptive_k13's
exported anchors (no edit to adaptive_k13.py): dynamic-N margin update runs
on every A-grid signal day (t-and-before data, t+1 exec), confirm-delay
gates the desired flip on 2 consecutive same-direction signals.
No lookahead: every new line reads _rs(sig_i) (t-and-before) or signal-day
state; execution stays on the native t+1 exec_map.

Output: results/r30_bt/sweep_beat_m07_k14.json (K13 schema + base="g_bf07").
Repro:
  .venv/bin/python research/sweep_beat_m07_k14.py           # 2 calib + 3 new, dump
  .venv/bin/python research/sweep_beat_m07_k14.py --only k14_dynT10_both
  .venv/bin/python research/sweep_beat_m07_k14.py --triple  # append triple iff 1-3 all !beat_all
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
from adaptive_k13 import (
    build_ns_k13_dynN, build_ns_k13_dly, FAMILY_DYN, FAMILY_DLY,
    AA, BB, CC, DESIRED, STATE_BLK, BRAKE_EVAL, GG, _apply_verbatim_tail,
)
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB

M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05, "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
K3_GBF07 = {"total": 2128.41, "mdd": -24.28}
M07_SWITCH = [["2023-06-21", "B"], ["2024-08-15", "A"], ["2026-09-08", "B"]]
assert RUN_START == "2023-01-03", RUN_START
assert str(EVAL_END)[:10] == "2026-11-12", EVAL_END
assert WINDOWS == {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}, WINDOWS

piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))

# ---- seats ----
A_M07 = dict(band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
B_M07 = dict(band=(0.05, 0.30), gate60=-1.0, max_cut=0.80, max_win=20)
A_GBF07 = dict(band=(0.02, 0.30), gate60=-0.15, max_cut=0.78, max_win=40)
B_GBF07 = dict(band=(0.05, 0.30), gate60=-1.0, max_cut=0.78, max_win=20)
GBX, GBY, GBF = 0.15, 0.05, 0.7      # g_bf07 brake
MBX, MBY, MBF = 0.18, 0.08, 0.6      # M07 native brake

NS_M07 = build_ns(MBX, MBY, MBF)
NS_GBF07 = build_ns(GBX, GBY, GBF)
_NS = {}

def NS_DYN_G(t, legs):
    k = ("dyn_g", t, legs)
    if k not in _NS:
        _NS[k] = build_ns_k13_dynN(thresh=t, legs=legs, bx=GBX, by_=GBY, bf=GBF)
    return _NS[k]

def NS_DLY_G(d):
    k = ("dly_g", d)
    if k not in _NS:
        _NS[k] = build_ns_k13_dly(direction=d, bx=GBX, by_=GBY, bf=GBF)
    return _NS[k]

FAMILY_TRIPLE = "k14_triple"

def build_ns_k14_triple(thresh=0.10, legs="both", direction="exitB",
                        bx=GBX, by_=GBY, bf=GBF):
    """Triple stack (this file only): dynamic-N margin update + exitB confirm
    delay, composed from adaptive_k13's exported anchors. Dyn-N updates on
    every A-grid signal day from t-and-before margin; delay gates the flip.
    """
    assert legs in ("B", "both"), legs
    assert direction in ("enterB", "exitB"), direction
    src = (ROOT / "research" / "switch_engine.py").read_text()

    def _once(old, new):
        nonlocal src
        assert src.count(old) == 1, (old[:60], src.count(old))
        src = src.replace(old, new)

    add = ("\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n"
           "    _brake_log: List = []\n    _BRAKE_X = %s\n    _BRAKE_Y = %s\n"
           "    _BRAKE_F = %s\n    _DYN_T = %s\n    _DYN_LEGS = \"%s\"\n"
           "    _DLY_DIR = \"%s\"\n"
           "    _dyn_nA = 5\n    _dyn_nB = 5\n    _dyn_prev = (5, 5)\n"
           "    _dyn_log: List = []\n    _pend = None\n    _dly_log: List = []"
           % (bx, by_, bf, thresh, legs, direction))
    _once(AA, AA + add)
    _once(BB, BB + ", _brake, _brake_trough, _brake_peak, _brake_log, _dyn_nA, _dyn_nB, _dyn_prev, _pend")
    _once(CC, CC + BRAKE_EVAL)
    dyn_blk = (DESIRED + "\n"
               "            _ra = ra\n"
               "            _rb = rb\n"
               "            if _ra is not None and _rb is not None:\n"
               "                _margin = abs(float(_ra) - float(_rb))\n"
               "                _newN = 3 if _margin > _DYN_T else 5\n"
               '                if _DYN_LEGS == "both":\n'
               "                    _dyn_nA = _newN\n"
               "                    _dyn_nB = _newN\n"
               "                else:\n"
               "                    _dyn_nB = _newN\n"
               "                if (_dyn_nA, _dyn_nB) != _dyn_prev:\n"
               '                    _dyn_log.append((str(sig_day.date()), _dyn_nA, _dyn_nB, round(float(_margin), 4)))\n'
               "                    _dyn_prev = (_dyn_nA, _dyn_nB)")
    dly_blk = ("\n"
               "            _raw = desired\n"
               '            if _DLY_DIR == "enterB":\n'
               '                _needs = (_raw == "B" and mode == "A")\n'
               '            elif _DLY_DIR == "exitB":\n'
               '                _needs = (_raw == "A" and mode == "B")\n'
               "            else:\n"
               "                _needs = (_raw != mode)\n"
               "            if _needs:\n"
               "                if _pend == _raw:\n"
               "                    desired = _raw\n"
               "                    _pend = None\n"
               '                    _dly_log.append((str(sig_day.date()), _raw, "confirmed"))\n'
               "                else:\n"
               "                    _pend = _raw\n"
               "                    desired = mode\n"
               '                    _dly_log.append((str(sig_day.date()), _raw, "pending"))\n'
               "            elif _raw != mode:\n"
               "                desired = _raw\n"
               "                _pend = None\n"
               '                _dly_log.append((str(sig_day.date()), _raw, "immediate"))\n'
               "            else:\n"
               "                if _pend is not None:\n"
               '                    _dly_log.append((str(sig_day.date()), _pend, "cancelled"))\n'
               "                _pend = None")
    _once(DESIRED, dyn_blk + dly_blk)
    _once(STATE_BLK, STATE_BLK + "\n        state_n = (_dyn_nA if mode == \"A\" else _dyn_nB)")
    src = _apply_verbatim_tail(src)
    _once(GG, GG + " brake_log=_brake_log, dyn_log=_dyn_log, dly_log=_dly_log,")
    ns = {}
    exec(compile(src, "switch_engine_k14_triple", "exec"), ns)
    return ns

def NS_TRIPLE():
    if "triple" not in _NS:
        _NS["triple"] = build_ns_k14_triple()
    return _NS["triple"]

_inp_cache = {}
_shadow_cache = {}

def get_inp(seat, leg):
    key = (seat, leg)
    if key not in _inp_cache:
        P = {"M07": A_M07 if leg == "A" else B_M07,
             "gbf07": A_GBF07 if leg == "A" else B_GBF07}[seat]
        _inp_cache[key] = MaxInputs(piv, **P)
    return _inp_cache[key]

def get_shadow(seat, leg, n, rebal, take, exposure):
    key = (seat, leg, n, rebal, take, exposure)
    if key not in _shadow_cache:
        inp = get_inp(seat, leg)
        CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB,
                  capital=50000.0, lot=100, cost_one_way=None, slip=0.002,
                  run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END,
                  legacy_grid=False, full_liquidate=True)
        _shadow_cache[key] = (inp, pc.run_strategy(inp, n=n, rebal=rebal, take=take,
                                                   exposure=exposure, phase=0, **CA), CA)
    return _shadow_cache[key]

def run_one(tag, combo, base, mechanism, legs, thresh=None, direction=None):
    is_m07 = (tag == "base_M07")
    seat = "M07" if is_m07 else "gbf07"
    inp_a, ra, CA = get_shadow(seat, "A", 5, 20, 1.2, 1.0)
    inp_b, rb, _CB = get_shadow(seat, "B", 4, 30, 0.80, 0.9)
    CFG_B = dict(n=4, rebal=30, take=0.80, exposure=0.9)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b,
              cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=60,
              exclude_a=MB, exclude_b=MB, factor="amihud_60",
              **{k: v for k, v in CA.items() if k not in ("exclude", "factor")})
    if is_m07:
        NS, family, mech = NS_M07, "m07_baseline", "baseline"
    elif tag == "base_gbf07":
        NS, family, mech = NS_GBF07, "m07_baseline", "baseline"
    elif mechanism == "dynamicN":
        NS, family, mech = NS_DYN_G(thresh, legs), FAMILY_DYN, mechanism
    elif mechanism == "confirmDelay":
        NS, family, mech = NS_DLY_G(direction), FAMILY_DLY, mechanism
    else:
        NS, family, mech = NS_TRIPLE(), FAMILY_TRIPLE, mechanism
    res = NS["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "base": base, "family": family, "mechanism": mech,
           "selector": "amihud_60", "legs": ("B(native)" if mech == "baseline" else (legs + "(native)")),
           "max_filter": "on", "thresh": thresh, "direction": direction, "combo": combo,
           "total": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
           "mdd": round(_mdd(eq) * 100, 2),
           "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]), 0),
           "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]),
           "brakes": len(res.meta.get("brake_log", [])) // 2,
           "switch_log": [list(x) for x in res.meta["switch_log"]],
           "brake_log": [list(x) for x in res.meta.get("brake_log", [])]}
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

CFGS_CORE = [
    dict(tag="base_M07", combo="M07 verbatim calibration row", base="M07",
         mechanism="baseline", legs="B", thresh=None, direction=None),
    dict(tag="base_gbf07", combo="g_bf07 verbatim calibration row (K3 row: by05+cut78both+bx15+bf0.7)", base="g_bf07",
         mechanism="baseline", legs="B", thresh=None, direction=None),
    dict(tag="k14_dynT10_both", combo="g_bf07 x dynamic-N T=10pp both-legs", base="g_bf07",
         mechanism="dynamicN", legs="both", thresh=0.10, direction=None),
    dict(tag="k14_dynT05_both", combo="g_bf07 x dynamic-N T=5pp both-legs", base="g_bf07",
         mechanism="dynamicN", legs="both", thresh=0.05, direction=None),
    dict(tag="k14_dly_exitB", combo="g_bf07 x confirm-delay exitB (delay B->A, 2-signal)", base="g_bf07",
         mechanism="confirmDelay", legs="both", thresh=None, direction="exitB"),
]
CFG_TRIPLE = dict(tag="k14_triple_T10xB", combo="g_bf07 x dynamic-N(T10,both) + confirm-delay exitB (triple stack)", base="g_bf07",
                  mechanism="dynamicN+confirmDelay", legs="both", thresh=0.10, direction="exitB")
assert len([c for c in CFGS_CORE if c["tag"] not in ("base_M07", "base_gbf07")]) == 3, CFGS_CORE

def check_calib(rows):
    m = {r["tag"]: r for r in rows}
    b = m.get("base_M07")
    assert b is not None, "missing base_M07"
    assert abs(b["total"] - M07["total"]) <= 0.01 and abs(b["mdd"] - M07["mdd"]) <= 0.01, ("M07 caliber drift", b["total"], b["mdd"])
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
    ap.add_argument("--triple", action="store_true",
                    help="append triple row iff existing core rows all fail beat_all")
    args = ap.parse_args()
    outp = ROOT / "results" / "r30_bt" / "sweep_beat_m07_k14.json"
    if args.triple:
        assert outp.exists(), "run core sweep first (no %s)" % outp
        rows = json.loads(outp.read_text())
        core_tags = [c["tag"] for c in CFGS_CORE if c["tag"].startswith("k14_")]
        core = [r for r in rows if r["tag"] in core_tags]
        assert len(core) == 3, ("core rows incomplete", [r["tag"] for r in rows])
        if any(r["beat_all"] for r in core):
            print("triple SKIPPED with note: at least one core config beat_all (%s); rule says skip" % ([r["tag"] for r in core if r["beat_all"]]), flush=True)
            raise SystemExit(0)
        if any(r["tag"] == CFG_TRIPLE["tag"] for r in rows):
            print("triple already present; nothing to do", flush=True)
            raise SystemExit(0)
        r = run_one(CFG_TRIPLE["tag"], CFG_TRIPLE["combo"], CFG_TRIPLE["base"],
                    CFG_TRIPLE["mechanism"], CFG_TRIPLE["legs"], CFG_TRIPLE["thresh"], CFG_TRIPLE["direction"])
        slim = {k: r[k] for k in ("tag", "total", "mdd", "trades", "cost", "switches", "1m", "3m", "6m", "1y", "2y", "3y", "nbeat_m07", "beat_all", "mdd_better", "win_all")}
        print(json.dumps(slim, ensure_ascii=False), flush=True)
        rows.append(r)
        outp.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        print("appended triple -> %s (%d rows)" % (outp, len(rows)), flush=True)
        raise SystemExit(0)
    kept = [c for c in CFGS_CORE if args.only is None or c["tag"] == args.only]
    assert kept, args.only
    rows = []
    for cfg in kept:
        try:
            r = run_one(cfg["tag"], cfg["combo"], cfg["base"], cfg["mechanism"], cfg["legs"], cfg["thresh"], cfg["direction"])
            slim = {k: r[k] for k in ("tag", "total", "mdd", "trades", "cost", "switches", "1m", "3m", "6m", "1y", "2y", "3y", "nbeat_m07", "beat_all", "mdd_better", "win_all")}
            print(json.dumps(slim, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (cfg["tag"], e), flush=True)
            import traceback; traceback.print_exc()
            raise SystemExit(1)
    if args.only is None:
        check_calib(rows)
        outp.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        print("saved %d rows -> %s" % (len(rows), outp), flush=True)
