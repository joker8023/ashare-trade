#!/usr/bin/env python3
"""F3 size族: B腿DInputs sel=size + A腿M07固定 (realshares_v2, 与F1正交).

正交声明: F1=C2_grid_mh0_bx0.15_by0.1_bf0.5 的B腿为 MaxInputs amihud_60 池
(band=(0.02,0.30), gate60=-0.15, cut0.80/win20, N5/R15/take0.45);
本族B腿为 DInputs sel=size (最小流通市值, cap升序取小), 与F1选股器正交.
A腿与F1同构固定: MaxInputs band=(0.02,0.30) gate60=-0.15 cut=0.80 win=40,
N=5/R20/take=1.2/exp=1.0. 不得改动F1冻结文件.

口径: RUN_START=2023-01-03, EVAL_END=2026-11-12, 本金5万, slip=0.002,
整手100, long-only全清, exp<=1, legacy_grid=False, full_liquidate=True.
切换: build_ns grid/daily+hyst (与search_C_stage2同构), rs_lookback=60,
刹车bx/by/bf, stop=0.25/stop_exec=next. 判定只用t及以前影子收益, 无前视.

扫描:
  Phase A: N{4,5,6} x R{15,20,30} x TP{0.45,0.6,0.8,1.0,1.2}
           @ band=(0.05,0.30)/gate60=-1.0/cut0.70/win20, grid/hyst0,
           brake bx0.18/by0.08/bf0.6, rs60.
  Phase B: band/gate 变体 (0.02-0.30 vs 0.05-0.30; gate -1.0 vs -0.15)
           在Phase A top3锚点上.
  Phase C: 刹车邻域 bx{0.12,0.15,0.18,0.22} x by{0.05,0.08,0.10} x bf{0.5,0.6,0.7},
           在累计top3锚点上.
  Phase D: daily+hyst{0.02,0.03,0.05} (+brake_daily T/F) 在累计top3上.
达标: 2024 slice>60且yoy>60, 2025_yoy>60, 2026 slice>60且yoy>60
(2026截至11-12注明), 全程mdd>-30且每年mdd>-30.
用法: .venv/bin/python research/fam_F3.py [--only TAG] [--phase A|B|C|D]
输出: results/r30_bt/fam_F3_stage.json
"""
import sys, json, textwrap
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import _mdd, RUN_START, EVAL_END, MB

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
            '                desired = "A" if ra >= rb else "B"')
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
            "                else:\n"
            "                    _confirm_count += 1\n"
            "                    if _confirm_count >= _CONFIRM and (sig_i - _last_switch_i) >= _MIN_HOLD:\n"
            "                        desired = _raw")
SWLOG = "            switch_log.append((str(sig_day.date()), mode))"

