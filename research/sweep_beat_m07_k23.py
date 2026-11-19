#!/usr/bin/env python3
"""K23: K21 + min-hold cooldown fix (daily+hyst + switch-interval gate).

Root cause (K22 attrib, batch_054): 2y gap -106.2pp concentrated in
2024-11 (-6.24pp) + 2024-12 (-6.83pp), where K21 did 4 whipsaw flips
(11-12->A / 11-13->B / 11-18->A / 11-27->B / 12-13->A) while M07 stayed
in A and realized 000908/600234 gains. The 11-12->A / 11-13->B pair is
1 trading day apart -- pure whipsaw that hysteresis 0.03 alone cannot kill.

Fix: minimum holding period between switches (_MIN_HOLD trading days on
sig index). Uses only past switch sig index (_LAST_SWITCH), no lookahead:
  if desired != mode and _LAST_SWITCH is not None
        and (sig_i - _LAST_SWITCH) < _MIN_HOLD: desired = mode
_LAST_SWITCH updated to sig_i whenever a switch executes.
First switch always allowed (preserves early entry 2023-06-07).
Brake verbatim K21/M07, evaluated on rebalance days only.

Caliber identical to K21/M07 otherwise (ph0 / RUN_START / EVAL_END / 5w /
realistic fees slip 0.002 / lot 100 / amihud_60 / full-liquidate).
Engine build_ns_k23 defined IN THIS FILE ONLY (string patches on
switch_engine.py, same style as K21). No edit to switch_engine.py.

Plan: base_M07 calibration + 4 cooldown variants on gbf07 seat
(hyst 0.03 / rs 60, min_hold 10/15/20/30). No phase-2 gate needed;
best picked by (nbeat, total). Verdict needs beat_all or nbeat=6/6 +
cross-phase + slipx2 re-check (done by audit script).

Output: results/r30_bt/sweep_beat_m07_k23.json (K21 schema + min_hold).
Repro: .venv/bin/python research/sweep_beat_m07_k23.py
"""
import sys
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))

import pandas as pd

import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, WINDOWS, RUN_START, EVAL_END, MB

M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05,
       "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
M07_SWITCH = [["2023-06-21", "B"], ["2024-08-15", "A"], ["2026-09-08", "B"]]
CONSTRAINT = ("K23: K21 daily+hyst02-03/rs60 + min-hold cooldown on sig index "
              "(uses t-and-earlier shadow RS + past switch date only, no lookahead); "
              "switch executed at t+1 close in round lots; brake verbatim M07 on "
              "rebalance days only; long-only full-liquidate, exposure<=1, no leverage.")

AA = "    switch_log: List[Tuple[str, str]] = []"
BB = "        nonlocal cash, total_cost, mode, state_take, state_n, state_exposure"
CC = "        sig_day = dates[sig_i]"
DD = "        picks = inp_cur.picks(sig_day, n_eff, exclude=exclude, factor=factor)"
EE = "        for code in picks:"
FF = "        eq_rows.append((day, cash + mv, mv, cash, len(pos)))"
GG = "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode,"
SIG = "    exclude: Tuple[str, ...] = (),"
PICKLINE = "        picks = inp_cur.picks(sig_day, n_eff, exclude=exclude, factor=factor)"
LOOPEND = "    loop_end = min(end_i, n_dates - 1)"
EVAL_OLD = ("        desired = mode\n"
            "        if lock_mode is None and inp_b is not None and sig_i in sig_a:\n"
            "            ra = _rs(shadow_a, sig_i)\n"
            "            rb = _rs(shadow_b, sig_i)\n"
            "            if ra is not None and rb is not None:\n"
            "                desired = \"A\" if ra >= rb else \"B\"")
EVAL_NEW_HYST_HOLD = ("        # switch-eval: grid=A-grid days only (orig); daily=each close t-and-earlier only + hysteresis band + min-hold\n"
                 "        desired = mode\n"
                 "        _eval_daily = (evalfreq == \"daily\")\n"
                 "        if lock_mode is None and inp_b is not None and ((sig_i in sig_a) or _eval_daily):\n"
                 "            ra = _rs(shadow_a, sig_i)\n"
                 "            rb = _rs(shadow_b, sig_i)\n"
                 "            if ra is not None and rb is not None:\n"
                 "                if mode == \"A\":\n"
                 "                    _d = \"B\" if rb - ra >= _HYST else \"A\"\n"
                 "                else:\n"
                 "                    _d = \"A\" if ra - rb >= _HYST else \"B\"\n"
                 "                if _d != mode and _LAST_SWITCH is not None and (sig_i - _LAST_SWITCH) < _MIN_HOLD:\n"
                 "                    _d = mode\n"
                 "                desired = _d")
EXECMAP_ADD = ("\n    if evalfreq == \"daily\" and lock_mode is None and inp_b is not None:\n"
               "        for _t in range(loop_start, loop_end + 1):\n"
               "            _ei = _t + 1 + sig_lag\n"
               "            if _ei <= loop_end:\n"
               "                exec_map.setdefault(_ei, _t)")
