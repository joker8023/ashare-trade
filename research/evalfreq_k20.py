#!/usr/bin/env python3
"""K20: evaluation-frequency pilot on top of switch_engine.py caliber.

Caliber statement (identical to M07/K2 except evaluation frequency):
ph0 / RUN_START=2023-01-03 / EVAL_END=2026-11-12 / capital 50000 /
realistic fees + slip 0.002 / round lots lot=100 / native amihud_60 both legs /
A-B params verbatim M07 / brake + RS60 verbatim sweep_beat_h1_v4.build_ns.
Only addition: evalfreq parameter (this file) + sweep script.

evalfreq:
- "grid"   : original caliber. Evaluate only on A-grid signal days (calibration).
- "daily"  : after each close, compare trailing shadow RS at t (t and earlier
             only), switch executed at t+1 close (full-liquidate round lots;
             picks use signal-day dates[t] factor data, same sig->exec+1 shape).
- "daily1" : daily + 1-day confirmation: flip only if desired(t)==desired(t-1)
             and != mode; executed at t+1 close.

Brake: by default still evaluated/acted ONLY on rebalance days (calls whose
signal belongs to the A/B grids), comparable to original caliber;
brake_daily=True is reserved for an explicitly-declared control variant.
No lookahead: daily eval uses only shadow values at/before t (_rs trailing RS).
Long-only, no leverage (full_liquidate=True, exposure<=1.0 unchanged).
"""
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))

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
_UNUSED_EXECMAP = ("    exec_map: Dict[int, int] = {}\n"
           "    for i in grid + grid_b:\n"
           "        ei = i + 1 + sig_lag\n"
           "        if ei < n_dates:\n"
           "            exec_map.setdefault(ei, i)")
EVAL_OLD = ("        desired = mode\n"
            "        if lock_mode is None and inp_b is not None and sig_i in sig_a:\n"
            "            ra = _rs(shadow_a, sig_i)\n"
            "            rb = _rs(shadow_b, sig_i)\n"
            "            if ra is not None and rb is not None:\n"
            "                desired = \"A\" if ra >= rb else \"B\"")
EVAL_NEW = ("        # switch-eval: grid=A-grid days only (orig); daily/daily1=evaluate each close, t and earlier only\n"
            "        desired = mode\n"
            "        _eval_daily = (evalfreq in (\"daily\", \"daily1\"))\n"
            "        if lock_mode is None and inp_b is not None and ((sig_i in sig_a) or _eval_daily):\n"
            "            ra = _rs(shadow_a, sig_i)\n"
            "            rb = _rs(shadow_b, sig_i)\n"
            "            if ra is not None and rb is not None:\n"
            "                _d = \"A\" if ra >= rb else \"B\"\n"
            "                if evalfreq == \"daily1\":\n"
            "                    _ra0 = _rs(shadow_a, sig_i - 1) if sig_i - 1 >= 0 else None\n"
            "                    _rb0 = _rs(shadow_b, sig_i - 1) if sig_i - 1 >= 0 else None\n"
            "                    if _ra0 is None or _rb0 is None:\n"
            "                        _d = mode\n"
            "                    else:\n"
            "                        _d0 = \"A\" if _ra0 >= _rb0 else \"B\"\n"
            "                        if _d0 != _d:\n"
            "                            _d = mode\n"
            "                desired = _d")
EXECMAP_ADD = ("\n    if evalfreq in (\"daily\", \"daily1\") and lock_mode is None and inp_b is not None:\n"
               "        for _t in range(loop_start, loop_end + 1):\n"
               "            _ei = _t + 1 + sig_lag\n"
               "            if _ei <= loop_end:\n"
               "                exec_map.setdefault(_ei, _t)")


def build_ns_k20(bx=0.18, by_=0.08, bf=0.6):
    src = (ROOT / "research" / "switch_engine.py").read_text()

    def _once(old, new):
        assert src.count(old) == 1, (old[:60], src.count(old))
        return src.replace(old, new)

    # --- verbatim build_ns (sweep_beat_h1_v4) patches: brake + caliber --- #
    add = "\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n    _brake_log: List = []\n    _BRAKE_X = %s\n    _BRAKE_Y = %s\n    _BRAKE_F = %s" % (bx, by_, bf)
    src = _once(AA, AA + add)
    src = _once(BB, BB + ", _brake, _brake_trough, _brake_peak, _brake_log")
    brake_eval = "\n        tb_mv_pre = 0.0\n        for tb_cc, tb_p in pos.items():\n            tb_px = px_ffill_or_nan(mark, day, tb_cc)\n            if pd.isna(tb_px):\n                tb_px = tb_p.entry_px\n            tb_mv_pre += tb_p.shares * tb_px\n        tb_eq_pre = cash + tb_mv_pre\n        if tb_eq_pre > _brake_peak:\n            _brake_peak = tb_eq_pre\n        if not _brake and _brake_peak > 0 and (_brake_peak - tb_eq_pre) / _brake_peak >= _BRAKE_X:\n            _brake = True\n            _brake_trough = tb_eq_pre\n            _brake_log.append((str(day.date()), 'ON', round(float((_brake_peak - tb_eq_pre) / _brake_peak) * 100, 2)))\n        elif _brake:\n            if tb_eq_pre < _brake_trough:\n                _brake_trough = tb_eq_pre\n            if _brake_trough > 0 and tb_eq_pre >= _brake_trough * (1.0 + _BRAKE_Y):\n                _brake = False\n                _brake_log.append((str(day.date()), 'OFF', round(float(tb_eq_pre / _brake_trough - 1) * 100, 2)))"
    # K20 gate: brake still acts only on rebalance days (grid-signal calls), unless brake_daily control.
    brake_gated = ("\n        _brake_gate = brake_daily or (sig_i in sig_a) or (sig_i in sig_b)\n"
                   "        if _brake_gate:" + textwrap.indent(brake_eval, "    "))
    src = _once(CC, CC + brake_gated)
    skip_block = "\n        if not switching and set(picks) == set(pos):\n            return False"
    src = _once(DD, DD + skip_block)
    src = _once(PICKLINE, "        _ex = (exclude_a if mode == 'A' else exclude_b) if (exclude_a is not None or exclude_b is not None) else exclude\n" + PICKLINE.replace("exclude=exclude", "exclude=_ex"))
    src = _once(SIG, SIG + "\n    exclude_a=None,\n    exclude_b=None,")
    # --- K20 signature additions --- #
    src = _once("    exclude_a=None,\n    exclude_b=None,",
                "    exclude_a=None,\n    exclude_b=None,\n    evalfreq=\"grid\",\n    brake_daily=False,")
    src = _once(EE, "        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n" + EE)
    src = _once(FF, FF + "\n        if (cash + mv) > _brake_peak:\n            _brake_peak = cash + mv")
    src = _once(GG, "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode, brake_log=_brake_log,")
    # --- K20 daily-eval additions --- #
    src = _once(LOOPEND, LOOPEND + EXECMAP_ADD)
    src = _once(EVAL_OLD, EVAL_NEW)
    ns = {}
    exec(compile(src, "switch_engine_k20", "exec"), ns)
    return ns
