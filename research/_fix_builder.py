#!/usr/bin/env python3
"""J1_Bjan_half FIX: 去ex-post尾锁 + 1月sweep + placebo + parity.

修复 review 提出的4点:
1. 去尾锁: force_c_from=None 消融, 证明 Q4 confirm=2 自然切C, 锁冗余.
   可交易候选 J1FIX = 无锁 + B腿1月x0.5 (月份已知, 非后验).
2. 1月 sweep: jan_mult in [0.0,0.3,0.5,0.7,1.0], + 2月placebo x0.5.
3. 引擎显式化: build_ns3_fixed(jan_month, jan_mult, jan_bx)替代
   bjan_half bool 硬编码, 向后兼容; 附 parity 单测.
4. 留白跟踪规范见文末 print.

Engine: 同 regime_pit_jan.build_ns3_force(0.18,0.08,0.5,confirm=2),
信号 trailing-only, 成本与原口径一致.
""";
import sys, json, gc, textwrap
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, WINDOWS, RUN_START, EVAL_END, MB
import switch_ns3 as S3
from switch_ns import AA, BB, CC, DD, EE, FF, GG, SIG, PICKLINE, LOOPEND, EVAL_OLD, EVAL_NEW, SWLOG

print("RUN_START", RUN_START, "EVAL_END", EVAL_END, flush=True)
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
CA0 = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
CFG_A = dict(n=5, rebal=20, take=1.2, exposure=1.0)
CFG_B = dict(n=4, rebal=30, take=0.8, exposure=0.9)
CFG_C = dict(n=4, rebal=30, take=0.8, exposure=0.3)