SWITCH_LOG_LINE = "            switch_log.append((str(sig_day.date()), mode))"


def build_ns_k23(bx=0.18, by_=0.08, bf=0.6, hyst=0.0, min_hold=0):
    src = (ROOT / "research" / "switch_engine.py").read_text()

    def _once(old, new):
        assert src.count(old) == 1, (old[:60], src.count(old))
        return src.replace(old, new)

    add = ("\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n"
           "    _brake_log: List = []\n    _BRAKE_X = %s\n    _BRAKE_Y = %s\n"
           "    _BRAKE_F = %s\n    _HYST = %s\n    _MIN_HOLD = %s\n    _LAST_SWITCH = None" % (bx, by_, bf, hyst, min_hold))
    src = _once(AA, AA + add)
    src = _once(BB, BB + ", _brake, _brake_trough, _brake_peak, _brake_log, _LAST_SWITCH")
    brake_eval = ("\n        tb_mv_pre = 0.0\n        for tb_cc, tb_p in pos.items():\n"
                  "            tb_px = px_ffill_or_nan(mark, day, tb_cc)\n"
                  "            if pd.isna(tb_px):\n"
                  "                tb_px = tb_p.entry_px\n"
                  "            tb_mv_pre += tb_p.shares * tb_px\n"
                  "        tb_eq_pre = cash + tb_mv_pre\n"
                  "        if tb_eq_pre > _brake_peak:\n"
                  "            _brake_peak = tb_eq_pre\n"
                  "        if not _brake and _brake_peak > 0 and (_brake_peak - tb_eq_pre) / _brake_peak >= _BRAKE_X:\n"
                  "            _brake = True\n"
                  "            _brake_trough = tb_eq_pre\n"
                  "            _brake_log.append((str(day.date()), 'ON', round(float((_brake_peak - tb_eq_pre) / _brake_peak) * 100, 2)))\n"
                  "        elif _brake:\n"
                  "            if tb_eq_pre < _brake_trough:\n"
                  "                _brake_trough = tb_eq_pre\n"
                  "            if _brake_trough > 0 and tb_eq_pre >= _brake_trough * (1.0 + _BRAKE_Y):\n"
                  "                _brake = False\n"
                  "                _brake_log.append((str(day.date()), 'OFF', round(float(tb_eq_pre / _brake_trough - 1) * 100, 2)))")
    brake_gated = ("\n        _brake_gate = brake_daily or (sig_i in sig_a) or (sig_i in sig_b)\n"
                   "        if _brake_gate:" + textwrap.indent(brake_eval, "    "))
    src = _once(CC, CC + brake_gated)
    skip_block = "\n        if not switching and set(picks) == set(pos):\n            return False"
    src = _once(DD, DD + skip_block)
    src = _once(PICKLINE, "        _ex = (exclude_a if mode == 'A' else exclude_b) if (exclude_a is not None or exclude_b is not None) else exclude\n" + PICKLINE.replace("exclude=exclude", "exclude=_ex"))
    src = _once(SIG, SIG + "\n    exclude_a=None,\n    exclude_b=None,")
    src = _once("    exclude_a=None,\n    exclude_b=None,",
                "    exclude_a=None,\n    exclude_b=None,\n    evalfreq=\"grid\",\n    brake_daily=False,")
    src = _once(EE, "        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n" + EE)
    src = _once(FF, FF + "\n        if (cash + mv) > _brake_peak:\n            _brake_peak = cash + mv")
    src = _once(GG, "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode, brake_log=_brake_log,")
    src = _once(LOOPEND, LOOPEND + EXECMAP_ADD)
    src = _once(EVAL_OLD, EVAL_NEW_HYST_HOLD)
    src = _once(SWITCH_LOG_LINE, SWITCH_LOG_LINE + "\n            _LAST_SWITCH = sig_i")
    ns = {}
    exec(compile(src, "switch_engine_k23", "exec"), ns)
    return ns


piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))

_shadow_cache = {}
_ns_cache = {}


def get_ns(bx, by_, bf, hyst, min_hold):
    k = (bx, by_, bf, hyst, min_hold)
    if k not in _ns_cache:
        _ns_cache[k] = build_ns_k23(bx, by_, bf, hyst, min_hold)
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


def run_one(tag, seat="M07", combo="", cut_a=0.80, win_a=40, cut_b=0.80,
            win_b=20, stop=0.25, a_take=1.2, b_take=0.80, a_n=5, b_n=4,
            b_exp=0.9, rs=60, bx=0.18, by_=0.08, bf=0.6, evalfreq="grid",
            hyst=0.0, min_hold=0):
    assert evalfreq in ("grid", "daily"), evalfreq
    inp_a, inp_b, ra, rb, CA, CFG_B = get_shadows(
        cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp)
    KW = dict(n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0,
              inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq,
              rs_lookback=rs, exclude_a=MB, exclude_b=MB,
              evalfreq=evalfreq, brake_daily=False,
              **{k: v for k, v in CA.items() if k != "exclude"})
    ns = get_ns(bx, by_, bf, hyst, min_hold)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "seat": seat, "combo": combo, "evalfreq": evalfreq,
           "hyst": hyst, "min_hold": min_hold, "rs": rs, "bx": bx, "by": by_, "bf": bf,
           "brake_daily": False, "constraint": CONSTRAINT,
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


