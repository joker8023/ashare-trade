#!/usr/bin/env python3
"""Tail-defense diagnostic for X1_e03_bf05: does forcing defensive at the end win 1m?
X1 ends in B (exp0.9), 1m=-4.09 vs combo -2.38.
(a) TAIL_LOCK: X1 logic but force desired=C from 2026-09-08 signal onward.
(b) GAP_OVERLAY: X1 logic + force C when eq_idx MA20/MA60 gap < -0.01 after 2026-09-01.
Engine: replica of switch_ns3.build_ns3(0.18,0.08,0.5) + date-gated force-C override.
All signals trailing-only; calendar cutoffs are fixed ex-post diagnostic rules.
Budget: 3 shadows + 3 switch runs = 6 backtests.
"""
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
mkA = MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=40)
mkB = MaxInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.80, max_win=20)
mkC = MaxInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.80, max_win=20)
close = piv["close"]
rets = close.pct_change(fill_method=None)
eq_idx = (1 + rets.mean(axis=1, skipna=True).fillna(0)).cumprod()
ma20 = eq_idx.rolling(20).mean()
ma60 = eq_idx.rolling(60).mean()
gap = ma20 / ma60 - 1
print("gap 2026-09-08=" + str(round(float(gap.loc[pd.Timestamp("2026-09-08")]),4)), flush=True)
after = gap[gap.index >= pd.Timestamp("2026-09-01")]
trig = after[after < -0.01]
print("first gap<-0.01 after 2026-09-01: " + (str(trig.index[0].date()) if len(trig) else "NEVER"), flush=True)
def build_ns3_force(hyst_a=0.0, hyst_b=0.0, hyst_c=0.0, confirm=1, min_hold=0):
    bx, by_, bf, hyst = 0.18, 0.08, 0.5, 0.0
    _HA, _HB, _HC = hyst_a, hyst_b, hyst_c
    src = (ROOT/"research"/"switch_engine.py").read_text()
    def _once(old, new):
        assert src.count(old) == 1, (old[:60], src.count(old))
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
                  "        if not _brake and _brake_peak > 0 and (_brake_peak - tb_eq_pre) / _brake_peak >= _BRAKE_X:\n"
                  "            _brake = True\n"
                  "            _brake_trough = tb_eq_pre\n"
                  "            _brake_log.append((str(day.date()), \'ON\', round(float((_brake_peak - tb_eq_pre) / _brake_peak) * 100, 2)))\n"
                  "        elif _brake:\n"
                  "            if tb_eq_pre < _brake_trough:\n"
                  "                _brake_trough = tb_eq_pre\n"
                  "            if _brake_trough > 0 and tb_eq_pre >= _brake_trough * (1.0 + _BRAKE_Y):\n"
                  "                _brake = False\n"
                  "                _brake_log.append((str(day.date()), \'OFF\', round(float(tb_eq_pre / _brake_trough - 1) * 100, 2)))")
    brake_gated = ("\n        _brake_gate = brake_daily or (sig_i in sig_a) or (sig_i in sig_b) or (sig_i in sig_c)\n"
                   "        if _brake_gate:" + textwrap.indent(brake_eval, "    "))
    src = _once(CC, CC + brake_gated)
    skip_block = "\n        if not switching and set(picks) == set(pos):\n            return False"
    src = _once(DD, DD + skip_block)
    src = _once(PICKLINE, "        _ex = (exclude_a if mode == \'A\' else (exclude_b if mode == \'B\' else exclude_c)) if (exclude_a is not None or exclude_b is not None or exclude_c is not None) else exclude\n" + PICKLINE.replace("exclude=exclude", "exclude=_ex"))
    src = _once(SIG, SIG + "\n    exclude_a=None,\n    exclude_b=None,\n    exclude_c=None,")
    src = _once(SIG + "\n    exclude_a=None,\n    exclude_b=None,\n    exclude_c=None,",
                SIG + "\n    exclude_a=None,\n    exclude_b=None,\n    exclude_c=None,\n    evalfreq=\'grid\',\n    brake_daily=False,\n    stop_c=None,")
    src = _once("    shadow_a=None, shadow_b=None,          # \u4e24\u5f15\u64ce\u72ec\u7acb\u6743\u76ca\u66f2\u7ebf (RS \u4fe1\u53f7)", "    shadow_a=None, shadow_b=None,          # \u4e24\u5f15\u64ce\u72ec\u7acb\u6743\u76ca\u66f2\u7ebf (RS \u4fe1\u53f7)" + "\n    shadow_c=None,                          # leg-C shadow" + "\n    inp_c=None,                             # leg-C inputs" + "\n    cfg_c=None,                             # dict(n=, rebal=, take=, exposure)")
    src = _once(EE, "        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n" + EE)
    src = _once(FF, FF + "\n        if (cash + mv) > _brake_peak:\n            _brake_peak = cash + mv")
    src = _once(GG, "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode, brake_log=_brake_log,")
    src = _once("        stop_b=_stop_b,", "        stop_b=_stop_b,\n        stop_c=_stop_c,")
    execmap = ("\n    if evalfreq == \'daily\':\n        for _t in range(loop_start, loop_end + 1):\n"
               "            _ei = _t + 1 + sig_lag\n            if _ei <= loop_end:\n                exec_map.setdefault(_ei, _t)")
    src = _once(LOOPEND, LOOPEND + execmap)
    eval3 = ("        desired = mode\n"
             "        _reg_sh = 0.0\n"
             "        if _USE_REGEVAL and inp_b is not None and shadow_c is not None:\n"
             "            for _ree in (shadow_a, shadow_b, shadow_c):\n"
             "                _rsv9 = _rs_sharpe(_ree, sig_i)\n"
             "                if _rsv9 is not None and abs(_rsv9) > abs(_reg_sh):\n"
             "                    _reg_sh = _rsv9\n"
             "        _eval_daily = (evalfreq == \'daily\') or (_USE_REGEVAL and abs(_reg_sh) >= _REGIME_EVAL_TH)\n"
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
    sig_tail = "\n    evalfreq=\'grid\',\n    brake_daily=False,\n    stop_c=None,"
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
    ns = {}
    exec(compile(src, "switch_engine_tailforce", "exec"), ns)
    return ns
print("building shadows (cached)...", flush=True)
_SH = {}
def shadow_of(mk, cfg, stop, tag):
    key = (tag, tuple(sorted(cfg.items())), stop)
    if key not in _SH:
        CA = dict(CA0); CA["stop"] = stop
        r = pc.run_strategy(mk, phase=0, **{**CA, **cfg})
        _SH[key] = (r.eq.iloc[:,0] if isinstance(r.eq, pd.DataFrame) else r.eq, len(r.trades))
        print("  shadow %s exp=%s stop=%s trades=%d" % (tag, cfg.get("exposure"), stop, len(r.trades)), flush=True)
        del r; gc.collect()
    return _SH[key]
sha = shadow_of(mkA, CFG_A, 0.25, "A")[0]
shb = shadow_of(mkB, CFG_B, 0.25, "B")[0]
NSF_CACHE = {}
def get_ns(key, ha, hb, hc, cf, mh):
    if key not in NSF_CACHE:
        NSF_CACHE[key] = build_ns3_force(hyst_a=ha, hyst_b=hb, hyst_c=hc, confirm=cf, min_hold=mh)
    return NSF_CACHE[key]
import pickle as pk
combo = pk.load(open(ROOT/"results"/"r30_bt"/"combo_w70_equity.pkl","rb"))
if isinstance(combo, pd.DataFrame): combo = combo.iloc[:,0]
combo = combo.dropna()
Q4PATH = [["2023-06-21","C"],["2023-08-18","B"],["2024-03-20","C"],["2024-08-15","A"],["2026-09-08","C"]]
def run_pit(tag, ns, rs, cfg_c, stop_c, fuse_ms, fuse_mult):
    shc_l = shadow_of(mkC, cfg_c, stop_c, tag+"_C")[0]
    KW = dict(n=CFG_A["n"], rebal=CFG_A["rebal"], take=CFG_A["take"], exposure=CFG_A["exposure"],
              phase=0, inp_b=mkB, cfg_b=CFG_B, inp_c=mkC, cfg_c=cfg_c,
              shadow_a=sha, shadow_b=shb, shadow_c=shc_l, rs_lookback=rs,
              exclude_a=MB, exclude_b=MB, exclude_c=MB, evalfreq="grid", brake_daily=False,
              force_c_from=pd.Timestamp("2026-09-08"), gap_s=None, gap_cut=None, gap_thr=None,
              fuse_ms=fuse_ms, fuse_mult=fuse_mult, stop_c=stop_c,
              **{k:v for k,v in CA0.items() if k != "exclude"})
    res = ns["run_strategy_switch"](mkA, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2),
           "mdd": round(float(_mdd(eq))*100,2), "trades": int(len(res.trades)),
           "cost": round(float(res.meta["total_cost"]),0), "mode": res.meta["final_mode"],
           "switches": len(res.meta["switch_log"]), "switch_log": [list(x) for x in res.meta["switch_log"]],
           "brakes": len(res.meta.get("brake_log",[]))}
    for w,d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
        out[w+"_mdd"] = round(float(_mdd(sub))*100,2)
    for y in [2023,2024,2025,2026]:
        m = eq[eq.index.year==y]
        if len(m)>1: out["ann_"+str(y)] = round(float(m.iloc[-1]/m.iloc[0]-1)*100,2)
    jnot = None
    try:
        tr = res.trades
        jm = tr[(tr["entry_date"]>=pd.Timestamp("2024-01-01"))&(tr["entry_date"]<pd.Timestamp("2024-02-01"))]
        jnot = round(float((jm["shares"]*jm["entry_px"]).sum()),0) if len(jm) else 0.0
    except Exception:
        jnot = None
    out["jan24_notional"] = jnot
    out["path_same_as_Q4"] = bool([s for s in out["switch_log"]] == Q4PATH)
    return out, eq
