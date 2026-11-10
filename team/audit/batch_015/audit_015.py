#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""batch_015 独立审计: E6 dd_breaker 0触发核查 + E5/基线 + bond腿NAV合成 + 8项对抗.
禁调 team/harness.py team/lib; 日线腿用 prior_check (审计员自写); dd_breaker 自实现
(策略自身 trailing-peak 回撤<=-8% 触发降半仓、当日收盘砍半仓+后续买入减半, 回到-2%恢复).
数据: data/pivots_long_clean.pkl, data/bond_511880.pkl, results/_cache/index_000905.pkl(仅作触发口径对照).
用法: .venv/bin/python team/audit/batch_015/audit_015.py [--out team/audit/out/batch_015_audit.json]
"""
from __future__ import annotations
import argparse, json, os, sys
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..'))
import prior_check as pc
ROOT = pc.ROOT
MB = ('688', '689', '300', '301', '8', '4')
CAP = 50000.0
BASE_ID = 'b015_G0_BASELINE_N4R30TP45e09'
E6_ID = 'b015_E6_N4R30TP45_ddhalf'
E5_ID = 'b015_E5_N4R30_N5R40none_70_30'

def wilson(k, n, z=1.96):
    if n == 0: return (float('nan'), float('nan'))
    p = k / n; d = 1 + z*z/n; c = (p + z*z/(2*n))/d
    h = z*((p*(1-p)/n + z*z/(4*n*n))**0.5)/d
    return (c-h, c+h)

def enrich(label, res, save=True, tag=None):
    m = pc.metrics(res)
    tr = res.trades
    ev = tr[(tr.exit_date >= pc.EVAL_START) & (tr.exit_date <= pc.EVAL_END)] if len(tr) else tr
    pnl = ev.groupby('code')['net_pnl'].sum().sort_values(ascending=False) if len(ev) else pd.Series(dtype=float)
    tot = float(pnl.sum()) if len(pnl) else 0.0
    w = res.exposure.loc[pc.EVAL_START:pc.EVAL_END]
    reasons = ev['reason'].value_counts().to_dict() if len(ev) and 'reason' in ev.columns else {}
    out = dict(label=label, fresh_total=m['total_2026'], fresh_ann=m['ann_2026'],
        mdd=m['mdd_2026'], wp=m['win_period'], n_periods=m['n_periods'],
        period_rets=m['period_rets'], last_partial_ret=m['last_partial_ret'],
        wm=m['win_month'], wm_n=m['win_month_n'], monthly=m['monthly_rets'],
        wt=m['win_trade'], n_trades=m['n_trades'], trade_win_n=m['trade_win_n'],
        avg_win=m['avg_win'], avg_loss=m['avg_loss'], profit_factor=m['profit_factor'],
        vol=m['vol'], sharpe=m['sharpe'], calmar_total_over_mdd=(m['total_2026']/abs(m['mdd_2026']) if m['mdd_2026']<0 else float('nan')),
        exposure_mean=float(w.mean()), exposure_min=float(w.min()),
        top1_share=float(pnl.iloc[0]/tot) if len(pnl) and tot else float('nan'),
        top3_share=float(pnl.head(3).sum()/tot) if len(pnl) and tot else float('nan'),
        top3_codes=list(pnl.index[:3]), n_codes=int(len(pnl)),
        cost_total=float(res.meta.get('total_cost',0.0)),
        cost_pct_cap=float(res.meta.get('total_cost',0.0))/m['base_equity'],
        skipped_lot=int(res.meta.get('skipped_lot',0)),
        stale_buys=int(res.meta.get('stale_buys',0)), stale_sells=int(res.meta.get('stale_sells',0)),
        n_rebalances=int(res.meta.get('n_rebalances',0)),
        reasons={str(k): int(v) for k,v in reasons.items()},
        end_equity=m['end_equity'], base_equity=m['base_equity'])
    k = int(round(m['win_period']*m['n_periods'])) if m['n_periods'] else 0
    out['wilson_wp'] = list(wilson(k, m['n_periods']))
    out['wilson_wt'] = list(wilson(m['trade_win_n'], m['n_trades']))
    try:
        ab = m['win_month_n'].split('/')
        out['wilson_wm'] = list(wilson(int(ab[0]), int(ab[1])))
    except Exception:
        out['wilson_wm'] = [float('nan'), float('nan')]
    if save:
        res.trades.to_csv(os.path.join(ROOT, 'team', 'audit', 'out', f'b015_{tag or label}_trades.csv'), index=False)
        res.eq.to_csv(os.path.join(ROOT, 'team', 'audit', 'out', f'b015_{tag or label}_equity.csv'))
    return out, m, res

def bootstrap_daily(res, base, n_iter=1000, seed=7):
    rng = np.random.default_rng(seed)
    win = res.eq.loc[pc.EVAL_START:pc.EVAL_END]
    dret = win.pct_change(); dret.iloc[0] = win.iloc[0]/base - 1.0
    r = dret.to_numpy(dtype=float)
    sims = np.empty(n_iter)
    for i in range(n_iter):
        sims[i] = float(np.prod(1.0+rng.choice(r, size=len(r), replace=True))-1.0)
    return dict(p5=float(np.quantile(sims,0.05)), p50=float(np.quantile(sims,0.5)),
                p_neg=float((sims<0).mean()), mean=float(sims.mean()), n_iter=n_iter, seed=seed)

def leg_kw(n, rebal, take, capital, exposure=0.9):
    return dict(factor='amihud_60', n=n, rebal=rebal, stop=None, take=take,
                capital=capital, lot=100, cost_one_way=None, slip=0.002,
                run_start='2026-01-05', phase=0, legacy_grid=False,
                stop_exec='next', exclude=MB, exposure=exposure)

def bond_nav(root):
    b = pd.read_pickle(os.path.join(root, 'data', 'bond_511880.pkl'))
    b['date'] = pd.to_datetime(b['date'])
    return b.set_index('date')['close'].astype(float).sort_index()

def synth_ensemble(inp, legs, R_seg=30):
    eqs, trs, cost = [], [], 0.0
    for kw, w in legs:
        r = pc.run_strategy(inp, **kw)
        eqs.append(r.eq)
        t = r.trades.copy()
        if len(t):
            t['leg'] = f"{kw['n']}R{kw['rebal']}TP{kw['take']}"
            trs.append(t)
        cost += float(r.meta.get('total_cost', 0.0))
    ens = pd.concat(eqs, axis=1).sum(axis=1)
    ens.name = 'eq'
    tr = pd.concat(trs, ignore_index=True) if trs else pd.DataFrame()
    dates = inp.dates
    grid = [i for i in inp.grid(R_seg, 0) if dates[i] >= pd.Timestamp('2026-01-05') and i + 1 < len(dates)]
    execs = [(i + 1, float(ens.loc[dates[i + 1]])) for i in grid if dates[i + 1] in ens.index]
    per = pc.build_periods(ens, execs, inp.ret, dates, R_seg)
    res = pc.Result(eq=ens, trades=tr, periods=per,
                    meta=dict(capital=CAP, total_cost=cost, cost_by_year={},
                              n_rebalances=len(execs)),
                    exposure=(ens / ens.cummax() * 0 + 0.9), nhold=pd.Series(0, index=ens.index))
    return res, cost

def run_dd_breaker(inp, *, n=4, rebal=30, take=0.45, capital=CAP, lot=100, slip=0.002,
                   run_start='2026-01-05', phase=0, exclude=MB, factor='amihud_60',
                   exposure=0.9, trig=-0.08, recover=-0.02, cut=0.5):
    """自研 dd_breaker: 自身 trailing-peak 回撤<=trig 当日收盘砍半仓+后续买入减半; 回到>=recover 恢复."""
    kw = dict(factor=factor, n=n, rebal=rebal, stop=None, take=take, capital=capital,
              lot=lot, cost_one_way=None, slip=slip, run_start=run_start, phase=phase,
              legacy_grid=False, stop_exec='next', exclude=tuple(exclude), exposure=exposure)
    # 为记录触发, 这里用简化版: 先跑无breaker得权益路径定触发日, 再跑带breaker版
    r0 = pc.run_strategy(inp, **kw)
    eq0 = r0.eq
    peak = float(eq0.iloc[0])
    trig_days, rec_days = [], []
    armed = False
    for d, v in eq0.items():
        if v > peak:
            peak = float(v)
        dd = float(v) / peak - 1.0
        if not armed and dd <= trig:
            trig_days.append(d); armed = True
        elif armed and dd >= recover:
            rec_days.append(d); armed = False
    # 带breaker重跑: 触发日收盘砍半仓, armed期间买入量减半
    c, mark, dates, ret = inp.close, inp.mark, inp.dates, inp.ret
    n_dates = len(dates)
    grid = inp.grid(rebal, phase, legacy=False)
    run_ts = pd.Timestamp(run_start)
    grid = [i for i in grid if dates[i] >= run_ts]
    exec_map = {}
    for g in grid:
        ei = g + 1
        if ei < n_dates:
            exec_map[ei] = g
    loop_start, loop_end = grid[0], min(int(dates.searchsorted(pc.EVAL_END, side='right') - 1), n_dates - 1)
    trig_set = set(pd.to_datetime(trig_days)); rec_set = set(pd.to_datetime(rec_days))
    cash, pos, eq_rows, trades = float(capital), {}, [], []
    total_cost, cost_by_year, mult, n_trig, n_rec = 0.0, {}, 1.0, 0, 0
    peak2 = float(capital)
    cur_eq = float(capital)
    trig_log, rec_log = [], []
    def px(day, code):
        v = mark.at[day, code]
        return float(v) if pd.notna(v) else float('nan')
    for i in range(loop_start, loop_end + 1):
        day = dates[i]
        if day in trig_set and mult == 1.0:
            for code in list(pos.keys()):
                p = pos[code]
                sh = p['shares'] * (1.0 - cut)
                pr = px(day, code)
                if pd.isna(pr):
                    pr = p['entry_px']
                notional = sh * pr
                fee = pc._cost_sell_real(notional, slip)
                cash += notional - fee
                total_cost += fee
                cost_by_year[int(day.year)] = cost_by_year.get(int(day.year), 0.0) + fee
                basis = p['entry_px'] * sh + p['buy_cost'] * (sh / p['shares'] if p['shares'] else 0)
                trades.append(dict(code=code, entry_day=p['entry_i'], exit_day=day, shares=sh,
                    entry_px=p['entry_px'], exit_px=pr, gross_ret=pr / p['entry_px'] - 1.0,
                    net_pnl=notional - fee - basis, net_ret=(notional - fee - basis) / basis if basis > 0 else np.nan,
                    reason='dd_halve', stale=False))
                p['shares'] -= sh
                p['buy_cost'] *= cut
                if p['shares'] <= 1e-9:
                    del pos[code]
            mult = cut
            n_trig += 1
            trig_log.append(str(day.date()))
        if day in rec_set and mult < 1.0:
            mult = 1.0
            n_rec += 1
            rec_log.append(str(day.date()))
        if i in exec_map:
            for code in list(pos.keys()):
                p = pos[code]
                pr = px(day, code)
                if pd.isna(pr):
                    pr = p['entry_px']
                notional = p['shares'] * pr
                fee = pc._cost_sell_real(notional, slip)
                cash += notional - fee
                total_cost += fee
                cost_by_year[int(day.year)] = cost_by_year.get(int(day.year), 0.0) + fee
                basis = p['entry_px'] * p['shares'] + p['buy_cost']
                trades.append(dict(code=code, entry_day=p['entry_i'], exit_day=day, shares=p['shares'],
                    entry_px=p['entry_px'], exit_px=pr, gross_ret=pr / p['entry_px'] - 1.0,
                    net_pnl=notional - fee - basis, net_ret=(notional - fee - basis) / basis if basis > 0 else np.nan,
                    reason='rebalance', stale=False))
            pos.clear()
            picks = inp.picks(dates[exec_map[i]], n, exclude=tuple(exclude), factor=factor)
            alloc = cash * exposure * mult / len(picks) if picks else 0
            for code in picks:
                pr = px(day, code)
                if pd.isna(pr) or pr <= 0:
                    continue
                sh = int(alloc / pr // lot) * lot if lot and lot > 1 else alloc / pr
                if sh <= 0:
                    continue
                notional = sh * pr
                fee = pc._cost_buy_real(notional, slip)
                if notional + fee > cash:
                    continue
                cash -= notional + fee
                total_cost += fee
                cost_by_year[int(day.year)] = cost_by_year.get(int(day.year), 0.0) + fee
                pos[code] = dict(shares=sh, entry_px=pr, entry_i=day, buy_cost=fee)
        mv = sum(p['shares'] * (px(day, cc) if not pd.isna(px(day, cc)) else p['entry_px']) for cc, p in pos.items())
        eq_rows.append((day, cash + mv))
    eq = pd.Series([x[1] for x in eq_rows], index=[x[0] for x in eq_rows], name='eq')
    tr = pd.DataFrame(trades)
    if len(tr):
        tr['entry_date'] = pd.to_datetime(tr['entry_day'])
        tr['exit_date'] = pd.to_datetime(tr['exit_day'])
        tr['net_pnl'] = tr['net_pnl'].astype(float)
        tr['net_ret'] = tr['net_ret'].astype(float)
        tr['shares'] = tr['shares'].astype(float)
        tr['entry_px'] = tr['entry_px'].astype(float)
        tr['exit_px'] = tr['exit_px'].astype(float)
    exp = pd.Series(0.9, index=eq.index)
    meta = dict(n=n, rebal=rebal, take=take, capital=capital, lot=lot, dd_trigger=trig,
                dd_cut=cut, n_dd_trig=n_trig, n_dd_rec=n_rec, trig_log=trig_log, rec_log=rec_log,
                total_cost=float(total_cost), cost_by_year={str(k): float(v) for k, v in cost_by_year.items()})
    return eq, tr, meta

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default='team/audit/out/batch_015_audit.json')
    a = ap.parse_args()
    inp = pc.get_inputs()
    nav = bond_nav(ROOT)
    out = {'e6_id': E6_ID, 'e5_id': E5_ID, 'base_id': BASE_ID}
    df = pd.read_csv(os.path.join(ROOT, 'team', 'runs', 'batch_015_results.csv'))
    # leg 复算 (fresh 2026-01-05)
    legdefs = {
        'N4R30TP45': dict(factor='amihud_60', n=4, rebal=30, stop=None, take=0.45),
        'N4R30TP30': dict(factor='amihud_60', n=4, rebal=30, stop=None, take=0.30),
        'N4R20TP45': dict(factor='amihud_60', n=4, rebal=20, stop=None, take=0.45),
        'N5R40TPnone': dict(factor='amihud_60', n=5, rebal=40, stop=None, take=None),
    }
    legres = {}
    for name, kw in legdefs.items():
        for cap in (35000.0, 25000.0, 15000.0):
            k2 = dict(kw, capital=cap, lot=100, cost_one_way=None, slip=0.002,
                      run_start='2026-01-05', phase=0, legacy_grid=False, stop_exec='next',
                      exclude=MB, exposure=0.9)
            r = pc.run_strategy(inp, **k2)
            m = pc.metrics(r)
            legres[f'{name}@{int(cap)}'] = dict(total=m['total_2026'], mdd=m['mdd_2026'],
                n_trades=m['n_trades'], end_eq=m['end_equity'], res=r)
    # bond 腿: buy-hold NAV
    b0 = float(nav.loc['2026-01-05':'2026-11-04'].iloc[0])
    b1 = float(nav.loc['2026-01-05':'2026-11-04'].iloc[-1])
    out['bond_leg'] = dict(nav_start=b0, nav_end=b1, ret=b1 / b0 - 1.0)
    def bond_leg_eq(cap):
        seg = nav.loc['2026-01-05':'2026-11-04']
        return seg / seg.iloc[0] * cap
    WIDX = nav.loc['2026-01-05':'2026-11-04'].index
    def to_full(eq, cap):
        s = eq.reindex(WIDX)
        fv = s.first_valid_index()
        if fv is not None:
            s.loc[s.index < fv] = float(cap)
        return s
    def full_leg(name, cap):
        return to_full(legres[f'{name}@{int(cap)}']['res'].eq, cap)
    def full_bond(cap):
        seg = nav.loc['2026-01-05':'2026-11-04']
        return seg / seg.iloc[0] * cap
    # ensemble 合成
    ens_defs = {
        'b015_E1_N4R30_bond_70_30': [('N4R30TP45', 35000.0, 0.7), ('BOND', 15000.0, 0.3)],
        'b015_E2_N4R30_bond_50_50': [('N4R30TP45', 25000.0, 0.5), ('BOND', 25000.0, 0.5)],
        'b015_E3_N4_N4TP30_50_50': [('N4R30TP45', 25000.0, 0.5), ('N4R30TP30', 25000.0, 0.5)],
        'b015_E4_N4R30_N4R20_50_50': [('N4R30TP45', 25000.0, 0.5), ('N4R20TP45', 25000.0, 0.5)],
        'b015_E5_N4R30_N5R40none_70_30': [('N4R30TP45', 35000.0, 0.7), ('N5R40TPnone', 15000.0, 0.3)],
        'b015_E8_N4TP45_N4TP30_70_30': [('N4R30TP45', 35000.0, 0.7), ('N4R30TP30', 15000.0, 0.3)],
    }
    for eid, legs in ens_defs.items():
        parts, cost = [], 0.0
        for name, cap, w in legs:
            if name == 'BOND':
                parts.append(full_bond(cap))
            else:
                lr = legres[f'{name}@{int(cap)}']
                parts.append(to_full(lr['res'].eq, cap))
                cost += float(lr['res'].meta.get('total_cost', 0.0))
        ens = pd.concat(parts, axis=1).sum(axis=1)
        base = ens.loc['2026-01-05':'2026-11-04'].iloc[0]
        seg = ens.loc['2026-01-05':'2026-11-04']
        tot = float(seg.iloc[-1] / base - 1)
        mdd = float((seg / seg.cummax() - 1).min())
        hrow = df[df['id'] == eid].iloc[0]
        out[eid+':mine'] = dict(fresh_total=tot, mdd=mdd, cost_total=cost)
        out[eid+':harness'] = dict(fresh_total=float(hrow['fresh_total']), mdd=float(hrow['fresh_mdd']),
            cost_paid_pct=float(hrow['fresh_cost_paid_pct']), n_trades=float(hrow['fresh_n_trades']))
        out[eid+':delta_pp'] = (tot - float(hrow['fresh_total'])) * 100.0
    # E6: plain 复算 + 自研dd_breaker (fresh + 连续)
    r_base = pc.run_strategy(inp, **dict(factor='amihud_60', n=4, rebal=30, stop=None, take=0.45,
        capital=CAP, lot=100, cost_one_way=None, slip=0.002, run_start='2026-01-05', phase=0,
        legacy_grid=False, stop_exec='next', exclude=MB, exposure=0.9))
    e6e, e6m, e6r = enrich('e6_nobreaker', r_base, save=False)
    out['e6_nobreaker'] = {k: e6e[k] for k in ('fresh_total','mdd','n_trades','cost_total')}
    for rs, tag in (('2026-01-05', 'fresh'), ('2024-01-01', 'cont')):
        eq, tr, meta = run_dd_breaker(inp, run_start=rs)
        seg = eq.loc['2026-01-05':'2026-11-04'] if tag == 'cont' else eq
        base = float(seg.iloc[0])
        tot = float(seg.iloc[-1] / base - 1)
        mdd = float((seg / seg.cummax() - 1).min())
        out[f'e6_dd:{tag}'] = dict(fresh_total=tot, mdd=mdd,
            n_trig=int(meta['n_dd_trig']), n_rec=int(meta['n_dd_rec']),
            trig_log=meta['trig_log'][:8], rec_log=meta['rec_log'][:8])
    # E6 harness 全量对照
    hrow = df[df['id'] == E6_ID].iloc[0]
    out['e6:harness'] = dict(fresh_total=float(hrow['fresh_total']), mdd=float(hrow['fresh_mdd']),
        n_trades=float(hrow['fresh_n_trades']), total_2025=float(hrow['total_2025']),
        total_2024=float(hrow['total_2024']))
    hb = df[df['id'] == BASE_ID].iloc[0]
    out['base:harness'] = dict(fresh_total=float(hb['fresh_total']), mdd=float(hb['fresh_mdd']))
    # E5 8项对抗: enrich E5 合成 (用leg equity合成 + 合并trades)
    lr1 = legres['N4R30TP45@35000']['res']; lr2 = legres['N5R40TPnone@15000']['res']
    ens = to_full(lr1.eq, 35000.0) + to_full(lr2.eq, 15000.0)
    tr = pd.concat([lr1.trades.assign(leg='N4R30'), lr2.trades.assign(leg='N5R40')], ignore_index=True)
    dates = inp.dates
    grid = [i for i in inp.grid(30, 0) if dates[i] >= pd.Timestamp('2026-01-05') and i + 1 < len(dates)]
    execs = [(i + 1, float(ens.loc[dates[i + 1]])) for i in grid if dates[i + 1] in ens.index]
    per = pc.build_periods(ens, execs, inp.ret, dates, 30)
    er = pc.Result(eq=ens, trades=tr, periods=per,
                   meta=dict(capital=CAP, total_cost=float(lr1.meta.get('total_cost',0.0))+float(lr2.meta.get('total_cost',0.0)), cost_by_year={}),
                   exposure=(ens / ens.cummax() * 0 + 0.9), nhold=pd.Series(0, index=ens.index))
    ee, em, erx = enrich('e5', er)
    ee['bootstrap'] = bootstrap_daily(erx, em['base_equity'])
    out['e5'] = ee
    eb, mb, rb = enrich('base', r_base, save=False)
    eb['bootstrap'] = bootstrap_daily(rb, mb['base_equity'])
    out['base'] = eb
    out['e5:delta_pp_vs_harness'] = (ee['fresh_total'] - float(df[df['id']==E5_ID].iloc[0]['fresh_total']))*100.0
    out['base:delta_pp_vs_harness'] = (eb['fresh_total'] - float(hb['fresh_total']))*100.0
    # E5 攻击项: cost08 (legs各按0.8%重跑后合成)
    out['e5:cost08_note'] = 'legs各按0.8%重跑后合成'
    ens_c = None
    cost_c = 0.0
    for lname, cap, w in (('N4R30TP45', 35000.0, 0.7), ('N5R40TPnone', 15000.0, 0.3)):
        rc = pc.run_strategy(inp, **dict(legdefs[lname], capital=cap, lot=100, cost_one_way=0.008, slip=0.002, run_start='2026-01-05', phase=0, legacy_grid=False, stop_exec='next', exclude=MB, exposure=0.9))
        cost_c += float(rc.meta.get('total_cost', 0.0))
        ens_c = rc.eq if ens_c is None else ens_c + rc.eq
    segc = ens_c.loc['2026-01-05':'2026-11-04']
    out['e5:cost08'] = dict(fresh_total=float(segc.iloc[-1]/segc.iloc[0]-1),
        mdd=float((segc/segc.cummax()-1).min()), cost_total=cost_c)
    # phase/OOS/exTop3/lag1/wilson/tradability 对 E5 合成 (legs 同 phase)
    phe = {}
    for p in (-10, -5, 0, 5, 10):
        eqs = []
        for lname, cap, w in (('N4R30TP45', 35000.0, 0.7), ('N5R40TPnone', 15000.0, 0.3)):
            rp = pc.run_strategy(inp, **dict(legdefs[lname], capital=cap, lot=100, cost_one_way=None, slip=0.002, run_start='2026-01-05', phase=p, legacy_grid=False, stop_exec='next', exclude=MB, exposure=0.9))
            eqs.append(rp.eq)
        ensp = pd.concat(eqs, axis=1).sum(axis=1)
        segp = ensp.loc['2026-01-05':'2026-11-04']
        phe[str(p)] = dict(fresh_total=float(segp.iloc[-1]/segp.iloc[0]-1),
            mdd=float((segp/segp.cummax()-1).min()))
    out['e5:phase'] = phe
    # E5 OOS2025 (连续legs)
    eqs25, b25 = [], None
    for lname, cap, w in (('N4R30TP45', 35000.0, 0.7), ('N5R40TPnone', 15000.0, 0.3)):
        k2 = dict(legdefs[lname], capital=cap, lot=100, cost_one_way=None, slip=0.002, run_start='2024-01-01', phase=0, legacy_grid=False, stop_exec='next', exclude=MB, exposure=0.9)
        ro = pc.run_strategy(inp, **k2)
        eqs25.append(ro.eq)
    enso = pd.concat(eqs25, axis=1).sum(axis=1)
    sego = enso.loc['2025-01-01':'2025-12-31']; bo = enso.loc[:'2024-12-31']
    bb = float(bo.iloc[-1]) if len(bo) else CAP
    out['e5:oos2025'] = dict(total=float(sego.iloc[-1]/bb-1), mdd=float((sego/sego.cummax()-1).min()))
    # exTop3对E5: 剔除合成top3后两腿重跑
    top3 = out['e5']['top3_codes']
    eqsX = []
    for lname, cap, w in (('N4R30TP45', 35000.0, 0.7), ('N5R40TPnone', 15000.0, 0.3)):
        k2 = dict(legdefs[lname], capital=cap, lot=100, cost_one_way=None, slip=0.002, run_start='2026-01-05', phase=0, legacy_grid=False, stop_exec='next', exclude=tuple(MB)+tuple(top3), exposure=0.9)
        rx = pc.run_strategy(inp, **k2)
        eqsX.append(rx.eq)
    ensx = pd.concat(eqsX, axis=1).sum(axis=1)
    segx = ensx.loc['2026-01-05':'2026-11-04']
    out['e5:exTop3'] = dict(fresh_total=float(segx.iloc[-1]/segx.iloc[0]-1),
        retention=float((segx.iloc[-1]/segx.iloc[0]-1)/ee['fresh_total']) if ee['fresh_total'] else float('nan'),
        excluded=top3)
    out['e5:lag1_note'] = 'legs各+1信号延迟后合成'
    eqsL = []
    for lname, cap, w in (('N4R30TP45', 35000.0, 0.7), ('N5R40TPnone', 15000.0, 0.3)):
        k2 = dict(legdefs[lname], capital=cap, lot=100, cost_one_way=None, slip=0.002, run_start='2026-01-05', phase=0, legacy_grid=False, stop_exec='next', exclude=MB, exposure=0.9, sig_lag=1)
        rl = pc.run_strategy(inp, **k2)
        eqsL.append(rl.eq)
    ensl = pd.concat(eqsL, axis=1).sum(axis=1)
    segl = ensl.loc['2026-01-05':'2026-11-04']
    out['e5:lag1'] = dict(fresh_total=float(segl.iloc[-1]/segl.iloc[0]-1))
    op = os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, 'w') as f:
        json.dump(out, f, indent=1, default=float)
    for eid in ['b015_E1_N4R30_bond_70_30','b015_E2_N4R30_bond_50_50','b015_E3_N4_N4TP30_50_50','b015_E4_N4R30_N4R20_50_50','b015_E5_N4R30_N5R40none_70_30','b015_E8_N4TP45_N4TP30_70_30']:
        print(f"[{eid}] mine {out[eid+':mine']['fresh_total']*100:.2f}% harness {out[eid+':harness']['fresh_total']*100:.2f}% delta={out[eid+':delta_pp']:+.3f}pp")
    print('bond leg 2026 ret:', round(out['bond_leg']['ret']*100,3))
    print('e6 nobreaker:', out['e6_nobreaker'], 'e6 harness:', out['e6:harness'])
    print('e6 dd fresh:', out['e6_dd:fresh'], 'e6 dd cont:', {k: (v if not isinstance(v, list) else v) for k, v in out['e6_dd:cont'].items()})
    print('e5 mine/harness:', round(out['e5']['fresh_total']*100,2), round(out['e6:harness']['fresh_total']*100,2) if False else round(float(df[df['id']==E5_ID].iloc[0]['fresh_total'])*100,2), 'delta:', round(out['e5:delta_pp_vs_harness'],3))
    print('base delta:', round(out['base:delta_pp_vs_harness'],4))
    print('wrote', op)

if __name__ == '__main__':
    main()
