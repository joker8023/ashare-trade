#!/usr/bin/env python3
# F6 turn/vol family search (realshares_v2 true-equity caliber, F1=C2_grid frozen).
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
# Usage: .venv/bin/python research/fam_F6.py [--only TAG]
# Output: results/r30_bt/fam_F6_stage.json
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
F6_SELS = ("turn20", "vol20", "c_4", "c_a60_turn", "c_a60_vol")
# build_ns: single implementation from switch_ns (C2-fixed confirm semantics)
piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
print("RUN", RUN_START, EVAL_END, "first_sig", first_sig.date(), "F6 sels", F6_SELS, flush=True)
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
    r = dict(tag=tag, fam='F6', b_sel=sel, b_band=list(band), b_gate=gate, b_n=b_n, b_rebal=b_rebal, b_take=b_take, b_cut=b_cut, b_win=b_win, bx=bx, by_=by_, bf=bf, rs=rs, hyst=hyst, mh=mh, confirm=confirm, evalfreq=evalfreq, brake_daily=brake_daily, stop=stop, exp_b=exp_b, lock=lock, sw_stop=(sw_stop if sw_stop is not None else stop), total=round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2), mdd=round(_mdd(eq) * 100, 2), trades=len(res.trades), cost=round(float(res.meta['total_cost']), 0), mode=res.meta['final_mode'], switches=len(res.meta['switch_log']), switch_log=[list(x) for x in res.meta['switch_log']], brake_log=[list(x) for x in res.meta.get('brake_log', [])], brakes=len(res.meta.get('brake_log', [])) // 2, eq_start=str(eq.index[0].date()), eq_end=str(eq.index[-1].date()), y2023_yoy=an[2023]['yoy'], y2023_mdd=an[2023]['mdd'], y2024_slice=an[2024]['slice'], y2024_yoy=an[2024]['yoy'], y2024_mdd=an[2024]['mdd'], y2025_slice=an[2025]['slice'], y2025_yoy=an[2025]['yoy'], y2025_mdd=an[2025]['mdd'], y2026_slice=an[2026]['slice'], y2026_yoy=an[2026]['yoy'], y2026_mdd=an[2026]['mdd'])
    r['pass_all'] = bool(r['y2024_slice'] is not None and r['y2024_slice'] > 60 and r['y2024_yoy'] > 60 and r['y2025_yoy'] > 60 and r['y2026_slice'] is not None and r['y2026_slice'] > 60 and r['y2026_yoy'] > 60 and r['mdd'] > -30 and r['y2024_mdd'] > -30 and r['y2025_mdd'] > -30 and r['y2026_mdd'] > -30)
    r['margin'] = round(min(r['y2024_slice'] - 60, r['y2024_yoy'] - 60, r['y2025_yoy'] - 60, r['y2026_slice'] - 60, r['y2026_yoy'] - 60, r['mdd'] + 30, r['y2024_mdd'] + 30, r['y2025_mdd'] + 30, r['y2026_mdd'] + 30), 2)
    r['avg_exp'] = round(float(res.exposure.mean()), 4) if res.exposure is not None else None
    r['max_exp'] = round(float(res.exposure.max()), 4) if res.exposure is not None else None
    _pe = float(eq.iloc[-1] - eq.iloc[0])
    r['cost_eff'] = round(_pe / float(res.meta['total_cost']), 2) if float(res.meta['total_cost']) > 0 else None
    r['take_sells'] = int(res.meta.get('take_sells', 0))
    return r

F6_ANCHOR = dict(sel='c_4', b_n=4, b_rebal=15, b_take=0.45, b_cut=0.70, b_win=20)

def build_configs():
    cfgs = []
    # ---- Stage A: c_4 anchor grid @ default brake (bx0.18/by0.08/bf0.6, grid rs60) ----
    for n in (4, 5, 6):
        for R in (15, 20, 30):
            for tp in (0.45, 0.6, 0.8, 1.0, 1.2):
                cfgs.append(dict(tag='F6_c4_N%d_R%d_T%s' % (n, R, str(tp).replace('.', '')),
                                  sel='c_4', b_n=n, b_rebal=R, b_take=tp))
    # backups: vol20/turn20 pure N4/R15/TP0.45 anchors
    for sel in ('vol20', 'turn20'):
        cfgs.append(dict(tag='F6_%s_N4_R15_T045' % sel, sel=sel, b_n=4, b_rebal=15, b_take=0.45))
    # ---- Stage B: daily-switch microgrid on c_4 N4/R15/TP0.45 @ default brake ----
    for rs in (12, 15, 20, 25, 30, 35, 40, 42, 45, 48, 50, 55, 60):
        for hyst in (0.02, 0.03, 0.04, 0.05):
            cfgs.append(dict(tag='F6sB_rs%d_h%s_dg' % (rs, str(hyst).replace('.', '')),
                             sel='c_4', b_n=4, b_rebal=15, b_take=0.45,
                             bx=0.18, by_=0.08, bf=0.6, rs=rs, hyst=hyst,
                             mh=0, evalfreq='daily', brake_daily=False))
    return cfgs

BRAKES_C = [(0.12, 0.05, 0.4), (0.12, 0.05, 0.5), (0.12, 0.06, 0.5), (0.12, 0.08, 0.6),
            (0.15, 0.08, 0.5), (0.15, 0.10, 0.5), (0.18, 0.08, 0.4), (0.18, 0.08, 0.7),
            (0.18, 0.10, 0.6), (0.22, 0.05, 0.5), (0.22, 0.08, 0.6), (0.22, 0.10, 0.7)]

def topn(rows, n=3):
    ok = [r for r in rows if r.get('pass_all')]
    pool = ok if ok else rows
    return sorted(pool, key=lambda r: (r.get('margin', -999), r.get('total', 0)), reverse=True)[:n]


