#!/usr/bin/env python3
"""Route-A stage2: brake/rs/exposure refine around two B-leg bases (realshares_v2).
Caliber: RUN_START=2023-01-03 EVAL_END=2026-11-12 capital 5w slip 0.002 lot 100
long-only exposure<=1. Switch decision uses t-and-earlier shadow RS only,
executed t+1 close in round lots; brake evaluated/acted on rebalance days only.
No lookahead, no future quantiles. Annual defs match bt_m07_family_rs2_annual.py:
slice=last/first-1 within year; yoy=year_end/prev_year_end-1; mdd=yearly max DD.
Bases (from search_A_spark_prog.jsonl, direct-leg, no brake):
  B1: cut_b=0.8 win_b=20 b_n=3 b_r=30 stop=0.25 b_take=0.80 -> 2024_yoy 60.44, 2024_mdd -32.75 (FAIL mdd)
  B2: cut_b=0.9 win_b=15 b_n=3 b_r=30 stop=0.25 b_take=0.80 -> 2024_yoy 60.06, 2024_mdd -32.71 (FAIL mdd)
Sweep (lock_B via switch engine so brake applies):
  bx in {0.15,0.18,0.22} x by in {0.05,0.08,0.10} x bf in {0.5,0.6,0.7}
  x rs in {60,90} x b_exp in {0.9,1.0}  (=108/base)
  + lock=None switch对照 2 brakes x 2 rs x 2 exp (=8/base)
Usage:
  .venv/bin/python -u research/search_A_stage2.py --base B1   # background-safe, appends jsonl
  .venv/bin/python -u research/search_A_stage2.py --base B2
  .venv/bin/python research/search_A_stage2.py --combine     # -> search_A_stage2.json
"""
import sys, json, time, argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'team/audit')); sys.path.insert(0, str(ROOT/'research'))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, RUN_START, EVAL_END, MB

OUT_JSONL = ROOT/'results'/'r30_bt'/'search_A_stage2_prog.jsonl'
OUT_JSON = ROOT/'results'/'r30_bt'/'search_A_stage2.json'
print('RUN', RUN_START, EVAL_END, flush=True)
piv = pd.read_pickle(ROOT/'data'/'pivots_2020_clean_realshares_v2.pkl')
dates = piv['close'].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
print('first_sig', first_sig, flush=True)

_leg = {}
_ns = {}

BASES = {
    'B1': dict(cut_b=0.80, win_b=20, b_n=3, b_r=30, stop=0.25, b_take=0.80),
    'B2': dict(cut_b=0.90, win_b=15, b_n=3, b_r=30, stop=0.25, b_take=0.80),
}
A_SIDE = dict(cut_a=0.80, win_a=40, a_n=5, a_r=20, a_take=1.20)

def get_ns(bx, by_, bf):
    k = (bx, by_, bf)
    if k not in _ns:
        _ns[k] = build_ns(bx, by_, bf)
    return _ns[k]

def leg(side, cut, win, stop, take, n, r, exp):
    key = (side, cut, win, stop, take, n, r, exp)
    if key in _leg:
        return _leg[key]
    inp = (MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=cut, max_win=win) if side == 'A'
           else MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=cut, max_win=win))
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
        y[str(yr)+'_yoy'] = round(float(sub.iloc[-1]/prev_end-1)*100, 2) if prev_end is not None else round(sret, 2)
        prev_end = float(sub.iloc[-1])
    try:
        b = y.get('2026_bars', 0); yy = y.get('2026_yoy')
        y['2026_yoy_ann'] = round(((1+yy/100.0)**(252.0/b)-1)*100, 2) if (b and yy is not None and yy > -100) else None
    except Exception:
        y['2026_yoy_ann'] = None
    return y

def ok2024(r):
    try:
        return (r['2024'] > 60 and r['2024_yoy'] > 60
                and r['2025_yoy'] > 60 and r['2026_yoy'] > 60
                and r['mdd'] > -30 and r['2024_mdd'] > -30
                and r['2025_mdd'] > -30 and r['2026_mdd'] > -30)
    except Exception:
        return False

def emit(row):
    with open(OUT_JSONL, 'a') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(json.dumps({k: row.get(k) for k in ['tag','total','mdd','2024','2024_mdd','2024_yoy','2025_yoy','2026_yoy','2026_yoy_ann','switches','brakes','trades','cost']}, ensure_ascii=False), flush=True)
    if ok2024(row):
        print('*** PASS2024 *** ' + row['tag'], flush=True)