def build_ns(bx=0.18, by_=0.08, bf=0.6, hyst=0.0, min_hold=0, confirm=1):
    assert bf > 0, 'bf=0 + full_liquidate deadlocks'
    from typing import List, Tuple
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
                  "            _brake_log.append((str(day.date()), 'ON', round(float((_brake_peak - tb_eq_pre) / _brake_peak) * 100, 2)))\n"
                  '        elif _brake:\n'
                  '            if tb_eq_pre < _brake_trough:\n'
                  '                _brake_trough = tb_eq_pre\n'
                  '            if _brake_trough > 0 and tb_eq_pre >= _brake_trough * (1.0 + _BRAKE_Y):\n'
                  '                _brake = False\n'
                  "                _brake_log.append((str(day.date()), 'OFF', round(float(tb_eq_pre / _brake_trough - 1) * 100, 2)))")
    src = _once(CC, CC + ('\n        _brake_gate = brake_daily or (sig_i in sig_a) or (sig_i in sig_b)\n'
                   '        if _brake_gate:' + textwrap.indent(brake_eval, '    ')))
    skip_block = '\n        if not switching and set(picks) == set(pos):\n            return False'
    src = _once(DD, DD + skip_block)
    src = _once(PICKLINE, "        _ex = (exclude_a if mode == 'A' else exclude_b) if (exclude_a is not None or exclude_b is not None) else exclude\n" + PICKLINE.replace('exclude=exclude', 'exclude=_ex'))
    src = _once(SIG, SIG + '\n    exclude_a=None,\n    exclude_b=None,')
    src = _once('    exclude_a=None,\n    exclude_b=None,',
                "    exclude_a=None,\n    exclude_b=None,\n    evalfreq='grid',\n    brake_daily=False,")
    src = _once(EE, '        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n' + EE)
    src = _once(FF, FF + '\n        if (cash + mv) > _brake_peak:\n            _brake_peak = cash + mv')
    src = _once(GG, '        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode, brake_log=_brake_log,')
    execmap = ('\n    if evalfreq == \'daily\':\n        for _t in range(loop_start, loop_end + 1):\n'
               '            _ei = _t + 1 + sig_lag\n            if _ei <= loop_end:\n                exec_map.setdefault(_ei, _t)')
    src = _once(LOOPEND, LOOPEND + execmap)
    src = _once(EVAL_OLD, EVAL_NEW)
    src = _once(SWLOG, SWLOG + '\n            _last_switch_i = sig_i\n            _confirm_count = 0')
    ns = {}
    exec(compile(src, 'switch_engine_F3', 'exec'), ns)
    return ns

piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
print("RUN", RUN_START, EVAL_END, "first_sig", first_sig.date(), flush=True)

def annuals(eq):
    out = {}
    prev_end = None
    for y in [2023, 2024, 2025, 2026]:
        sub = eq[eq.index.year == y]
        if len(sub) == 0:
            out[y] = dict(slice=None, yoy=None, mdd=None); continue
        sret = float(sub.iloc[-1] / sub.iloc[0] - 1) * 100
        out[y] = dict(slice=round(sret, 2),
                      yoy=round((float(sub.iloc[-1] / prev_end - 1) * 100 if prev_end is not None else sret), 2),
                      mdd=round(float((sub / sub.cummax() - 1).min()) * 100, 2))
        prev_end = float(sub.iloc[-1])
    return out

_inpA = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
_CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0,
          lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
          eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
_CFG_A = dict(n=5, rebal=20, take=1.2, exposure=1.0)
print("building shadow A (M07 fixed)...", flush=True)
_ra = pc.run_strategy(_inpA, phase=0, **{**_CA, **_CFG_A})
print("shadow A ready trades=%d" % len(_ra.trades), flush=True)

_rb_cache = {}
_ns_cache = {}
def get_rb(b_band, b_gate, b_cut, b_win, b_n, b_rebal, b_take):
    key = (b_band, b_gate, b_cut, b_win, b_n, b_rebal, b_take)
    if key not in _rb_cache:
        inp_b = DInputs(piv, band=b_band, gate60=b_gate, max_cut=b_cut, max_win=b_win, sel="size")
        rb = pc.run_strategy(inp_b, n=b_n, rebal=b_rebal, take=b_take, exposure=0.9, phase=0, **_CA)
        _rb_cache[key] = (inp_b, rb)
    return _rb_cache[key]

def get_ns(bx, by_, bf, hyst, evalfreq, brake_daily):
    key = (bx, by_, bf, hyst, evalfreq, brake_daily)
    if key not in _ns_cache:
        _ns_cache[key] = build_ns(bx, by_, bf, hyst=hyst, min_hold=0, confirm=1)
    return _ns_cache[key]