def build_stageE():
    cfgs = []
    BB = dict(sel='c_4', b_n=4, b_rebal=15, b_take=0.45, b_cut=0.70, b_win=20)
    # E1: brake fine grid @ rs60/h0.04 daily
    for bx in (0.08, 0.10, 0.12):
        for by_ in (0.03, 0.05):
            for bf in (0.3, 0.4, 0.5):
                cfgs.append(dict(tag='F6sE_brake_b%s%s%s_rs60_h004' % (str(bx).replace('.', ''), str(by_).replace('.', ''), str(bf).replace('.', '')), rs=60, hyst=0.04, mh=0, evalfreq='daily', brake_daily=False, bx=bx, by_=by_, bf=bf, **BB))
    # E2: rs x hyst @ soft brake (0.12/0.05/0.4)
    for rs in (62, 65, 70, 75, 80):
        for hyst in (0.03, 0.04, 0.05, 0.06):
            cfgs.append(dict(tag='F6sE_rs%d_h%s_b120504' % (rs, str(hyst).replace('.', '')), rs=rs, hyst=hyst, mh=0, evalfreq='daily', brake_daily=False, bx=0.12, by_=0.05, bf=0.4, **BB))
    # E3: min-hold (properly passed) @ rs60/h0.04 soft brake
    for mh in (3, 5, 10, 15):
        cfgs.append(dict(tag='F6sE_rs60_h004_mh%d' % mh, rs=60, hyst=0.04, mh=mh, evalfreq='daily', brake_daily=False, bx=0.12, by_=0.05, bf=0.4, **BB))
    # E4: brake_daily=True @ top rs/hyst
    for rs, hyst in ((60, 0.04), (62, 0.04), (65, 0.04)):
        cfgs.append(dict(tag='F6sE_rs%d_h%s_bd' % (rs, str(hyst).replace('.', '')), rs=rs, hyst=hyst, mh=0, evalfreq='daily', brake_daily=True, bx=0.12, by_=0.05, bf=0.4, **BB))
    # E5: B-leg N/R variants @ rs60/h0.04 soft brake
    for n2, R2 in ((5, 15), (6, 15), (4, 20), (5, 20), (4, 30), (5, 30)):
        cfgs.append(dict(tag='F6sE_N%dR%d_rs60_h004' % (n2, R2), rs=60, hyst=0.04, mh=0, evalfreq='daily', brake_daily=False, bx=0.12, by_=0.05, bf=0.4, **dict(BB, b_n=n2, b_rebal=R2)))
    # E6: pool variants (band/gate) @ rs60/h0.04 soft brake
    for band, gate in (((0.02, 0.30), -1.0), ((0.05, 0.30), -0.15), ((0.02, 0.30), -0.15)):
        cfgs.append(dict(tag='F6sE_band%s_gate%s' % (str(band[0]).replace('.', ''), str(gate).replace('.', '').replace('-', 'm')), band=band, gate=gate, rs=60, hyst=0.04, mh=0, evalfreq='daily', brake_daily=False, bx=0.12, by_=0.05, bf=0.4, **BB))
    # E7: backup pure legs @ soft brake daily
    for sel in ('vol20', 'turn20'):
        for rs, hyst in ((60, 0.04), (45, 0.04)):
            cfgs.append(dict(tag='F6sE_%s_rs%d_h%s' % (sel, rs, str(hyst).replace('.', '')), sel=sel, rs=rs, hyst=hyst, mh=0, evalfreq='daily', brake_daily=False, bx=0.12, by_=0.05, bf=0.4, b_n=4, b_rebal=15, b_take=0.45, b_cut=0.70, b_win=20))
    return cfgs


def build_stageF(groups=None):
    cfgs = []
    BB = dict(sel='c_4', b_n=4, b_rebal=15, b_take=0.45, b_cut=0.70, b_win=20)
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    if groups is None or 'F1' in groups:
        for bx in (0.15, 0.18, 0.22, 0.25, 0.30):
            for bf in (0.4, 0.6, 0.8, 1.0):
                add('F6sF_bx%sbf%s_rs60_h004' % (str(bx).replace('.', ''), str(bf).replace('.', '')),
                    rs=60, hyst=0.04, mh=0, evalfreq='daily', brake_daily=False, bx=bx, by_=0.05, bf=bf, **BB)
    if groups is None or 'F2' in groups:
        for rs in (58, 59, 60, 61, 62, 63, 64):
            for hyst in (0.035, 0.04, 0.045, 0.05):
                add('F6sF_rs%d_h%s' % (rs, str(hyst).replace('.', '')),
                    rs=rs, hyst=hyst, mh=0, evalfreq='daily', brake_daily=False, bx=0.12, by_=0.05, bf=0.4, **BB)
    if groups is None or 'F3' in groups:
        for mh in (20, 25, 30):
            add('F6sF_rs60_h004_mh%d' % mh, rs=60, hyst=0.04, mh=mh, evalfreq='daily', brake_daily=False, bx=0.12, by_=0.05, bf=0.4, **BB)
        for cf in (2, 3):
            add('F6sF_rs60_h004_cf%d' % cf, rs=60, hyst=0.04, mh=0, evalfreq='daily', brake_daily=False, bx=0.12, by_=0.05, bf=0.4, confirm=cf, **BB)
    if groups is None or 'F4' in groups:
        add('F6sF_lockB_c4', lock='B', bx=0.18, by_=0.08, bf=0.6, rs=60, **BB)
        add('F6sF_lockB_c4_soft', lock='B', bx=0.12, by_=0.05, bf=0.4, rs=60, **BB)
        add('F6sF_lockA_M07', lock='A', bx=0.18, by_=0.08, bf=0.6, rs=60, **BB)
        add('F6sF_lockA_M07_soft', lock='A', bx=0.12, by_=0.05, bf=0.4, rs=60, **BB)
    if groups is None or 'F5' in groups:
        for rs in (90, 120):
            add('F6sF_grid_rs%d' % rs, rs=rs, hyst=0.0, mh=0, evalfreq='grid', brake_daily=False, bx=0.12, by_=0.05, bf=0.4, **BB)
    return [c for c in cfgs if groups is None or True]


def build_stageG(groups=None):
    cfgs = []
    BB = dict(sel='c_4', b_cut=0.70, b_win=20)
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    if groups is None or 'G1' in groups:
        for n2 in (4, 5):
            for R2 in (15, 20, 30):
                for rs in (55, 60, 65):
                    for hyst in (0.03, 0.04, 0.05):
                        if n2 == 4 and R2 == 15 and rs == 60 and hyst == 0.04:
                            continue
                        add('F6sG_N%dR%d_rs%d_h%s' % (n2, R2, rs, str(hyst).replace('.', '')),
                            b_n=n2, b_rebal=R2, b_take=0.45, rs=rs, hyst=hyst, mh=0,
                            evalfreq='daily', brake_daily=False, bx=0.12, by_=0.05, bf=0.4, **BB)
    if groups is None or 'G2' in groups:
        for bx in (0.10, 0.12):
            for by_ in (0.03, 0.05, 0.07):
                for bf in (0.3, 0.4):
                    if bx == 0.12 and by_ == 0.05 and bf == 0.4:
                        continue
                    add('F6sG_b%s%s%s_rs60_h004' % (str(bx).replace('.', ''), str(by_).replace('.', ''), str(bf).replace('.', '')),
                        b_n=4, b_rebal=15, b_take=0.45, rs=60, hyst=0.04, mh=0,
                        evalfreq='daily', brake_daily=False, bx=bx, by_=by_, bf=bf, **BB)
    if groups is None or 'G3' in groups:
        for stop in (0.15, 0.20):
            for rs in (60, 62):
                add('F6sG_stop%s_rs%d' % (str(stop).replace('.', ''), rs),
                    b_n=4, b_rebal=15, b_take=0.45, rs=rs, hyst=0.04, mh=0,
                    evalfreq='daily', brake_daily=False, bx=0.12, by_=0.05, bf=0.4, stop=stop, **BB)
    if groups is None or 'G4' in groups:
        for rs, hyst in ((60, 0.04), (60, 0.045), (62, 0.04), (62, 0.045)):
            add('F6sG_expb10_rs%d_h%s' % (rs, str(hyst).replace('.', '')),
                b_n=4, b_rebal=15, b_take=0.45, rs=rs, hyst=hyst, mh=0,
                evalfreq='daily', brake_daily=False, bx=0.12, by_=0.05, bf=0.4, exp_b=1.0, **BB)
    if groups is None or 'G5' in groups:
        for n2 in (4, 5):
            add('F6sG_N%dR10_rs60_h004' % n2,
                b_n=n2, b_rebal=10, b_take=0.45, rs=60, hyst=0.04, mh=0,
                evalfreq='daily', brake_daily=False, bx=0.12, by_=0.05, bf=0.4, **BB)
    return cfgs


