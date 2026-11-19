#!/usr/bin/env python3
"""Route-A M07-family annual sweep (realshares_v2 caliber).
Caliber: RUN_START=2023-01-03 EVAL_END=2026-11-12 capital 5w slip 0.002 lot 100
long-only exposure<=1. Switch decision uses t-and-earlier shadow RS only,
executed t+1 close in round lots; brake on rebalance days only (unless
brake_daily=True explicitly logged). No lookahead, no future quantiles.
Annual defs match research/bt_m07_family_rs2_annual.py:
slice=last/first-1 within year; yoy=year_end/prev_year_end-1; mdd=yearly max DD.
Progress is appended incrementally to results/r30_bt/search_A_spark_prog.jsonl
so partial work survives job timeouts. Run with python -u, no tail pipe.
Stages (each <~110s):
  b07|b08|b09 : B-leg coarse per cut_b (win x n x r; fixed stop/take)
  aleg        : A-leg coarse (cut x win x n)
  s1b         : B-leg stop/take/exp refine around best B shapes in progress file
  s2          : switch coarse around best B shapes
  s3          : k21-daily/hyst + stop/take/n refine around best switch rows
  final       : re-run shortlist -> results/r30_bt/search_A_spark_annual.json
"""
import sys, json, time, argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'team/audit')); sys.path.insert(0, str(ROOT/'research'))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
from sweep_beat_m07_k21 import build_ns_k21

PROG = ROOT/'results'/'r30_bt'/'search_A_spark_prog.jsonl'
print('RUN', RUN_START, EVAL_END, flush=True)
piv = pd.read_pickle(ROOT/'data'/'pivots_2020_clean_realshares_v2.pkl')
dates = piv['close'].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
print('first_sig', first_sig, flush=True)

_leg = {}
_ns_grid = {}
_ns_k21 = {}

def get_ns_grid(bx, by_, bf):
    k = (bx, by_, bf)
    if k not in _ns_grid:
        _ns_grid[k] = build_ns(bx, by_, bf)
    return _ns_grid[k]

def get_ns_k21(bx, by_, bf, hyst):
    k = (bx, by_, bf, hyst)
    if k not in _ns_k21:
        _ns_k21[k] = build_ns_k21(bx, by_, bf, hyst)
    return _ns_k21[k]

