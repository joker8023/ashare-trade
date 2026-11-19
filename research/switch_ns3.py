#!/usr/bin/env python3
"""switch_ns3: three-leg switch namespace (A/B/C rotation).
New file; research/switch_ns.py untouched. When C leg absent (inp_c/shadow_c/cfg_c all None),
the compiled engine executes the audited 2-way block verbatim (parity with switch_ns.build_ns).
3-way rule generalizes 2-way hyst/confirm/min_hold semantics to best-of-three with hysteresis gate.
"""
import sys, textwrap
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))
from switch_ns import AA, BB, CC, DD, EE, FF, GG, SIG, PICKLINE, LOOPEND, EVAL_OLD, EVAL_NEW, SWLOG

_RSHARPE_SRC = '    def _rs_sharpe(eq_s, s_idx):\n        if eq_s is None:\n            return None\n        j = int(eq_s.index.searchsorted(dates[s_idx], side="right") - 1)\n        if j < rs_lookback:\n            return None\n        _r = eq_s.iloc[j - rs_lookback + 1:j + 1].pct_change().dropna()\n        if len(_r) < 10:\n            return 0.0\n        _sd = float(_r.std())\n        if _sd <= 0:\n            return 0.0\n        return float(_r.mean() / _sd * (float(len(_r)) ** 0.5))'

_EVAL_INNER = "\n".join(EVAL_NEW.split("\n")[3:])

_THREEWAY = '''            _best = None
            _bestv = None
            for _mm, _vv in (("A", ra), ("B", rb), ("C", rc)):
                if _vv is None:
                    _best = None
                    break
                if _bestv is None or _vv > _bestv:
                    _best = _mm
                    _bestv = _vv
            _HEFF = {"A": _HYST_A, "B": _HYST_B, "C": _HYST_C}
            if _USE_REGIME:
                _rsh = 0.0
                for _ree in (shadow_a, shadow_b, shadow_c):
                    _rsv = _rs_sharpe(_ree, sig_i)
                    if _rsv is not None and abs(_rsv) > abs(_rsh):
                        _rsh = _rsv
                if abs(_rsh) < _REGIME_THRESH:
                    _HEFF = {"A": _HYST_A * _REGIME_MULT, "B": _HYST_B * _REGIME_MULT, "C": _HYST_C * _REGIME_MULT}
            if _best is not None:
                if _best == mode:
                    _confirm_count = 0
                else:
                    _mv = {"A": ra, "B": rb, "C": rc}[mode]
                    if (_bestv - _mv) >= _HEFF[mode]:
                        if (sig_i - _last_switch_i) < _MIN_HOLD:
                            _confirm_count = 0
                        else:
                            _confirm_count += 1
                            if _confirm_count >= _CONFIRM:
                                desired = _best
                    else:
                        _confirm_count = 0'''

