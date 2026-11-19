#!/usr/bin/env python3
"""T40E valid repro: E18 single-run reproduce (identical logic to research/t40e_24.py)."""
import sys, json, gc, time
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/"team"/"audit"))
sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import _mdd, EVAL_END, MB
from switch_ns import AA, BB, CC, DD, EE, FF, GG, SIG, PICKLINE, LOOPEND, EVAL_OLD, EVAL_NEW, SWLOG
from switch_ns3 import build_ns3
import switch_ns3 as S3
import textwrap
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
RUN_START = str(dates[0].date())
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
print("RUN_START=%s first_sig=%s EVAL_END=%s bars=%d" % (RUN_START, first_sig.date(), EVAL_END, len(dates)), flush=True)
_MOM_TAIL = "\n            _MX = {}\n            for _mmx, _eqx in ((\"A\", shadow_a), (\"B\", shadow_b), (\"C\", shadow_c)):\n                if _eqx is None:\n                    _MX[_mmx] = None\n                else:\n                    _jx = int(_eqx.index.searchsorted(dates[sig_i], side=\"right\") - 1)\n                    if _jx >= _MOM_LB:\n                        _MX[_mmx] = float(_eqx.iloc[_jx] / _eqx.iloc[_jx - _MOM_LB] - 1.0)\n                    else:\n                        _MX[_mmx] = None\n            _mom_best = None\n            _mom_bestv = None\n            for _mmx in _MOM_LEGS:\n                _vx = _MX.get(_mmx)\n                if _vx is not None and _vx >= _MOM_TH and (_mom_bestv is None or _vx > _mom_bestv):\n                    _mom_best = _mmx\n                    _mom_bestv = _vx\n            if _mom_best is not None and _mom_best != mode and (sig_i - _last_switch_i) >= _MIN_HOLD:\n                desired = _mom_best\n                _confirm_count = 0"
def build_ns3x(bx=0.18, by_=0.08, bf=0.6, hyst=0.0, min_hold=0, confirm=1, hyst_a=None, hyst_b=None, hyst_c=None, rs_decay_hl=None, rg_mult=None, rg_thresh=1.0, rg_eval_th=None, mom_lb=30, mom_thresh=None, mom_legs=("C",)):
    assert bf > 0
    src = (ROOT/"research"/"switch_engine.py").read_text()
    _HA = hyst if hyst_a is None else hyst_a
    _HB = hyst if hyst_b is None else hyst_b
    _HC = hyst if hyst_c is None else hyst_c
    def _once(old, new):
        assert src.count(old) == 1, (old[:60], src.count(old))
        return src.replace(old, new)
    add = "\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n    _brake_log: List = []\n    _BRAKE_X = %s\n    _BRAKE_Y = %s\n    _BRAKE_F = %s\n    _HYST = %s\n    _MIN_HOLD = %d\n    _CONFIRM = %d\n    _confirm_count = 0\n    _last_switch_i = -1000000000" % (bx, by_, bf, hyst, min_hold, confirm)
    src = _once(AA, AA + add)
    src = _once(BB, BB + ", _brake, _brake_trough, _brake_peak, _brake_log, _confirm_count, _last_switch_i")
    src = _once("    _confirm_count = 0\n    _last_switch_i = -1000000000", "    _confirm_count = 0\n    _last_switch_i = -1000000000\n    _HYST_A = %s\n    _HYST_B = %s\n    _HYST_C = %s" % (_HA, _HB, _HC))
    brake_eval = "\n        tb_mv_pre = 0.0\n        for tb_cc, tb_p in pos.items():\n            tb_px = px_ffill_or_nan(mark, day, tb_cc)\n            if pd.isna(tb_px):\n                tb_px = tb_p.entry_px\n            tb_mv_pre += tb_p.shares * tb_px\n        tb_eq_pre = cash + tb_mv_pre\n        if tb_eq_pre > _brake_peak:\n            _brake_peak = tb_eq_pre\n        if not _brake and _brake_peak > 0 and (_brake_peak - tb_eq_pre) / _brake_peak >= _BRAKE_X:\n            _brake = True\n            _brake_trough = tb_eq_pre\n            _brake_log.append((str(day.date()), 'ON', round(float((_brake_peak - tb_eq_pre) / _brake_peak) * 100, 2)))\n        elif _brake:\n            if tb_eq_pre < _brake_trough:\n                _brake_trough = tb_eq_pre\n            if _brake_trough > 0 and tb_eq_pre >= _brake_trough * (1.0 + _BRAKE_Y):\n                _brake = False\n                _brake_log.append((str(day.date()), 'OFF', round(float(tb_eq_pre / _brake_trough - 1) * 100, 2)))"
    brake_gated = "\n        _brake_gate = brake_daily or (sig_i in sig_a) or (sig_i in sig_b) or (sig_i in sig_c)\n        if _brake_gate:" + textwrap.indent(brake_eval, "    ")
    src = _once(CC, CC + brake_gated)
    src = _once(DD, DD + "\n        if not switching and set(picks) == set(pos):\n            return False")
    src = _once(PICKLINE, "        _ex = (exclude_a if mode == 'A' else (exclude_b if mode == 'B' else exclude_c)) if (exclude_a is not None or exclude_b is not None or exclude_c is not None) else exclude\n" + PICKLINE.replace("exclude=exclude", "exclude=_ex"))
    src = _once(SIG, SIG + "\n    exclude_a=None,\n    exclude_b=None,\n    exclude_c=None,")
    src = _once(SIG + "\n    exclude_a=None,\n    exclude_b=None,\n    exclude_c=None,", SIG + "\n    exclude_a=None,\n    exclude_b=None,\n    exclude_c=None,\n    evalfreq='grid',\n    brake_daily=False,\n    stop_c=None,")
    src = _once("    shadow_a=None, shadow_b=None,", "    shadow_a=None, shadow_b=None,\n    shadow_c=None,\n    inp_c=None,\n    cfg_c=None,")
    src = _once(EE, "        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n" + EE)
    src = _once(FF, FF + "\n        if (cash + mv) > _brake_peak:\n            _brake_peak = cash + mv")
    src = _once(GG, "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode, brake_log=_brake_log,")
    src = _once("        stop_b=_stop_b,", "        stop_b=_stop_b,\n        stop_c=_stop_c,")
    _RG_EVON = rg_eval_th is not None
    _EXEC_EXTRA = " or True" if _RG_EVON else ""
    execmap = "\n    if evalfreq == 'daily'" + _EXEC_EXTRA + ":\n        for _t in range(loop_start, loop_end + 1):\n            _ei = _t + 1 + sig_lag\n            if _ei <= loop_end:\n                exec_map.setdefault(_ei, _t)"
    src = _once(LOOPEND, LOOPEND + execmap)
    threeway = S3._THREEWAY + (_MOM_TAIL if mom_thresh is not None else "")
    eval3 = ("        desired = mode\n        _reg_sh = 0.0\n        if _USE_REGEVAL and inp_b is not None and shadow_c is not None:\n            for _ree in (shadow_a, shadow_b, shadow_c):\n                _rsv9 = _rs_sharpe(_ree, sig_i)\n                if _rsv9 is not None and abs(_rsv9) > abs(_reg_sh):\n                    _reg_sh = _rsv9\n        _eval_daily = (evalfreq == 'daily') or (_USE_REGEVAL and abs(_reg_sh) >= _REGIME_EVAL_TH)\n        if lock_mode is None and inp_b is not None and ((sig_i in sig_a) or _eval_daily):\n            if _USE_DECAY:\n                ra = _rs_w(shadow_a, sig_i)\n                rb = _rs_w(shadow_b, sig_i)\n                rc = _rs_w(shadow_c, sig_i) if shadow_c is not None else None\n            else:\n                ra = _rs(shadow_a, sig_i)\n                rb = _rs(shadow_b, sig_i)\n                rc = _rs(shadow_c, sig_i) if shadow_c is not None else None\n            if rc is None and shadow_c is None:\n" + textwrap.indent("\n".join(EVAL_NEW.split("\n")[3:]), "    ") + "\n            else:\n" + textwrap.indent(threeway, "    "))
    _RSW_SRC = "    def _rs_w(eq_s, s_idx):\n        if eq_s is None:\n            return None\n        j = int(eq_s.index.searchsorted(dates[s_idx], side=\"right\") - 1)\n        if j < rs_lookback:\n            return None\n        _rr = eq_s.pct_change().iloc[j - rs_lookback + 1:j + 1]\n        _wsum = 0.0\n        _acc = 0.0\n        for _k, _rv in enumerate(_rr.fillna(0.0)):\n            _w = 0.5 ** ((rs_lookback - 1 - _k) / _RS_HL)\n            _acc += _w * float(_rv)\n            _wsum += _w\n        if _wsum <= 0:\n            return None\n        return float(_acc / _wsum * rs_lookback)"
    mom_const = "\n    _MOM_LB = %r\n    _MOM_TH = %r\n    _MOM_LEGS = %r" % (mom_lb, mom_thresh if mom_thresh is not None else 0.0, tuple(mom_legs))
    src = _once("    def board_limit(code: str) -> float:", "    _RS_HL = " + repr(rs_decay_hl) + "\n    _USE_DECAY = " + repr(rs_decay_hl is not None) + "\n" + _RSW_SRC + "\n    _USE_REGIME = " + repr(rg_mult is not None) + "\n    _REGIME_THRESH = " + repr(rg_thresh) + "\n    _REGIME_MULT = " + repr(rg_mult if rg_mult is not None else 1.0) + "\n" + S3._RSHARPE_SRC + "\n    _USE_REGEVAL = " + repr(_RG_EVON) + "\n    _REGIME_EVAL_TH = " + repr(rg_eval_th if _RG_EVON else 1.0) + mom_const + "\n    def board_limit(code: str) -> float:")
    src = _once(EVAL_OLD, eval3)
    src = _once(SWLOG, SWLOG + "\n            _last_switch_i = sig_i\n            _confirm_count = 0")
    src = _once('    grid_b = []', '    grid_b = []\n    grid_c = []\n    if inp_c is not None:\n        assert cfg_c is not None\n        grid_c = inp_c.grid(cfg_c["rebal"], phase, legacy=legacy_grid)\n        grid_c = [i for i in grid_c if dates[i] >= run_ts]')
    src = _once('    sig_a, sig_b = set(grid), set(grid_b)', '    sig_a, sig_b = set(grid), set(grid_b)\n    sig_c = set(grid_c)')
    src = _once('    for i in grid + grid_b:', '    for i in grid + grid_b + grid_c:')
    src = _once('    mode = lock_mode or "A"', '    mode = lock_mode or "A"\n    _stop_b = stop if stop_b is None else stop_b\n    _stop_c = stop if stop_c is None else stop_c\n    _cfgm0 = cfg_b if mode == "B" else (cfg_c if mode == "C" else None)\n    state_take = take if mode == "A" else _cfgm0["take"]\n    state_stop = stop if mode == "A" else (_stop_b if mode == "B" else _stop_c)\n    state_n = n if mode == "A" else _cfgm0["n"]\n    state_exposure = exposure if mode == "A" else _cfgm0["exposure"]')
    src = _once('        on_grid = (sig_i in sig_a) if desired == "A" else (sig_i in sig_b)', '        on_grid = (sig_i in sig_a) if desired == "A" else ((sig_i in sig_b) if desired == "B" else (sig_i in sig_c))')
    src = _once('            state_take = take if mode == "A" else cfg_b["take"]\n            state_stop = stop if mode == "A" else _stop_b\n            state_n = n if mode == "A" else cfg_b["n"]\n            state_exposure = exposure if mode == "A" else cfg_b["exposure"]', '            _cfgm = cfg_b if mode == "B" else cfg_c\n            state_take = take if mode == "A" else _cfgm["take"]\n            state_stop = stop if mode == "A" else (_stop_b if mode == "B" else _stop_c)\n            state_n = n if mode == "A" else _cfgm["n"]\n            state_exposure = exposure if mode == "A" else _cfgm["exposure"]')
    src = _once('        inp_cur = inp if mode == "A" else inp_b', '        inp_cur = inp if mode == "A" else (inp_b if mode == "B" else inp_c)')
    _old_init = """    state_take = take if mode == "A" else cfg_b["take"]\n    _stop_b = stop if stop_b is None else stop_b\n    state_stop = stop if mode == "A" else _stop_b  # A \u817f\u6052\u7528 stop, B \u817f\u7528 stop_b(\u9ed8\u8ba4=stop)\n    state_n = n if mode == "A" else cfg_b["n"]\n    state_exposure = exposure if mode == "A" else cfg_b["exposure"]""";
    _new_init = """    _stop_b = stop if stop_b is None else stop_b\n    _stop_c = stop if stop_c is None else stop_c\n    _cfgm0 = cfg_b if mode == "B" else (cfg_c if mode == "C" else None)\n    state_take = take if mode == "A" else _cfgm0["take"]\n    state_stop = stop if mode == "A" else (_stop_b if mode == "B" else _stop_c)\n    state_n = n if mode == "A" else _cfgm0["n"]\n    state_exposure = exposure if mode == "A" else _cfgm0["exposure"]""";
    src = _once(_old_init, _new_init)
    ns = {}
    exec(compile(src, "switch_engine_C2_3leg_mom", "exec"), ns)
    return ns
