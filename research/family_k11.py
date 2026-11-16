#!/usr/bin/env python3
"""K11 new family: hysteresis-band switch + brake-freeze linkage (new file only).

Background: K1-K10 total 138 configs beat_all=0. Within the same switch family
(trailing-60 shadow RS switch + brake), thresholds/families/mechanisms/selectors
(pure + composite keys) are exhausted. Short-window wall = tail holdings share
the same identity + denominator effect. In K9/K10, new-selector configs show
switches soaring to 7-15 (M07=3): whipsaw. The new selectors' shadow-RS spread
crosses the zero line at high frequency, and the bandwidth-free ra>=rb rule
generates lots of follower switches. Joint rebuild K11 = change the SWITCH
mechanism (no more single-threshold search) x new selector.

New switch mechanism (both are fixed family traits, never jointly tried in K1-K10):
  1. hysteresis band: switch only if the leader exceeds by >= h (return units,
     e.g. h=0.05 = 5pp), else keep current mode. Anti-whipsaw.
  2. brake-freeze linkage: when brake state _brake=True, freeze switching
     (desired=mode); do not change course in defensive periods. The brake
     itself is verbatim M07 (bx/by/bf identical); only the new linkage line
     brake-state -> switch-decision is added.

No lookahead: _rs reads shadow values at/before sig_i only via
searchsorted(right-1); _brake is updated from pre-rebalance holdings mark-to-
market on signal day t, execution at t+1, same info set as the M07 brake.
Switching is evaluated on A-grid signal days only (verbatim M07).

Selector: reuse research/inputs_k10.py K10Inputs sel='a60_a5'
(amihud60-rank + amihud5-rank composite, MAX on) -- i.e. the task's
"K9 amihud_5 or one of the K10 composite keys" (a60_a5 contains the amihud5
leg; amihud5-family selectors showed the strongest short-window alpha trace
in K9/K10: k9_amihud_5_both nbeat=3).
"""
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]

AA = "    switch_log: List[Tuple[str, str]] = []"
BB = "        nonlocal cash, total_cost, mode, state_take, state_n, state_exposure"
CC = "        sig_day = dates[sig_i]"
DD = "        picks = inp_cur.picks(sig_day, n_eff, exclude=exclude, factor=factor)"
EE = "        for code in picks:"
FF = "        eq_rows.append((day, cash + mv, mv, cash, len(pos)))"
GG = "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode,"
SIG = "    exclude: Tuple[str, ...] = (),"
PICKLINE = "        picks = inp_cur.picks(sig_day, n_eff, exclude=exclude, factor=factor)"
# M07 original rule (inside switch_engine.py do_rebalance)
DESIRED = ("            if ra is not None and rb is not None:\n"
           '                desired = "A" if ra >= rb else "B"')

FAMILY = "k11_hyst_brakefreeze"


def build_ns_k11(hyst=0.05, brake_freeze=True, bx=0.18, by_=0.08, bf=0.6):
    """Build the K11 family switch-engine namespace (brake_log etc. same as build_ns).

    All patches verbatim sweep_beat_h1_v4.build_ns except the switch rule and
    the brake_eval position note below (skip_block / exclude_a_b / brake-scaled
    alloc / brake_peak update / meta brake_log), so caliber differs from M07
    ONLY in the switch-mechanism dimension.
    """
    src = (ROOT / "research" / "switch_engine.py").read_text()

    def _once(old, new):
        assert src.count(old) == 1, (old[:60], src.count(old))
        return src.replace(old, new)

    # -- brake state vars (+K11 params) --
    add = ("\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n"
           "    _brake_log: List = []\n    _BRAKE_X = %s\n    _BRAKE_Y = %s\n"
           "    _BRAKE_F = %s\n    _HYST = %s\n    _BRAKE_FREEZE = %s"
           % (bx, by_, bf, hyst, bool(brake_freeze)))
    src = _once(AA, AA + add)
    src = _once(BB, BB + ", _brake, _brake_trough, _brake_peak, _brake_log")
    # brake_eval after CC = before switch evaluation (same position/order as build_ns)
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
    src = _once(CC, CC + brake_eval)
    # -- K11 new switch rule: hysteresis + brake freeze --
    new_desired = ("            if ra is not None and rb is not None:\n"
                   "                if _brake and _BRAKE_FREEZE:\n"
                   "                    desired = mode\n"
                   '                elif mode == "A":\n'
                   '                    desired = "B" if rb - ra >= _HYST else "A"\n'
                   "                else:\n"
                   '                    desired = "A" if ra - rb >= _HYST else "B"')
    src = _once(DESIRED, new_desired)
    # -- below verbatim build_ns --
    skip_block = "\n        if not switching and set(picks) == set(pos):\n            return False"
    src = _once(DD, DD + skip_block)
    src = _once(PICKLINE, "        _ex = (exclude_a if mode == 'A' else exclude_b) if (exclude_a is not None or exclude_b is not None) else exclude\n" + PICKLINE.replace("exclude=exclude", "exclude=_ex"))
    src = _once(SIG, SIG + "\n    exclude_a=None,\n    exclude_b=None,")
    src = _once(EE, "        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n" + EE)
    src = _once(FF, FF + "\n        if (cash + mv) > _brake_peak:\n            _brake_peak = cash + mv")
    src = _once(GG, "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode, brake_log=_brake_log,")
    ns = {}
    exec(compile(src, "switch_engine_k11", "exec"), ns)
    return ns
