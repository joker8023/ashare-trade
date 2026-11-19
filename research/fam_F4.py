"""F4 amount复合族搜索. A腿M07固定, B腿DInputs amount/c_a60_size/c_a60_amt/c_a60_a5."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'team' / 'audit'))
sys.path.insert(0, str(ROOT / 'research'))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import _mdd, RUN_START, EVAL_END, MB
from switch_ns import build_ns, atomic_write_json  # 唯一实现(C2 fixed 语义): 旧内联版缺 min_hold 持有期保护, daily+mh>0 配置需重跑




piv = pd.read_pickle(ROOT / 'data' / 'pivots_2020_clean_realshares_v2.pkl')
dates = piv['close'].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
print('RUN ' + str(RUN_START) + ' EVAL_END=' + str(EVAL_END) + ' first_sig=' + str(first_sig), flush=True)

SEL_LIST = ['amount', 'c_a60_size', 'c_a60_amt', 'c_a60_a5']
N_LIST = [4, 5, 6]
R_LIST = [15, 20, 30]
TP_LIST = [0.45, 0.6, 0.8, 1.0, 1.2]
BRAKES = [(0.15, 0.10, 0.5), (0.15, 0.10, 0.7), (0.15, 0.05, 0.5), (0.18, 0.08, 0.6), (0.12, 0.06, 0.5)]
SWITCHES = [
    dict(key='grid', hyst=0.0, mh=0, evalfreq='grid', brake_daily=False),
    dict(key='d_h003_mh0_bd', hyst=0.03, mh=0, evalfreq='daily', brake_daily=True),
    dict(key='d_h003_mh10_bd', hyst=0.03, mh=10, evalfreq='daily', brake_daily=True),
    dict(key='d_h002_mh10_bg', hyst=0.02, mh=10, evalfreq='daily', brake_daily=False),
]
BAND_GATE = [((0.05, 0.30), -1.0), ((0.02, 0.30), -1.0), ((0.05, 0.30), -0.15)]

inpA = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
CA = dict(factor='amihud_60', stop=0.25, stop_exec='next', exclude=MB, capital=50000.0,
          lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
          eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
print('building shadow A(N5/R20/take1.2)...', flush=True)
ra = pc.run_strategy(inpA, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
print('shadow A ready trades=%d' % len(ra.trades), flush=True)

_ns = {}
def get_ns(bx, by_, bf, hyst, mh, cf=1):
    k = (bx, by_, bf, hyst, mh, cf)
    if k not in _ns:
        _ns[k] = build_ns(bx, by_, bf, hyst, mh, cf)
    return _ns[k]

def get_shadowB(sel, band, gate, cut, win, n, r, tp):
    # no cross-run cache: each DInputs carries 3 full rolling matrices (~200MB);
    # caching OOM-killed phase1. Build fresh; locals freed on return (only eq kept).
    inp = DInputs(piv, band=band, gate60=gate, max_cut=cut, max_win=win, sel=sel)
    rb = pc.run_strategy(inp, n=n, rebal=r, take=tp, exposure=0.9, phase=0,
                         **dict(CA, factor='amihud_60'))
    return inp, rb.eq

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
            out[str(y)] = None
            continue
        sret = float(sub.iloc[-1] / sub.iloc[0] - 1) * 100
        out[str(y)] = round(sret, 2)
        out[str(y) + '_mdd'] = round(_mdd(sub) * 100, 2)
        out[str(y) + '_bars'] = int(len(sub))
        out[str(y) + '_yoy'] = round((float(sub.iloc[-1] / prev_end - 1) * 100) if prev_end is not None else sret, 2)
        prev_end = float(sub.iloc[-1])
    ok = (out['2024'] is not None and out['2024'] > 60 and out['2024_yoy'] is not None and out['2024_yoy'] > 60
          and out['2025_yoy'] is not None and out['2025_yoy'] > 60
          and out['2026'] is not None and out['2026'] > 60 and out['2026_yoy'] is not None and out['2026_yoy'] > 60
          and out['mdd'] is not None and out['mdd'] > -30 and out['2024_mdd'] is not None and out['2024_mdd'] > -30
          and out['2025_mdd'] is not None and out['2025_mdd'] > -30 and out['2026_mdd'] is not None and out['2026_mdd'] > -30)
    out['pass'] = bool(ok)
    try:
        out['margin'] = round(min(out['2024'] - 60, out['2024_yoy'] - 60, out['2025_yoy'] - 60,
                                  out['2026'] - 60, out['2026_yoy'] - 60, out['mdd'] + 30,
                                  out['2024_mdd'] + 30, out['2025_mdd'] + 30, out['2026_mdd'] + 30), 2)
    except Exception:
        out['margin'] = None
    pe = float(eq.iloc[-1] - eq.iloc[0])
    out['cost_eff'] = round(pe / float(res.meta['total_cost']), 2) if float(res.meta['total_cost']) > 0 else None
    return out

def run_one(tag, sel='amount', n=4, r=30, tp=0.8, cut=0.70, win=20, band=(0.05, 0.30), gate=-1.0,
            bx=0.15, by_=0.10, bf=0.5, hyst=0.0, mh=0, cf=1, evalfreq='grid', brake_daily=False,
            rs=60, lock=None):
    inp_b, sh_b = get_shadowB(sel, band, gate, cut, win, n, r, tp)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b,
              cfg_b=dict(n=n, rebal=r, take=tp, exposure=0.9),
              shadow_a=ra.eq, shadow_b=sh_b, rs_lookback=rs, exclude_a=MB, exclude_b=MB,
              evalfreq=evalfreq, brake_daily=brake_daily)
    for k, v in CA.items():
        if k != 'exclude':
            KW[k] = v
    ns = get_ns(bx, by_, bf, hyst, mh, cf)
    res = ns['run_strategy_switch'](inpA, lock_mode=lock, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    cfg = dict(sel=sel, n=n, r=r, tp=tp, cut=cut, win=win, band=list(band), gate=gate,
               bx=bx, by_=by_, bf=bf, hyst=hyst, min_hold=mh, confirm=cf,
               evalfreq=evalfreq, brake_daily=brake_daily, rs=rs, lock=lock)
    return annual_out(eq, res, tag, cfg), eq

SLIM = ('tag', 'total', 'mdd', 'calmar', 'sharpe', '2024', '2024_yoy', '2024_mdd',
        '2025_yoy', '2025_mdd', '2026', '2026_yoy', '2026_mdd', 'trades', 'cost', 'cost_eff',
        'switches', 'brakes', 'mode', 'avg_exp', 'max_exp', 'pass', 'margin')

def phase1_cfgs(only_sel=None):
    out = []
    for sel in SEL_LIST:
        if only_sel and sel != only_sel:
            continue
        for n in N_LIST:
            for r in R_LIST:
                for tp in TP_LIST:
                    tps = str(tp).replace('.', '')
                    out.append(dict(tag='F4_' + sel + '_N' + str(n) + '_R' + str(r) + '_T' + tps,
                                    sel=sel, n=n, r=r, tp=tp))
    return out

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', default='all')
    ap.add_argument('--only', default=None)
    ap.add_argument('--out', default='results/r30_bt/fam_F4_stage.json')
    ap.add_argument('--sel', default=None)
    args = ap.parse_args()
    if args.only:
        cfgs = phase1_cfgs()
        c = next((c for c in cfgs if c['tag'] == args.only), None)
        if c is None:
            print('only tag not in phase1 list: ' + str(args.only) + ' (only supports phase1 F4_* tags)', flush=True)
            return
        o, _e = run_one(**c)
        print(json.dumps({k: o[k] for k in SLIM}, ensure_ascii=False), flush=True)
        return
    rows = []
    if args.phase in ('phase1', 'all'):
        try:
            rows = json.loads(open(ROOT / args.out).read())
        except Exception:
            rows = []
        done = set(x.get('tag') for x in rows)
        for c in phase1_cfgs(args.sel):
            if c['tag'] in done:
                continue
            try:
                o, _e = run_one(**c)
                print(json.dumps({k: o[k] for k in SLIM}, ensure_ascii=False), flush=True)
                rows.append(o)
                if len(rows) % 5 == 0:
                    atomic_write_json(ROOT / args.out, rows)
            except Exception as e:
                print('FAIL ' + c['tag'] + ': ' + str(e), flush=True)
        atomic_write_json(ROOT / args.out, rows)
        print('saved phase1 rows=' + str(len(rows)), flush=True)
        if args.phase == 'phase1':
            return rows
    else:
        try:
            rows = json.loads(open(ROOT / args.out).read())
        except Exception:
            rows = []
    if args.phase in ('phase2', 'all'):
        base = rows if rows else []
        anchors = []
        for sel in SEL_LIST:
            pool = [x for x in base if x.get('cfg', {}).get('sel') == sel]
            pool = sorted(pool, key=lambda x: (x.get('margin', -999) or -999), reverse=True)[:3]
            anchors += pool
        if not anchors:
            anchors = [dict(tag='F4_' + s + '_N4_R30_T08', cfg=dict(sel=s, n=4, r=30, tp=0.8)) for s in SEL_LIST]
        print('ANCHORS: ' + json.dumps([(a['tag'], a.get('margin')) for a in anchors], ensure_ascii=False), flush=True)
        for a in anchors:
            c0 = a['cfg']
            sel, n, r, tp = c0['sel'], c0['n'], c0['r'], c0['tp']
            for (bx, by_, bf) in BRAKES:
                for sw in SWITCHES:
                    tag = a['tag'] + '_b' + str(bx).replace('.', '') + str(by_).replace('.', '') + str(bf).replace('.', '') + '_' + sw['key']
                    if any(x.get('tag') == tag for x in rows):
                        continue
                    try:
                        o, _e = run_one(tag, sel=sel, n=n, r=r, tp=tp, bx=bx, by_=by_, bf=bf,
                                        hyst=sw['hyst'], mh=sw['mh'], evalfreq=sw['evalfreq'], brake_daily=sw['brake_daily'])
                        print(json.dumps({k: o[k] for k in SLIM}, ensure_ascii=False), flush=True)
                        rows.append(o)
                        if len(rows) % 10 == 0:
                            atomic_write_json(ROOT / args.out, rows)
                    except Exception as e:
                        print('FAIL ' + tag + ': ' + str(e), flush=True)
            for (band, gate) in BAND_GATE[1:]:
                tag = a['tag'] + '_band' + str(band[1]).replace('.', '') + '_g' + str(gate).replace('.', '').replace('-', 'm')
                if any(x.get('tag') == tag for x in rows):
                    continue
                try:
                    o, _e = run_one(tag, sel=sel, n=n, r=r, tp=tp, band=band, gate=gate)
                    print(json.dumps({k: o[k] for k in SLIM}, ensure_ascii=False), flush=True)
                    rows.append(o)
                except Exception as e:
                    print('FAIL ' + tag + ': ' + str(e), flush=True)
            for cut, win in [(0.60, 20), (0.80, 20), (0.70, 10), (0.70, 40)]:
                tag = a['tag'] + '_c' + str(cut).replace('.', '') + '_w' + str(win)
                if any(x.get('tag') == tag for x in rows):
                    continue
                try:
                    o, _e = run_one(tag, sel=sel, n=n, r=r, tp=tp, cut=cut, win=win)
                    print(json.dumps({k: o[k] for k in SLIM}, ensure_ascii=False), flush=True)
                    rows.append(o)
                except Exception as e:
                    print('FAIL ' + tag + ': ' + str(e), flush=True)
        for sel in SEL_LIST:
            pool = [x for x in rows if x.get('cfg', {}).get('sel') == sel]
            pool = sorted(pool, key=lambda x: (x.get('margin', -999) or -999), reverse=True)
            if not pool:
                continue
            best = pool[0]['cfg']
            tag = 'F4_lockB_' + sel + '_N' + str(best['n']) + '_R' + str(best['r']) + '_T' + str(best['tp']).replace('.', '')
            if any(x.get('tag') == tag for x in rows):
                continue
            try:
                o, _e = run_one(tag, sel=sel, n=best['n'], r=best['r'], tp=best['tp'],
                                cut=best.get('cut', 0.70), win=best.get('win', 20),
                                band=tuple(best.get('band', (0.05, 0.30))), gate=best.get('gate', -1.0),
                                lock='B')
                print(json.dumps({k: o[k] for k in SLIM}, ensure_ascii=False), flush=True)
                rows.append(o)
            except Exception as e:
                print('FAIL ' + tag + ': ' + str(e), flush=True)
    atomic_write_json(ROOT / args.out, rows)
    rs = sorted(rows, key=lambda r: (bool(r.get('pass')), r.get('margin', -999) or -999, r.get('total', 0)), reverse=True)
    print('=== F4 TOP10 ===', flush=True)
    for b in rs[:10]:
        print(json.dumps({k: b[k] for k in SLIM}, ensure_ascii=False), flush=True)
    print('saved rows=' + str(len(rows)) + ' npass=' + str(sum(1 for r in rows if r.get('pass'))), flush=True)
    return rows

def run_bsole(tag, sel='c_a60_a5', n=5, r=30, tp=0.8, cut=0.70, win=20, band=(0.05, 0.30), gate=-1.0):
    import gc
    inp = DInputs(piv, band=band, gate60=gate, max_cut=cut, max_win=win, sel=sel)
    rb = pc.run_strategy(inp, n=n, rebal=r, take=tp, exposure=0.9, phase=0,
                         **dict(CA, factor='amihud_60'))
    eq = rb.eq.iloc[:, 0] if isinstance(rb.eq, pd.DataFrame) else rb.eq
    eq = eq.dropna()
    to = float(eq.iloc[-1] / eq.iloc[0] - 1) * 100
    md = _mdd(eq) * 100
    out = {'tag': tag, 'total': round(to, 2), 'mdd': round(md, 2),
           'trades': int(len(rb.trades)), 'cost': round(float(rb.meta['total_cost']), 0)}
    prev = None
    for y in [2023, 2024, 2025, 2026]:
        sub = eq[eq.index.year == y]
        s = float(sub.iloc[-1] / sub.iloc[0] - 1) * 100
        out[str(y)] = round(s, 2)
        out[str(y) + '_mdd'] = round(_mdd(sub) * 100, 2)
        out[str(y) + '_yoy'] = round((float(sub.iloc[-1] / prev - 1) * 100) if prev is not None else s, 2)
        prev = float(sub.iloc[-1])
    out['cfg'] = dict(sel=sel, n=n, r=r, tp=tp, cut=cut, win=win, band=list(band), gate=gate, lock='Bsole')
    out['pass'] = bool(out['2024'] > 60 and out['2024_yoy'] > 60 and out['2025_yoy'] > 60
                        and out['2026'] > 60 and out['2026_yoy'] > 60 and out['mdd'] > -30)
    del inp, rb
    gc.collect()
    return out

def main_phase3(args):
    rows = json.loads(open(ROOT / args.out).read())
    pool = [x for x in rows if x.get('cfg', {}).get('lock') is None and not x['tag'].startswith('F4_lockB')]
    anchors = sorted(pool, key=lambda x: (x.get('margin', -999) or -999), reverse=True)[:2]
    print('PH3_ANCHORS: ' + json.dumps([(a['tag'], a.get('margin')) for a in anchors], ensure_ascii=False), flush=True)
    RS_LIST = [30, 45, 90]
    BRAKES3 = [(0.15, 0.10, 0.5), (0.12, 0.06, 0.5), (0.18, 0.08, 0.6)]
    SWITCHES3 = SWITCHES + [dict(key='d_h005_mh0_bd', hyst=0.05, mh=0, evalfreq='daily', brake_daily=True)]
    for a in anchors:
        c0 = a['cfg']
        sel, n, r, tp = c0['sel'], c0['n'], c0['r'], c0['tp']
        for rs in RS_LIST:
            for (bx, by_, bf) in BRAKES3:
                for sw in SWITCHES3:
                    tag = a['tag'] + '_rs%d_b%s%s%s_%s' % (rs, str(bx).replace('.', ''), str(by_).replace('.', ''), str(bf).replace('.', ''), sw['key'])
                    if any(x.get('tag') == tag for x in rows):
                        continue
                    try:
                        o, _e = run_one(tag, sel=sel, n=n, r=r, tp=tp, bx=bx, by_=by_, bf=bf,
                                        hyst=sw['hyst'], mh=sw['mh'], evalfreq=sw['evalfreq'],
                                        brake_daily=sw['brake_daily'], rs=rs)
                        print(json.dumps({k: o[k] for k in SLIM}, ensure_ascii=False), flush=True)
                        rows.append(o)
                        if len(rows) % 10 == 0:
                            atomic_write_json(ROOT / args.out, rows)
                    except Exception as e:
                        print('FAIL ' + tag + ': ' + str(e), flush=True)
    if not any(x.get('tag') == 'F4_lockA_M07' for x in rows):
        try:
            o, _e = run_one('F4_lockA_M07', sel='c_a60_a5', n=5, r=30, tp=0.8, lock='A')
            print(json.dumps({k: o[k] for k in SLIM}, ensure_ascii=False), flush=True)
            rows.append(o)
        except Exception as e:
            print('FAIL F4_lockA_M07: ' + str(e), flush=True)
    atomic_write_json(ROOT / args.out, rows)
    rs = sorted(rows, key=lambda r: (bool(r.get('pass')), r.get('margin', -999) or -999, r.get('total', 0)), reverse=True)
    print('=== F4 PH3 TOP10 ===', flush=True)
    for b in rs[:10]:
        print(json.dumps({k: b[k] for k in SLIM}, ensure_ascii=False), flush=True)
    print('saved rows=' + str(len(rows)) + ' npass=' + str(sum(1 for r in rows if r.get('pass'))), flush=True)

def main_bsole(args):
    outp = ROOT / 'results' / 'r30_bt' / 'fam_F4_bsole.json'
    try:
        rows = json.loads(open(outp).read())
    except Exception:
        rows = []
    done = set(x.get('tag') for x in rows)
    for sel in SEL_LIST:
        for n in N_LIST:
            for r in R_LIST:
                for tp in TP_LIST:
                    tag = 'BS_' + sel + '_N' + str(n) + '_R' + str(r) + '_T' + str(tp).replace('.', '')
                    if tag in done:
                        continue
                    try:
                        o = run_bsole(tag, sel=sel, n=n, r=r, tp=tp)
                        print(json.dumps(o, ensure_ascii=False), flush=True)
                        rows.append(o)
                        if len(rows) % 10 == 0:
                            atomic_write_json(outp, rows)
                    except Exception as e:
                        print('FAIL ' + tag + ': ' + str(e), flush=True)
    atomic_write_json(outp, rows)
    okn = sum(1 for x in rows if x.get('pass'))
    print('bsole saved rows=' + str(len(rows)) + ' npass=' + str(okn), flush=True)
    for b in sorted(rows, key=lambda x: (x.get('2024', -999) or -999), reverse=True)[:8]:
        print(json.dumps(b, ensure_ascii=False), flush=True)

def main_phase4(args):
    rows = json.loads(open(ROOT / args.out).read())
    ANCH = [
        ('c_a60_a5', 5, 30, 0.8),
        ('c_a60_a5', 5, 30, 1.0),
    ]
    RS4 = [20, 25, 30, 35, 40]
    BR4 = [(0.10, 0.05, 0.5), (0.10, 0.06, 0.5), (0.12, 0.05, 0.5),
           (0.12, 0.06, 0.5), (0.12, 0.06, 0.6), (0.12, 0.08, 0.5), (0.15, 0.06, 0.5)]
    SW4 = [dict(key='grid', hyst=0.0, mh=0, evalfreq='grid', brake_daily=False)]
    for (sel, n, r, tp) in ANCH:
        base = 'F4_%s_N%d_R%d_T%s' % (sel, n, r, str(tp).replace('.', ''))
        for rs in RS4:
            for (bx, by_, bf) in BR4:
                for sw in SW4:
                    tag = base + '_rs%d_b%s%s%s_%s' % (rs, str(bx).replace('.', ''), str(by_).replace('.', ''), str(bf).replace('.', ''), sw['key'])
                    if any(x.get('tag') == tag for x in rows):
                        continue
                    try:
                        o, _e = run_one(tag, sel=sel, n=n, r=r, tp=tp, bx=bx, by_=by_, bf=bf,
                                        hyst=sw['hyst'], mh=sw['mh'], evalfreq=sw['evalfreq'],
                                        brake_daily=sw['brake_daily'], rs=rs)
                        print(json.dumps({k: o[k] for k in SLIM}, ensure_ascii=False), flush=True)
                        rows.append(o)
                        if len(rows) % 10 == 0:
                            atomic_write_json(ROOT / args.out, rows)
                    except Exception as e:
                        print('FAIL ' + tag + ': ' + str(e), flush=True)
    atomic_write_json(ROOT / args.out, rows)
    rs = sorted(rows, key=lambda r: (bool(r.get('pass')), r.get('margin', -999) or -999, r.get('total', 0)), reverse=True)
    print('=== F4 PH4 TOP10 ===', flush=True)
    for b in rs[:10]:
        print(json.dumps({k: b[k] for k in SLIM}, ensure_ascii=False), flush=True)
    print('saved rows=' + str(len(rows)) + ' npass=' + str(sum(1 for r in rows if r.get('pass'))), flush=True)

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', default='all')
    ap.add_argument('--out', default='results/r30_bt/fam_F4_stage.json')
    ap.add_argument('--sel', default=None)
    ap.add_argument('--only', default=None)
    a = ap.parse_args()
    if a.phase == 'phase3':
        main_phase3(a)
    elif a.phase == 'bsole':
        main_bsole(a)
    elif a.phase == 'phase4':
        main_phase4(a)
    else:
        main()