def build_ns3(bx=0.18, by_=0.08, bf=0.6, hyst=0.0, min_hold=0, confirm=1, hyst_a=None, hyst_b=None, hyst_c=None, rs_decay_hl=None, rg_mult=None, rg_thresh=1.0, rg_eval_th=None):
    assert bf > 0, 'bf=0 + full_liquidate deadlocks'
    _RG_EV = rg_eval_th
    _RG_EVON = _RG_EV is not None
    _RG_EVTH = _RG_EV if _RG_EVON else 1.0
    src = (ROOT / 'research' / 'switch_engine.py').read_text()
    _HA = hyst if hyst_a is None else hyst_a
    _HB = hyst if hyst_b is None else hyst_b
    _HC = hyst if hyst_c is None else hyst_c
    def _once(old, new):
        assert src.count(old) == 1, (old[:60], src.count(old))
        return src.replace(old, new)
    add = ('\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n'
           '    _brake_log: List = []\n    _BRAKE_X = %s\n    _BRAKE_Y = %s\n'
           '    _BRAKE_F = %s\n    _HYST = %s\n    _MIN_HOLD = %d\n    _CONFIRM = %d\n'
           '    _confirm_count = 0\n    _last_switch_i = -1000000000' % (bx, by_, bf, hyst, min_hold, confirm))
    src = _once(AA, AA + add)
    src = _once(BB, BB + ', _brake, _brake_trough, _brake_peak, _brake_log, _confirm_count, _last_switch_i')
    src = _once('    _confirm_count = 0\n    _last_switch_i = -1000000000', '    _confirm_count = 0\n    _last_switch_i = -1000000000\n    _HYST_A = %s\n    _HYST_B = %s\n    _HYST_C = %s' % (_HA, _HB, _HC))
    brake_eval = ('\n        tb_mv_pre = 0.0\n        for tb_cc, tb_p in pos.items():\n'
                  '            tb_px = px_ffill_or_nan(mark, day, tb_cc)\n'
                  '            if pd.isna(tb_px):\n'
                  '                tb_px = tb_p.entry_px\n'
                  '            tb_mv_pre += tb_p.shares * tb_px\n'
                  '        tb_eq_pre = cash + tb_mv_pre\n'
                  '        if tb_eq_pre > _brake_peak:\n'
                  '            _brake_peak = tb_eq_pre\n'
                  '        if not _brake and _brake_peak > 0 and (_brake_peak - tb_eq_pre) / _brake_peak >= _BRAKE_X:\n'
                  '            _brake = True\n'
                  '            _brake_trough = tb_eq_pre\n'
                  '            _brake_log.append((str(day.date()), \'ON\', round(float((_brake_peak - tb_eq_pre) / _brake_peak) * 100, 2)))\n'
                  '        elif _brake:\n'
                  '            if tb_eq_pre < _brake_trough:\n'
                  '                _brake_trough = tb_eq_pre\n'
                  '            if _brake_trough > 0 and tb_eq_pre >= _brake_trough * (1.0 + _BRAKE_Y):\n'
                  '                _brake = False\n'
                  '                _brake_log.append((str(day.date()), \'OFF\', round(float(tb_eq_pre / _brake_trough - 1) * 100, 2)))')
    brake_gated = ('\n        _brake_gate = brake_daily or (sig_i in sig_a) or (sig_i in sig_b) or (sig_i in sig_c)\n'
                   '        if _brake_gate:' + textwrap.indent(brake_eval, '    '))
    src = _once(CC, CC + brake_gated)
    skip_block = '\n        if not switching and set(picks) == set(pos):\n            return False'
    src = _once(DD, DD + skip_block)
    src = _once(PICKLINE, '        _ex = (exclude_a if mode == \'A\' else (exclude_b if mode == \'B\' else exclude_c)) if (exclude_a is not None or exclude_b is not None or exclude_c is not None) else exclude\n' + PICKLINE.replace('exclude=exclude', 'exclude=_ex'))
    src = _once(SIG, SIG + '\n    exclude_a=None,\n    exclude_b=None,\n    exclude_c=None,')
    src = _once(SIG + '\n    exclude_a=None,\n    exclude_b=None,\n    exclude_c=None,',
                SIG + '\n    exclude_a=None,\n    exclude_b=None,\n    exclude_c=None,\n    evalfreq=\'grid\',\n    brake_daily=False,\n    stop_c=None,')
    src = _once('    shadow_a=None, shadow_b=None,          # 两引擎独立权益曲线 (RS 信号)', '    shadow_a=None, shadow_b=None,          # 两引擎独立权益曲线 (RS 信号)' + '\n    shadow_c=None,                          # leg-C shadow' + '\n    inp_c=None,                             # leg-C inputs' + '\n    cfg_c=None,                             # dict(n=, rebal=, take=, exposure)')
    src = _once(EE, '        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n' + EE)
    src = _once(FF, FF + '\n        if (cash + mv) > _brake_peak:\n            _brake_peak = cash + mv')
    src = _once(GG, '        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode, brake_log=_brake_log,')
    src = _once('        stop_b=_stop_b,', '        stop_b=_stop_b,\n        stop_c=_stop_c,')
    _EXEC_EXTRA = ' or True' if _RG_EVON else ''
    execmap = ('\n    if evalfreq == \'daily\'' + _EXEC_EXTRA + ':\n        for _t in range(loop_start, loop_end + 1):\n'
               '            _ei = _t + 1 + sig_lag\n            if _ei <= loop_end:\n                exec_map.setdefault(_ei, _t)')
    src = _once(LOOPEND, LOOPEND + execmap)
    eval3 = ('        desired = mode\n'
             '        _reg_sh = 0.0\n'
             '        if _USE_REGEVAL and inp_b is not None and shadow_c is not None:\n'
             '            for _ree in (shadow_a, shadow_b, shadow_c):\n'
             '                _rsv9 = _rs_sharpe(_ree, sig_i)\n'
             '                if _rsv9 is not None and abs(_rsv9) > abs(_reg_sh):\n'
             '                    _reg_sh = _rsv9\n'
             '        _eval_daily = (evalfreq == \'daily\') or (_USE_REGEVAL and abs(_reg_sh) >= _REGIME_EVAL_TH)\n'
             '        if lock_mode is None and inp_b is not None and ((sig_i in sig_a) or _eval_daily):\n'
             '            if _USE_DECAY:\n'
             '                ra = _rs_w(shadow_a, sig_i)\n'
             '                rb = _rs_w(shadow_b, sig_i)\n'
             '                rc = _rs_w(shadow_c, sig_i) if shadow_c is not None else None\n'
             '            else:\n'
             '                ra = _rs(shadow_a, sig_i)\n'
             '                rb = _rs(shadow_b, sig_i)\n'
             '                rc = _rs(shadow_c, sig_i) if shadow_c is not None else None\n'
             '            if rc is None and shadow_c is None:\n'
             + textwrap.indent(_EVAL_INNER, '    ') + '\n'
             '            else:\n'
             + textwrap.indent(_THREEWAY, '    '))
    _HL = rs_decay_hl
    _USE = _HL is not None
    _RG = rg_mult
    _RG_ON = _RG is not None
    _RG_TH = rg_thresh
    _RG_M = _RG if _RG_ON else 1.0
    _RSW_SRC = '    def _rs_w(eq_s, s_idx):\n        if eq_s is None:\n            return None\n        j = int(eq_s.index.searchsorted(dates[s_idx], side="right") - 1)\n        if j < rs_lookback:\n            return None\n        _rr = eq_s.pct_change().iloc[j - rs_lookback + 1:j + 1]\n        _wsum = 0.0\n        _acc = 0.0\n        for _k, _rv in enumerate(_rr.fillna(0.0)):\n            _w = 0.5 ** ((rs_lookback - 1 - _k) / _RS_HL)\n            _acc += _w * float(_rv)\n            _wsum += _w\n        if _wsum <= 0:\n            return None\n        return float(_acc / _wsum * rs_lookback)'
    src = _once('    def board_limit(code: str) -> float:', '    _RS_HL = ' + repr(_HL) + '\n    _USE_DECAY = ' + repr(_USE) + '\n' + _RSW_SRC + '\n    _USE_REGIME = ' + repr(_RG_ON) + '\n    _REGIME_THRESH = ' + repr(_RG_TH) + '\n    _REGIME_MULT = ' + repr(_RG_M) + '\n' + _RSHARPE_SRC + '\n    _USE_REGEVAL = ' + repr(_RG_EVON) + '\n    _REGIME_EVAL_TH = ' + repr(_RG_EVTH) + '\n    def board_limit(code: str) -> float:')
    src = _once(EVAL_OLD, eval3)
    src = _once(SWLOG, SWLOG + '\n            _last_switch_i = sig_i\n            _confirm_count = 0')
    src = _once('    grid_b = []\n    if inp_b is not None:\n        grid_b = inp_b.grid(cfg_b["rebal"], phase, legacy=legacy_grid)\n        grid_b = [i for i in grid_b if dates[i] >= run_ts]',
                '    grid_b = []\n    if inp_b is not None:\n        grid_b = inp_b.grid(cfg_b["rebal"], phase, legacy=legacy_grid)\n        grid_b = [i for i in grid_b if dates[i] >= run_ts]\n    grid_c = []\n    if inp_c is not None:\n        assert cfg_c is not None, "inp_c needs cfg_c"\n        grid_c = inp_c.grid(cfg_c["rebal"], phase, legacy=legacy_grid)\n        grid_c = [i for i in grid_c if dates[i] >= run_ts]')
    src = _once('    sig_a, sig_b = set(grid), set(grid_b)', '    sig_a, sig_b = set(grid), set(grid_b)\n    sig_c = set(grid_c)')
    src = _once('    for i in grid + grid_b:', '    for i in grid + grid_b + grid_c:')
    src = _once('    mode = lock_mode or "A"  # switch_log 记的是信号日 sig_day, 实际成交在 sig_day+1, 按日期统计切换频率时注意偏移 1 日\n    state_take = take if mode == "A" else cfg_b["take"]\n    _stop_b = stop if stop_b is None else stop_b\n    state_stop = stop if mode == "A" else _stop_b  # A 腿恒用 stop, B 腿用 stop_b(默认=stop)\n    state_n = n if mode == "A" else cfg_b["n"]\n    state_exposure = exposure if mode == "A" else cfg_b["exposure"]',
                '    mode = lock_mode or "A"  # switch_log 记的是信号日 sig_day, 实际成交在 sig_day+1, 按日期统计切换频率时注意偏移 1 日\n    _stop_b = stop if stop_b is None else stop_b\n    _stop_c = stop if stop_c is None else stop_c\n    _cfgm0 = cfg_b if mode == "B" else (cfg_c if mode == "C" else None)\n    state_take = take if mode == "A" else _cfgm0["take"]\n    state_stop = stop if mode == "A" else (_stop_b if mode == "B" else _stop_c)  # A 腿恒用 stop, B 腿用 stop_b(默认=stop), C 腿用 stop_c(默认=stop)\n    state_n = n if mode == "A" else _cfgm0["n"]\n    state_exposure = exposure if mode == "A" else _cfgm0["exposure"]')
    src = _once('        on_grid = (sig_i in sig_a) if desired == "A" else (sig_i in sig_b)', '        on_grid = (sig_i in sig_a) if desired == "A" else ((sig_i in sig_b) if desired == "B" else (sig_i in sig_c))')
    src = _once('            state_take = take if mode == "A" else cfg_b["take"]\n            state_stop = stop if mode == "A" else _stop_b\n            state_n = n if mode == "A" else cfg_b["n"]\n            state_exposure = exposure if mode == "A" else cfg_b["exposure"]',
                '            _cfgm = cfg_b if mode == "B" else cfg_c\n            state_take = take if mode == "A" else _cfgm["take"]\n            state_stop = stop if mode == "A" else (_stop_b if mode == "B" else _stop_c)\n            state_n = n if mode == "A" else _cfgm["n"]\n            state_exposure = exposure if mode == "A" else _cfgm["exposure"]')
    src = _once('        inp_cur = inp if mode == "A" else inp_b', '        inp_cur = inp if mode == "A" else (inp_b if mode == "B" else inp_c)')
    ns = {}
    exec(compile(src, 'switch_engine_C2_3leg', 'exec'), ns)
    return ns