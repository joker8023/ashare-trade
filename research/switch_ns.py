#!/usr/bin/env python3
"""switch_ns: 切换引擎命名空间构造的唯一实现 (canonical build_ns).

语义说明 (经核对, 非 bug, 故不改引擎语义, 只留档):
- brake: brake_eval 用调仓前权益 tb_eq_pre 判断, peak 更新(FF 钩子)用调仓后权益.
  调仓后权益 = 调仓前 - 买卖费用, 恒更小, 故调仓日 FF 更新恒不触发;
  peak 实际由非调仓日的日终盯市权益推进. 两者皆为真实权益观测, 无偏差.
- exec 新 ns 时 `from prior_check import *` 走 sys.modules 缓存只做名字绑定,
  不重跑模块体 (除非 prior_check 尚未被 import, 属正常一次性导入).
"""
import json
import os
import sys
import textwrap
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))

AA = "    switch_log: List[Tuple[str, str]] = []"
BB = "        nonlocal cash, total_cost, mode, state_take, state_n, state_exposure, state_stop"
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
EVAL_NEW = ("        desired = mode\n"
            "        _eval_daily = (evalfreq == 'daily')\n"
            "        if lock_mode is None and inp_b is not None and ((sig_i in sig_a) or _eval_daily):\n"
            "            ra = _rs(shadow_a, sig_i)\n"
            "            rb = _rs(shadow_b, sig_i)\n"
            "            if ra is not None and rb is not None:\n"
            "                if mode == 'A':\n"
            "                    _raw = 'B' if rb - ra >= _HYST else 'A'\n"
            "                else:\n"
            "                    _raw = 'A' if ra - rb >= _HYST else 'B'\n"
            "                if _raw == mode:\n"
            "                    _confirm_count = 0\n"
            "                elif (sig_i - _last_switch_i) < _MIN_HOLD:\n"
            "                    _confirm_count = 0  # min_hold持有期内不累积确认, 确认只计持有期满后的连续信号\n"
            "                else:\n"
            "                    _confirm_count += 1\n"
            "                    if _confirm_count >= _CONFIRM:\n"
            "                        desired = _raw")
SWLOG = "            switch_log.append((str(sig_day.date()), mode))"


def build_ns(bx=0.18, by_=0.08, bf=0.6, hyst=0.0, min_hold=0, confirm=1):
    assert bf > 0, 'bf=0 + full_liquidate deadlocks (verified stage1)'
    src = (ROOT / 'research' / 'switch_engine.py').read_text()
    def _once(old, new):
        assert src.count(old) == 1, (old[:60], src.count(old))
        return src.replace(old, new)
    add = ('\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n'
           '    _brake_log: List = []\n    _BRAKE_X = %s\n    _BRAKE_Y = %s\n'
           '    _BRAKE_F = %s\n    _HYST = %s\n    _MIN_HOLD = %d\n    _CONFIRM = %d\n'
           '    _confirm_count = 0\n    _last_switch_i = -1000000000' % (bx, by_, bf, hyst, min_hold, confirm))
    src = _once(AA, AA + add)
    src = _once(BB, BB + ', _brake, _brake_trough, _brake_peak, _brake_log, _confirm_count, _last_switch_i')
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
    brake_gated = ('\n        _brake_gate = brake_daily or (sig_i in sig_a) or (sig_i in sig_b)\n'
                   '        if _brake_gate:' + textwrap.indent(brake_eval, '    '))
    src = _once(CC, CC + brake_gated)
    skip_block = '\n        if not switching and set(picks) == set(pos):\n            return False'
    src = _once(DD, DD + skip_block)
    src = _once(PICKLINE, '        _ex = (exclude_a if mode == \'A\' else exclude_b) if (exclude_a is not None or exclude_b is not None) else exclude\n' + PICKLINE.replace('exclude=exclude', 'exclude=_ex'))
    src = _once(SIG, SIG + '\n    exclude_a=None,\n    exclude_b=None,')
    src = _once(SIG + '\n    exclude_a=None,\n    exclude_b=None,',
                SIG + '\n    exclude_a=None,\n    exclude_b=None,\n    evalfreq=\'grid\',\n    brake_daily=False,')
    src = _once(EE, '        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n' + EE)
    src = _once(FF, FF + '\n        if (cash + mv) > _brake_peak:\n            _brake_peak = cash + mv')
    src = _once(GG, '        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode, brake_log=_brake_log,')
    execmap = ('\n    if evalfreq == \'daily\':\n        for _t in range(loop_start, loop_end + 1):\n'
               '            _ei = _t + 1 + sig_lag\n            if _ei <= loop_end:\n                exec_map.setdefault(_ei, _t)')
    src = _once(LOOPEND, LOOPEND + execmap)
    src = _once(EVAL_OLD, EVAL_NEW)
    src = _once(SWLOG, SWLOG + '\n            _last_switch_i = sig_i\n            _confirm_count = 0')
    ns = {}
    exec(compile(src, 'switch_engine_C2', 'exec'), ns)
    return ns


def atomic_write_json(path, obj):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1))
    os.replace(tmp, path)


_ENGINE_SRC = (ROOT / 'research' / 'switch_engine.py').read_text()
assert _ENGINE_SRC.count(EVAL_OLD) == 1, 'EVAL_OLD parity broken vs switch_engine.py'
assert '(sig_i - _last_switch_i) < _MIN_HOLD' in EVAL_NEW, 'EVAL_NEW must carry min_hold guard'
assert 'take_sells' in _ENGINE_SRC, 'switch_engine must count take_sells'
del _ENGINE_SRC