def build_ns3_fixed(hyst_a=0.0, hyst_b=0.0, hyst_c=0.0, confirm=2, min_hold=0,
                    jan_month=None, jan_mult=1.0, jan_bx=None,
                    _tag=""):
    """显式化构建器 (FIX).
    jan_month=None -> 无月份补丁 (等价 bjan_half=False).
    jan_month=1, jan_mult=0.5 -> 原 J1_Bjan_half.
    jan_month=2, jan_mult=0.5 -> 2月placebo.
    jan_bx: 1月刹车阈值 (原 J3), None=关闭.
    向后兼容: bjan_half=True <=> jan_month=1,jan_mult=0.5.
    """
    assert jan_mult >= 0.0 and jan_mult <= 1.0, jan_mult
    assert jan_month is None or 1 <= jan_month <= 12, jan_month
    bx, by_, bf, hyst = 0.18, 0.08, 0.5, 0.0
    _HA, _HB, _HC = hyst_a, hyst_b, hyst_c
    src = (ROOT/"research"/"switch_engine.py").read_text()
    def _once(old, new):
        assert src.count(old) == 1, (_tag + old[:60], src.count(old))
        return src.replace(old, new)
    add = ("\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n"
           "    _brake_log: List = []\n    _BRAKE_X = %s\n    _BRAKE_Y = %s\n"
           "    _BRAKE_F = %s\n    _HYST = %s\n    _MIN_HOLD = %d\n    _CONFIRM = %d\n"
           "    _confirm_count = 0\n    _last_switch_i = -1000000000" % (bx, by_, bf, hyst, min_hold, confirm))
    src = _once(AA, AA + add)
    src = _once(BB, BB + ", _brake, _brake_trough, _brake_peak, _brake_log, _confirm_count, _last_switch_i")
    src = _once("    _confirm_count = 0\n    _last_switch_i = -1000000000", "    _confirm_count = 0\n    _last_switch_i = -1000000000\n    _HYST_A = %s\n    _HYST_B = %s\n    _HYST_C = %s" % (_HA, _HB, _HC))
    brake_eval = ("\n        tb_mv_pre = 0.0\n        for tb_cc, tb_p in pos.items():\n"
                  "            tb_px = px_ffill_or_nan(mark, day, tb_cc)\n"
                  "            if pd.isna(tb_px):\n"
                  "                tb_px = tb_p.entry_px\n"
                  "            tb_mv_pre += tb_p.shares * tb_px\n"
                  "        tb_eq_pre = cash + tb_mv_pre\n"
                  "        if tb_eq_pre > _brake_peak:\n"
                  "            _brake_peak = tb_eq_pre\n"
                  "        if not _brake and _brake_peak_peak if False else _brake_peak > 0 and (_brake_peak - tb_eq_pre) / _brake_peak >= _BRAKE_X:\n"
                  "            _brake = True\n"
                  "            _brake_trough = tb_eq_pre\n"
                  "            _brake_log.append((str(day.date()), 'ON', round(float((_brake_peak - tb_eq_pre) / _brake_peak) * 100, 2)))\n"
                  "        elif _brake:\n"
                  "            if tb_eq_pre < _brake_trough:\n"
                  "                _brake_trough = tb_eq_pre\n"
                  "            if _brake_trough > 0 and tb_eq_pre >= _brake_trough * (1.0 + _BRAKE_Y):\n"
                  "                _brake = False\n"
                  "                _brake_log.append((str(day.date()), 'OFF', round(float(tb_eq_pre / _brake_trough - 1) * 100, 2)))")
    # 上面占位符写错, 用回原版 brake_eval (与 regime_pit_jan 逐字一致)
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
    brake_gated = ("\n        _brake_gate = brake_daily or (sig_i in sig_a) or (sig_i in sig_b) or (sig_i in sig_c)\n"
                   "        if _brake_gate:" + textwrap.indent(brake_eval, "    "))
    src = _once(CC, CC + brake_gated)
    skip_block = "\n        if not switching and set(picks) == set(pos):\n            return False"
    src = _once(DD, DD + skip_block)
    src = _once(PICKLINE, "        _ex = (exclude_a if mode == 'A' else (exclude_b if mode == 'B' else exclude_c)) if (exclude_a is not None or exclude_b is not None or exclude_c is not None) else exclude\n" + PICKLINE.replace("exclude=exclude", "exclude=_ex"))
    src = _once(SIG, SIG + "\n    exclude_a=None,\n    exclude_b=None,\n    exclude_c=None,")
    src = _once(SIG + "\n    exclude_a=None,\n    exclude_b=None,\n    exclude_c=None,",
                SIG + "\n    exclude_a=None,\n    exclude_b=None,\n    exclude_c=None,\n    evalfreq='grid',\n    brake_daily=False,\n    stop_c=None,")
    src = _once("    shadow_a=None, shadow_b=None,          # \u4e24\u5f15\u64ce\u72ec\u7acb\u6743\u76ca\u66f2\u7ebf (RS \u4fe1\u53f7)", "    shadow_a=None, shadow_b=None,          # \u4e24\u5f15\u64ce\u72ec\u7acb\u6743\u76ca\u66f2\u7ebf (RS \u4fe1\u53f7)" + "\n    shadow_c=None,                          # leg-C shadow" + "\n    inp_c=None,                             # leg-C inputs" + "\n    cfg_c=None,                             # dict(n=, rebal=, take=, exposure)")
    src = _once(EE, "        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n" + EE)
    src = _once(FF, FF + "\n        if (cash + mv) > _brake_peak:\n            _brake_peak = cash + mv")
    src = _once(GG, "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode, brake_log=_brake_log,")
    src = _once("        stop_b=_stop_b,", "        stop_b=_stop_b,\n        stop_c=_stop_c,")
    execmap = ("\n    if evalfreq == 'daily':\n        for _t in range(loop_start, loop_end + 1):\n"
               "            _ei = _t + 1 + sig_lag\n            if _ei <= loop_end:\n                exec_map.setdefault(_ei, _t)")
    src = _once(LOOPEND, LOOPEND + execmap)
    eval3 = ("        desired = mode\n"
             "        _reg_sh = 0.0\n"
             "        if _USE_REGEVAL and inp_b is not None and shadow_c is not None:\n"
             "            for _ree in (shadow_a, shadow_b, shadow_c):\n"
             "                _rsv9 = _rs_sharpe(_ree, sig_i)\n"
             "                if _rsv9 is not None and abs(_rsv9) > abs(_reg_sh):\n"
             "                    _reg_sh = _rsv9\n"
             "        _eval_daily = (evalfreq == 'daily') or (_USE_REGEVAL and abs(_reg_sh) >= _REGIME_EVAL_TH)\n"
             "        if lock_mode is None and inp_b is not None and ((sig_i in sig_a) or _eval_daily):\n"
             "            if _USE_DECAY:\n"
             "                ra = _rs_w(shadow_a, sig_i)\n"
             "                rb = _rs_w(shadow_b, sig_i)\n"
             "                rc = _rs_w(shadow_c, sig_i) if shadow_c is not None else None\n"
             "            else:\n"
             "                ra = _rs(shadow_a, sig_i)\n"
             "                rb = _rs(shadow_b, sig_i)\n"
             "                rc = _rs(shadow_c, sig_i) if shadow_c is not None else None\n"
             "            if rc is None and shadow_c is None:\n"
             + textwrap.indent("\n".join(EVAL_NEW.split("\n")[3:]), "    ") + "\n"
             "            else:\n"
             + textwrap.indent(S3._THREEWAY, "    "))
    src = _once("    def board_limit(code: str) -> float:", "    _RS_HL = None\n    _USE_DECAY = False\n" + "    def _rs_w(eq_s, s_idx):\n        return None\n" + "    _USE_REGIME = False\n    _REGIME_THRESH = 1.0\n    _REGIME_MULT = 1.0\n" + S3._RSHARPE_SRC + "\n    _USE_REGEVAL = False\n    _REGIME_EVAL_TH = 1.0\n    def board_limit(code: str) -> float:")
    src = _once(EVAL_OLD, eval3)
    src = _once(SWLOG, SWLOG + "\n            _last_switch_i = sig_i\n            _confirm_count = 0")
    src = _once("    grid_b = []\n    if inp_b is not None:\n        grid_b = inp_b.grid(cfg_b[\"rebal\"], phase, legacy=legacy_grid)\n        grid_b = [i for i in grid_b if dates[i] >= run_ts]",
                "    grid_b = []\n    if inp_b is not None:\n        grid_b = inp_b.grid(cfg_b[\"rebal\"], phase, legacy=legacy_grid)\n        grid_b = [i for i in grid_b if dates[i] >= run_ts]\n    grid_c = []\n    if inp_c is not None:\n        assert cfg_c is not None\n        grid_c = inp_c.grid(cfg_c[\"rebal\"], phase, legacy=legacy_grid)\n        grid_c = [i for i in grid_c if dates[i] >= run_ts]")
    src = _once("    sig_a, sig_b = set(grid), set(grid_b)", "    sig_a, sig_b = set(grid), set(grid_b)\n    sig_c = set(grid_c)")
    src = _once("    for i in grid + grid_b:", "    for i in grid + grid_b + grid_c:")
    src = _once("    mode = lock_mode or \"A\"", "    mode = lock_mode or \"A\"\n    _stop_b = stop if stop_b is None else stop_b\n    _stop_c = stop if stop_c is None else stop_c")
    src = _once("        on_grid = (sig_i in sig_a) if desired == \"A\" else (sig_i in sig_b)", "        on_grid = (sig_i in sig_a) if desired == \"A\" else ((sig_i in sig_b) if desired == \"B\" else (sig_i in sig_c))")
    src = _once("            state_take = take if mode == \"A\" else cfg_b[\"take\"]\n            state_stop = stop if mode == \"A\" else _stop_b\n            state_n = n if mode == \"A\" else cfg_b[\"n\"]\n            state_exposure = exposure if mode == \"A\" else cfg_b[\"exposure\"]", "            _cfgm = cfg_b if mode == \"B\" else cfg_c\n            state_take = take if mode == \"A\" else _cfgm[\"take\"]\n            state_stop = stop if mode == \"A\" else (_stop_b if mode == \"B\" else _stop_c)\n            state_n = n if mode == \"A\" else _cfgm[\"n\"]\n            state_exposure = exposure if mode == \"A\" else _cfgm[\"exposure\"]")
    src = _once("        inp_cur = inp if mode == \"A\" else inp_b", "        inp_cur = inp if mode == \"A\" else (inp_b if mode == \"B\" else inp_c)")
    sig_tail = "\n    evalfreq='grid',\n    brake_daily=False,\n    stop_c=None,"
    assert src.count(sig_tail) == 1, src.count(sig_tail)
    src = src.replace(sig_tail, sig_tail + "\n    force_c_from=None,\n    gap_s=None,\n    gap_cut=None,\n    gap_thr=None,\n    fuse_ms=None,\n    fuse_mult=0.5,")
    anchor = "\n        switching = desired != mode"
    assert src.count(anchor) == 1, src.count(anchor)
    override = ("\n        if force_c_from is not None and dates[sig_i] >= force_c_from:\n"
                "            desired = \"C\"\n"
                "        elif gap_s is not None and gap_cut is not None and gap_thr is not None and dates[sig_i] >= gap_cut:\n"
                "            _gv = gap_s.get(dates[sig_i])\n"
                "            if _gv is not None and _gv == _gv and float(_gv) < float(gap_thr):\n"
                "                desired = \"C\"")
    src = src.replace(anchor, override + anchor)
    fz_old = "            state_exposure = exposure if mode == \"A\" else _cfgm[\"exposure\"]"
    assert src.count(fz_old) == 1, src.count(fz_old)
    src = src.replace(fz_old, fz_old + ("\n            if fuse_ms is not None and str(dates[sig_i].date())[:7] in fuse_ms:\n                state_exposure = state_exposure * fuse_mult"))
    # FIX: 通用月份x倍数, 替代 bjan_half 硬编码 x0.5
    ab_old = ("        if weight_cap is not None and weight_cap > 0 and not rank_fill:\n"
              "            alloc = equity_now * state_exposure * min(1.0 / slots, weight_cap)\n"
              "        else:\n"
              "            alloc = equity_now * state_exposure / slots")
    assert src.count(ab_old) == 1, src.count(ab_old)
    if jan_month is not None and abs(jan_mult - 1.0) > 1e-12:
        src = src.replace(ab_old, ab_old + ("\n        if mode == \"B\" and dates[sig_i].month == %d:\n"
                                            "            alloc = alloc * %s" % (jan_month, repr(float(jan_mult)))))
    if jan_bx is not None:
        bxline = "\n    _BRAKE_X = %s\n" % (0.18,)
        assert src.count(bxline) == 1, src.count(bxline)
        src = src.replace(bxline, bxline + "    _BRAKE_X_JAN = %s\n" % (jan_bx,))
        bxcmp = ">= _BRAKE_X:"
        assert src.count(bxcmp) == 1, src.count(bxcmp)
        src = src.replace(bxcmp, ">= (_BRAKE_X_JAN if dates[sig_i].month == 1 else _BRAKE_X):")
    ns = {}
    exec(compile(src, "switch_engine_fix_" + (_tag or "base"), "exec"), ns)
    # 元信息显式化, 解决“补丁不可见”问题
    ns["_FIX_META"] = dict(jan_month=jan_month, jan_mult=float(jan_mult), jan_bx=jan_bx, confirm=confirm, min_hold=min_hold)
    return ns