def run_lockB(tag, base, bx, by_, bf, rs, b_exp, lock='B'):
    cut_b, win_b, b_n, b_r, stop, b_take = (base['cut_b'], base['win_b'], base['b_n'], base['b_r'], base['stop'], base['b_take'])
    cut_a, win_a, a_n, a_r, a_take = (A_SIDE['cut_a'], A_SIDE['win_a'], A_SIDE['a_n'], A_SIDE['a_r'], A_SIDE['a_take'])
    inp_a, ra, CA, _ = leg('A', cut_a, win_a, stop, a_take, a_n, a_r, 1.0)
    inp_b, rb, _, CFG_B = leg('B', cut_b, win_b, stop, b_take, b_n, b_r, b_exp)
    base_kw = {k: v for k, v in CA.items() if k != 'exclude'}
    KW = dict(n=a_n, rebal=a_r, take=a_take, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B,
              shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB, **base_kw)
    res = get_ns(bx, by_, bf)['run_strategy_switch'](inp_a, lock_mode=lock, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    params = dict(family='M07', cut_a=cut_a, win_a=win_a, cut_b=cut_b, win_b=win_b, stop=stop,
                  a_take=a_take, b_take=b_take, a_n=a_n, b_n=b_n, a_r=a_r, b_r=b_r, b_exp=b_exp,
                  rs=rs, bx=bx, by=by_, bf=bf, lock=lock, evalfreq='grid', hyst=0.0,
                  brake='rebal_days_only', brake_daily=False, exposure_le_1=True,
                  cost='realistic+slip0.002', lot=100)
    out = {'tag': tag, 'eq_len': int(len(eq)), 'eq_start': str(eq.index[0].date()), 'eq_end': str(eq.index[-1].date()),
           'total': round(float(eq.iloc[-1]/eq.iloc[0]-1)*100, 2), 'mdd': round(_mdd(eq)*100, 2),
           'trades': len(res.trades), 'cost': round(float(res.meta['total_cost']), 0),
           'mode': res.meta.get('final_mode'), 'switches': len(res.meta.get('switch_log', [])),
           'brakes': len(res.meta.get('brake_log', []))//2,
           'brake_log': [[str(d), s, v] for (d, s, v) in res.meta.get('brake_log', [])],
           'switch_log': [[str(d), m] for (d, m) in res.meta.get('switch_log', [])],
           'params': params}
    out.update(yearly(eq))
    return out

def done_tags():
    s = set()
    if OUT_JSONL.exists():
        for line in open(OUT_JSONL):
            line = line.strip()
            if line:
                try:
                    s.add(json.loads(line)['tag'])
                except Exception:
                    pass
    return s

def stage_base(name):
    base = BASES[name]
    done = done_tags()
    n = 0
    for bx in [0.15, 0.18, 0.22]:
        for by_ in [0.05, 0.08, 0.10]:
            for bf in [0.5, 0.6, 0.7]:
                for rs in [60, 90]:
                    for b_exp in [0.9, 1.0]:
                        tag = f"S2_{name}_bx{bx}_by{by_}_bf{bf}_rs{rs}_e{b_exp}"
                        if tag in done:
                            continue
                        try:
                            emit(run_lockB(tag, base, bx, by_, bf, rs, b_exp, lock='B'))
                        except Exception as e:
                            print('FAIL', tag, e, flush=True)
                        n += 1
    for (bx, by_, bf) in [(0.15, 0.05, 0.7), (0.18, 0.08, 0.6)]:
        for rs in [60, 90]:
            for b_exp in [0.9, 1.0]:
                tag = f"S2_{name}_SW_bx{bx}_by{by_}_bf{bf}_rs{rs}_e{b_exp}"
                if tag in done:
                    continue
                try:
                    emit(run_lockB(tag, base, bx, by_, bf, rs, b_exp, lock=None))
                except Exception as e:
                    print('FAIL', tag, e, flush=True)
                n += 1
    print(f'done {name} new={n}', flush=True)

def stage_combine():
    rows = []
    for line in open(OUT_JSONL):
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    rows.sort(key=lambda r: (r.get('2024_yoy') if r.get('2024_yoy') is not None else -999), reverse=True)
    open(OUT_JSON, 'w').write(json.dumps(rows, ensure_ascii=False, indent=1))
    print('saved', OUT_JSON, len(rows), flush=True)
    print('PASSES:', sum(1 for r in rows if ok2024(r)), flush=True)
    print('TOP by 2024_yoy:', flush=True)
    for r in rows[:8]:
        print(json.dumps({k: r.get(k) for k in ['tag','total','mdd','2024','2024_mdd','2024_yoy','2025_yoy','2026_yoy','2026_yoy_ann','switches','brakes','trades','cost']}, ensure_ascii=False), flush=True)
    print('TOP mdd-passing (full & yearly >-30) by 2024_yoy:', flush=True)
    ok = [r for r in rows if r['mdd'] > -30 and r['2024_mdd'] > -30 and r['2025_mdd'] > -30 and r['2026_mdd'] > -30]
    ok.sort(key=lambda r: r['2024_yoy'], reverse=True)
    for r in ok[:8]:
        print(json.dumps({k: r.get(k) for k in ['tag','total','mdd','2024','2024_mdd','2024_yoy','2025_yoy','2026_yoy','2026_yoy_ann','switches','brakes','trades','cost']}, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--base', default=''); ap.add_argument('--combine', action='store_true')
    a = ap.parse_args()
    t0 = time.time()
    if a.combine:
        stage_combine()
    else:
        stage_base(a.base)
    print('elapsed', round(time.time()-t0, 1), flush=True)