def build_stageH(groups=None):
    cfgs = []
    BB = dict(sel='c_4', b_n=4, b_rebal=15, b_take=0.45, b_cut=0.70, b_win=20)
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    if groups is None or 'H1' in groups:
        for rs in (15, 20, 25, 30):
            for hyst in (0.02, 0.03):
                for mh in (5, 10, 15):
                    add('F6sH_rs%d_h%s_mh%d' % (rs, str(hyst).replace('.', ''), mh),
                        rs=rs, hyst=hyst, mh=mh, evalfreq='daily', brake_daily=False,
                        bx=0.12, by_=0.05, bf=0.4, **BB)
    if groups is None or 'H2' in groups:
        for rs in (15, 20, 25, 30):
            for bx, by_, bf in ((0.12, 0.07, 0.3), (0.10, 0.07, 0.3)):
                add('F6sH_rs%d_b%s%s%s' % (rs, str(bx).replace('.', ''), str(by_).replace('.', ''), str(bf).replace('.', '')),
                    rs=rs, hyst=0.02, mh=0, evalfreq='daily', brake_daily=False,
                    bx=bx, by_=by_, bf=bf, **BB)
    if groups is None or 'H3' in groups:
        for rs in (20, 25, 30):
            for hyst in (0.04, 0.05):
                for mh in (10, 15):
                    add('F6sH_rs%d_h%s_mh%d' % (rs, str(hyst).replace('.', ''), mh),
                        rs=rs, hyst=hyst, mh=mh, evalfreq='daily', brake_daily=False,
                        bx=0.12, by_=0.05, bf=0.4, **BB)
    if groups is None or 'H4' in groups:
        for rs in (40, 45, 50):
            for hyst in (0.02, 0.03):
                for mh in (10, 15):
                    add('F6sH_rs%d_h%s_mh%d' % (rs, str(hyst).replace('.', ''), mh),
                        rs=rs, hyst=hyst, mh=mh, evalfreq='daily', brake_daily=False,
                        bx=0.12, by_=0.05, bf=0.4, **BB)
    return cfgs


def build_stageI(groups=None):
    cfgs = []
    BB = dict(sel='c_4', b_n=4, b_rebal=15, b_take=0.45, b_cut=0.70, b_win=20)
    SBB = dict(bx=0.12, by_=0.05, bf=0.4)
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    if groups is None or 'I1' in groups:
        for mh in (3, 5, 10, 15, 20, 25):
            add('F6sI_rs62_h0045_mh%d' % mh, rs=62, hyst=0.045, mh=mh,
                evalfreq='daily', brake_daily=False, **SBB, **BB)
    if groups is None or 'I2' in groups:
        for rs in (60, 61, 62, 63):
            for hyst in (0.0425, 0.0475):
                add('F6sI_rs%d_h%s' % (rs, str(hyst).replace('.', '')),
                    rs=rs, hyst=hyst, mh=0, evalfreq='daily', brake_daily=False, **SBB, **BB)
    if groups is None or 'I3' in groups:
        for n2 in (4, 5, 6):
            for R2 in (15, 20, 30):
                for rs in (61, 62):
                    if n2 == 4 and R2 == 15:
                        continue
                    add('F6sI_N%dR%d_rs%d_h0045' % (n2, R2, rs),
                        rs=rs, hyst=0.045, mh=0,
                        evalfreq='daily', brake_daily=False, **SBB,
                        **dict(BB, b_n=n2, b_rebal=R2))
        for mh in (10, 15):
            add('F6sI_rs62_h0045_mh%d_N4R15' % mh, rs=62, hyst=0.045, mh=mh,
                evalfreq='daily', brake_daily=False, **SBB, **BB)
    if groups is None or 'I4' in groups:
        for band, gate in (((0.02, 0.30), -1.0), ((0.05, 0.30), -0.15), ((0.02, 0.30), -0.15)):
            for rs in (60, 62):
                add('F6sI_band%s_gate%s_rs%d' % (str(band[0]).replace('.', ''), str(gate).replace('.', '').replace('-', 'm'), rs),
                    band=band, gate=gate, rs=rs, hyst=0.045, mh=0,
                    evalfreq='daily', brake_daily=False, **SBB, **BB)
    if groups is None or 'I5' in groups:
        for stop in (0.10, 0.35, 0.50):
            add('F6sI_stop%s_rs62' % str(stop).replace('.', ''),
                stop=stop, rs=62, hyst=0.045, mh=0,
                evalfreq='daily', brake_daily=False, **SBB, **BB)
        for tp in (0.25, 0.35):
            for rs in (60, 62):
                add('F6sI_T%s_rs%d' % (str(tp).replace('.', ''), rs),
                    rs=rs, hyst=0.045, mh=0,
                    evalfreq='daily', brake_daily=False, **SBB, **dict(BB, b_take=tp))
    if groups is None or 'I6' in groups:
        for bx in (0.11, 0.12, 0.13):
            for by_ in (0.04, 0.05, 0.06):
                if bx == 0.12 and by_ == 0.05:
                    continue
                add('F6sI_b%s%s_rs62' % (str(bx).replace('.', ''), str(by_).replace('.', '')),
                    bx=bx, by_=by_, bf=0.4, rs=62, hyst=0.045, mh=0,
                    evalfreq='daily', brake_daily=False, **BB)
    if groups is None or 'I7' in groups:
        for rs in (66, 67, 68, 69):
            for hyst in (0.04, 0.045, 0.05):
                add('F6sI_rs%d_h%s' % (rs, str(hyst).replace('.', '')),
                    rs=rs, hyst=hyst, mh=0, evalfreq='daily', brake_daily=False, **SBB, **BB)
    return cfgs