def trail6(eq):
    end = eq.index[-1]
    def win(days):
        cutoff = end - pd.Timedelta(days=days)
        sub = eq[eq.index > cutoff]
        return dict(ret=round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2), mdd=round(float(_mdd(sub))*100,2), start=str(sub.index[0].date()), bars=int(len(sub)))
    return {"m1": win(31), "m3": win(93), "m6": win(182), "y1": win(365), "y2": win(730), "y3": win(1095)}
def ann_stats(eq):
    d = {}
    for y in (2021, 2022, 2023, 2024, 2025, 2026):
        sub = eq[eq.index.year == y]
        if len(sub) > 1:
            d[str(y)] = dict(ret=round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2), mdd=round(float(_mdd(sub))*100,2))
        else:
            d[str(y)] = dict(ret=None, mdd=None)
    return d
# ---- neighborhood + combo driver (all phase=0 slip=0.002), mirrors t40e_24.py ----
A3 = dict(n=3, rebal=30, take=0.8, exposure=1.0)
B6 = dict(n=6, rebal=30, take=0.8, exposure=1.0)
C4 = dict(n=4, rebal=30, take=0.8, exposure=1.0)
SLIP0 = 0.002
def CAof(slip):
    return dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=slip, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
def make_inp(sel, max_cut=0.70, use_max=True, gate60=-1.0):
    return DInputs(piv, band=(0.05,0.30), gate60=gate60, max_cut=max_cut, max_win=20, use_max=use_max, sel=sel)
