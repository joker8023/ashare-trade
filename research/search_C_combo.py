#!/usr/bin/env python3
"""Route C search: combo/exposure/brake/daily-hyst/min_hold/confirm (rs2 caliber)."""
import sys, json, textwrap
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'team' / 'audit'))
sys.path.insert(0, str(ROOT / 'research'))
import pandas as pd
import numpy as np
import prior_check as pc
from fresh2_max import MaxInputs
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
            "                desired = \"A\" if ra >= rb else \"B\"")
EVAL_NEW_C = ("        desired = mode\n"
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

def build_ns_c(bx=0.18, by_=0.08, bf=0.6, hyst=0.0, min_hold=0, confirm=1):
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
    src = _once('    exclude_a=None,\n    exclude_b=None,',
                '    exclude_a=None,\n    exclude_b=None,\n    evalfreq=\'grid\',\n    brake_daily=False,')
    src = _once(EE, '        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n' + EE)
    src = _once(FF, FF + '\n        if (cash + mv) > _brake_peak:\n            _brake_peak = cash + mv')
    src = _once(GG, '        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode, brake_log=_brake_log,')
    execmap = ('\n    if evalfreq == \'daily\':\n        for _t in range(loop_start, loop_end + 1):\n'
               '            _ei = _t + 1 + sig_lag\n            if _ei <= loop_end:\n                exec_map.setdefault(_ei, _t)')
    src = _once(LOOPEND, LOOPEND + execmap)
    src = _once(EVAL_OLD, EVAL_NEW_C)
    src = _once(SWLOG, SWLOG + '\n            _last_switch_i = sig_i\n            _confirm_count = 0')
    ns = {}
    exec(compile(src, 'switch_engine_C', 'exec'), ns)
    return ns

print('build_ns_c defined', flush=True)

piv = pd.read_pickle(ROOT / 'data' / 'pivots_2020_clean_realshares_v2.pkl')
dates = piv['close'].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
print('RUN ' + str(RUN_START) + ' ' + str(EVAL_END) + ' first_sig=' + str(first_sig), flush=True)

_legA = {}
_legB = {}
def legA(cut_a=0.80, win_a=40):
    k = (cut_a, win_a)
    if k not in _legA:
        _legA[k] = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=cut_a, max_win=win_a)
    return _legA[k]
def legB(cut_b=0.80, win_b=20):
    k = (cut_b, win_b)
    if k not in _legB:
        _legB[k] = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=cut_b, max_win=win_b)
    return _legB[k]

def CA_DICT():
    return dict(factor='amihud_60', stop=0.25, stop_exec='next', exclude=MB, capital=50000.0,
                lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
                eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)

_sh = {}
def shadows(cut_a, win_a, cut_b, win_b, a_take=1.2, b_take=0.80, a_n=5, b_n=4, b_exp=0.9, stop=0.25):
    key = (cut_a, win_a, cut_b, win_b, a_take, b_take, a_n, b_n, b_exp, stop)
    if key in _sh:
        return _sh[key]
    ia, ib = legA(cut_a, win_a), legB(cut_b, win_b)
    CA = CA_DICT(); CA['stop'] = stop
    CB = dict(CA); CFG_B = dict(n=b_n, rebal=30, take=b_take, exposure=b_exp)
    ra = pc.run_strategy(ia, n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0, **CA)
    rb = pc.run_strategy(ib, phase=0, **dict(CB, **CFG_B))
    _sh[key] = (ia, ib, ra, rb, CA, CFG_B)
    return _sh[key]