def build_stageJ(groups=None):
    cfgs = []
    BB = dict(sel='c_4', b_n=4, b_rebal=15, b_cut=0.70, b_win=20)
    SBB = dict(bx=0.12, by_=0.05, bf=0.4)
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    if groups is None or 'J1' in groups:
        for tp in (0.15, 0.20, 0.25, 0.30, 0.35):
            for rs in (60, 62):
                for mh in (0, 15):
                    add('F6sJ_T%s_rs%d_mh%d' % (str(tp).replace('.', ''), rs, mh),
                        rs=rs, hyst=0.045, mh=mh,
                        evalfreq='daily', brake_daily=False, **SBB, **dict(BB, b_take=tp))
    if groups is None or 'J2' in groups:
        for rs in (58, 59, 60, 61, 62, 63):
            add('F6sJ_T025_rs%d' % rs, rs=rs, hyst=0.045, mh=0,
                evalfreq='daily', brake_daily=False, **SBB, **dict(BB, b_take=0.25))
        for rs in (58, 59, 60, 61, 62, 63):
            add('F6sJ_T025_rs%d_mh15' % rs, rs=rs, hyst=0.045, mh=15,
                evalfreq='daily', brake_daily=False, **SBB, **dict(BB, b_take=0.25))
    if groups is None or 'J3' in groups:
        for tp in (0.25, 0.30):
            for hyst in (0.04, 0.05):
                for mh in (0, 15):
                    add('F6sJ_T%s_h%s_mh%d' % (str(tp).replace('.', ''), str(hyst).replace('.', ''), mh),
                        rs=60, hyst=hyst, mh=mh,
                        evalfreq='daily', brake_daily=False, **SBB, **dict(BB, b_take=tp))
    return cfgs


def build_stageK(groups=None):
    cfgs = []
    BB = dict(sel='c_4', b_n=4, b_rebal=15, b_cut=0.70, b_win=20)
    SBB = dict(bx=0.12, by_=0.05, bf=0.4)
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    if groups is None or 'K1' in groups:
        for tp in (0.05, 0.08, 0.10, 0.12):
            for rs in (60, 62):
                for mh in (0, 15):
                    add('F6sK_T%s_rs%d_mh%d' % (str(tp).replace('.', ''), rs, mh),
                        rs=rs, hyst=0.045, mh=mh,
                        evalfreq='daily', brake_daily=False, **SBB, **dict(BB, b_take=tp))
    if groups is None or 'K2' in groups:
        for rs in (58, 59, 60, 61, 62, 63, 64):
            for mh in (0, 15):
                add('F6sK_T015_rs%d_mh%d' % (rs, mh),
                    rs=rs, hyst=0.045, mh=mh,
                    evalfreq='daily', brake_daily=False, **SBB, **dict(BB, b_take=0.15))
    if groups is None or 'K3' in groups:
        for hyst in (0.04, 0.05):
            for mh in (0, 10, 15, 20):
                add('F6sK_T015_h%s_mh%d' % (str(hyst).replace('.', ''), mh),
                    rs=62, hyst=hyst, mh=mh,
                    evalfreq='daily', brake_daily=False, **SBB, **dict(BB, b_take=0.15))
    if groups is None or 'K4' in groups:
        for hyst in (0.04, 0.045, 0.05):
            for rs in (60, 62):
                add('F6sK_T01_rs%d_h%s' % (rs, str(hyst).replace('.', '')),
                    rs=rs, hyst=hyst, mh=0,
                    evalfreq='daily', brake_daily=False, **SBB, **dict(BB, b_take=0.10))
    return cfgs


def build_stageL(groups=None):
    cfgs = []
    BB = dict(sel='c_4', b_n=4, b_rebal=15, b_cut=0.70, b_win=20)
    SBB = dict(bx=0.12, by_=0.05, bf=0.4)
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    CH = dict(rs=62, hyst=0.045, mh=0, evalfreq='daily', brake_daily=False)
    if groups is None or 'L1' in groups:
        for tp in (0.13, 0.14, 0.16, 0.17, 0.18):
            add('F6sL_T%s_rs62' % str(tp).replace('.', ''),
                **CH, **SBB, **dict(BB, b_take=tp))
    if groups is None or 'L2' in groups:
        for bx, by_ in ((0.11, 0.05), (0.13, 0.05), (0.12, 0.04), (0.12, 0.06), (0.11, 0.04), (0.13, 0.06)):
            add('F6sL_T015_b%s%s' % (str(bx).replace('.', ''), str(by_).replace('.', '')),
                bx=bx, by_=by_, bf=0.4, **CH, **dict(BB, b_take=0.15))
    if groups is None or 'L3' in groups:
        for mh in (3, 5, 10, 20):
            add('F6sL_T015_mh%d' % mh, mh=mh,
                rs=62, hyst=0.045, evalfreq='daily', brake_daily=False, **SBB, **dict(BB, b_take=0.15))
        for stop in (0.20, 0.30):
            add('F6sL_T015_stop%s' % str(stop).replace('.', ''),
                stop=stop, **CH, **SBB, **dict(BB, b_take=0.15))
    if groups is None or 'L4' in groups:
        for n2, R2 in ((5, 15), (4, 20), (4, 30)):
            add('F6sL_T015_N%dR%d' % (n2, R2),
                **CH, **SBB, **dict(BB, b_n=n2, b_rebal=R2, b_take=0.15))
        for band, gate in (((0.02, 0.30), -1.0), ((0.05, 0.30), -0.15)):
            add('F6sL_T015_band%s_gate%s' % (str(band[0]).replace('.', ''), str(gate).replace('.', '').replace('-', 'm')),
                band=band, gate=gate, **CH, **SBB, **dict(BB, b_take=0.15))
        add('F6sL_T015_expb10', exp_b=1.0, **CH, **SBB, **dict(BB, b_take=0.15))
    return cfgs


def build_stageM(groups=None):
    cfgs = []
    BB = dict(sel='c_4', b_n=4, b_rebal=15, b_cut=0.70, b_win=20)
    SBB = dict(bx=0.12, by_=0.05, bf=0.4)
    CH = dict(rs=62, hyst=0.045, mh=0, evalfreq='daily', brake_daily=False)
    T15 = dict(BB, b_take=0.15)
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    if groups is None or 'M1' in groups:
        for bx in (0.13, 0.14):
            for stop in (0.25, 0.30):
                add('F6sM_b%s_stop%s' % (str(bx).replace('.', ''), str(stop).replace('.', '')),
                    bx=bx, by_=0.05, bf=0.4, stop=stop, **CH, **dict(T15))
    if groups is None or 'M2' in groups:
        for hyst in (0.043, 0.044, 0.046, 0.047):
            add('F6sM_h%s' % str(hyst).replace('.', ''),
                hyst=hyst, rs=62, mh=0, evalfreq='daily', brake_daily=False, **SBB, **dict(T15))
    if groups is None or 'M3' in groups:
        for bf in (0.35, 0.45, 0.5):
            add('F6sM_bf%s' % str(bf).replace('.', ''),
                **CH, **dict(SBB, bf=bf), **dict(T15))
    if groups is None or 'M4' in groups:
        for by_ in (0.045, 0.055):
            add('F6sM_by%s' % str(by_).replace('.', ''),
                **CH, **dict(SBB, by_=by_), **dict(T15))
    if groups is None or 'M5' in groups:
        for rs in (60, 90):
            add('F6sM_grid_rs%d' % rs, rs=rs, hyst=0.0, mh=0,
                evalfreq='grid', brake_daily=False, **SBB, **dict(T15))
    if groups is None or 'M6' in groups:
        for mh in (0, 3, 5):
            add('F6sM_b013_stop03_mh%d' % mh,
                bx=0.13, by_=0.05, bf=0.4, stop=0.30, mh=mh, rs=62, hyst=0.045,
                evalfreq='daily', brake_daily=False, **dict(T15))
    if groups is None or 'M7' in groups:
        for tp in (0.14, 0.16):
            add('F6sM_T%s_b013' % str(tp).replace('.', ''),
                bx=0.13, by_=0.05, bf=0.4, rs=62, hyst=0.045, mh=0,
                evalfreq='daily', brake_daily=False, **dict(BB, b_take=tp))
    if groups is None or 'M8' in groups:
        for R2 in (12, 18):
            add('F6sM_R%d' % R2, **CH, **SBB, **dict(T15, b_rebal=R2))
    return cfgs


