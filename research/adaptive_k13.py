#!/usr/bin/env python3
"""K13 adaptive mechanisms (new file only): dynamic-N + switch-confirm delay.

Caliber verbatim M07 (ph0 / RUN_START=2023-01-03 / EVAL_END=2026-11-12 / 50k /
real fee (cost_one_way=None) / slip=0.002 / lot=100 / legacy_grid=False /
full_liquidate=True / stop_exec=next / MB exclusion / native amihud_60 legs /
A band=(0.02,0.30) gate60=-0.15 cut=0.80 win=40 take=1.2 n=5 rebal=20 exp=1.0;
B band=(0.05,0.30) gate60=-1.0 cut=0.80 win=20 take=0.8 n=4 rebal=30 exp=0.9;
RS trailing-60 shadow (ra>=rb->A else B) / brake bx0.18/by0.08/bf0.6)
EXCEPT the single new-mechanism dimension under test.

Mechanism A -- dynamic N (build_ns_k13_dynN):
  On every A-grid switch-signal day, using shadow values at t and before only
  (_rs via searchsorted right-1, same info set as the M07 switch rule),
  margin = abs(ra - rb) (trailing-60 shadow-RS spread, return units).
  If margin > thresh T the leg concentrates (N=3), else it holds N=5.
  T in {0.05, 0.10} (5pp/10pp).
  legs="B": only the B leg is dynamic (A stays native n=5);
         legs="both": both legs follow the same margin rule.
  NOTE: dynamic legs toggle in {3,5}, so a dynamic B leg rests at N=5 rather
  than the M07 native B n=4 -- that deviation IS the mechanism under test.
  The N decision is made on signal day t and takes effect at t+1 execution
  via the native exec_map; the rebuild runs through the native full_liquidate
  chain (full clear + repick with the new n_eff). N changes only on signal
  days (no intraday/path-dependent sizing).

Mechanism B -- switch-confirm delay (build_ns_k13_dly):
  A delayed-direction flip executes only if 2 CONSECUTIVE A-grid signal days
  vote the same new direction. The 1st signal day only records pending (no
  action, no rebuild); the 2nd consecutive same-direction signal confirms and
  executes at t+1 through the native chain. A same-as-mode signal in between
  cancels the pending flip (streak broken). Confirmation signals use
  t-and-before data only (same _rs info set).
  direction="enterB" (delay-ON):  only A->B flips need confirmation, B->A
      immediate. direction="exitB" (delay-OFF): only B->A flips need
      confirmation, A->B immediate. Brake HELD verbatim M07 in both
      (no freeze, bf=0.6 allocation scaling unchanged).

No lookahead: every new line reads _rs(sig_i) (t-and-before) or signal-day
state; execution stays on the native t+1 exec_map.
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
DESIRED = ("            if ra is not None and rb is not None:\n"
           '                desired = "A" if ra >= rb else "B"')
STATE_BLK = ("            state_exposure = exposure if mode == \"A\" else cfg_b[\"exposure\"]\n"
             "            switch_log.append((str(sig_day.date()), mode))")
BRAKE_EVAL = ("\n        tb_mv_pre = 0.0\n        for tb_cc, tb_p in pos.items():\n"
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
SKIP_BLOCK = "\n        if not switching and set(picks) == set(pos):\n            return False"

FAMILY_DYN = "k13_dynamicN"
FAMILY_DLY = "k13_confirm_delay"


def _apply_verbatim_tail(src):
    def _once(old, new):
        assert src.count(old) == 1, (old[:60], src.count(old))
        return src.replace(old, new)
    src = _once(DD, DD + SKIP_BLOCK)
    src = _once(PICKLINE, "        _ex = (exclude_a if mode == 'A' else exclude_b) if (exclude_a is not None or exclude_b is not None) else exclude\n" + PICKLINE.replace("exclude=exclude", "exclude=_ex"))
    src = _once(SIG, SIG + "\n    exclude_a=None,\n    exclude_b=None,")
    src = _once(EE, "        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n" + EE)
    src = _once(FF, FF + "\n        if (cash + mv) > _brake_peak:\n            _brake_peak = cash + mv")
    return src


def build_ns_k13_dynN(thresh=0.05, legs="B", bx=0.18, by_=0.08, bf=0.6):
    """Dynamic-N switch engine (mechanism A). See module docstring."""
    assert legs in ("B", "both"), legs
    src = (ROOT / "research" / "switch_engine.py").read_text()

    def _once(old, new):
        nonlocal src
        assert src.count(old) == 1, (old[:60], src.count(old))
        src = src.replace(old, new)

    add = ("\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n"
           "    _brake_log: List = []\n    _BRAKE_X = %s\n    _BRAKE_Y = %s\n"
           "    _BRAKE_F = %s\n    _DYN_T = %s\n    _DYN_LEGS = \"%s\"\n"
           "    _dyn_nA = 5\n    _dyn_nB = 5\n    _dyn_prev = (5, 5)\n    _dyn_log: List = []"
           % (bx, by_, bf, thresh, legs))
    _once(AA, AA + add)
    _once(BB, BB + ", _brake, _brake_trough, _brake_peak, _brake_log, _dyn_nA, _dyn_nB, _dyn_prev")
    _once(CC, CC + BRAKE_EVAL)
    new_desired = (DESIRED + "\n"
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
                   "                    _dyn_log.append((str(sig_day.date()), _dyn_nA, _dyn_nB, round(float(_margin), 4)))\n"
                   "                    _dyn_prev = (_dyn_nA, _dyn_nB)")
    _once(DESIRED, new_desired)
    _once(STATE_BLK, STATE_BLK + "\n        state_n = (_dyn_nA if mode == \"A\" else _dyn_nB)")
    src = _apply_verbatim_tail(src)
    _once(GG, GG + " brake_log=_brake_log, dyn_log=_dyn_log,")
    ns = {}
    exec(compile(src, "switch_engine_k13_dynN", "exec"), ns)
    return ns


def build_ns_k13_dly(direction="enterB", bx=0.18, by_=0.08, bf=0.6):
    """Confirm-delay switch engine (mechanism B). See module docstring."""
    assert direction in ("enterB", "exitB"), direction
    src = (ROOT / "research" / "switch_engine.py").read_text()

    def _once(old, new):
        nonlocal src
        assert src.count(old) == 1, (old[:60], src.count(old))
        src = src.replace(old, new)

    add = ("\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n"
           "    _brake_log: List = []\n    _BRAKE_X = %s\n    _BRAKE_Y = %s\n"
           "    _BRAKE_F = %s\n    _DLY_DIR = \"%s\"\n    _pend = None\n    _dly_log: List = []"
           % (bx, by_, bf, direction))
    _once(AA, AA + add)
    _once(BB, BB + ", _brake, _brake_trough, _brake_peak, _brake_log, _pend")
    _once(CC, CC + BRAKE_EVAL)
    new_desired = (DESIRED + "\n"
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
    _once(DESIRED, new_desired)
    src = _apply_verbatim_tail(src)
    _once(GG, GG + " brake_log=_brake_log, dly_log=_dly_log,")
    ns = {}
    exec(compile(src, "switch_engine_k13_dly", "exec"), ns)
    return ns