_SH = {}
def shadow(sel, cfg, max_cut=0.70, use_max=True, gate60=-1.0, phase=0, slip=SLIP0):
    key = (sel, tuple(sorted(cfg.items())), max_cut, use_max, gate60, phase, slip)
    if key not in _SH:
        rb = pc.run_strategy(make_inp(sel, max_cut, use_max, gate60), phase=phase, **{**CAof(slip), **cfg})
        _SH[key] = (rb.eq.iloc[:,0] if isinstance(rb.eq, pd.DataFrame) else rb.eq, len(rb.trades))
        print("  shadow %s cut=%.2f nomax=%s ph=%d slip=%.4f trades=%d" % (sel, max_cut, (not use_max), phase, slip, len(rb.trades)), flush=True)
        del rb; gc.collect()
    return _SH[key]
def run_switch(tag, mech, sA, sB, sC, rs=90, hyst_c=0.08, hyst_a=0.005, hyst_b=0.005, mom=None, phase=0, slip=SLIP0):
    import time
    t0 = time.time()
    selA, cfgA, cutA, maxA = sA
    selB, cfgB, cutB, maxB = sB
    selC, cfgC, cutC, maxC = sC
    sha = shadow(selA, cfgA, cutA, maxA, -1.0, phase, slip)[0]
    shb = shadow(selB, cfgB, cutB, maxB, -1.0, phase, slip)[0]
    shc = shadow(selC, cfgC, cutC, maxC, -1.0, phase, slip)[0]
    ns = build_ns3x(0.12, 0.05, 0.4, 0.02, 0, 1, hyst_a=hyst_a, hyst_b=hyst_b, hyst_c=hyst_c, rg_eval_th=None, mom_lb=30, mom_thresh=(mom[1] if mom else None), mom_legs=(mom[0] if mom else ("C",)))
    inpA = make_inp(selA, cutA, maxA)
    CA = CAof(slip)
    KW = dict(n=cfgA["n"], rebal=cfgA["rebal"], take=cfgA["take"], exposure=1.0, phase=phase, inp_b=make_inp(selB, cutB, maxB), cfg_b=cfgB, inp_c=make_inp(selC, cutC, maxC), cfg_c=cfgC, shadow_a=sha, shadow_b=shb, shadow_c=shc, rs_lookback=rs, exclude_a=MB, exclude_b=MB, exclude_c=MB, evalfreq="grid", brake_daily=False, **{k: v for k, v in CA.items() if k != "exclude"})
    res = ns["run_strategy_switch"](inpA, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    ann = ann_stats(eq)
    y = {k: ann[k]["ret"] for k in ("2022","2023","2024","2025","2026")}
    ok5 = all(v is not None and v > 60 for v in y.values()) and row_mdd_ok(round(float(_mdd(eq))*100,2))
    row = dict(tag=tag, mech=mech, rs=rs, hyst_c=hyst_c, hyst_a=hyst_a, hyst_b=hyst_b, mom=(dict(legs=list(mom[0]), lb=30, thresh=mom[1]) if mom else None), phase=phase, slip=slip, total=round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), mdd=round(float(_mdd(eq))*100,2), ann=ann, trail=trail6(eq), switches=len(res.meta["switch_log"]), trades=int(len(res.trades)), cost=round(float(res.meta["total_cost"]),0), mode=res.meta["final_mode"], secs=round(time.time()-t0,1), five_over_60=bool(ok5), switch_log=[[d, m] for d, m in res.meta["switch_log"]])
    del res; gc.collect()
    return row