def build_stageN(groups=None):
    cfgs = []
    BB = dict(sel='c_4', b_n=4, b_rebal=15, b_cut=0.70, b_win=20)
    SBB = dict(bx=0.12, by_=0.05, bf=0.4)
    T15 = dict(BB, b_take=0.15)
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    if groups is None or 'N1' in groups:
        for rs in (15, 20, 25, 30, 40, 45):
            for hyst in (0.02, 0.03):
                for mh in (10, 15):
                    add('F6sN_rs%d_h%s_mh%d' % (rs, str(hyst).replace('.', ''), mh),
                        rs=rs, hyst=hyst, mh=mh,
                        evalfreq='daily', brake_daily=False, **SBB, **dict(T15))
    if groups is None or 'N2' in groups:
        for rs in (15, 20, 25, 30):
            for mh in (10, 15):
                for bx, by_, bf in ((0.12, 0.07, 0.3), (0.10, 0.07, 0.3)):
                    add('F6sN_rs%d_mh%d_b%s%s%s' % (rs, mh, str(bx).replace('.', ''), str(by_).replace('.', ''), str(bf).replace('.', '')),
                        rs=rs, hyst=0.02, mh=mh,
                        evalfreq='daily', brake_daily=False, bx=bx, by_=by_, bf=bf, **dict(T15))
    if groups is None or 'N3' in groups:
        for rs in (20, 25, 30):
            for mh in (20, 25):
                add('F6sN_rs%d_h003_mh%d' % (rs, mh),
                    rs=rs, hyst=0.03, mh=mh,
                    evalfreq='daily', brake_daily=False, **SBB, **dict(T15))
    return cfgs


def build_stageO(groups=None):
    cfgs = []
    BB = dict(sel='c_4', b_n=4, b_rebal=15, b_cut=0.70, b_win=20)
    SBB = dict(bx=0.12, by_=0.05, bf=0.4)
    T15 = dict(BB, b_take=0.15)
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    if groups is None or 'O1' in groups:
        for rs in (12, 15, 20):
            for hyst in (0.005, 0.01, 0.015):
                for mh in (5, 10):
                    add('F6sO_rs%d_h%s_mh%d' % (rs, str(hyst).replace('.', ''), mh),
                        rs=rs, hyst=hyst, mh=mh,
                        evalfreq='daily', brake_daily=False, **SBB, **dict(T15))
    if groups is None or 'O2' in groups:
        for rs in (12, 15, 20):
            for mh in (0, 5):
                add('F6sO_rs%d_h002_mh%d' % (rs, mh),
                    rs=rs, hyst=0.02, mh=mh,
                    evalfreq='daily', brake_daily=False, **SBB, **dict(T15))
    return cfgs


def build_stageP(groups=None):
    cfgs = []
    BB = dict(sel='c_4', b_cut=0.70, b_win=20)
    SBB = dict(bx=0.12, by_=0.05, bf=0.4)
    CH = dict(rs=62, hyst=0.045, mh=0, evalfreq='daily', brake_daily=False)
    T15 = dict(BB, b_n=4, b_rebal=15, b_take=0.15)
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    if groups is None or 'P1' in groups:
        for n2 in (5, 6):
            for R2 in (15, 20, 30):
                for rs in (60, 62):
                    add('F6sP_N%dR%d_rs%d' % (n2, R2, rs),
                        rs=rs, hyst=0.045, mh=0,
                        evalfreq='daily', brake_daily=False, **SBB, **dict(BB, b_n=n2, b_rebal=R2, b_take=0.15))
    if groups is None or 'P2' in groups:
        for stop in (0.10, 0.15, 0.35, 0.50):
            add('F6sP_stop%s' % str(stop).replace('.', ''),
                stop=stop, **CH, **SBB, **dict(T15))
    if groups is None or 'P3' in groups:
        for bx in (0.06, 0.08, 0.10):
            add('F6sP_bx%s' % str(bx).replace('.', ''),
                **CH, **dict(SBB, bx=bx), **dict(T15))
    if groups is None or 'P4' in groups:
        for mh in (7, 12):
            add('F6sP_mh%d' % mh, rs=62, hyst=0.045, mh=mh, evalfreq='daily', brake_daily=False, **SBB, **dict(T15))
    return cfgs


def build_stageQ(groups=None):
    cfgs = []
    BB = dict(sel='c_4', b_n=4, b_rebal=15, b_cut=0.70, b_win=20)
    SBB = dict(bx=0.12, by_=0.05, bf=0.4)
    CH = dict(rs=62, hyst=0.045, mh=0, evalfreq='daily', brake_daily=False)
    T15 = dict(BB, b_take=0.15)
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    if groups is None or 'Q1' in groups:
        for stop in (0.21, 0.22, 0.23, 0.24):
            add('F6sQ_stop%s' % str(stop).replace('.', ''),
                stop=stop, **CH, **SBB, **dict(T15))
    if groups is None or 'Q2' in groups:
        for band in ((0.10, 0.30), (0.15, 0.30), (0.05, 0.25), (0.05, 0.20)):
            add('F6sQ_band%s_%s' % (str(band[0]).replace('.', ''), str(band[1]).replace('.', '')),
                band=band, **CH, **SBB, **dict(T15))
        for gate in (0.0, 0.10):
            add('F6sQ_gate%s' % str(gate).replace('.', ''),
                gate=gate, **CH, **SBB, **dict(T15))
    if groups is None or 'Q3' in groups:
        for cut in (0.5, 0.9):
            add('F6sQ_cut%s' % str(cut).replace('.', ''),
                **CH, **SBB, **dict(T15, b_cut=cut))
    if groups is None or 'Q4' in groups:
        for hyst in (0.044, 0.046):
            add('F6sQ_b013stop03_h%s' % str(hyst).replace('.', ''),
                bx=0.13, by_=0.05, bf=0.4, stop=0.30, hyst=hyst,
                rs=62, mh=0, evalfreq='daily', brake_daily=False, **dict(T15))
    if groups is None or 'Q5' in groups:
        for exp in (0.7, 0.8):
            add('F6sQ_exp%s' % str(exp).replace('.', ''),
                exp_b=exp, **CH, **SBB, **dict(T15))
    if groups is None or 'Q7' in groups:
        for bx in (0.115, 0.125):
            add('F6sQ_bx%s' % str(bx).replace('.', ''),
                **CH, **dict(SBB, bx=bx), **dict(T15))
    return cfgs