def run_switch(tag, b_n=4, b_rebal=30, b_take=0.80, b_band=(0.05, 0.30), b_gate=-1.0,
               b_cut=0.70, b_win=20, bx=0.18, by_=0.08, bf=0.6, rs=60,
               hyst=0.0, evalfreq="grid", brake_daily=False, stop=0.25, lock=None):
    inp_b, rb = get_rb(b_band, b_gate, b_cut, b_win, b_n, b_rebal, b_take)
    CA = dict(_CA); CA["stop"] = stop
    CFG_B = dict(n=b_n, rebal=b_rebal, take=b_take, exposure=0.9)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B,
              shadow_a=_ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB,
              evalfreq=evalfreq, brake_daily=brake_daily,
              **{k: v for k, v in CA.items() if k != "exclude"})
    ns = get_ns(bx, by_, bf, hyst, evalfreq, brake_daily)
    res = ns["run_strategy_switch"](_inpA, lock_mode=lock, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    an = annuals(eq)
    r = dict(tag=tag, fam="F3", b_sel="size", b_n=b_n, b_rebal=b_rebal, b_take=b_take,
             b_band=list(b_band), b_gate=b_gate, b_cut=b_cut, b_win=b_win,
             bx=bx, by_=by_, bf=bf, rs=rs, hyst=hyst, evalfreq=evalfreq,
             brake_daily=brake_daily, stop=stop, lock=lock,
             total=round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
             mdd=round(_mdd(eq) * 100, 2), trades=len(res.trades),
             cost=round(float(res.meta["total_cost"]), 0), mode=res.meta["final_mode"],
             switches=len(res.meta["switch_log"]),
             switch_log=[list(x) for x in res.meta["switch_log"]],
             brake_log=[list(x) for x in res.meta.get("brake_log", [])],
             y2024_slice=an[2024]["slice"], y2024_yoy=an[2024]["yoy"], y2024_mdd=an[2024]["mdd"],
             y2025_slice=an[2025]["slice"], y2025_yoy=an[2025]["yoy"], y2025_mdd=an[2025]["mdd"],
             y2026_slice=an[2026]["slice"], y2026_yoy=an[2026]["yoy"], y2026_mdd=an[2026]["mdd"],
             y2023_yoy=an[2023]["yoy"], y2023_mdd=an[2023]["mdd"])
    r["pass_all"] = bool(r["y2024_slice"] is not None and r["y2024_slice"] > 60 and r["y2024_yoy"] > 60
                         and r["y2025_yoy"] > 60 and r["y2026_slice"] is not None and r["y2026_slice"] > 60
                         and r["y2026_yoy"] > 60 and r["mdd"] > -30 and r["y2024_mdd"] > -30
                         and r["y2025_mdd"] > -30 and r["y2026_mdd"] > -30)
    r["margin"] = round(min(r["y2024_slice"] - 60, r["y2024_yoy"] - 60, r["y2025_yoy"] - 60,
                            r["y2026_slice"] - 60, r["y2026_yoy"] - 60,
                            r["mdd"] + 30, r["y2024_mdd"] + 30, r["y2025_mdd"] + 30,
                            r["y2026_mdd"] + 30), 2)
    return r

def _tp(x): return str(x).replace(".", "")
def top3(rows):
    ok = [r for r in rows if r.get("pass_all")]
    pool = ok if ok else rows
    return sorted(pool, key=lambda r: (r.get("margin", -999), r.get("total", 0)), reverse=True)[:3]

CFGS_A = []
for n in (4, 5, 6):
    for R in (15, 20, 30):
        for tp in (0.45, 0.6, 0.8, 1.0, 1.2):
            CFGS_A.append(dict(tag="f3_N%d_R%d_T%s" % (n, R, _tp(tp)), b_n=n, b_rebal=R, b_take=tp))
BAND_GATE = [((0.02, 0.30), -1.0), ((0.05, 0.30), -0.15), ((0.02, 0.30), -0.15)]
BRAKES = [(0.12, 0.05, 0.5), (0.15, 0.05, 0.5), (0.15, 0.10, 0.5),
          (0.18, 0.08, 0.6), (0.22, 0.05, 0.7), (0.12, 0.10, 0.7)]
HYS = [0.02, 0.03, 0.05]

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--only", default=None); ap.add_argument("--phase", default=None); args = ap.parse_args()
    if args.only is not None:
        cands = list(CFGS_A)
        c = next(c for c in cands if c["tag"] == args.only)
        print(json.dumps(run_switch(**c), ensure_ascii=False), flush=True)
        sys.exit(0)
    rows = []
    def do(c):
        try:
            r = run_switch(**c)
            print(json.dumps(r, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (c.get("tag"), e), flush=True)
            import traceback; traceback.print_exc()
    phases = [args.phase] if args.phase else ["A", "B", "C", "D"]
    if "A" in phases:
        for c in CFGS_A:
            do(dict(c))
        print("PHASE_A_TOP3: %s" % json.dumps([(a["tag"], a.get("margin")) for a in top3(rows)], ensure_ascii=False), flush=True)
    if "B" in phases:
        for a in top3(rows):
            base = dict(b_n=a["b_n"], b_rebal=a["b_rebal"], b_take=a["b_take"], b_cut=a["b_cut"], b_win=a["b_win"],
                        bx=a["bx"], by_=a["by_"], bf=a["bf"], rs=a["rs"])
            for (band, gate) in BAND_GATE:
                tag = "%s_bd%s_g%s" % (a["tag"], _tp(band[0]) + _tp(band[1]), str(gate).replace(".", "").replace("-", "m"))
                do(dict(base, tag=tag, b_band=band, b_gate=gate))
        print("PHASE_B_TOP3: %s" % json.dumps([(a["tag"], a.get("margin")) for a in top3(rows)], ensure_ascii=False), flush=True)
    if "C" in phases:
        for a in top3(rows):
            base = dict(b_n=a["b_n"], b_rebal=a["b_rebal"], b_take=a["b_take"], b_band=tuple(a["b_band"]),
                        b_gate=a["b_gate"], b_cut=a["b_cut"], b_win=a["b_win"], rs=a["rs"])
            for (bx, by_, bf) in BRAKES:
                if (bx, by_, bf) == (a["bx"], a["by_"], a["bf"]):
                    continue
                tag = "%s_bx%sby%sb%s" % (a["tag"], _tp(bx), _tp(by_), _tp(bf))
                do(dict(base, tag=tag, bx=bx, by_=by_, bf=bf))
        print("PHASE_C_TOP3: %s" % json.dumps([(a["tag"], a.get("margin")) for a in top3(rows)], ensure_ascii=False), flush=True)
    if "D" in phases:
        for a in top3(rows):
            base = dict(b_n=a["b_n"], b_rebal=a["b_rebal"], b_take=a["b_take"], b_band=tuple(a["b_band"]),
                        b_gate=a["b_gate"], b_cut=a["b_cut"], b_win=a["b_win"],
                        bx=a["bx"], by_=a["by_"], bf=a["bf"], rs=a["rs"])
            for h in HYS:
                for bd in (False, True):
                    tag = "%s_dh%s%s" % (a["tag"], _tp(h), "_bd" if bd else "")
                    do(dict(base, tag=tag, hyst=h, evalfreq="daily", brake_daily=bd))
        print("PHASE_D_TOP3: %s" % json.dumps([(a["tag"], a.get("margin")) for a in top3(rows)], ensure_ascii=False), flush=True)
    if args.phase is None:
        open(ROOT / "results" / "r30_bt" / "fam_F3_stage.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
        print("saved %d rows -> results/r30_bt/fam_F3_stage.json" % len(rows), flush=True)
        ok = [r for r in rows if r.get("pass_all")]
        print("PASS=%d/%d" % (len(ok), len(rows)), flush=True)
        for r in sorted(ok, key=lambda r: (r["margin"], r["total"]), reverse=True)[:5]:
            print("STAR " + json.dumps({k: r[k] for k in ("tag", "total", "mdd", "y2024_slice", "y2024_yoy", "y2025_yoy", "y2026_slice", "y2026_yoy", "margin", "mode", "switches", "trades")}, ensure_ascii=False), flush=True)