def row_mdd_ok(mdd):
    return mdd is not None and mdd > -20
LA = ("c_a60_vol", A3, 0.70, True)
LB = ("c_a60_turn", B6, 0.70, True)
LC0 = ("amihud_5", C4, 0.70, True)
PLAN = [
    dict(tag="N1_momC12", mech="nbr: mom C>=12%", sA=LA, sB=LB, sC=LC0, mom=(("C",), 0.12)),
    dict(tag="N2_momC18", mech="nbr: mom C>=18%", sA=LA, sB=LB, sC=LC0, mom=(("C",), 0.18)),
    dict(tag="N3_momC15ha001", mech="nbr: momC15 + ha0.01", sA=LA, sB=LB, sC=LC0, mom=(("C",), 0.15), hyst_a=0.01, hyst_b=0.01),
    dict(tag="N4_momC15ha002", mech="nbr: momC15 + ha0.02", sA=LA, sB=LB, sC=LC0, mom=(("C",), 0.15), hyst_a=0.02, hyst_b=0.02),
    dict(tag="C1_momC15rs60", mech="combo: momC15 x RS60", sA=LA, sB=LB, sC=LC0, mom=(("C",), 0.15), rs=60),
    dict(tag="C2_momC15rs120", mech="combo: momC15 x RS120", sA=LA, sB=LB, sC=LC0, mom=(("C",), 0.15), rs=120),
    dict(tag="C3_momC15ha001rs60", mech="combo: momC15 x ha0.01 x RS60", sA=LA, sB=LB, sC=LC0, mom=(("C",), 0.15), hyst_a=0.01, hyst_b=0.01, rs=60),
    dict(tag="C4_momC18ha001", mech="combo: momC18 x ha0.01", sA=LA, sB=LB, sC=LC0, mom=(("C",), 0.18), hyst_a=0.01, hyst_b=0.01),
    dict(tag="C5_momC15hc003", mech="combo: momC15 x hyst_c 0.03", sA=LA, sB=LB, sC=LC0, mom=(("C",), 0.15), hyst_c=0.03),
    dict(tag="C6_momC15ha001rs120", mech="combo: momC15 x ha0.01 x RS120", sA=LA, sB=LB, sC=LC0, mom=(("C",), 0.15), hyst_a=0.01, hyst_b=0.01, rs=120),
]
OUTP = ROOT/"results"/"r30_bt"/"t40e_valid_nbrcombo.json"
rows = []
for p in PLAN:
    print("RUN %s :: %s" % (p["tag"], p["mech"]), flush=True)
    row = run_switch(**p)
    rows.append(row)
    a = row["ann"]
    print("  => total=%s mdd=%s 21=%s 22=%s 23=%s 24=%s 25=%s 26=%s five>60=%s sw=%d tr=%d cost=%s mode=%s secs=%s" % (row["total"], row["mdd"], a["2021"]["ret"], a["2022"]["ret"], a["2023"]["ret"], a["2024"]["ret"], a["2025"]["ret"], a["2026"]["ret"], row["five_over_60"], row["switches"], row["trades"], row["cost"], row["mode"], row["secs"]), flush=True)
    OUTP.write_text(json.dumps(dict(base="T40_asym00508+E18_momC15", n_runs=len(PLAN), runs=rows), ensure_ascii=False, indent=1))
print("saved %s (%d runs)" % (OUTP, len(rows)), flush=True)