def build_stageR(groups=None):
    cfgs = []
    SBB = dict(bx=0.12, by_=0.05, bf=0.4)
    BASE = dict(b_n=4, b_rebal=15, b_cut=0.70, b_win=20)
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    if groups is None or 'R1' in groups:
        for rs in (40, 45, 50, 55, 65, 70):
            for hyst in (0.04, 0.045, 0.05):
                add('F6sR_c4_rs%d_h%s' % (rs, str(hyst).replace('.', '')),
                    sel='c_4', rs=rs, hyst=hyst, mh=0,
                    evalfreq='daily', brake_daily=False, **SBB, **dict(BASE, b_take=0.15))
    if groups is None or 'R2' in groups:
        for tp in (0.15, 0.25):
            for rs in (40, 45, 50, 55, 60, 62):
                for hyst in (0.03, 0.04, 0.05):
                    add('F6sR_turn_T%s_rs%d_h%s' % (str(tp).replace('.', ''), rs, str(hyst).replace('.', '')),
                        sel='turn20', rs=rs, hyst=hyst, mh=0,
                        evalfreq='daily', brake_daily=False, **SBB, **dict(BASE, b_take=tp))
    if groups is None or 'R3' in groups:
        for tp in (0.15, 0.25):
            for rs in (55, 60, 62):
                for hyst in (0.04, 0.05):
                    add('F6sR_vol_T%s_rs%d_h%s' % (str(tp).replace('.', ''), rs, str(hyst).replace('.', '')),
                        sel='vol20', rs=rs, hyst=hyst, mh=0,
                        evalfreq='daily', brake_daily=False, **SBB, **dict(BASE, b_take=tp))
    return cfgs


def build_stageS(groups=None):
    cfgs = []
    BB = dict(sel='c_4', b_n=4, b_rebal=15, b_cut=0.70, b_win=20)
    SBB = dict(bx=0.12, by_=0.05, bf=0.4)
    T15 = dict(BB, b_take=0.15)
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    if groups is None or 'S1' in groups:
        for sw in (0.10, 0.15, 0.20, 0.35, 0.50):
            add('F6sS_swstop%s' % str(sw).replace('.', ''),
                stop=0.25, sw_stop=sw, rs=62, hyst=0.045, mh=0,
                evalfreq='daily', brake_daily=False, **SBB, **dict(T15))
    if groups is None or 'S2' in groups:
        for sw in (0.15, 0.35):
            add('F6sS_rs70_swstop%s' % str(sw).replace('.', ''),
                stop=0.25, sw_stop=sw, rs=70, hyst=0.045, mh=0,
                evalfreq='daily', brake_daily=False, **SBB, **dict(T15))
        for sw in (0.15, 0.35):
            add('F6sS_turn_swstop%s' % str(sw).replace('.', ''),
                stop=0.25, sw_stop=sw, rs=45, hyst=0.03, mh=0,
                evalfreq='daily', brake_daily=False, **SBB, **dict(BB, sel='turn20', b_take=0.15))
    if groups is None or 'S3' in groups:
        for rs in (66, 67, 68, 69, 71, 72):
            for hyst in (0.045, 0.05):
                add('F6sS_c4_rs%d_h%s' % (rs, str(hyst).replace('.', '')),
                    stop=0.25, rs=rs, hyst=hyst, mh=0,
                    evalfreq='daily', brake_daily=False, **SBB, **dict(T15))
        for tp in (0.08, 0.10, 0.12):
            for hyst in (0.045, 0.05):
                add('F6sS_T%s_rs70_h%s' % (str(tp).replace('.', ''), str(hyst).replace('.', '')),
                    stop=0.25, rs=70, hyst=hyst, mh=0,
                    evalfreq='daily', brake_daily=False, **SBB, **dict(BB, b_take=tp))
        for mh in (10, 15):
            add('F6sS_rs70_mh%d' % mh, stop=0.25, rs=70, hyst=0.045, mh=mh,
                evalfreq='daily', brake_daily=False, **SBB, **dict(T15))
    return cfgs


def build_stageT(groups=None):
    cfgs = []
    BB = dict(sel='c_4', b_n=4, b_rebal=15, b_cut=0.70, b_win=20)
    SBB = dict(bx=0.12, by_=0.05, bf=0.4)
    T15 = dict(BB, b_take=0.15)
    CH = dict(rs=62, hyst=0.045, mh=0, evalfreq='daily', brake_daily=False)
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    if groups is None or 'T1' in groups:
        for R2 in (13, 14, 16, 17):
            add('F6sT_R%d' % R2, **CH, **SBB, **dict(T15, b_rebal=R2))
    if groups is None or 'T2' in groups:
        for hyst in (0.025, 0.03):
            add('F6sT_h%s' % str(hyst).replace('.', ''),
                hyst=hyst, rs=62, mh=0, evalfreq='daily', brake_daily=False, **SBB, **dict(T15))
        for rs in (61, 63):
            add('F6sT_rs%d_h003' % rs,
                hyst=0.03, rs=rs, mh=0, evalfreq='daily', brake_daily=False, **SBB, **dict(T15))
    if groups is None or 'T3' in groups:
        for mh in (10, 15):
            add('F6sT_rs71_mh%d' % mh, rs=71, hyst=0.045, mh=mh,
                evalfreq='daily', brake_daily=False, **SBB, **dict(T15))
        for bf in (0.2, 0.25):
            add('F6sT_bf%s' % str(bf).replace('.', ''),
                **CH, **dict(SBB, bf=bf), **dict(T15))
        for R2 in (20, 30):
            add('F6sT_rs70_R%d' % R2, rs=70, hyst=0.045, mh=0,
                evalfreq='daily', brake_daily=False, **SBB, **dict(T15, b_rebal=R2))
    if groups is None or 'T4' in groups:
        for tp in (0.10, 0.12):
            add('F6sT_turn_T%s_rs45' % str(tp).replace('.', ''),
                rs=45, hyst=0.03, mh=0, evalfreq='daily', brake_daily=False,
                **SBB, **dict(BB, sel='turn20', b_take=tp))
        for rs in (43, 44, 46, 47):
            add('F6sT_turn_rs%d' % rs,
                rs=rs, hyst=0.03, mh=0, evalfreq='daily', brake_daily=False,
                **SBB, **dict(BB, sel='turn20', b_take=0.15))
    return cfgs


