#!/usr/bin/env python3
# F7 c_a60_vol/size/amt-daily family search (realshares_v2 true-equity caliber, F1=C2_grid frozen).
# Caliber: RUN_START=2023-01-03 EVAL_END=2026-11-12, 50k, slip=0.002, lot=100,
#   real fees, stop=0.25 stop_exec=next, legacy_grid=False, full_liquidate=True,
#   long-only, exposure<=1, MB both legs excluded.
# A-leg fixed M07: MaxInputs band=(0.02,0.30) gate60=-0.15 cut=0.80 win=40,
#   n=5/R20/TP1.2/exp1.0.
# B-leg DInputs sel in {c_a60_vol(main), c_a60_size, c_a60_amt, vol20(backup)},
#   band=(0.05,0.30) gate60=-1.0 (gate off), stop=0.25, RS trailing-60 shadows.
# Selectors (trailing-only, no lookahead): c_a60_vol=rank-sum(amihud60,vol20);
#   c_a60_size=rank-sum(amihud60,size); c_a60_amt=rank-sum(amihud60,adv20);
#   vol20=trailing-20d std(daily ret) smallest wins (pure backup).
# Orthogonal vs F1/F2/F4/F5/F6: sel strings differ; F4 only grid-tested
#   c_a60_size/c_a60_amt (never daily); F5 batch-A only grid-tested c_a60_vol
#   (weak: 2024 slice ~6-18). This family = first daily deep-dig of these sels.
# Path: anchor N4/R15/TP0.45 @default brake grid rs60 -> daily rs12-60 x h0.02-0.05
#   -> brake bx0.12-0.22/by0.05-0.1/bf0.4-0.7; F6 lesson TP0.15/0.25 x R15/20 first.
# Strict pass: 2024_slice>60 & 2024_yoy>60 & 2025_yoy>60 & 2026_slice>60 & 2026_yoy>60
#   (2026 thru 11-12) & full & yearly mdd>-30.
# Usage: .venv/bin/python research/fam_F7.py [--stage A|B|C|D|E|V|all] [--groups D1..]
# Output: results/r30_bt/fam_F7_stage.json
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
F7_SELS = ("c_a60_vol", "c_a60_size", "c_a60_amt", "vol20")
# build_ns: single implementation from switch_ns (C2-fixed confirm semantics)
piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
print("RUN", RUN_START, EVAL_END, "first_sig", first_sig.date(), "F7 sels", F7_SELS, flush=True)
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
def run_switch(tag, sel, b_n=4, b_rebal=30, b_take=0.80, b_cut=0.70, b_win=20, band=(0.05, 0.30), gate=-1.0, bx=0.18, by_=0.08, bf=0.6, rs=60, hyst=0.0, mh=0, confirm=1, evalfreq='grid', brake_daily=False, stop=0.25, exp_b=0.9, lock=None, sw_stop=None):
    inp_b = get_inp_b(sel, band, gate, b_cut, b_win)
    CFG_B = dict(n=b_n, rebal=b_rebal, take=b_take, exposure=exp_b)
    rb = get_shadow_b(sel, band, gate, b_cut, b_win, b_n, b_rebal, b_take, stop, exp_b)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB, evalfreq=evalfreq, brake_daily=brake_daily)
    for k, v in CA.items():
        if k != 'exclude':
            KW[k] = v
    KW['stop'] = CA['stop']  # A leg always frozen 0.25; B-leg experiment stop goes via stop_b
    KW['stop_b'] = sw_stop if sw_stop is not None else stop
    ns = get_ns(bx, by_, bf, hyst, mh, confirm)
    res = ns['run_strategy_switch'](inpA, lock_mode=lock, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    an = annuals(eq)
    r = dict(tag=tag, fam='F7', b_sel=sel, b_band=list(band), b_gate=gate, b_n=b_n, b_rebal=b_rebal, b_take=b_take, b_cut=b_cut, b_win=b_win, bx=bx, by_=by_, bf=bf, rs=rs, hyst=hyst, mh=mh, confirm=confirm, evalfreq=evalfreq, brake_daily=brake_daily, stop=stop, exp_b=exp_b, lock=lock, sw_stop=(sw_stop if sw_stop is not None else stop), total=round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2), mdd=round(_mdd(eq) * 100, 2), trades=len(res.trades), cost=round(float(res.meta['total_cost']), 0), mode=res.meta['final_mode'], switches=len(res.meta['switch_log']), switch_log=[list(x) for x in res.meta['switch_log']], brake_log=[list(x) for x in res.meta.get('brake_log', [])], brakes=len(res.meta.get('brake_log', [])) // 2, eq_start=str(eq.index[0].date()), eq_end=str(eq.index[-1].date()), bars2026=207, y2023_yoy=an[2023]['yoy'], y2023_mdd=an[2023]['mdd'], y2024_slice=an[2024]['slice'], y2024_yoy=an[2024]['yoy'], y2024_mdd=an[2024]['mdd'], y2025_slice=an[2025]['slice'], y2025_yoy=an[2025]['yoy'], y2025_mdd=an[2025]['mdd'], y2026_slice=an[2026]['slice'], y2026_yoy=an[2026]['yoy'], y2026_mdd=an[2026]['mdd'])
    r['pass_all'] = bool(r['y2024_slice'] is not None and r['y2024_slice'] > 60 and r['y2024_yoy'] > 60 and r['y2025_yoy'] > 60 and r['y2026_slice'] is not None and r['y2026_slice'] > 60 and r['y2026_yoy'] > 60 and r['mdd'] > -30 and r['y2024_mdd'] > -30 and r['y2025_mdd'] > -30 and r['y2026_mdd'] > -30)
    r['margin'] = round(min(r['y2024_slice'] - 60, r['y2024_yoy'] - 60, r['y2025_yoy'] - 60, r['y2026_slice'] - 60, r['y2026_yoy'] - 60, r['mdd'] + 30, r['y2024_mdd'] + 30, r['y2025_mdd'] + 30, r['y2026_mdd'] + 30), 2)
    r['avg_exp'] = round(float(res.exposure.mean()), 4) if res.exposure is not None else None
    r['max_exp'] = round(float(res.exposure.max()), 4) if res.exposure is not None else None
    _pe = float(eq.iloc[-1] - eq.iloc[0])
    r['cost_eff'] = round(_pe / float(res.meta['total_cost']), 2) if float(res.meta['total_cost']) > 0 else None
    r['take_sells'] = int(res.meta.get('take_sells', 0))
    return r
F7_SELS4 = ("c_a60_vol", "c_a60_size", "c_a60_amt", "vol20")
F7_DEF_BRAKE = dict(bx=0.18, by_=0.08, bf=0.6)
F7_ANCHOR = dict(b_n=4, b_rebal=15, b_take=0.45, b_cut=0.70, b_win=20)

BRAKES_C = [(0.12, 0.05, 0.4), (0.12, 0.05, 0.5), (0.12, 0.06, 0.5), (0.12, 0.08, 0.6),
            (0.15, 0.08, 0.5), (0.15, 0.10, 0.5), (0.18, 0.08, 0.4), (0.18, 0.08, 0.7),
            (0.18, 0.10, 0.6), (0.22, 0.05, 0.5), (0.22, 0.08, 0.6), (0.22, 0.10, 0.7)]


def build_stageA():
    cfgs = []
    for sel in F7_SELS4:
        for n in (4, 5, 6):
            for R in (15, 20, 30):
                for tp in (0.45, 0.6, 0.8, 1.0, 1.2):
                    cfgs.append(dict(tag='F7_%s_N%d_R%d_T%s' % (sel, n, R, str(tp).replace('.', '')),
                                      sel=sel, b_n=n, b_rebal=R, b_take=tp))
    # F6 lesson: TP/R resonance first -- low-TP sweep on main sel (grid rs60, default brake)
    for n in (4, 5):
        for R in (15, 20):
            for tp in (0.15, 0.25):
                cfgs.append(dict(tag='F7_c_a60_vol_N%d_R%d_T%s' % (n, R, str(tp).replace('.', '')),
                                  sel='c_a60_vol', b_n=n, b_rebal=R, b_take=tp))
    return cfgs


def build_stageB():
    # fixed-anchor daily microgrid per sel (F5 path): N4/R15/TP0.45 @ default brake
    cfgs = []
    for sel in F7_SELS4:
        for rs in (12, 15, 20, 25, 30, 35, 40, 42, 45, 48, 50, 55, 60):
            for hyst in (0.02, 0.03, 0.04, 0.05):
                cfgs.append(dict(tag='F7sB_%s_rs%d_h%s_dg' % (sel, rs, str(hyst).replace('.', '')),
                                  sel=sel, rs=rs, hyst=hyst, mh=0,
                                  evalfreq='daily', brake_daily=False,
                                  **dict(dict(F7_ANCHOR), **F7_DEF_BRAKE)))
    # F6 lesson: TP/R-resonance daily on main sel (TP0.15/0.25 x R15/20)
    for tp in (0.15, 0.25):
        for R in (15, 20):
            for rs in (45, 55, 60, 62):
                for hyst in (0.03, 0.04, 0.05):
                    cfgs.append(dict(tag='F7sB_T%s_R%d_rs%d_h%s_dg' % (str(tp).replace('.', ''), R, rs, str(hyst).replace('.', '')),
                                      sel='c_a60_vol', b_take=tp, b_rebal=R, rs=rs, hyst=hyst, mh=0,
                                      evalfreq='daily', brake_daily=False,
                                      **dict(dict(b_n=4, b_cut=0.70, b_win=20), **F7_DEF_BRAKE)))
    return cfgs


def topn(rows, n=3, daily_only=True):
    pool = [r for r in rows if r.get('evalfreq') == 'daily'] if daily_only else list(rows)
    ok = [r for r in pool if r.get('pass_all')]
    pool = ok if ok else pool
    return sorted(pool, key=lambda r: (r.get('margin', -999), r.get('total', 0)), reverse=True)[:n]


def build_stageC(rows):
    cfgs = []
    for a in topn(rows, 3):
        base = dict(sel=a['b_sel'], b_n=a['b_n'], b_rebal=a['b_rebal'], b_take=a['b_take'],
                    b_cut=a['b_cut'], b_win=a['b_win'], band=tuple(a['b_band']), gate=a['b_gate'],
                    rs=a['rs'], hyst=a['hyst'], mh=a.get('mh', 0), evalfreq=a['evalfreq'],
                    brake_daily=a['brake_daily'], stop=a['stop'], exp_b=a['exp_b'])
        for (bx, by_, bf) in BRAKES_C:
            if bx == a['bx'] and by_ == a['by_'] and bf == a['bf']:
                continue
            cfgs.append(dict(tag=a['tag'] + '_b%s%s%s' % (str(bx).replace('.', ''), str(by_).replace('.', ''), str(bf).replace('.', '')),
                              bx=bx, by_=by_, bf=bf, **base))
    return cfgs


def _bases_for_D(rows):
    # global best daily + best daily of each other sel (if margin within 30pts of global best)
    daily = [r for r in rows if r.get('evalfreq') == 'daily']
    if not daily:
        return []
    ranked = sorted(daily, key=lambda r: (r.get('pass_all', False), r.get('margin', -999), r.get('total', 0)), reverse=True)
    best = ranked[0]
    bases = [best]
    for sel in F7_SELS4:
        if sel == best['b_sel']:
            continue
        cand = [r for r in ranked if r['b_sel'] == sel]
        if cand and cand[0]['margin'] >= best['margin'] - 30:
            bases.append(cand[0])
    out = []
    for a in bases:
        out.append(dict(tag=a['tag'], sel=a['b_sel'], b_n=a['b_n'], b_rebal=a['b_rebal'], b_take=a['b_take'],
                        b_cut=a['b_cut'], b_win=a['b_win'], band=tuple(a['b_band']), gate=a['b_gate'],
                        bx=a['bx'], by_=a['by_'], bf=a['bf'], rs=a['rs'], hyst=a['hyst'], mh=a.get('mh', 0),
                        evalfreq=a['evalfreq'], brake_daily=a['brake_daily'], stop=a['stop'], exp_b=a['exp_b']))
    return out


def build_stageD(rows, groups=None):
    cfgs = []
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    for b in _bases_for_D(rows):
        pfx = b.pop('tag')
        if groups is None or 'D1' in groups:
            for rs in sorted(set([max(8, b['rs'] - 3), max(8, b['rs'] - 2), max(8, b['rs'] - 1), b['rs'] + 1, b['rs'] + 2, b['rs'] + 3])):
                add('%s_rs%d' % (pfx, rs), **dict(b, rs=rs))
        if groups is None or 'D2' in groups:
            for h in sorted(set([round(max(0.005, b['hyst'] - 0.01), 4), round(max(0.005, b['hyst'] - 0.005), 4), round(b['hyst'] + 0.005, 4), round(b['hyst'] + 0.01, 4)])):
                add('%s_h%s' % (pfx, str(h).replace('.', '')), **dict(b, hyst=h))
        if groups is None or 'D3' in groups:
            # mh honest sweep: tag mh == min_hold actually passed; confirm=1 throughout
            for mh in (3, 5, 10, 15):
                if mh == b.get('mh', 0):
                    continue
                add('%s_mh%d' % (pfx, mh), **dict(b, mh=mh))
            add('%s_cf2' % pfx, **dict(b, confirm=2))
        if groups is None or 'D4' in groups:
            if not b['brake_daily']:
                add('%s_bd' % pfx, **dict(b, brake_daily=True))
            for cut, win in ((0.6, 20), (0.8, 20), (0.7, 10), (0.7, 40)):
                if cut == b['b_cut'] and win == b['b_win']:
                    continue
                add('%s_c%s_w%d' % (pfx, str(cut).replace('.', ''), win), **dict(b, b_cut=cut, b_win=win))
        if groups is None or 'D5' in groups:
            for band, gate in (((0.02, 0.30), -1.0), ((0.05, 0.30), -0.15), ((0.02, 0.30), -0.15)):
                if list(band) == list(b['band']) and gate == b['gate']:
                    continue
                add('%s_band%s_gate%s' % (pfx, str(band[0]).replace('.', ''), str(gate).replace('.', '').replace('-', 'm')), **dict(b, band=band, gate=gate))
            for n2, R2 in ((5, 15), (4, 20), (4, 30), (5, 20)):
                if n2 == b['b_n'] and R2 == b['b_rebal']:
                    continue
                add('%s_N%dR%d' % (pfx, n2, R2), **dict(b, b_n=n2, b_rebal=R2))
        if groups is None or 'D6' in groups:
            # TP resonance around base TP (F6 lesson): low TPs + neighbors
            for tp in sorted(set([0.15, 0.25, 0.35, round(max(0.1, b['b_take'] - 0.1), 2), round(b['b_take'] + 0.1, 2)])):
                if tp == b['b_take']:
                    continue
                add('%s_T%s' % (pfx, str(tp).replace('.', '')), **dict(b, b_take=tp))
            for exp in (0.8, 1.0):
                if exp == b['exp_b']:
                    continue
                add('%s_exp%s' % (pfx, str(exp).replace('.', '')), **dict(b, exp_b=exp))
            if b['stop'] != 0.20:
                add('%s_stop02' % pfx, **dict(b, stop=0.20))
    return cfgs


def build_stageE():
    # confirmation neighborhood around the Stage-D pass:
    # c_a60_amt N4/R15/TP0.45 bx0.22/by0.05/bf0.5 rs48/h0.04 mh0 daily exp0.8
    P = dict(sel='c_a60_amt', b_n=4, b_rebal=15, b_take=0.45, b_cut=0.70, b_win=20,
             band=(0.05, 0.30), gate=-1.0, bx=0.22, by_=0.05, bf=0.5,
             rs=48, hyst=0.04, mh=0, confirm=1, evalfreq='daily', brake_daily=False,
             stop=0.25, exp_b=0.8)
    cfgs = []
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    for rs in (44, 45, 46, 47, 49, 50, 51, 52):
        add('F7sE_rs%d_h004_exp08' % rs, **dict(P, rs=rs))
    for rs in (46, 47, 48, 49, 50):
        for h in (0.035, 0.045):
            add('F7sE_rs%d_h%s_exp08' % (rs, str(h).replace('.', '')), **dict(P, rs=rs, hyst=h))
    for exp in (0.7, 0.75, 0.85, 0.9):
        add('F7sE_rs48_h004_exp%s' % str(exp).replace('.', ''), **dict(P, exp_b=exp))
    for mh in (3, 5, 10):
        add('F7sE_rs48_h004_mh%d_exp08' % mh, **dict(P, mh=mh))
    add('F7sE_rs48_h004_cf2_exp08', **dict(P, confirm=2))
    for n2, R2 in ((5, 15), (4, 20), (4, 30), (5, 20)):
        add('F7sE_N%dR%d_exp08' % (n2, R2), **dict(P, b_n=n2, b_rebal=R2))
    for tp in (0.25, 0.35, 0.55):
        add('F7sE_T%s_exp08' % str(tp).replace('.', ''), **dict(P, b_take=tp))
    for cut, win in ((0.6, 20), (0.8, 20), (0.7, 10), (0.7, 40)):
        add('F7sE_c%s_w%d_exp08' % (str(cut).replace('.', ''), win), **dict(P, b_cut=cut, b_win=win))
    for band, gate in (((0.02, 0.30), -1.0), ((0.05, 0.30), -0.15)):
        add('F7sE_band%s_gate%s_exp08' % (str(band[0]).replace('.', ''), str(gate).replace('.', '').replace('-', 'm')), **dict(P, band=band, gate=gate))
    for stop in (0.20, 0.30):
        add('F7sE_stop%s_exp08' % str(stop).replace('.', ''), **dict(P, stop=stop))
    add('F7sE_bd_exp08', **dict(P, brake_daily=True))
    return cfgs


def build_stageF():
    # ridge refinement: rs47-48 x h0.0325-0.0425 @ TP0.45/exp08 + TP035 on rs47h0035
    P = dict(sel='c_a60_amt', b_n=4, b_rebal=15, b_take=0.45, b_cut=0.70, b_win=20,
             band=(0.05, 0.30), gate=-1.0, bx=0.22, by_=0.05, bf=0.5,
             mh=0, confirm=1, evalfreq='daily', brake_daily=False,
             stop=0.25, exp_b=0.8)
    cfgs = []
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    for rs in (47, 48):
        for h in (0.0325, 0.0375, 0.0425):
            add('F7sF_rs%d_h%s_exp08' % (rs, str(h).replace('.', '')), **dict(P, rs=rs, hyst=h))
    add('F7sF_rs47_h0035_T035', **dict(P, rs=47, hyst=0.035, b_take=0.35))
    add('F7sF_rs47_h0035_exp078', **dict(P, rs=47, hyst=0.035, exp_b=0.78))
    add('F7sF_rs47_h0035_exp082', **dict(P, rs=47, hyst=0.035, exp_b=0.82))
    return cfgs


def build_stageV():
    # vol follow-up for the 主攻 mandate: N5-6/R15-20/TP0.15 daily @ default brake
    DB = dict(F7_DEF_BRAKE)
    cfgs = []
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    for R in (15, 20):
        for rs in (40, 50, 60):
            for hyst in (0.02, 0.03, 0.04):
                add('F7sV_vol_N5R%d_rs%d_h%s' % (R, rs, str(hyst).replace('.', '')),
                    sel='c_a60_vol', b_n=5, b_rebal=R, b_take=0.15, b_cut=0.70, b_win=20,
                    rs=rs, hyst=hyst, mh=0, evalfreq='daily', brake_daily=False, **DB)
    for rs in (50, 55, 60):
        for hyst in (0.02, 0.03):
            add('F7sV_vol_N6R15_rs%d_h%s' % (rs, str(hyst).replace('.', '')),
                sel='c_a60_vol', b_n=6, b_rebal=15, b_take=0.15, b_cut=0.70, b_win=20,
                rs=rs, hyst=hyst, mh=0, evalfreq='daily', brake_daily=False, **DB)
    return cfgs


FP = ROOT / 'results' / 'r30_bt' / 'fam_F7_stage.json'


def save(rows):
    atomic_write_json(FP, rows)


def run_and_log(tag, rows, **kw):
    try:
        r = run_switch(tag, **kw)
        print(json.dumps(r, ensure_ascii=False), flush=True)
        rows.append(r)
        save(rows)
        return r
    except Exception as e:
        print('FAIL ' + tag + ': ' + str(e), flush=True)
        return None


def load_rows():
    if FP.exists():
        return json.loads(FP.read_text())
    return []


def run_list(todo, rows):
    have = set(r['tag'] for r in rows)
    for c in todo:
        tag = c.pop('tag')
        if tag in have:
            print('SKIP ' + tag, flush=True)
            continue
        run_and_log(tag, rows, **c)


def show_top(rows, n=12, title='F7 TOP'):
    best = sorted(rows, key=lambda r: (r.get('pass_all', False), r.get('margin', -999), r.get('total', 0)), reverse=True)[:n]
    print('=== %s (n=%d) ===' % (title, len(rows)), flush=True)
    for b in best:
        print(json.dumps({k: b.get(k) for k in ('tag', 'b_sel', 'b_n', 'b_rebal', 'b_take', 'bx', 'by_', 'bf', 'rs', 'hyst', 'mh', 'evalfreq', 'brake_daily', 'lock', 'total', 'mdd', 'y2024_slice', 'y2024_yoy', 'y2024_mdd', 'y2025_yoy', 'y2025_mdd', 'y2026_slice', 'y2026_yoy', 'y2026_mdd', 'trades', 'cost', 'switches', 'brakes', 'mode', 'pass_all', 'margin')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default=None)
    ap.add_argument('--stage', default='all')
    ap.add_argument('--groups', default=None)
    args = ap.parse_args()
    grps = args.groups.split(',') if args.groups else None
    if args.only is not None:
        pool = build_stageA() + build_stageB()
        c = next((c for c in pool if c['tag'] == args.only), None)
        if c is None:
            print('only tag not in stageA/B list: ' + str(args.only), flush=True)
        else:
            tag = c.pop('tag')
            print(json.dumps(run_switch(tag, **c), ensure_ascii=False), flush=True)
    elif args.stage == 'A':
        rows = []
        run_list(build_stageA(), rows)
        show_top(rows, title='F7 TOP10 (after A)')
        save(rows)
        print('saved stage A rows=' + str(len(rows)), flush=True)
    elif args.stage == 'B':
        rows = load_rows()
        run_list(build_stageB(), rows)
        show_top(rows, title='F7 TOP12 (after B)')
        save(rows)
        print('saved rows=' + str(len(rows)), flush=True)
    elif args.stage == 'C':
        rows = load_rows()
        run_list(build_stageC(rows), rows)
        show_top(rows, title='F7 TOP12 (after C)')
        save(rows)
        print('saved rows=' + str(len(rows)), flush=True)
    elif args.stage == 'D':
        rows = load_rows()
        run_list(build_stageD(rows, grps), rows)
        show_top(rows, title='F7 TOP12 (after D)')
        save(rows)
        print('saved rows=' + str(len(rows)), flush=True)
    elif args.stage == 'E':
        rows = load_rows()
        run_list(build_stageE(), rows)
        show_top(rows, title='F7 TOP12 (after E)')
        save(rows)
        print('saved rows=' + str(len(rows)), flush=True)
    elif args.stage == 'F':
        rows = load_rows()
        run_list(build_stageF(), rows)
        show_top(rows, title='F7 TOP12 (after F)')
        save(rows)
        print('saved rows=' + str(len(rows)), flush=True)
    elif args.stage == 'V':
        rows = load_rows()
        run_list(build_stageV(), rows)
        show_top(rows, title='F7 TOP12 (after V)')
        save(rows)
        print('saved rows=' + str(len(rows)), flush=True)
    else:
        rows = []
        run_list(build_stageA(), rows)
        show_top(rows, title='F7 TOP10 (after A)')
        run_list(build_stageB(), rows)
        show_top(rows, title='F7 TOP12 (after B)')
        run_list(build_stageC(rows), rows)
        show_top(rows, title='F7 TOP12 (after C)')
        run_list(build_stageD(rows), rows)
        show_top(rows, title='F7 TOP12 (after D)')
        save(rows)
        print('saved all rows=' + str(len(rows)), flush=True)