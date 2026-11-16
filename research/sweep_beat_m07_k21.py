#!/usr/bin/env python3
"""K21: daily-eval + hysteresis band / long-RS-lookback pilot (4 new + base + cond phase-2).

Caliber identical to M07 / K20 except the switch-evaluation dimension
(ph0 / RUN_START=2023-01-03 / EVAL_END=2026-11-12 / 5w / realistic fees
(cost_one_way=None) + slip 0.002 / round lots lot=100 / native amihud_60 both
legs / A-B params verbatim M07 / brake verbatim M07 gated on rebalance days
only). Engine build_ns_k21 is defined IN THIS FILE ONLY: K20 daily-eval
patches (research/evalfreq_k20.py mechanism) + K11 hysteresis idea applied to
the daily rule. No edit to switch_engine.py or evalfreq_k20.py.

Switch rule (t-and-earlier shadow values only, switch executed at t+1 close):
  grid  : M07 verbatim (A-grid days only, ra>=rb -> A else B; hyst=0.0 reproduces it).
  daily : evaluate EVERY close with hysteresis band h on the return spread:
            mode A -> flip to B only if rb - ra >= h, else stay A;
            mode B -> flip to A only if ra - rb >= h, else stay B.
          ra/rb = trailing shadow RS over rs_lookback (60/120/252) via _rs
          (searchsorted right-1, t and earlier only). No confirmation delay.
Brake: verbatim M07 (bx/by/bf), evaluated/acted on rebalance days only.
Long-only full-liquidate, exposure<=1, no leverage, no lookahead.

Plan (phase-1 = 4 fixed new on M07 seat; phase-2 gated; total new <= 6):
  base_M07                  grid  hyst=0.00 rs=60  (calibration, must == M07_final)
  k21_daily_hyst003_M07     daily hyst=0.03 rs=60
  k21_daily_hyst008_M07     daily hyst=0.08 rs=60
  k21_daily_rs120_M07       daily hyst=0.00 rs=120
  k21_daily_rs252_M07       daily hyst=0.00 rs=252
  phase-2 gate: max phase-1 nbeat_m07 >= 4 else SKIP with note.
    best mechanism x g_bf07 seat (cut 0.78/0.78, bx0.15/by0.05/bf0.7,
    K3/K17 canonical g_bf07) -> 1 row; runner-up x g_bf07 -> 2nd row iff it
    also has nbeat>=4 with different (hyst, rs).

Output: results/r30_bt/sweep_beat_m07_k21.json (K20 schema + hyst/rs/seat/
brake params + constraint field).
Repro:
  .venv/bin/python research/sweep_beat_m07_k21.py --only base_M07  # calibration row
  .venv/bin/python research/sweep_beat_m07_k21.py                  # full sweep + dump
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
CONSTRAINT = ("compare uses trailing shadow RS at t from t-and-earlier values "
              "only (_rs searchsorted right-1 over rs_lookback window); switch "
              "executed at t+1 close in round lots; hysteresis band h on the "
              "return spread; brake verbatim M07 on rebalance days only; "
              "long-only full-liquidate, exposure<=1, no leverage; no lookahead; "
              "all other caliber verbatim M07 ph0.")

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
EVAL_NEW_HYST = ("        # switch-eval: grid=A-grid days only (orig); daily=each close t-and-earlier only + hysteresis band\n"
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
                 "                desired = _d")
EXECMAP_ADD = ("\n    if evalfreq == \"daily\" and lock_mode is None and inp_b is not None:\n"
               "        for _t in range(loop_start, loop_end + 1):\n"
               "            _ei = _t + 1 + sig_lag\n"
               "            if _ei <= loop_end:\n"
               "                exec_map.setdefault(_ei, _t)")


def build_ns_k21(bx=0.18, by_=0.08, bf=0.6, hyst=0.0):
    src = (ROOT / "research" / "switch_engine.py").read_text()

    def _once(old, new):
        assert src.count(old) == 1, (old[:60], src.count(old))
        return src.replace(old, new)

    add = ("\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n"
           "    _brake_log: List = []\n    _BRAKE_X = %s\n    _BRAKE_Y = %s\n"
           "    _BRAKE_F = %s\n    _HYST = %s" % (bx, by_, bf, hyst))
    src = _once(AA, AA + add)
    src = _once(BB, BB + ", _brake, _brake_trough, _brake_peak, _brake_log")
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
    src = _once(EVAL_OLD, EVAL_NEW_HYST)
    ns = {}
    exec(compile(src, "switch_engine_k21", "exec"), ns)
    return ns


piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))

_shadow_cache = {}
_ns_cache = {}


def get_ns(bx, by_, bf, hyst):
    k = (bx, by_, bf, hyst)
    if k not in _ns_cache:
        _ns_cache[k] = build_ns_k21(bx, by_, bf, hyst)
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
            hyst=0.0):
    assert evalfreq in ("grid", "daily"), evalfreq
    inp_a, inp_b, ra, rb, CA, CFG_B = get_shadows(
        cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp)
    KW = dict(n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0,
              inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq,
              rs_lookback=rs, exclude_a=MB, exclude_b=MB,
              evalfreq=evalfreq, brake_daily=False,
              **{k: v for k, v in CA.items() if k != "exclude"})
    ns = get_ns(bx, by_, bf, hyst)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "seat": seat, "combo": combo, "evalfreq": evalfreq,
           "hyst": hyst, "rs": rs, "bx": bx, "by": by_, "bf": bf,
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


PHASE1 = [
    dict(tag="k21_daily_hyst003_M07", seat="M07", combo="daily+hyst0.03",
         evalfreq="daily", hyst=0.03, rs=60),
    dict(tag="k21_daily_hyst008_M07", seat="M07", combo="daily+hyst0.08",
         evalfreq="daily", hyst=0.08, rs=60),
    dict(tag="k21_daily_rs120_M07", seat="M07", combo="daily+rs120",
         evalfreq="daily", hyst=0.0, rs=120),
    dict(tag="k21_daily_rs252_M07", seat="M07", combo="daily+rs252",
         evalfreq="daily", hyst=0.0, rs=252),
]

SLIM_KEYS = ("tag", "evalfreq", "hyst", "rs", "seat", "total", "mdd", "trades",
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
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]
    rows = []
    base = run_cfg(dict(tag="base_M07", seat="M07", combo="calibration",
                        evalfreq="grid", hyst=0.0, rs=60))
    rows.append(base)
    calib_check(base)
    if only == "base_M07":
        open(ROOT / "results" / "r30_bt" / "sweep_beat_m07_k21.json", "w").write(
            json.dumps(rows, ensure_ascii=False, indent=1))
        print("saved 1 row (only=base_M07)", flush=True)
        sys.exit(0)
    phase1 = []
    for cfg in PHASE1:
        if only is not None and cfg["tag"] != only:
            continue
        try:
            r = run_cfg(cfg)
            rows.append(r)
            phase1.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (cfg["tag"], e), flush=True)
            import traceback
            traceback.print_exc()
    if only is None:
        rank = sorted(phase1, key=lambda r: (r["nbeat_m07"], r["total"]), reverse=True)
        best = rank[0]
        if best["nbeat_m07"] >= 4:
            cands = [best]
            if (len(rank) > 1 and rank[1]["nbeat_m07"] >= 4
                    and (rank[1]["hyst"], rank[1]["rs"]) != (best["hyst"], best["rs"])):
                cands.append(rank[1])
            for src in cands[:2]:
                tag2 = src["tag"].replace("_M07", "_gbf07")
                cfg2 = dict(tag=tag2, seat="gbf07",
                            combo="phase2: %s x g_bf07 seat" % src["tag"],
                            cut_a=0.78, cut_b=0.78, bx=0.15, by_=0.05, bf=0.7,
                            evalfreq=src["evalfreq"], hyst=src["hyst"], rs=src["rs"])
                try:
                    r2 = run_cfg(cfg2)
                    rows.append(r2)
                except Exception as e:
                    print("FAIL %s: %s" % (tag2, e), flush=True)
                    import traceback
                    traceback.print_exc()
        else:
            print("SKIP phase2: max phase-1 nbeat_m07=%d < 4 (gate); no g_bf07 rows" % best["nbeat_m07"], flush=True)
        print("=== K21 VERDICT ===", flush=True)
        ab = [r["tag"] for r in rows if r.get("beat_all")]
        print("beat_all rows: %s" % (ab if ab else "NONE"), flush=True)
        pool = [r for r in rows if r["tag"] != "base_M07"]
        best2 = sorted(pool, key=lambda r: (r["nbeat_m07"], r["total"]), reverse=True)[0]
        diffs = ", ".join(["%s %+.2f" % (w, best2[w] - M07[w]) for w in ("1m", "3m", "6m", "1y", "2y", "3y")])
        print("BEST %s nbeat=%d six-window diffs vs M07: %s" % (best2["tag"], best2["nbeat_m07"], diffs), flush=True)
        print("BEST total=%.2f mdd=%.2f switches=%d cost=%.0f first_switch=%s" % (
            best2["total"], best2["mdd"], best2["switches"], best2["cost"],
            (best2["switch_log"][0] if best2["switch_log"] else None)), flush=True)
        for r in pool:
            fs = r["switch_log"][0] if r["switch_log"] else None
            early = bool(fs and fs[0] <= "2023-06-21" and fs[1] == "B")
            print("CONSTRAINT %s first=%s earlyB=%s switches=%d(vs K20-daily 33) cost=%.0f(vs K20-daily 97391)" % (
                r["tag"], fs, early, r["switches"], r["cost"]), flush=True)
        open(ROOT / "results" / "r30_bt" / "sweep_beat_m07_k21.json", "w").write(
            json.dumps(rows, ensure_ascii=False, indent=1))
        print("saved %d rows" % len(rows), flush=True)
