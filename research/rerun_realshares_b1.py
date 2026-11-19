#!/usr/bin/env python3
"""Rerun 5 frozen-caliber configs on data/pivots_2020_clean_realshares.pkl.
Caliber verbatim vs frozen (ph0/RUN_START=2023-01-03/EVAL_END=2026-11-12/
5w/realistic fees cost_one_way=None + slip 0.002/lot 100):
  M07 (research/run_m07_final.py) / J04 (research/run_j04_final.py) /
  g_bf07 (K3 row: by05+cut78both+bx15+bf07) /
  k21_daily_hyst003_gbf07 (K21 phase2 row: daily/hyst.03/rs60 on gbf07 seat) /
  g_bf07_winA30 (K8 row: gbf07+winA30).
Only change: piv input file. No lookahead (same-day shares; MAX/Amihud trailing).
Output: results/r30_bt/rerun_realshares_b1.json
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
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
assert RUN_START == "2023-01-03", RUN_START
assert str(EVAL_END)[:10] == "2026-11-12", EVAL_END
assert WINDOWS == {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}
NEW_PIV = ROOT / "data" / "pivots_2020_clean_realshares.pkl"
assert NEW_PIV.exists(), "build data/pivots_2020_clean_realshares.pkl first"
piv = pd.read_pickle(NEW_PIV)
print("new piv: %s days=%d codes=%d shares_type=%s" % (
    NEW_PIV.name, piv["close"].shape[0], piv["close"].shape[1],
    type(piv["shares"]).__name__), flush=True)
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
print("first_sig:", first_sig.date(), flush=True)
_shadow_cache = {}
_ns_cache = {}
def get_ns(bx, by, bf):
    k = (bx, by, bf)
    if k not in _ns_cache:
        _ns_cache[k] = build_ns(bx, by, bf)
    return _ns_cache[k]
def get_shadows(cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n,
                b_exp, gate_a=-0.15, band_a_lo=0.02):
    key = (cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n,
           b_exp, gate_a, band_a_lo)
    if key in _shadow_cache:
        return _shadow_cache[key]
    inp_a = MaxInputs(piv, band=(band_a_lo, 0.30), gate60=gate_a,
                      max_cut=cut_a, max_win=win_a)
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0,
                      max_cut=cut_b, max_win=win_b)
    CA = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=MB,
              capital=50000.0, lot=100, cost_one_way=None, slip=0.002,
              run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END,
              legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=b_n, rebal=30, take=b_take, exposure=b_exp)
    ra = pc.run_strategy(inp_a, n=a_n, rebal=20, take=a_take, exposure=1.0,
                         phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
    _shadow_cache[key] = (inp_a, inp_b, ra, rb, CA, CFG_B)
    return _shadow_cache[key]
def run_one(tag, combo="", cut_a=0.80, win_a=40, cut_b=0.80, win_b=20,
            stop=0.25, a_take=1.2, b_take=0.80, a_n=5, b_n=4, b_exp=0.9,
            rs=60, bx=0.18, by_=0.08, bf=0.6,
            gate_a=-0.15, band_a_lo=0.02):
    inp_a, inp_b, ra, rb, CA, CFG_B = get_shadows(
        cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp,
        gate_a, band_a_lo)
    KW = dict(n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0,
              inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq,
              rs_lookback=rs, exclude_a=MB, exclude_b=MB,
              **{k: v for k, v in CA.items() if k != "exclude"})
    ns = get_ns(bx, by_, bf)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "combo": combo,
           "total": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
           "mdd": round(_mdd(eq) * 100, 2),
           "trades": len(res.trades),
           "cost": round(float(res.meta["total_cost"]), 0),
           "mode": res.meta["final_mode"],
           "switches": len(res.meta["switch_log"]),
           "switch_log": [list(x) for x in res.meta["switch_log"]],
           "brake_log": [list(x) for x in res.meta.get("brake_log", [])]}
    for w, d in WINDOWS.items():
        sub = eq.tail(d + 1)
        out[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
        out[w + "_mdd"] = round(_mdd(sub) * 100, 2)
    return out
# ---- K21 engine, verbatim logic of build_ns_k21 in ----
# ---- research/sweep_beat_m07_k21.py (no frozen-piv reload) ----
K21_ENGINE_NOTE = "verbatim port of sweep_beat_m07_k21.build_ns_k21 (same asserts, same string patches)"
def build_ns_k21(bx=0.18, by_=0.08, bf=0.6, hyst=0.0):
    import textwrap as _tw
    src = (ROOT / "research" / "switch_engine.py").read_text()
    def _once(old, new):
        assert src.count(old) == 1, (old[:60], src.count(old))
        return src.replace(old, new)
    AA = "    switch_log: List[Tuple[str, str]] = []"
    BB = "        nonlocal cash, total_cost, mode, state_take, state_n, state_exposure"
    CC = "        sig_day = dates[sig_i]"
    DD = "        picks = inp_cur.picks(sig_day, n_eff, exclude=exclude, factor=factor)"
    EE = "        for code in picks:"
    FF = "        eq_rows.append((day, cash + mv, mv, cash, len(pos)))"
    GG = "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode,"
    SIG = "    exclude: Tuple[str, ...] = (),"
    LOOPEND = "    loop_end = min(end_i, n_dates - 1)"
    EVAL_OLD = "        desired = mode" + chr(10) + "        if lock_mode is None and inp_b is not None and sig_i in sig_a:" + chr(10) + "            ra = _rs(shadow_a, sig_i)" + chr(10) + "            rb = _rs(shadow_b, sig_i)" + chr(10) + "            if ra is not None and rb is not None:" + chr(10) + chr(32) + chr(32) + chr(32) + chr(32) + chr(32) + chr(32) + chr(32) + chr(32) + chr(32) + chr(32) + chr(32) + chr(32) + chr(32) + chr(32) + chr(32) + chr(32) + "desired = " + chr(34) + "A" + chr(34) + " if ra >= rb else " + chr(34) + "B" + chr(34)
    EVAL_NEW = "        desired = mode" + chr(10) + "        _eval_daily = (evalfreq == " + chr(34) + "daily" + chr(34) + ")" + chr(10) + "        if lock_mode is None and inp_b is not None and ((sig_i in sig_a) or _eval_daily):" + chr(10) + "            ra = _rs(shadow_a, sig_i)" + chr(10) + "            rb = _rs(shadow_b, sig_i)" + chr(10) + "            if ra is not None and rb is not None:" + chr(10) + "                if mode == " + chr(34) + "A" + chr(34) + ":" + chr(10) + "                    _d = " + chr(34) + "B" + chr(34) + " if rb - ra >= _HYST else " + chr(34) + "A" + chr(34) + chr(10) + "                else:" + chr(10) + "                    _d = " + chr(34) + "A" + chr(34) + " if ra - rb >= _HYST else " + chr(34) + "B" + chr(34) + chr(10) + "                desired = _d"
    EXECMAP_ADD = chr(10) + "    if evalfreq == " + chr(34) + "daily" + chr(34) + " and lock_mode is None and inp_b is not None:" + chr(10) + "        for _t in range(loop_start, loop_end + 1):" + chr(10) + "            _ei = _t + 1 + sig_lag" + chr(10) + "            if _ei <= loop_end:" + chr(10) + "                exec_map.setdefault(_ei, _t)"
    Q = chr(39)
    NL = chr(10)
    add = NL + "    _brake = False" + NL + "    _brake_trough = 0.0" + NL + "    _brake_peak = 0.0" + NL + "    _brake_log: List = []" + NL + "    _BRAKE_X = %s" % bx + NL + "    _BRAKE_Y = %s" % by_ + NL + "    _BRAKE_F = %s" % bf + NL + "    _HYST = %s" % hyst
    src = _once(AA, AA + add)
    src = _once(BB, BB + ", _brake, _brake_trough, _brake_peak, _brake_log")
    L1 = NL + "        tb_mv_pre = 0.0" + NL + "        for tb_cc, tb_p in pos.items():" + NL + "            tb_px = px_ffill_or_nan(mark, day, tb_cc)" + NL + "            if pd.isna(tb_px):" + NL + "                tb_px = tb_p.entry_px" + NL + "            tb_mv_pre += tb_p.shares * tb_px" + NL + "        tb_eq_pre = cash + tb_mv_pre" + NL + "        if tb_eq_pre > _brake_peak:" + NL + "            _brake_peak = tb_eq_pre" + NL + "        if not _brake and _brake_peak > 0 and (_brake_peak - tb_eq_pre) / _brake_peak >= _BRAKE_X:" + NL + "            _brake = True" + NL + "            _brake_trough = tb_eq_pre" + NL + "            _brake_log.append((str(day.date()), " + Q + "ON" + Q + ", round(float((_brake_peak - tb_eq_pre) / _brake_peak) * 100, 2)))" + NL + "        elif _brake:" + NL + "            if tb_eq_pre < _brake_trough:" + NL + "                _brake_trough = tb_eq_pre" + NL + "            if _brake_trough > 0 and tb_eq_pre >= _brake_trough * (1.0 + _BRAKE_Y):" + NL + "                _brake = False" + NL + "                _brake_log.append((str(day.date()), " + Q + "OFF" + Q + ", round(float(tb_eq_pre / _brake_trough - 1) * 100, 2)))"
    brake_gated = NL + "        _brake_gate = brake_daily or (sig_i in sig_a) or (sig_i in sig_b)" + NL + "        if _brake_gate:" + _tw.indent(L1, "    ")
    src = _once(CC, CC + brake_gated)
    skip_block = NL + "        if not switching and set(picks) == set(pos):" + NL + "            return False"
    src = _once(DD, DD + skip_block)
    src = _once(DD, "        _ex = (exclude_a if mode == " + Q + "A" + Q + " else exclude_b) if (exclude_a is not None or exclude_b is not None) else exclude" + NL + DD.replace("exclude=exclude", "exclude=_ex"))
    src = _once(SIG, SIG + NL + "    exclude_a=None," + NL + "    exclude_b=None,")
    src = _once("    exclude_a=None," + NL + "    exclude_b=None,", "    exclude_a=None," + NL + "    exclude_b=None," + NL + "    evalfreq=" + chr(34) + "grid" + chr(34) + "," + NL + "    brake_daily=False,")
    src = _once(EE, "        alloc = alloc * (_BRAKE_F if _brake else 1.0)" + NL + EE)
    src = _once(FF, FF + NL + "        if (cash + mv) > _brake_peak:" + NL + "            _brake_peak = cash + mv")
    src = _once(GG, "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode, brake_log=_brake_log,")
    src = _once(LOOPEND, LOOPEND + EXECMAP_ADD)
    src = _once(EVAL_OLD, EVAL_NEW)
    ns = {}
    exec(compile(src, "switch_engine_k21", "exec"), ns)
    return ns
_ns_k21_cache = {}
def get_ns_k21(bx, by_, bf, hyst):
    k = (bx, by_, bf, hyst)
    if k not in _ns_k21_cache:
        _ns_k21_cache[k] = build_ns_k21(bx, by_, bf, hyst)
    return _ns_k21_cache[k]
def run_one_k21(tag, seat="gbf07", combo="", cut_a=0.80, win_a=40,
                cut_b=0.80, win_b=20, stop=0.25, a_take=1.2, b_take=0.80,
                a_n=5, b_n=4, b_exp=0.9, rs=60, bx=0.18, by_=0.08, bf=0.6,
                evalfreq="daily", hyst=0.0):
    assert evalfreq in ("grid", "daily"), evalfreq
    inp_a, inp_b, ra, rb, CA, CFG_B = get_shadows(
        cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp)
    KW = dict(n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0,
              inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq,
              rs_lookback=rs, exclude_a=MB, exclude_b=MB,
              evalfreq=evalfreq, brake_daily=False,
              **{k: v for k, v in CA.items() if k != "exclude"})
    ns = get_ns_k21(bx, by_, bf, hyst)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "seat": seat, "combo": combo, "evalfreq": evalfreq,
           "hyst": hyst, "rs": rs, "bx": bx, "by": by_, "bf": bf,
           "total": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
           "mdd": round(_mdd(eq) * 100, 2),
           "trades": len(res.trades),
           "cost": round(float(res.meta["total_cost"]), 0),
           "mode": res.meta["final_mode"],
           "switches": len(res.meta["switch_log"]),
           "switch_log": [list(x) for x in res.meta["switch_log"]],
           "brake_log": [list(x) for x in res.meta.get("brake_log", [])]}
    for w, d in WINDOWS.items():
        sub = eq.tail(d + 1)
        out[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
        out[w + "_mdd"] = round(_mdd(sub) * 100, 2)
    return out
FROZEN = {
    "M07": {"src": "results/r30_bt/M07_final.json", "total": 1863.27, "mdd": -27.05, "trades": 184, "cost": 50990.0, "switches": 3, "1m": -4.09, "3m": 17.28, "6m": 39.0, "1y": 164.05, "2y": 1474.08, "3y": 1677.53},
    "J04": {"src": "results/r30_bt/J04_final.json", "total": 1765.84, "mdd": -27.63, "trades": 195, "cost": 49337.0, "switches": 3, "1m": -4.84, "3m": 15.64, "6m": 37.17, "1y": 160.27, "2y": 1449.34, "3y": 1581.48},
    "g_bf07": {"src": "results/r30_bt/sweep_beat_m07_k3.json", "total": 2128.41, "mdd": -24.28, "trades": 184, "cost": 57657.0, "switches": 3, "1m": -4.1, "3m": 17.29, "6m": 39.3, "1y": 164.9, "2y": 1487.61, "3y": 1875.48},
    "k21_daily_hyst003_gbf07": {"src": "results/r30_bt/sweep_beat_m07_k21.json", "total": 1934.29, "mdd": -24.28, "trades": 218, "cost": 63201.0, "switches": 11, "1m": -2.61, "3m": 22.55, "6m": 45.53, "1y": 176.51, "2y": 1367.88, "3y": 1733.48},
    "g_bf07_winA30": {"src": "results/r30_bt/sweep_beat_m07_k8.json", "total": 2400.29, "mdd": -24.17, "trades": 184, "cost": 64607.0, "switches": 3, "1m": -4.09, "3m": 17.25, "6m": 39.26, "1y": 164.4, "2y": 1480.3, "3y": 1870.56},
}
KEYS = ["total", "mdd", "trades", "cost", "switches", "1m", "3m", "6m", "1y", "2y", "3y"]
M07W = {"1m": -4.09, "3m": 17.28, "6m": 39.0, "1y": 164.05, "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
if __name__ == "__main__":
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]
    rows = []
    def emit(r, fkey):
        f = FROZEN[fkey]
        r["frozen_src"] = f["src"]
        r["frozen"] = {k: f[k] for k in KEYS}
        r["diff_vs_frozen"] = {k: round(r[k] - f[k], 2) for k in KEYS}
        slim = {k: r[k] for k in ("tag", "total", "mdd", "trades", "cost", "switches", "1m", "3m", "6m", "1y", "2y", "3y")}
        slim["diff"] = r["diff_vs_frozen"]
        print(json.dumps(slim, ensure_ascii=False), flush=True)
        rows.append(r)
    if only is None or only == "M07":
        emit(run_one("M07", "M07 verbatim (A40/B20/B-N4, brake bx.18/by.08/bf.6)"), "M07")
    if only is None or only == "J04":
        emit(run_one("J04", "J04 verbatim (A40/B40, b_n=5)", win_b=40, b_n=5), "J04")
    if only is None or only == "g_bf07":
        emit(run_one("g_bf07", "K3 row: by05+cut78both+bx15+bf07", by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.7), "g_bf07")
    if only is None or only == "k21_daily_hyst003_gbf07":
        emit(run_one_k21("k21_daily_hyst003_gbf07", seat="gbf07", combo="phase2: k21_daily_hyst003_M07 x g_bf07 seat", cut_a=0.78, cut_b=0.78, bx=0.15, by_=0.05, bf=0.7, evalfreq="daily", hyst=0.03, rs=60), "k21_daily_hyst003_gbf07")
    if only is None or only == "g_bf07_winA30":
        emit(run_one("g_bf07_winA30", "K8 row: g_bf07+winA30", win_a=30, by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.7), "g_bf07_winA30")
    if only is None:
        m07 = next(r for r in rows if r["tag"] == "M07")
        j04 = next(r for r in rows if r["tag"] == "J04")
        g = next(r for r in rows if r["tag"] == "g_bf07")
        w = ["1m", "3m", "6m", "1y", "2y", "3y"]
        verdict = {
            "M07_beat_J04_windows": sum(1 for k in w if m07[k] > j04[k]),
            "M07_mdd_better_than_J04": bool(m07["mdd"] > j04["mdd"]),
            "g_bf07_nbeat_M07real": sum(1 for k in w if g[k] > m07[k]),
            "g_bf07_mdd_better_than_M07real": bool(g["mdd"] > m07["mdd"]),
        }
        print("VERDICT " + json.dumps(verdict, ensure_ascii=False), flush=True)
        open(ROOT / "results" / "r30_bt" / "rerun_realshares_b1.json", "w").write(
            json.dumps({"meta": {"piv": "data/pivots_2020_clean_realshares.pkl", "verdict": verdict}, "rows": rows}, ensure_ascii=False, indent=1))
        print("saved %d rows" % len(rows), flush=True)
    else:
        print("single-row mode, not saved", flush=True)