def annual_out(eq, res, tag, cfg):
    eq = eq.dropna()
    rets = eq.pct_change().dropna()
    shr = float(rets.mean() / rets.std() * (252 ** 0.5)) if float(rets.std()) > 0 else 0.0
    tot = float(eq.iloc[-1] / eq.iloc[0] - 1) * 100
    md = _mdd(eq) * 100
    out = {'tag': tag, 'cfg': cfg, 'eq_len': int(len(eq)),
           'eq_start': str(eq.index[0].date()), 'eq_end': str(eq.index[-1].date()),
           'total': round(tot, 2), 'mdd': round(md, 2),
           'calmar': round(tot / abs(md), 3) if md != 0 else None,
           'sharpe': round(shr, 3), 'trades': int(len(res.trades)),
           'cost': round(float(res.meta['total_cost']), 0),
           'cost_eff': round(float((eq.iloc[-1] - eq.iloc[0]) / float(res.meta['total_cost'])), 2) if float(res.meta['total_cost']) > 0 else None,
           'mode': res.meta['final_mode'], 'switches': len(res.meta['switch_log']),
           'switch_log': [list(x) for x in res.meta['switch_log']],
           'brakes': len(res.meta.get('brake_log', [])) // 2,
           'brake_log': [list(x) for x in res.meta.get('brake_log', [])],
           'avg_exp': round(float(res.exposure.mean()), 4) if res.exposure is not None else None,
           'max_exp': round(float(res.exposure.max()), 4) if res.exposure is not None else None}
    prev_end = None
    for y in [2023, 2024, 2025, 2026]:
        sub = eq[eq.index.year == y]
        if len(sub) == 0:
            out[str(y)] = None; out[str(y) + '_mdd'] = None; out[str(y) + '_yoy'] = None
            continue
        sret = float(sub.iloc[-1] / sub.iloc[0] - 1) * 100
        out[str(y)] = round(sret, 2)
        out[str(y) + '_mdd'] = round(_mdd(sub) * 100, 2)
        out[str(y) + '_bars'] = int(len(sub))
        out[str(y) + '_start'] = str(sub.index[0].date())
        out[str(y) + '_end'] = str(sub.index[-1].date())
        out[str(y) + '_yoy'] = round((float(sub.iloc[-1] / prev_end - 1) * 100) if prev_end is not None else sret, 2)
        prev_end = float(sub.iloc[-1])
    out['pass'] = bool(out['2024'] is not None and out['2024'] > 60 and out['2024_yoy'] > 60
                        and out['2025_yoy'] > 60 and out['2026_yoy'] > 60
                        and out['mdd'] > -30 and out['2024_mdd'] > -30
                        and out['2025_mdd'] > -30 and out['2026_mdd'] > -30)
    out['margin'] = round(min(out['2024'] - 60, out['2024_yoy'] - 60, out['2025_yoy'] - 60,
                              out['2026_yoy'] - 60, out['mdd'] + 30, out['2024_mdd'] + 30,
                              out['2025_mdd'] + 30, out['2026_mdd'] + 30), 2)
    return out

_ns = {}
def get_ns(bx, by_, bf, hyst, mh, cf):
    k = (bx, by_, bf, hyst, mh, cf)
    if k not in _ns:
        _ns[k] = build_ns_c(bx, by_, bf, hyst, mh, cf)
    return _ns[k]