def leg(side, cut, win, stop=0.25, take=1.2, n=5, r=20, exp=1.0):
    key = (side, cut, win, stop, take, n, r, exp)
    if key in _leg:
        return _leg[key]
    if side == 'A':
        inp = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=cut, max_win=win)
    else:
        inp = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=cut, max_win=win)
    CA = dict(factor='amihud_60', stop=stop, stop_exec='next', exclude=MB, capital=50000.0,
              lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig,
              eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    if side == 'A':
        res = pc.run_strategy(inp, n=n, rebal=r, take=take, exposure=exp, phase=0, **CA)
        cfg = None
    else:
        cfg = dict(n=n, rebal=r, take=take, exposure=exp)
        res = pc.run_strategy(inp, phase=0, **{**CA, **cfg})
    _leg[key] = (inp, res, CA, cfg)
    return _leg[key]

def yearly(eq):
    y = {}
    prev_end = None
    for yr in [2023, 2024, 2025, 2026]:
        sub = eq[eq.index.year == yr]
        if len(sub) == 0:
            y[str(yr)] = None; y[str(yr)+'_mdd'] = None; y[str(yr)+'_yoy'] = None
            y[str(yr)+'_bars'] = 0
            continue
        sret = float(sub.iloc[-1]/sub.iloc[0]-1)*100
        y[str(yr)] = round(sret, 2)
        y[str(yr)+'_mdd'] = round(_mdd(sub)*100, 2)
        y[str(yr)+'_bars'] = int(len(sub))
        y[str(yr)+'_start'] = str(sub.index[0].date())
        y[str(yr)+'_end'] = str(sub.index[-1].date())
        if prev_end is not None:
            y[str(yr)+'_yoy'] = round(float(sub.iloc[-1]/prev_end-1)*100, 2)
        else:
            y[str(yr)+'_yoy'] = round(sret, 2)
        prev_end = float(sub.iloc[-1])
    try:
        b = y.get('2026_bars', 0); yy = y.get('2026_yoy')
        if b and yy is not None and yy > -100:
            y['2026_yoy_ann'] = round(((1+yy/100.0)**(252.0/b)-1)*100, 2)
        else:
            y['2026_yoy_ann'] = None
    except Exception:
        y['2026_yoy_ann'] = None
    return y

def base_row(tag, eq, res, params):
    out = {'tag': tag,
           'eq_len': int(len(eq)), 'eq_start': str(eq.index[0].date()), 'eq_end': str(eq.index[-1].date()),
           'total': round(float(eq.iloc[-1]/eq.iloc[0]-1)*100, 2),
           'mdd': round(_mdd(eq)*100, 2),
           'trades': len(res.trades), 'cost': round(float(res.meta['total_cost']), 0),
           'mode': res.meta.get('final_mode'), 'switches': len(res.meta.get('switch_log', [])),
           'params': params}
    out.update(yearly(eq))
    return out

def emit(row):
    with open(PROG, 'a') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(json.dumps({k: row.get(k) for k in ['tag','total','mdd','2024','2024_mdd','2024_yoy','2025_yoy','2026_yoy','switches','trades','cost']}, ensure_ascii=False), flush=True)
    if ok2024(row):
        print('*** PASS2024 *** ' + row['tag'], flush=True)

def run_direct_leg(tag, side, cut, win, stop=0.25, take=1.2, n=5, r=20, exp=1.0,
                   cut_a=0.80, win_a=40, cut_b=0.80, win_b=20):
    inp, res, CA, cfg = leg(side, cut, win, stop, take, n, r, exp)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    params = dict(family='M07', leg='lock_'+side, cut_a=cut_a, win_a=win_a, cut_b=cut_b, win_b=win_b,
                  stop=stop, a_take=(take if side == 'A' else 1.2), b_take=(take if side == 'B' else 0.80),
                  a_n=(n if side == 'A' else 5), b_n=(n if side == 'B' else 4),
                  a_r=(r if side == 'A' else 20), b_r=(r if side == 'B' else 30),
                  b_exp=(exp if side == 'B' else 0.9), brake='none(direct)', rs='na',
                  evalfreq='na', hyst='na', lock=side, exposure_le_1=True,
                  cost='realistic+slip0.002', lot=100)
    return base_row(tag, eq, res, params)

def run_switch(tag, cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, stop=0.25, a_take=1.2,
               b_take=0.80, a_n=5, b_n=4, a_r=20, b_r=30, b_exp=0.9, rs=60,
               bx=0.18, by_=0.08, bf=0.6, lock=None, evalfreq='grid', hyst=0.0, brake_daily=False):
    inp_a, ra, CA, _ = leg('A', cut_a, win_a, stop, a_take, a_n, a_r, 1.0)
    inp_b, rb, _, CFG_B = leg('B', cut_b, win_b, stop, b_take, b_n, b_r, b_exp)
    base = {k: v for k, v in CA.items() if k != 'exclude'}
    if evalfreq == 'grid':
        KW = dict(n=a_n, rebal=a_r, take=a_take, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B,
                  shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB, **base)
        ns = get_ns_grid(bx, by_, bf)
        res = ns['run_strategy_switch'](inp_a, lock_mode=lock, **KW)
    else:
        KW = dict(n=a_n, rebal=a_r, take=a_take, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B,
                  shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB,
                  evalfreq='daily', brake_daily=brake_daily, **base)
        ns = get_ns_k21(bx, by_, bf, hyst)
        res = ns['run_strategy_switch'](inp_a, lock_mode=lock, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    params = dict(family='M07', cut_a=cut_a, win_a=win_a, cut_b=cut_b, win_b=win_b, stop=stop,
                  a_take=a_take, b_take=b_take, a_n=a_n, b_n=b_n, a_r=a_r, b_r=b_r, b_exp=b_exp,
                  rs=rs, bx=bx, by=by_, bf=bf, lock=lock, evalfreq=evalfreq, hyst=hyst,
                  brake_daily=brake_daily, exposure_le_1=True, cost='realistic+slip0.002', lot=100)
    row = base_row(tag, eq, res, params)
    row['brakes'] = len(res.meta.get('brake_log', [])) // 2
    return row

def ok2024(r):
    try:
        return (r['2024'] is not None and r['2024_yoy'] is not None
                and r['2024'] > 60 and r['2024_yoy'] > 60
                and r['2025_yoy'] is not None and r['2025_yoy'] > 60
                and r['2026_yoy'] is not None and r['2026_yoy'] > 60
                and r['mdd'] is not None and r['mdd'] > -30
                and r['2024_mdd'] is not None and r['2024_mdd'] > -30
                and r['2025_mdd'] is not None and r['2025_mdd'] > -30
                and r['2026_mdd'] is not None and r['2026_mdd'] > -30)
    except Exception:
        return False

def load_prog():
    rows = []
    if PROG.exists():
        for line in open(PROG):
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    return rows

def done_tags():
    return set(r.get('tag') for r in load_prog())

def stage_bcut(cut_b):
    done = done_tags()
    for win_b in [15, 20, 30, 40]:
        for b_n in [3, 4, 5, 6]:
            for b_r in [20, 30]:
                tag = f"B_c{cut_b}_w{win_b}_n{b_n}_r{b_r}"
                if tag in done:
                    continue
                try:
                    emit(run_direct_leg(tag, 'B', cut_b, win_b, n=b_n, r=b_r,
                                        take=0.80, stop=0.25, exp=0.9))
                except Exception as e:
                    print('FAIL', tag, e, flush=True)

def stage_aleg():
    done = done_tags()
    for cut_a in [0.70, 0.78, 0.80, 0.90]:
        for win_a in [15, 20, 30, 40]:
            for a_n in [3, 4, 5, 6]:
                tag = f"A_c{cut_a}_w{win_a}_n{a_n}"
                if tag in done:
                    continue
                try:
                    emit(run_direct_leg(tag, 'A', cut_a, win_a, n=a_n, r=20,
                                        take=1.2, stop=0.25, exp=1.0))
                except Exception as e:
                    print('FAIL', tag, e, flush=True)

def best_bshapes(k=8):
    rows = [r for r in load_prog() if r.get('params', {}).get('leg') == 'lock_B']
    rows.sort(key=lambda r: (r.get('2024_yoy') if r.get('2024_yoy') is not None else -999), reverse=True)
    out = []
    for r in rows[:k]:
        pr = r['params']
        out.append((pr['cut_b'], pr['win_b'], pr['b_n'], pr['b_r']))
    return list(dict.fromkeys(out)) or [(0.70, 40, 3, 30), (0.70, 30, 3, 30)]

def stage_s1b():
    done = done_tags()
    for (cut_b, win_b, b_n, b_r) in best_bshapes(6):
        for stop in [0.20, 0.25, 0.30, 0.35]:
            for b_take in [0.45, 0.60, 0.80, 1.00, 1.20]:
                for b_exp in [0.9, 1.0]:
                    tag = f"B_c{cut_b}_w{win_b}_n{b_n}_r{b_r}_s{stop}_t{b_take}_e{b_exp}"
                    if tag in done:
                        continue
                    try:
                        emit(run_direct_leg(tag, 'B', cut_b, win_b, stop=stop,
                                            take=b_take, n=b_n, r=b_r, exp=b_exp))
                    except Exception as e:
                        print('FAIL', tag, e, flush=True)

def stage_s2():
    done = done_tags()
    rows = [r for r in load_prog() if r.get('params', {}).get('leg') == 'lock_B']
    rows.sort(key=lambda r: (r.get('2024_yoy') if r.get('2024_yoy') is not None else -999), reverse=True)
    bshapes = []
    for r in rows[:8]:
        pr = r['params']
        bshapes.append((pr['cut_b'], pr['win_b'], pr['b_n'], pr['b_r'], pr['stop'], pr['b_take'], pr['b_exp']))
    bshapes = list(dict.fromkeys(bshapes)) or [(0.70, 40, 3, 30, 0.25, 0.80, 0.9)]
    ashapes = [(0.80, 40, 5, 1.2), (0.78, 40, 5, 1.2), (0.80, 30, 5, 1.2), (0.70, 40, 3, 0.8)]
    for (cut_b, win_b, b_n, b_r, stop, b_take, b_exp) in bshapes:
        for (cut_a, win_a, a_n, a_take) in ashapes:
            for rs in [30, 60, 90]:
                for (bx, by_, bf) in [(0.18, 0.08, 0.6), (0.15, 0.05, 0.7), (0.12, 0.03, 0.5), (0.22, 0.10, 0.8)]:
                    for lock in [None, 'B', 'A']:
                        for a_r in [20, 30]:
                            tag = f"S_a{cut_a}_{win_a}_{a_n}_b{cut_b}_{win_b}_{b_n}_r{a_r}{b_r}_rs{rs}_br{bx}_{by_}_{bf}_lk{lock}"
                            if tag in done:
                                continue
                            try:
                                emit(run_switch(tag, cut_a=cut_a, win_a=win_a, cut_b=cut_b, win_b=win_b,
                                    stop=stop, a_take=a_take, b_take=b_take, a_n=a_n, b_n=b_n,
                                    a_r=a_r, b_r=b_r, b_exp=b_exp, rs=rs, bx=bx, by_=by_, bf=bf,
                                    lock=lock, evalfreq='grid'))
                            except Exception as e:
                                print('FAIL', tag, e, flush=True)

def stage_s3():
    done = done_tags()
    rows = [r for r in load_prog() if r.get('params', {}).get('leg') is None]
    rows.sort(key=lambda r: (r.get('2024_yoy') if r.get('2024_yoy') is not None else -999), reverse=True)
    seeds = rows[:10]
    if not seeds:
        print('no s2 seeds', flush=True); return
    for s in seeds:
        pr = dict(s['params'])
        base = dict(cut_a=pr['cut_a'], win_a=pr['win_a'], cut_b=pr['cut_b'], win_b=pr['win_b'],
                    stop=pr['stop'], a_take=pr['a_take'], b_take=pr['b_take'], a_n=pr['a_n'],
                    b_n=pr['b_n'], a_r=pr['a_r'], b_r=pr['b_r'], b_exp=pr['b_exp'], rs=pr['rs'],
                    bx=pr['bx'], by_=pr['by'], bf=pr['bf'], lock=pr['lock'])
        for evalfreq, hyst in [('grid', 0.0), ('daily', 0.0), ('daily', 0.03), ('daily', 0.08)]:
            for rs in list(dict.fromkeys([base['rs'], 30, 60, 90])):
                for (bx, by_, bf) in list(dict.fromkeys([(base['bx'], base['by_'], base['bf']), (0.15, 0.05, 0.7), (0.12, 0.03, 0.6)])):
                    tag = f"R_{s['tag']}_e{evalfreq}h{hyst}_rs{rs}_br{bx}_{by_}_{bf}"
                    if tag in done:
                        continue
                    try:
                        emit(run_switch(tag, rs=rs, bx=bx, by_=by_, bf=bf, evalfreq=evalfreq, hyst=hyst,
                            **{k: v for k, v in base.items() if k not in ('rs', 'bx', 'by_', 'bf')}))
                    except Exception as e:
                        print('FAIL', tag, e, flush=True)
        for stop in list(dict.fromkeys([base['stop'], 0.20, 0.25, 0.30, 0.35])):
            for b_take in list(dict.fromkeys([base['b_take'], 0.45, 0.60, 0.80, 1.20])):
                for b_n in list(dict.fromkeys([base['b_n'], 3, 4, 5, 6])):
                    tag = f"R_{s['tag']}_s{stop}_t{b_take}_n{b_n}"
                    if tag in done:
                        continue
                    try:
                        emit(run_switch(tag, stop=stop, b_take=b_take, b_n=b_n,
                            **{k: v for k, v in base.items() if k not in ('stop', 'b_take', 'b_n')},
                            evalfreq='grid', hyst=0.0))
                    except Exception as e:
                        print('FAIL', tag, e, flush=True)

def stage_final():
    cands = load_prog()
    cands.sort(key=lambda r: (r.get('2024_yoy') if r.get('2024_yoy') is not None else -999), reverse=True)
    seen = set(); short = []
    for r in cands:
        key = json.dumps(r.get('params', {}), sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        short.append(r)
        if len(short) >= 40:
            break
    rows = []
    for r in short:
        pr = r['params']
        tag = 'F_' + r['tag']
        try:
            if pr.get('leg') == 'lock_A':
                rr = run_direct_leg(tag, 'A', pr['cut_a'], pr['win_a'], stop=pr['stop'],
                    take=pr['a_take'], n=pr['a_n'], r=pr.get('a_r', 20), exp=1.0)
            elif pr.get('leg') == 'lock_B':
                rr = run_direct_leg(tag, 'B', pr['cut_b'], pr['win_b'], stop=pr['stop'],
                    take=pr['b_take'], n=pr['b_n'], r=pr.get('b_r', 30), exp=pr.get('b_exp', 0.9))
            else:
                rr = run_switch(tag, cut_a=pr['cut_a'], win_a=pr['win_a'], cut_b=pr['cut_b'], win_b=pr['win_b'],
                    stop=pr['stop'], a_take=pr['a_take'], b_take=pr['b_take'], a_n=pr['a_n'], b_n=pr['b_n'],
                    a_r=pr.get('a_r', 20), b_r=pr.get('b_r', 30), b_exp=pr.get('b_exp', 0.9), rs=pr.get('rs', 60),
                    bx=pr.get('bx', 0.18), by_=pr.get('by', 0.08), bf=pr.get('bf', 0.6), lock=pr.get('lock'),
                    evalfreq=pr.get('evalfreq', 'grid'), hyst=pr.get('hyst', 0.0) or 0.0,
                    brake_daily=pr.get('brake_daily', False))
            rows.append(rr)
            print(json.dumps({k: rr.get(k) for k in ['tag','total','mdd','2024','2024_mdd','2024_yoy','2025_yoy','2026_yoy','switches','trades','cost']}, ensure_ascii=False), flush=True)
        except Exception as e:
            print('FAIL final', tag, e, flush=True)
    rows.sort(key=lambda r: (r.get('2024_yoy') if r.get('2024_yoy') is not None else -999), reverse=True)
    open(ROOT/'results'/'r30_bt'/'search_A_spark_annual.json', 'w').write(json.dumps(rows, ensure_ascii=False, indent=1))
    print('saved final', len(rows), flush=True)
    print('PASSES:', sum(1 for r in rows if ok2024(r)), flush=True)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--stage', default='b07')
    ap.add_argument('--cut', type=float, default=0.70)
    a = ap.parse_args()
    t0 = time.time()
    {'bcut': lambda: stage_bcut(a.cut), 'aleg': stage_aleg, 's1b': stage_s1b,
     's2': stage_s2, 's3': stage_s3, 'final': stage_final}[a.stage]()
    print('elapsed', round(time.time()-t0, 1), flush=True)