def build_stageU(groups=None):
    cfgs = []
    BB = dict(sel='c_4', b_n=4, b_rebal=15, b_cut=0.70, b_win=20)
    SBB = dict(bx=0.12, by_=0.05, bf=0.4)
    T15 = dict(BB, b_take=0.15)
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    if groups is None or 'U1' in groups:
        for rs in (20, 30, 45):
            add('F6sU_grid_rs%d' % rs, rs=rs, hyst=0.0, mh=0,
                evalfreq='grid', brake_daily=False, **SBB, **dict(T15))
        add('F6sU_turn_grid_rs45', rs=45, hyst=0.0, mh=0,
            evalfreq='grid', brake_daily=False, **SBB, **dict(BB, sel='turn20', b_take=0.15))
    if groups is None or 'U2' in groups:
        for rs in (62, 70):
            add('F6sU_bd_rs%d' % rs, rs=rs, hyst=0.045, mh=0,
                evalfreq='daily', brake_daily=True, **SBB, **dict(T15))
    if groups is None or 'U3' in groups:
        add('F6sU_lockB_T015', lock='B', bx=0.18, by_=0.08, bf=0.6, rs=60, **dict(T15))
        add('F6sU_lockB_T015_soft', lock='B', bx=0.12, by_=0.05, bf=0.4, rs=60, **dict(T15))
    if groups is None or 'U4' in groups:
        for mh in (4, 6, 8):
            add('F6sU_mh%d' % mh, rs=62, hyst=0.045, mh=mh,
                evalfreq='daily', brake_daily=False, **SBB, **dict(T15))
    if groups is None or 'U5' in groups:
        for rs in (45, 70):
            add('F6sU_band002_rs%d' % rs, band=(0.02, 0.30),
                rs=rs, hyst=0.045, mh=0, evalfreq='daily', brake_daily=False, **SBB, **dict(T15))
        add('F6sU_gate015_rs45', gate=-0.15,
            rs=45, hyst=0.045, mh=0, evalfreq='daily', brake_daily=False, **SBB, **dict(T15))
    return cfgs


def build_stageV(groups=None):
    cfgs = []
    BB = dict(sel='c_4', b_n=4, b_rebal=15, b_cut=0.70, b_win=20)
    SBB = dict(bx=0.12, by_=0.05, bf=0.4)
    T15 = dict(BB, b_take=0.15)
    CH = dict(rs=62, hyst=0.045, mh=0, evalfreq='daily', brake_daily=False)
    def add(tag, **kw):
        cfgs.append(dict(tag=tag, **kw))
    if groups is None or 'V1' in groups:
        for band in ((0.05, 0.50), (0.02, 0.50), (0.05, 1.00), (0.00, 0.30)):
            add('F6sV_band%s_%s' % (str(band[0]).replace('.', ''), str(band[1]).replace('.', '')),
                band=band, **CH, **SBB, **dict(T15))
    return cfgs