SLIM_KEYS = ("tag", "evalfreq", "hyst", "min_hold", "rs", "seat", "total", "mdd", "trades",
             "cost", "switches", "brakes", "1m", "3m", "6m", "1y", "2y", "3y",
             "nbeat_m07", "beat_all", "mdd_better", "switch_same_m07")


def run_cfg(cfg):
    c = dict(cfg)
    tag = c.pop("tag")
    r = run_one(tag, **c)
    print(json.dumps({k: r[k] for k in SLIM_KEYS}, ensure_ascii=False), flush=True)
    return r


def calib_check(base):
    cal = {k: base[k] for k in ("total", "mdd", "1m", "3m", "6m", "1y", "2y", "3y")}
    exp = {k: M07[k] for k in cal}
    assert cal == exp and base["trades"] == 184 and base["cost"] == 50990.0, \
        "CALIB DIFF base_M07 vs M07_final: %s" % json.dumps(base, ensure_ascii=False)
    assert base["switch_log"] == M07_SWITCH, "CALIB switch_log diff: %s" % base["switch_log"]
    print("CALIB OK base_M07 == M07_final", flush=True)


if __name__ == "__main__":
    rows = []
    base = run_cfg(dict(tag="base_M07", seat="M07", combo="calibration",
                        evalfreq="grid", hyst=0.0, min_hold=0))
    rows.append(base)
    calib_check(base)
    # K21 replica (min_hold=0 must reproduce k21_daily_hyst003_gbf07 exactly)
    k21rep = run_cfg(dict(tag="k21rep_mh00_gbf07", seat="gbf07",
                          combo="K21 replica min_hold=0",
                          cut_a=0.78, cut_b=0.78, bx=0.15, by_=0.05, bf=0.7,
                          evalfreq="daily", hyst=0.03, rs=60, min_hold=0))
    rows.append(k21rep)
    assert k21rep["total"] == 1934.29 and k21rep["switches"] == 11, \
        "K21 replica mismatch: %s" % json.dumps({k: k21rep[k] for k in SLIM_KEYS}, ensure_ascii=False)
    print("REPLICA OK k21rep==k21_daily_hyst003_gbf07", flush=True)
    for (mh, hyst) in ((10, 0.03), (11, 0.035), (11, 0.04)):
        r = run_cfg(dict(tag="k23_mh%02d_h%s_gbf07" % (mh, str(hyst).replace(".", "")), seat="gbf07",
                         combo="K23 fix: daily+hyst%s+min_hold%d" % (hyst, mh),
                         cut_a=0.78, cut_b=0.78, bx=0.15, by_=0.05, bf=0.7,
                         evalfreq="daily", hyst=hyst, rs=60, min_hold=mh))
        rows.append(r)
    for mh in (15, 20, 30):
        r = run_cfg(dict(tag="k23_mh%02d_gbf07" % mh, seat="gbf07",
                         combo="K23 fix: daily+hyst0.03+min_hold%d" % mh,
                         cut_a=0.78, cut_b=0.78, bx=0.15, by_=0.05, bf=0.7,
                         evalfreq="daily", hyst=0.03, rs=60, min_hold=mh))
        rows.append(r)
    print("=== K23 VERDICT ===", flush=True)
    ab = [r["tag"] for r in rows if r.get("beat_all")]
    print("beat_all rows: %s" % (ab if ab else "NONE"), flush=True)
    pool = [r for r in rows if r["tag"] not in ("base_M07", "k21rep_mh00_gbf07")]
    best2 = sorted(pool, key=lambda r: (r["nbeat_m07"], r["total"]), reverse=True)[0]
    diffs = ", ".join(["%s %+.2f" % (w, best2[w] - M07[w]) for w in ("1m", "3m", "6m", "1y", "2y", "3y")])
    print("BEST %s nbeat=%d six-window diffs vs M07: %s" % (best2["tag"], best2["nbeat_m07"], diffs), flush=True)
    for r in rows:
        print("ROW %s total=%.2f mdd=%.2f sw=%d cost=%.0f nbeat=%d beat_all=%s log=%s" % (
            r["tag"], r["total"], r["mdd"], r["switches"], r["cost"],
            r["nbeat_m07"], r["beat_all"], r["switch_log"]), flush=True)
    open(ROOT / "results" / "r30_bt" / "sweep_beat_m07_k23.json", "w").write(
        json.dumps(rows, ensure_ascii=False, indent=1))
    print("saved %d rows" % len(rows), flush=True)