def run_switch(tag, cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, stop=0.25,
               a_take=1.2, b_take=0.80, a_n=5, b_n=4, b_exp=0.9,
               rs=60, bx=0.18, by_=0.08, bf=0.6, hyst=0.0, mh=0, cf=1,
               evalfreq='grid', brake_daily=False, lock=None, a_exp=1.0):
    ia, ib, ra, rb, CA, CFG_B = shadows(cut_a, win_a, cut_b, win_b, a_take, b_take, a_n, b_n, b_exp, stop)
    KW = dict(n=a_n, rebal=20, take=a_take, exposure=a_exp, phase=0, inp_b=ib, cfg_b=CFG_B,
              shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB,
              evalfreq=evalfreq, brake_daily=brake_daily,
              **{k: v for k, v in CA.items() if k != 'exclude'})
    ns = get_ns(bx, by_, bf, hyst, mh, cf)
    res = ns['run_strategy_switch'](ia, lock_mode=lock, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    cfg = dict(cut_a=cut_a, win_a=win_a, cut_b=cut_b, win_b=win_b, stop=stop, a_take=a_take,
               b_take=b_take, a_n=a_n, b_n=b_n, b_exp=b_exp, a_exp=a_exp, rs=rs,
               bx=bx, by_=by_, bf=bf, hyst=hyst, min_hold=mh, confirm=cf,
               evalfreq=evalfreq, brake_daily=brake_daily, lock=lock)
    return annual_out(eq, res, tag, cfg), eq

SLIM = ('tag', 'total', 'mdd', 'calmar', 'sharpe', '2024', '2024_yoy', '2024_mdd',
        '2025_yoy', '2025_mdd', '2026_yoy', '2026_mdd', 'trades', 'cost', 'cost_eff',
        'switches', 'brakes', 'mode', 'avg_exp', 'max_exp', 'pass', 'margin')
def slim(o):
    return {k: o.get(k) for k in SLIM}

print('part2 loaded', flush=True)

def stage_blend():
    rows = []
    for seat, ca, wa, cb, wb in [('M07seat', 0.80, 40, 0.80, 20), ('gbf07seat', 0.78, 40, 0.78, 20)]:
        ia, ib, ra, rb, CA, CFG_B = shadows(ca, wa, cb, wb)
        ea = (ra.eq.iloc[:, 0] if isinstance(ra.eq, pd.DataFrame) else ra.eq).dropna()
        eb = (rb.eq.iloc[:, 0] if isinstance(rb.eq, pd.DataFrame) else rb.eq).dropna()
        idx = ea.index.intersection(eb.index)
        ea, eb = ea.loc[idx], eb.loc[idx]
        for w in [0.5, 0.6, 0.7]:
            bl = (ea / ea.iloc[0] * w + eb / eb.iloc[0] * (1 - w)) * ea.iloc[0]
            tot = float(bl.iloc[-1] / bl.iloc[0] - 1) * 100
            md = _mdd(bl) * 100
            o = {'tag': seat + '_blend%02d' % int(w * 100), 'total': round(tot, 2), 'mdd': round(md, 2)}
            prev = None
            for y in [2023, 2024, 2025, 2026]:
                sub = bl[bl.index.year == y]
                sret = float(sub.iloc[-1] / sub.iloc[0] - 1) * 100
                yoy = float(sub.iloc[-1] / prev - 1) * 100 if prev is not None else sret
                o[str(y)] = round(sret, 2); o[str(y) + '_yoy'] = round(yoy, 2)
                o[str(y) + '_mdd'] = round(_mdd(sub) * 100, 2)
                prev = float(sub.iloc[-1])
            o['pass'] = bool(o['2024'] > 60 and o['2024_yoy'] > 60 and o['2025_yoy'] > 60 and o['2026_yoy'] > 60 and o['mdd'] > -30)
            print(json.dumps(o, ensure_ascii=False), flush=True)
            rows.append(o)
        lret = ea.pct_change().fillna(0) - eb.pct_change().fillna(0)
        ls = (1 + lret).cumprod()
        ltot = float(ls.iloc[-1] / ls.iloc[0] - 1) * 100
        lmd = _mdd(ls) * 100
        lrets = ls.pct_change().dropna()
        lsh = float(lrets.mean() / lrets.std() * (252 ** 0.5)) if float(lrets.std()) > 0 else 0.0
        o = {'tag': seat + '_LONGSHORT_REF(做空不可实盘,仅Calmar参考)', 'total': round(ltot, 2),
             'mdd': round(lmd, 2), 'calmar_ls': round(ltot / abs(lmd), 3) if lmd != 0 else None,
             'sharpe_ls': round(lsh, 3), 'note': 'long-short spread无成本, 做空不可实盘, 主结果仍为long-only'}
        print(json.dumps(o, ensure_ascii=False), flush=True)
        rows.append(o)
    open(ROOT / 'results' / 'r30_bt' / 'search_C_blend_annual.json', 'w').write(json.dumps(rows, ensure_ascii=False, indent=1))
    print('saved blend rows=' + str(len(rows)), flush=True)

def stage1():
    rows = []
    bxs = [0.08, 0.10, 0.12, 0.15, 0.18]
    bfs = [0.0, 0.3, 0.5]
    bys = [0.05]
    bds = [False, True]
    exps = [0.8, 0.9, 1.0]
    takes = [0.80, 0.60, 0.45]
    for (ca, wa, cb, wb, seat) in [(0.80, 40, 0.80, 20, 'M07'), (0.78, 40, 0.78, 20, 'gbf07')]:
        for bt in takes:
            for be in exps:
                for bx in bxs:
                    for by_ in bys:
                        for bf in bfs:
                            for bd in bds:
                                tag = 'C1B_%s_bt%s_be%s_bx%s_bf%s_%s' % (seat, bt, be, bx, bf, 'bd' if bd else 'bg')
                                try:
                                    o, e = run_switch(tag, cut_a=ca, win_a=wa, cut_b=cb, win_b=wb,
                                                      b_take=bt, b_exp=be, bx=bx, by_=by_, bf=bf,
                                                      evalfreq='grid', brake_daily=bd, lock='B')
                                    print(json.dumps(slim(o), ensure_ascii=False), flush=True)
                                    rows.append(o)
                                except Exception as ex:
                                    print('FAIL ' + tag + ': ' + str(ex), flush=True)
    open(ROOT / 'results' / 'r30_bt' / 'search_C_stage1_annual.json', 'w').write(json.dumps(rows, ensure_ascii=False, indent=1))
    best = sorted(rows, key=lambda r: (r['pass'], r['margin'], r['total']), reverse=True)[:8]
    print('=== STAGE1 TOP8 ===', flush=True)
    for b in best:
        print(json.dumps(slim(b), ensure_ascii=False), flush=True)
    print('saved stage1 rows=' + str(len(rows)), flush=True)

def stage2():
    rows = []
    hysts = [0.02, 0.03, 0.05, 0.08]
    rss = [30, 45, 60, 90]
    brakes = [(0.15, 0.05, 0.7), (0.15, 0.05, 0.3), (0.12, 0.05, 0.0), (0.18, 0.08, 0.6)]
    for (ca, wa, cb, wb, seat) in [(0.80, 40, 0.80, 20, 'M07'), (0.78, 40, 0.78, 20, 'gbf07')]:
        for h in hysts:
            for rs in rss:
                for (bx, by_, bf) in brakes:
                    for bd in [False, True]:
                        tag = 'C2S_%s_h%s_rs%s_bx%s_bf%s_%s' % (seat, h, rs, bx, bf, 'bd' if bd else 'bg')
                        try:
                            o, e = run_switch(tag, cut_a=ca, win_a=wa, cut_b=cb, win_b=wb,
                                              rs=rs, bx=bx, by_=by_, bf=bf, hyst=h,
                                              evalfreq='daily', brake_daily=bd, lock=None)
                            print(json.dumps(slim(o), ensure_ascii=False), flush=True)
                            rows.append(o)
                        except Exception as ex:
                            print('FAIL ' + tag + ': ' + str(ex), flush=True)
    open(ROOT / 'results' / 'r30_bt' / 'search_C_stage2_annual.json', 'w').write(json.dumps(rows, ensure_ascii=False, indent=1))
    best = sorted(rows, key=lambda r: (r['pass'], r['margin'], r['total']), reverse=True)[:8]
    print('=== STAGE2 TOP8 ===', flush=True)
    for b in best:
        print(json.dumps(slim(b), ensure_ascii=False), flush=True)
    print('saved stage2 rows=' + str(len(rows)), flush=True)

STAGE3_CFGS = [
]

def stage3():
    rows = []
    for c in STAGE3_CFGS:
        tag = c.pop('tag')
        try:
            o, e = run_switch(tag, **c)
            print(json.dumps(slim(o), ensure_ascii=False), flush=True)
            print(json.dumps({'switch_log': o['switch_log'], 'brake_log': o['brake_log'][:20]}, ensure_ascii=False), flush=True)
            rows.append(o)
            pd.to_pickle(e, ROOT / 'results' / 'r30_bt' / ('search_C_' + tag + '_equity.pkl'))
        except Exception as ex:
            print('FAIL ' + tag + ': ' + str(ex), flush=True)
            import traceback; traceback.print_exc()
    open(ROOT / 'results' / 'r30_bt' / 'search_C_stage3_annual.json', 'w').write(json.dumps(rows, ensure_ascii=False, indent=1))
    print('saved stage3 rows=' + str(len(rows)), flush=True)

if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'stage1'
    if which == 'stage1':
        stage1()
    elif which == 'stage2':
        stage2()
    elif which == 'stage3':
        stage3()
    elif which == 'blend':
        stage_blend()
    else:
        print('unknown stage: ' + which)