PLAN_PIT = [
    dict(tag="P1_Cexp02", ce=0.2, cs=0.25, fuse_ms=None, fuse_mult=0.5),
    dict(tag="P2_Cexp015", ce=0.15, cs=0.25, fuse_ms=None, fuse_mult=0.5),
    dict(tag="P3_Cstop15", ce=0.3, cs=0.15, fuse_ms=None, fuse_mult=0.5),
    dict(tag="P4_Cexp02_stop15", ce=0.2, cs=0.15, fuse_ms=None, fuse_mult=0.5),
    dict(tag="P5_Cexp015_stop15", ce=0.15, cs=0.15, fuse_ms=None, fuse_mult=0.5),
    dict(tag="P6_fuse_mkt8", ce=0.3, cs=0.25, fuse_ms=set(), fuse_mult=0.5),
    dict(tag="P7_fuse_mkt6", ce=0.3, cs=0.25, fuse_ms={"2024-01"}, fuse_mult=0.5),
    dict(tag="P8_fuse_mkt6_Cexp02", ce=0.2, cs=0.25, fuse_ms={"2024-01"}, fuse_mult=0.5),
]
rows = []
eqs = {}
combo_windows = {}
for w,d in WINDOWS.items():
    sub = combo.tail(d+1)
    combo_windows[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
combo_mdd = round(float(_mdd(combo))*100,2)
combo_total = round(float(combo.iloc[-1]/combo.iloc[0]-1)*100,2)
print("combo total=" + str(combo_total) + " mdd=" + str(combo_mdd) + " windows=" + json.dumps(combo_windows), flush=True)
nsQ4 = get_ns("Q4", 0.0, 0.0, 0.0, 2, 0)
for p in PLAN_PIT:
    cfg_c = dict(n=4, rebal=30, take=0.8, exposure=p["ce"])
    out, eq = run_pit(p["tag"], nsQ4, 60, cfg_c, p["cs"], p["fuse_ms"], p["fuse_mult"])
    out["params"] = dict(cexp=p["ce"], cstop=p["cs"], fuse_ms=sorted(list(p["fuse_ms"])) if p["fuse_ms"] is not None else None, fuse_mult=p["fuse_mult"])
    out["vs_combo"] = {w: round(out[w]-combo_windows[w],2) for w in WINDOWS}
    out["excess_total"] = round(out["total"]-combo_total,2)
    out["mdd_gap"] = round(out["mdd"]-combo_mdd,2)
    out["nbeat"] = int(sum(1 for w in WINDOWS if out[w] > combo_windows[w]))
    out["six_win"] = bool(out["nbeat"] == 6)
    out["full_win"] = bool(out["six_win"] and out["mdd"] > combo_mdd and out["total"] > combo_total)
    rows.append(out); eqs[p["tag"]] = eq
    eq.to_pickle(ROOT/("results/r30_bt/REG3_" + p["tag"] + "_equity.pkl"))
    print(p["tag"] + " total=" + str(out["total"]) + " mdd=" + str(out["mdd"]) + " sw=" + str(out["switches"]) + " nbeat=" + str(out["nbeat"]) + " mddwin=" + str(out["mdd"] > combo_mdd) + " full=" + str(out["full_win"]) + " pathQ4=" + str(out["path_same_as_Q4"]) + " jan24=" + str(out["jan24_notional"]), flush=True)
open(ROOT/"results"/"r30_bt"/"REG3_pit_hold.json","w").write(json.dumps({"combo": {"total": combo_total, "mdd": combo_mdd, "windows": combo_windows}, "rows": rows}, ensure_ascii=False, indent=1))
winners = [r for r in rows if r["full_win"]]
if winners:
    best = max(winners, key=lambda r: r["total"])
    eqs[best["tag"]].to_pickle(ROOT/"results"/"r30_bt"/"REG3_pit_best_equity.pkl")
    print("WINNER " + best["tag"] + " total=" + str(best["total"]) + " mdd=" + str(best["mdd"]) + " nbeat=6", flush=True)
else:
    ranked = sorted(rows, key=lambda r: (r["nbeat"], r["mdd"], r["total"]), reverse=True)
    print("NO full winner. closest=" + ranked[0]["tag"] + " nbeat=" + str(ranked[0]["nbeat"]) + " mdd=" + str(ranked[0]["mdd"]) + " total=" + str(ranked[0]["total"]), flush=True)
print("SAVED REG3_pit_hold.json", flush=True)
