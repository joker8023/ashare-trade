#!/usr/bin/env python3
# F5 turn/vol family search (realshares_v2 true-equity caliber, F1=C2_grid frozen).
# Caliber: RUN_START=2023-01-03 EVAL_END=2026-11-12, 50k, slip=0.002, lot=100,
#   real fees, stop=0.25 stop_exec=next, legacy_grid=False, full_liquidate=True,
#   long-only, exposure<=1, MB both legs excluded.
# A-leg fixed M07: MaxInputs band=(0.02,0.30) gate60=-0.15 cut=0.80 win=40,
#   n=5/R20/TP1.2/exp1.0.
# B-leg DInputs sel in {turn20, vol20, c_4, c_a60_turn, c_a60_vol},
#   band=(0.05,0.30) gate60=-1.0 (gate off), stop=0.25, RS trailing-60 shadows.
# Selectors (trailing-only, no lookahead): turn20=trailing-20d mean(volume/shares)
#   smallest wins; vol20=trailing-20d std(daily ret) smallest wins;
#   c_4=rank-sum(amihud60,amihud5,size,turn20); c_a60_turn/c_a60_vol 2-key rank-sums.
# Grid: Batch A sel5 x N456 x R152030 x TP0.45-1.2 @cut0.7/win20 default brake grid rs60
#   Batch B top3 anchors x brake variants; Batch C switch variants rs90/daily+hyst;
#   Batch D MAX cut x win on 2 anchors; Batch E lock_B pure-B + brake.
# Strict pass: 2024_slice>60 & 2024_yoy>60 & 2025_yoy>60 & 2026_slice>60 & 2026_yoy>60
#   (2026 thru 11-12) & full & yearly mdd>-30.
# Usage: .venv/bin/python research/fam_F5.py [--only TAG]
# Output: results/r30_bt/fam_F5_stage.json
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import _mdd, RUN_START, EVAL_END, MB
from functools import lru_cache
from switch_ns import build_ns, atomic_write_json
F5_SELS = ("turn20", "vol20", "c_4", "c_a60_turn", "c_a60_vol")
# build_ns: single implementation from switch_ns (C2-fixed confirm semantics)
piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
print("RUN", RUN_START, EVAL_END, "first_sig", first_sig.date(), "F5 sels", F5_SELS, flush=True)
inpA = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
print("building shadow A M07(R20/TP1.2)...", flush=True)
ra = pc.run_strategy(inpA, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
print("shadow A ready trades=%d" % len(ra.trades), flush=True)
_NS_CACHE = {}
@lru_cache(maxsize=2)
def get_inp_b(sel, band=(0.05, 0.30), gate=-1.0, cut=0.70, win=20):
    return DInputs(piv, band=band, gate60=gate, max_cut=cut, max_win=win, sel=sel)
@lru_cache(maxsize=8)
def get_shadow_b(sel, band, gate, cut, win, n, R, take, stop=0.25, exp=0.9):
    inp_b = get_inp_b(sel, band, gate, cut, win)
    CB = dict(CA)
    CB["exclude"] = MB
    return pc.run_strategy(inp_b, phase=0, **dict(CB, n=n, rebal=R, take=take, exposure=exp))
def get_ns(bx, by_, bf, hyst=0.0, mh=0, cf=1):
    k = (bx, by_, bf, hyst, mh, cf)
    if k not in _NS_CACHE:
        _NS_CACHE[k] = build_ns(bx, by_, bf, hyst, mh, cf)
    return _NS_CACHE[k]
def annuals(eq):
    out = {}
    prev_end = None
    for y in [2023, 2024, 2025, 2026]:
        sub = eq[eq.index.year == y]
        if len(sub) == 0:
            out[y] = dict(slice=None, yoy=None, mdd=None)
            continue
        sret = float(sub.iloc[-1] / sub.iloc[0] - 1) * 100
        out[y] = dict(slice=round(sret, 2), yoy=round((float(sub.iloc[-1] / prev_end - 1) * 100 if prev_end is not None else sret), 2), mdd=round(float((sub / sub.cummax() - 1).min()) * 100, 2))
        prev_end = float(sub.iloc[-1])
    return out
def run_switch(tag, sel, b_n=4, b_rebal=30, b_take=0.80, b_cut=0.70, b_win=20, band=(0.05, 0.30), gate=-1.0, bx=0.18, by_=0.08, bf=0.6, rs=60, hyst=0.0, mh=0, confirm=1, evalfreq='grid', brake_daily=False, stop=0.25, exp_b=0.9, lock=None):
    inp_b = get_inp_b(sel, band, gate, b_cut, b_win)
    CFG_B = dict(n=b_n, rebal=b_rebal, take=b_take, exposure=exp_b)
    rb = get_shadow_b(sel, band, gate, b_cut, b_win, b_n, b_rebal, b_take, stop, exp_b)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB, evalfreq=evalfreq, brake_daily=brake_daily)
    for k, v in CA.items():
        if k != 'exclude':
            KW[k] = v
    KW['stop'] = CA['stop']  # A leg frozen; B-leg experiment stop goes via stop_b
    KW['stop_b'] = stop
    ns = get_ns(bx, by_, bf, hyst, mh, confirm)
    res = ns['run_strategy_switch'](inpA, lock_mode=lock, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    an = annuals(eq)
    r = dict(tag=tag, fam='F5', b_sel=sel, b_band=list(band), b_gate=gate, b_n=b_n, b_rebal=b_rebal, b_take=b_take, b_cut=b_cut, b_win=b_win, bx=bx, by_=by_, bf=bf, rs=rs, hyst=hyst, mh=mh, confirm=confirm, evalfreq=evalfreq, brake_daily=brake_daily, stop=stop, exp_b=exp_b, lock=lock, total=round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2), mdd=round(_mdd(eq) * 100, 2), trades=len(res.trades), cost=round(float(res.meta['total_cost']), 0), mode=res.meta['final_mode'], switches=len(res.meta['switch_log']), switch_log=[list(x) for x in res.meta['switch_log']], brake_log=[list(x) for x in res.meta.get('brake_log', [])], brakes=len(res.meta.get('brake_log', [])) // 2, eq_start=str(eq.index[0].date()), eq_end=str(eq.index[-1].date()), y2023_yoy=an[2023]['yoy'], y2023_mdd=an[2023]['mdd'], y2024_slice=an[2024]['slice'], y2024_yoy=an[2024]['yoy'], y2024_mdd=an[2024]['mdd'], y2025_slice=an[2025]['slice'], y2025_yoy=an[2025]['yoy'], y2025_mdd=an[2025]['mdd'], y2026_slice=an[2026]['slice'], y2026_yoy=an[2026]['yoy'], y2026_mdd=an[2026]['mdd'])
    r['pass_all'] = bool(r['y2024_slice'] is not None and r['y2024_slice'] > 60 and r['y2024_yoy'] > 60 and r['y2025_yoy'] > 60 and r['y2026_slice'] is not None and r['y2026_slice'] > 60 and r['y2026_yoy'] > 60 and r['mdd'] > -30 and r['y2024_mdd'] > -30 and r['y2025_mdd'] > -30 and r['y2026_mdd'] > -30)
    r['margin'] = round(min(r['y2024_slice'] - 60, r['y2024_yoy'] - 60, r['y2025_yoy'] - 60, r['y2026_slice'] - 60, r['y2026_yoy'] - 60, r['mdd'] + 30, r['y2024_mdd'] + 30, r['y2025_mdd'] + 30, r['y2026_mdd'] + 30), 2)
    r['avg_exp'] = round(float(res.exposure.mean()), 4) if res.exposure is not None else None
    r['max_exp'] = round(float(res.exposure.max()), 4) if res.exposure is not None else None
    _pe = float(eq.iloc[-1] - eq.iloc[0])
    r['cost_eff'] = round(_pe / float(res.meta['total_cost']), 2) if float(res.meta['total_cost']) > 0 else None
    r['take_sells'] = int(res.meta.get('take_sells', 0))
    r['stop_b'] = stop
    return r
CFGS_A = []
for sel in F5_SELS:
    for n in (4, 5, 6):
        for R in (15, 20, 30):
            for tp in (0.45, 0.6, 0.8, 1.0, 1.2):
                CFGS_A.append(dict(tag='F5_' + sel + '_N' + str(n) + '_R' + str(R) + '_T' + str(tp).replace('.', ''), sel=sel, b_n=n, b_rebal=R, b_take=tp))
BRAKES_B = [(0.15, 0.10, 0.5), (0.15, 0.10, 0.7), (0.12, 0.06, 0.5), (0.12, 0.08, 0.6), (0.18, 0.08, 0.3), (0.22, 0.05, 0.5)]
SWITCH_C = [dict(rs=90, hyst=0.0, mh=0, evalfreq='grid', brake_daily=False), dict(rs=60, hyst=0.02, mh=0, evalfreq='daily', brake_daily=False), dict(rs=60, hyst=0.03, mh=0, evalfreq='daily', brake_daily=True), dict(rs=60, hyst=0.02, mh=10, evalfreq='daily', brake_daily=False)]
def top3(rows):
    ok = [r for r in rows if r.get('pass_all')]
    pool = ok if ok else rows
    return sorted(pool, key=lambda r: (r.get('margin', -999), r.get('total', 0)), reverse=True)[:3]
if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default=None)
    args = ap.parse_args()
    if args.only is not None:
        c = next((c for c in CFGS_A if c['tag'] == args.only), None)
        if c is None:
            print('only tag not found (supports stage-A tags only): ' + str(args.only), flush=True)
        else:
            print(json.dumps(run_switch(**c), ensure_ascii=False), flush=True)
    else:
        rows = []
        for c in CFGS_A:
            try:
                r = run_switch(**c)
                print(json.dumps(r, ensure_ascii=False), flush=True)
                rows.append(r)
            except Exception as e:
                print('FAIL ' + c['tag'] + ': ' + str(e), flush=True)
        anchors = top3(rows)
        print('ANCHORS: ' + json.dumps([(a['tag'], a.get('margin')) for a in anchors], ensure_ascii=False), flush=True)
        for a in anchors:
            base = dict(sel=a['b_sel'], b_n=a['b_n'], b_rebal=a['b_rebal'], b_take=a['b_take'], b_cut=a['b_cut'], b_win=a['b_win'])
            for (bx, by_, bf) in BRAKES_B:
                tag = a['tag'] + '_b' + str(bx).replace('.', '') + str(by_).replace('.', '') + str(bf).replace('.', '')
                try:
                    r = run_switch(tag, bx=bx, by_=by_, bf=bf, **base)
                    print(json.dumps(r, ensure_ascii=False), flush=True)
                    rows.append(r)
                except Exception as e:
                    print('FAIL ' + tag + ': ' + str(e), flush=True)
            for sw in SWITCH_C:
                stag = a['tag'] + '_rs' + str(sw['rs']) + '_h' + str(sw['hyst']).replace('.', '') + '_mh' + str(sw['mh']) + '_' + sw['evalfreq'][0] + ('d' if sw['brake_daily'] else 'g')
                try:
                    r = run_switch(stag, bx=a['bx'], by_=a['by_'], bf=a['bf'], **dict(base, **sw))
                    print(json.dumps(r, ensure_ascii=False), flush=True)
                    rows.append(r)
                except Exception as e:
                    print('FAIL ' + stag + ': ' + str(e), flush=True)
        for a in anchors[:2]:
            for cut in (0.6, 0.7, 0.8):
                for win in (10, 20, 40):
                    if cut == 0.7 and win == 20:
                        continue
                    tag = a['tag'] + '_c' + str(cut).replace('.', '') + '_w' + str(win)
                    try:
                        r = run_switch(tag, sel=a['b_sel'], b_n=a['b_n'], b_rebal=a['b_rebal'], b_take=a['b_take'], b_cut=cut, b_win=win, bx=a['bx'], by_=a['by_'], bf=a['bf'], rs=a['rs'])
                        print(json.dumps(r, ensure_ascii=False), flush=True)
                        rows.append(r)
                    except Exception as e:
                        print('FAIL ' + tag + ': ' + str(e), flush=True)
        for a in anchors:
            for (bx, by_, bf) in [(0.15, 0.10, 0.5), (0.12, 0.06, 0.5), (0.18, 0.08, 0.6), (0.15, 0.05, 0.7), (0.22, 0.05, 0.5)]:
                tag = a['tag'] + '_lockB_b' + str(bx).replace('.', '') + str(by_).replace('.', '') + str(bf).replace('.', '')
                try:
                    r = run_switch(tag, sel=a['b_sel'], b_n=a['b_n'], b_rebal=a['b_rebal'], b_take=a['b_take'], b_cut=a['b_cut'], b_win=a['b_win'], bx=bx, by_=by_, bf=bf, lock='B')
                    print(json.dumps(r, ensure_ascii=False), flush=True)
                    rows.append(r)
                except Exception as e:
                    print('FAIL ' + tag + ': ' + str(e), flush=True)

        f_base = dict(sel='c_a60_turn', b_n=4, b_rebal=15, b_take=0.45, b_cut=0.70, b_win=20)
        f_cfgs = []
        for rs in (30, 45, 75):
            for hyst, mh in ((0.01, 0), (0.02, 0), (0.05, 0), (0.02, 5)):
                f_cfgs.append(dict(tag='F5s2_rs%d_h%s_mh%d_dg' % (rs, str(hyst).replace('.', ''), mh), rs=rs, hyst=hyst, mh=mh, evalfreq='daily', brake_daily=False, bx=0.18, by_=0.08, bf=0.6))
        for rs in (30, 45):
            f_cfgs.append(dict(tag='F5s2_grid_rs%d' % rs, rs=rs, hyst=0.0, mh=0, evalfreq='grid', brake_daily=False, bx=0.18, by_=0.08, bf=0.6))
        for bx, bf in ((0.25, 0.6), (0.30, 0.6), (0.25, 1.0), (0.18, 0.8)):
            f_cfgs.append(dict(tag='F5s2_b%s%s_daily_h002' % (str(bx).replace('.', ''), str(bf).replace('.', '')), rs=60, hyst=0.02, mh=0, evalfreq='daily', brake_daily=False, bx=bx, by_=0.08, bf=bf))
        for band, gate in (((0.02, 0.30), -1.0), ((0.05, 0.30), -0.15), ((0.02, 0.30), -0.15)):
            f_cfgs.append(dict(tag='F5s2_band%s_gate%s' % (str(band[0]).replace('.', ''), str(gate).replace('.', '').replace('-', 'm')), band=band, gate=gate, rs=60, hyst=0.02, mh=0, evalfreq='daily', brake_daily=False, bx=0.18, by_=0.08, bf=0.6))
        f_cfgs.append(dict(tag='F5s2_expb10', exp_b=1.0, rs=60, hyst=0.02, mh=0, evalfreq='daily', brake_daily=False, bx=0.18, by_=0.08, bf=0.6))
        for rs in (40, 42, 45, 48, 50):
            for hyst in (0.04, 0.05, 0.06, 0.07):
                f_cfgs.append(dict(tag='F5s3_rs%d_h%s_dg' % (rs, str(hyst).replace('.', '')), rs=rs, hyst=hyst, mh=0, evalfreq='daily', brake_daily=False, bx=0.18, by_=0.08, bf=0.6))
        for by_ in (0.06, 0.10):
            f_cfgs.append(dict(tag='F5s3_rs45_h005_by%s' % str(by_).replace('.', ''), rs=45, hyst=0.05, mh=0, evalfreq='daily', brake_daily=False, bx=0.18, by_=by_, bf=0.6))
        f_cfgs.append(dict(tag='F5s3_rs45_h005_mh5', rs=45, hyst=0.05, mh=5, evalfreq='daily', brake_daily=False, bx=0.18, by_=0.08, bf=0.6))
        f_cfgs.append(dict(tag='F5s3_rs45_h005_bd', rs=45, hyst=0.05, mh=0, evalfreq='daily', brake_daily=True, bx=0.18, by_=0.08, bf=0.6))
        for c in f_cfgs:
            tag = c.pop('tag')
            try:
                kw = dict(f_base)
                kw.update(c)
                r = run_switch(tag, **kw)
                print(json.dumps(r, ensure_ascii=False), flush=True)
                rows.append(r)
            except Exception as e:
                print('FAIL ' + tag + ': ' + str(e), flush=True)

        best = sorted(rows, key=lambda r: (r.get('pass_all', False), r.get('margin', -999), r.get('total', 0)), reverse=True)[:10]
        print('=== F5 TOP10 ===', flush=True)
        for b in best:
            print(json.dumps({k: b.get(k) for k in ('tag', 'b_sel', 'b_n', 'b_rebal', 'b_take', 'bx', 'by_', 'bf', 'rs', 'hyst', 'mh', 'evalfreq', 'lock', 'total', 'mdd', 'y2024_slice', 'y2024_yoy', 'y2024_mdd', 'y2025_yoy', 'y2025_mdd', 'y2026_slice', 'y2026_yoy', 'y2026_mdd', 'trades', 'cost', 'switches', 'brakes', 'mode', 'pass_all', 'margin')}, ensure_ascii=False), flush=True)
        atomic_write_json(ROOT / 'results' / 'r30_bt' / 'fam_F5_stage.json', rows)
        print('saved ' + str(len(rows)) + ' rows', flush=True)