def save(rows):
    atomic_write_json(ROOT / 'results' / 'r30_bt' / 'fam_F6_stage.json', rows)

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

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default=None)
    ap.add_argument('--stage', default='all')
    ap.add_argument('--groups', default=None)
    args = ap.parse_args()
    cfgs = build_configs()
    if args.only is not None:
        c = next((c for c in cfgs if c['tag'] == args.only), None)
        if c is None:
            print('only tag not found: ' + str(args.only), flush=True)
        else:
            tag = c.pop('tag')
            print(json.dumps(run_switch(tag, **c), ensure_ascii=False), flush=True)
    elif args.stage in ('E', 'F'):
        import os
        rows = []
        fp = ROOT / 'results' / 'r30_bt' / 'fam_F6_stage.json'
        if fp.exists():
            rows = json.loads(fp.read_text())
        have = set(r['tag'] for r in rows)
        builder = build_stageE if args.stage == 'E' else None
        if args.stage == 'F':
            grps = (args.groups.split(',') if args.groups else None)
            todo = build_stageF(grps) if not (grps and grps[0][0] in 'GHIJKLMNOPQRSTUV') else (build_stageG(grps) if grps[0][0] == 'G' else (build_stageH(grps) if grps[0][0] == 'H' else (build_stageI(grps) if grps[0][0] == 'I' else (build_stageJ(grps) if grps[0][0] == 'J' else (build_stageK(grps) if grps[0][0] == 'K' else (build_stageL(grps) if grps[0][0] == 'L' else (build_stageM(grps) if grps[0][0] == 'M' else (build_stageN(grps) if grps[0][0] == 'N' else (build_stageO(grps) if grps[0][0] == 'O' else (build_stageP(grps) if grps[0][0] == 'P' else (build_stageQ(grps) if grps[0][0] == 'Q' else (build_stageR(grps) if grps[0][0] == 'R' else (build_stageS(grps) if grps[0][0] == 'S' else (build_stageT(grps) if grps[0][0] == 'T' else (build_stageU(grps) if grps[0][0] == 'U' else build_stageV(grps))))))))))))))))
        else:
            todo = builder()
        for c in todo:
            tag = c.pop('tag')
            if tag in have:
                print('SKIP ' + tag, flush=True)
                continue
            run_and_log(tag, rows, **c)
        best = sorted(rows, key=lambda r: (r.get('pass_all', False), r.get('margin', -999), r.get('total', 0)), reverse=True)[:10]
        print('=== F6 TOP10 (after %s) ===' % args.stage, flush=True)
        for b in best:
            print(json.dumps({k: b.get(k) for k in ('tag', 'b_sel', 'b_n', 'b_rebal', 'b_take', 'bx', 'by_', 'bf', 'rs', 'hyst', 'mh', 'evalfreq', 'lock', 'total', 'mdd', 'y2024_slice', 'y2024_yoy', 'y2024_mdd', 'y2025_yoy', 'y2025_mdd', 'y2026_slice', 'y2026_yoy', 'y2026_mdd', 'trades', 'cost', 'switches', 'brakes', 'mode', 'pass_all', 'margin')}, ensure_ascii=False), flush=True)
        save(rows)
        print('saved ' + str(len(rows)) + ' rows', flush=True)
    elif args.stage in ('A', 'B'):
        rows = []
        for c in cfgs:
            is_b = c['tag'].startswith('F6sB_')
            if (args.stage == 'B') != is_b:
                continue
            tag = c.pop('tag')
            run_and_log(tag, rows, **c)
        print('saved stage %s rows=%d' % (args.stage, len(rows)), flush=True)
    else:
        rows = []
        # Stage A+B
        for c in cfgs:
            tag = c.pop('tag')
            run_and_log(tag, rows, **c)
        anchors = topn(rows, 3)
        print('ANCHORS: ' + json.dumps([(a['tag'], a.get('margin'), a.get('y2024_slice')) for a in anchors], ensure_ascii=False), flush=True)
        # Stage C: brake microgrid on top3 (keep each anchor's rs/hyst/evalfreq)
        for a in anchors:
            base = dict(sel=a['b_sel'], b_n=a['b_n'], b_rebal=a['b_rebal'], b_take=a['b_take'],
                        b_cut=a['b_cut'], b_win=a['b_win'], rs=a['rs'], hyst=a['hyst'],
                        mh=a.get('mh', 0), evalfreq=a['evalfreq'], brake_daily=a['brake_daily'])
            for (bx, by_, bf) in BRAKES_C:
                tag = a['tag'] + '_b%s%s%s' % (str(bx).replace('.', ''), str(by_).replace('.', ''), str(bf).replace('.', ''))
                if any(r['tag'] == tag for r in rows):
                    continue
                run_and_log(tag, rows, bx=bx, by_=by_, bf=bf, **base)
        # Stage D: refine around global best daily c_4 (rs/hyst neighbors, mh, brake_daily, cut/win, band/gate, exp, N/R/TP)
        best_daily = [r for r in rows if r['b_sel'] == 'c_4' and r['evalfreq'] == 'daily']
        best_daily = sorted(best_daily, key=lambda r: (r.get('margin', -999),), reverse=True)[:2]
        for a in best_daily:
            base = dict(sel=a['b_sel'], b_n=a['b_n'], b_rebal=a['b_rebal'], b_take=a['b_take'],
                        b_cut=a['b_cut'], b_win=a['b_win'], bx=a['bx'], by_=a['by_'], bf=a['bf'],
                        hyst=a['hyst'], mh=a.get('mh', 0), evalfreq='daily', brake_daily=a['brake_daily'])
            for rs in sorted(set([max(8, a['rs'] - 3), max(8, a['rs'] - 2), a['rs'] + 2, a['rs'] + 3])):
                tag = a['tag'] + '_rs%d' % rs
                if any(r['tag'] == tag for r in rows):
                    continue
                run_and_log(tag, rows, **dict(base, rs=rs))
            for h in sorted(set([round(max(0.01, a['hyst'] - 0.01), 2), round(a['hyst'] + 0.01, 2)])):
                tag = a['tag'] + '_h%s' % str(h).replace('.', '')
                if any(r['tag'] == tag for r in rows):
                    continue
                run_and_log(tag, rows, **dict(base, rs=a['rs'], hyst=h))
            for mh in (5, 10):
                if mh == a.get('mh', 0):
                    continue
                tag = a['tag'] + '_mh%d' % mh
                if any(r['tag'] == tag for r in rows):
                    continue
                run_and_log(tag, rows, **dict(base, rs=a['rs'], mh=mh))
            if not a['brake_daily']:
                tag = a['tag'] + '_bd'
                run_and_log(tag, rows, **dict(base, rs=a['rs'], brake_daily=True))
            for cut, win in ((0.6, 20), (0.8, 20), (0.7, 10), (0.7, 40)):
                if cut == a['b_cut'] and win == a['b_win']:
                    continue
                tag = a['tag'] + '_c%s_w%d' % (str(cut).replace('.', ''), win)
                if any(r['tag'] == tag for r in rows):
                    continue
                run_and_log(tag, rows, **dict(base, rs=a['rs'], b_cut=cut, b_win=win))
            for band, gate in (((0.02, 0.30), -1.0), ((0.05, 0.30), -0.15)):
                if list(band) == a['b_band'] and gate == a['b_gate']:
                    continue
                tag = a['tag'] + '_band%s_gate%s' % (str(band[0]).replace('.', ''), str(gate).replace('.', '').replace('-', 'm'))
                if any(r['tag'] == tag for r in rows):
                    continue
                run_and_log(tag, rows, **dict(base, rs=a['rs'], band=band, gate=gate))
            for n2, R2, tp2 in ((5, 15, 0.45), (4, 20, 0.45), (4, 15, 0.6)):
                if n2 == a['b_n'] and R2 == a['b_rebal'] and tp2 == a['b_take']:
                    continue
                tag = a['tag'] + '_N%dR%dT%s' % (n2, R2, str(tp2).replace('.', ''))
                if any(r['tag'] == tag for r in rows):
                    continue
                run_and_log(tag, rows, **dict(base, rs=a['rs'], b_n=n2, b_rebal=R2, b_take=tp2))
        # Backup leg spot-checks: vol20/turn20 daily on rs30-50/h0.02-0.05 @ default brake
        for sel in ('vol20', 'turn20'):
            for rs, hyst in ((30, 0.02), (40, 0.03), (45, 0.04), (50, 0.05)):
                tag = 'F6_%s_daily_rs%d_h%s' % (sel, rs, str(hyst).replace('.', ''))
                run_and_log(tag, rows, sel=sel, b_n=4, b_rebal=15, b_take=0.45,
                            bx=0.18, by_=0.08, bf=0.6, rs=rs, hyst=hyst,
                            mh=0, evalfreq='daily', brake_daily=False)
        best = sorted(rows, key=lambda r: (r.get('pass_all', False), r.get('margin', -999), r.get('total', 0)), reverse=True)[:10]
        print('=== F6 TOP10 ===', flush=True)
        for b in best:
            print(json.dumps({k: b.get(k) for k in ('tag', 'b_sel', 'b_n', 'b_rebal', 'b_take', 'bx', 'by_', 'bf', 'rs', 'hyst', 'mh', 'evalfreq', 'lock', 'total', 'mdd', 'y2024_slice', 'y2024_yoy', 'y2024_mdd', 'y2025_yoy', 'y2025_mdd', 'y2026_slice', 'y2026_yoy', 'y2026_mdd', 'trades', 'cost', 'switches', 'brakes', 'mode', 'pass_all', 'margin')}, ensure_ascii=False), flush=True)
        save(rows)
        print('saved ' + str(len(rows)) + ' rows', flush=True)

def attribution(tag):
    import pandas as pd
    rows = json.loads((ROOT / 'results' / 'r30_bt' / 'fam_F6_stage.json').read_text())
    r = next(x for x in rows if x['tag'] == tag)
    kw = dict(sel=r['b_sel'], b_n=r['b_n'], b_rebal=r['b_rebal'], b_take=r['b_take'],
              b_cut=r['b_cut'], b_win=r['b_win'], band=tuple(r['b_band']), gate=r['b_gate'],
              bx=r['bx'], by_=r['by_'], bf=r['bf'], rs=r['rs'], hyst=r['hyst'],
              mh=r.get('mh', 0), evalfreq=r['evalfreq'], brake_daily=r['brake_daily'],
              stop=r['stop'], exp_b=r['exp_b'], lock=r['lock'])
    full = run_switch(tag + '_attr', **kw)
    # rebuild eq via run_strategy_switch internals is complex; instead compare shadows
    rb = get_shadow_b(r['b_sel'], tuple(r['b_band']), r['b_gate'], r['b_cut'], r['b_win'],
                      r['b_n'], r['b_rebal'], r['b_take'], r['stop'], r['exp_b'])
    def monthly(eq):
        eq = eq.iloc[:, 0] if isinstance(eq, pd.DataFrame) else eq
        m = eq.resample('ME').last()
        return (m / m.shift(1) - 1) * 100
    ma = monthly(ra.eq).rename('A')
    mb = monthly(rb.eq).rename('B')
    df = __import__('pandas').concat([ma, mb], axis=1)
    df2024 = df[df.index.year == 2024]
    print('=== monthly % A vs B shadow (trailing-only) ===')
    for idx, row in df2024.iterrows():
        print(idx.strftime('%Y-%m'), 'A=%7.2f' % row['A'], 'B=%7.2f' % row['B'])
    print('switch_log:', json.dumps(r['switch_log'], ensure_ascii=False))
    print('brake_log:', json.dumps(r['brake_log'], ensure_ascii=False))
    return full