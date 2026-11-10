#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""batch_013 审计员自写小时级引擎 (独立实现, 不调 team/hourly_harness.py).
语义 (由 spec execution 描述 + harness 逐笔反推):
  * 日线选股: R7 网格 (dates[300] 起), t 日收盘信号, t+1 日收盘建仓 (与日线一致).
  * 持仓有独立 bar 序列: 有小时文件用其 4 bar/日收盘; 无文件回退为日线 15:00 序列 (计数).
  * trail: bar收盘 <= high*(1-p) 触发; tp: bar收盘 >= entry*(1+p) 触发.
    触发后**下一 bar 收盘**执行 (严格 t+1bar, 同 bar 永不执行, 跨夜顺延).
  * 跌停日 bar 不可成交顺延 (按日线是否跌停判定, board 感知).
  * 缺 bar (停牌): 该 bar 不存在, 不评估触发 (计数 stale).
  * 调仓日 t+1 收盘: 先执行到期的 15:00 pending, 再全清剩余并买新.
只依赖 data/pivots_long_clean.pkl + data/hourly_60m/*.csv + pandas/numpy.
"""
from __future__ import annotations
import glob, os, sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import prior_check as pc

def board_limit(code: str) -> float:
    c = str(code)
    if c.startswith(('688', '689', '300', '301')):
        return 0.20
    if c.startswith(('4', '8')):
        return 0.30
    return 0.10

@dataclass
class HPos:
    shares: float
    entry_px: float
    entry_i: int
    entry_bar: pd.Timestamp
    buy_cost: float
    high: float
    bars: list = field(default_factory=list)      # bar datetime 序列
    bpx: dict = field(default_factory=dict)       # bar -> close
    pending: Optional[tuple] = None               # (kind, sig_bar, exec_bar)
    fallback_daily: bool = False

@dataclass
class HResult:
    eq: pd.Series
    trades: pd.DataFrame
    periods: pd.DataFrame
    meta: dict
    exposure: pd.Series
    nhold: pd.Series
    align: dict

def load_bars(root: str) -> Dict[str, dict]:
    bars = {}
    for f in glob.glob(os.path.join(root, 'data', 'hourly_60m', '*.csv')):
        code = os.path.basename(f)[:-4]
        if code == 'manifest':
            continue
        d = pd.read_csv(f, parse_dates=['datetime'])
        d = d.sort_values('datetime')
        bars[code.zfill(6)] = dict(zip(d['datetime'], d['close'].astype(float)))
    return bars

def run_hourly(inp: pc.Inputs, bars: Dict[str, dict], *, n=4, rebal=7,
               trail: Optional[float] = None, tp: Optional[float] = None,
               capital=50000.0, lot=100, slip=0.002,
               run_start='2024-01-01', phase=0,
               exclude=(), factor='amihud_60', exposure=1.0, sig_lag=0,
               cost_one_way=None):
    c, mark, dates, ret = inp.close, inp.mark, inp.dates, inp.ret
    n_dates = len(dates)
    grid = inp.grid(rebal, phase, legacy=False)
    run_ts = pd.Timestamp(run_start)
    grid = [i for i in grid if dates[i] >= run_ts]
    exec_map = {}
    for i in grid:
        ei = i + 1 + sig_lag
        if ei < n_dates:
            exec_map[ei] = i
    loop_start = grid[0]
    end_i = int(dates.searchsorted(pc.EVAL_END, side='right') - 1)
    loop_end = min(end_i, n_dates - 1)
    ld = {}
    for code in c.columns:
        bl = board_limit(code)
        ld[code] = (ret[code] <= -(bl - 0.003) - 0.0005)
    def is_ld(code, day):
        s = ld.get(code)
        if s is None or day not in s.index:
            return False
        v = s.loc[day]
        return bool(v) if pd.notna(v) else False
    cash = float(capital)
    pos: Dict[str, HPos] = {}
    eq_rows, trades = [], []
    execs = []
    total_cost, cost_by_year = 0.0, {}
    stats = dict(stale_buys=0, stale_sells=0, skipped_lot=0, trail_sells=0, tp_sells=0,
                 rebal_sells=0, missing_fallback=0, stale_bars=0, deferred=0,
                 overnight_exec=0, samebar_exec=0, edge_no_nextbar=0)
    n_rebalances = 0
    gaps = []

    def px(day, code):
        if day not in mark.index:
            return float('nan')
        v = mark.at[day, code]
        return float(v) if pd.notna(v) else float('nan')

    def buy_cost(notional):
        return (notional * cost_one_way) if cost_one_way is not None else pc._cost_buy_real(notional, slip)

    def sell_cost(notional):
        return (notional * cost_one_way) if cost_one_way is not None else pc._cost_sell_real(notional, slip)

    def next_bar(p: HPos, bar):
        try:
            j = p.bars.index(bar) + 1
        except ValueError:
            return None
        return p.bars[j] if j < len(p.bars) else None

    def do_sell(code, exec_bar, reason, sig_bar, exec_px):
        nonlocal cash, total_cost
        p = pos[code]
        day = pd.Timestamp(exec_bar.date())
        stale = pd.isna(c.at[day, code]) if (code in c.columns and day in c.index) else True
        notional = p.shares * exec_px
        fee = sell_cost(notional)
        cash += notional - fee
        total_cost += fee
        cost_by_year[int(day.year)] = cost_by_year.get(int(day.year), 0.0) + fee
        basis = p.entry_px * p.shares + p.buy_cost
        net_pnl = notional - fee - basis
        trades.append(dict(code=code, entry_i=p.entry_i, exit_i=None,
            entry_date=dates[p.entry_i], exit_date=day, shares=p.shares,
            entry_px=p.entry_px, exit_px=exec_px, gross_ret=exec_px / p.entry_px - 1.0,
            net_ret=net_pnl / basis if basis > 0 else np.nan, net_pnl=net_pnl,
            reason=reason, stale=bool(stale), sig_bar=sig_bar, exec_bar=exec_bar))
        if stale:
            stats['stale_sells'] += 1
        if reason == 'trailing_stop_h':
            stats['trail_sells'] += 1
        elif reason == 'take_profit_h':
            stats['tp_sells'] += 1
        elif reason == 'rebalance':
            stats['rebal_sells'] += 1
        del pos[code]

    def exec_pending_at(bar):
        for code in list(pos.keys()):
            p = pos[code]
            if p.pending is None:
                continue
            kind, sig_bar, exec_bar = p.pending
            if exec_bar != bar:
                continue
            eb, pxv = exec_bar, p.bpx.get(exec_bar, float('nan'))
            while pd.notna(pxv) and is_ld(code, pd.Timestamp(eb.date())):
                nb = next_bar(p, eb)
                if nb is None:
                    break
                eb = nb
                pxv = p.bpx.get(eb, float('nan'))
                stats['deferred'] += 1
            if pd.isna(pxv):
                pxv = p.entry_px
                stats['stale_bars'] += 1
            gaps.append((sig_bar, eb))
            if eb == sig_bar:
                stats['samebar_exec'] += 1
            if eb.date() != sig_bar.date():
                stats['overnight_exec'] += 1
            do_sell(code, eb, 'take_profit_h' if kind == 'tp' else 'trailing_stop_h', sig_bar, pxv)

    for i in range(loop_start, loop_end + 1):
        day = dates[i]
        day_bars = [pd.Timestamp(day.date()) + t for t in
                    [pd.Timedelta('10:30:00'), pd.Timedelta('11:30:00'),
                     pd.Timedelta('14:00:00'), pd.Timedelta('15:00:00')]]
        for b in day_bars:
            exec_pending_at(b)
            for code in list(pos.keys()):
                p = pos[code]
                if p.pending is not None:
                    continue
                if b not in p.bpx:
                    continue
                pr = p.bpx[b]
                if pd.isna(pr) or pr <= 0:
                    stats['stale_bars'] += 1
                    continue
                if pr > p.high:
                    p.high = pr
                hit_trail = trail is not None and pr < p.high * (1.0 - trail)
                hit_tp = tp is not None and pr >= p.entry_px * (1.0 + tp)
                if hit_trail or hit_tp:
                    kind = 'trail' if hit_trail else 'tp'
                    eb = next_bar(p, b)
                    if eb is None:
                        stats['edge_no_nextbar'] += 1
                        eb = b
                    p.pending = (kind, b, eb)
        if i in exec_map:
            bar15 = pd.Timestamp(day.date()) + pd.Timedelta('15:00:00')
            for code in list(pos.keys()):
                p = pos[code]
                _px = bars.get(code, {}).get(bar15, float('nan'))
                if pd.isna(_px):
                    _px = px(day, code)
                if pd.isna(_px):
                    _px = p.entry_px
                    stats['stale_bars'] += 1
                do_sell(code, bar15, 'rebalance', p.entry_bar, _px)
            picks = inp.picks(dates[exec_map[i]], n, exclude=tuple(exclude), factor=factor)
            alloc = cash * exposure / len(picks) if picks else 0
            for code in picks:
                pr = bars.get(code, {}).get(pd.Timestamp(day.date()) + pd.Timedelta('15:00:00'), float('nan'))
                if pd.isna(pr):
                    pr = px(day, code)
                if pd.isna(pr) or pr <= 0:
                    continue
                sh = int(alloc / pr // lot) * lot if lot and lot > 1 else alloc / pr
                if sh <= 0:
                    stats['skipped_lot'] += 1
                    continue
                notional = sh * pr
                fee = buy_cost(notional)
                if notional + fee > cash:
                    continue
                stale = pd.isna(c.at[day, code]) if code in c.columns else True
                cash -= notional + fee
                total_cost += fee
                cost_by_year[int(day.year)] = cost_by_year.get(int(day.year), 0.0) + fee
                bm = bars.get(code)
                if bm is None:
                    stats['missing_fallback'] += 1
                    bl = [pd.Timestamp(d.date()) + pd.Timedelta('15:00:00') for d in dates[i:loop_end + 1]]
                    bpx = {d_: px(d_, code) for d_ in [pd.Timestamp(d.date()) for d in dates[i:loop_end + 1]]}
                    bpx = {pd.Timestamp(k.date()) + pd.Timedelta('15:00:00'): v for k, v in bpx.items()}
                    fb = True
                else:
                    bl = sorted(k for k in bm.keys() if k >= pd.Timestamp(day.date()) + pd.Timedelta('15:00:00'))
                    bpx = bm
                    fb = False
                pos[code] = HPos(shares=sh, entry_px=pr, entry_i=i,
                                 entry_bar=pd.Timestamp(day.date()) + pd.Timedelta('15:00:00'),
                                 buy_cost=fee, high=pr, bars=bl, bpx=bpx, fallback_daily=fb)
                if stale:
                    stats['stale_buys'] += 1
            _mv = sum(p.shares * (px(day, cc) if pd.notna(px(day, cc)) else p.entry_px) for cc, p in pos.items())
            execs.append((i, float(cash + _mv)))
            n_rebalances += 1
        mv = 0.0
        for code, p in pos.items():
            pr = px(day, code)
            mv += p.shares * (pr if pd.notna(pr) else p.entry_px)
        eq_rows.append((day, cash + mv, mv, cash, len(pos)))
    eq = pd.Series([x[1] for x in eq_rows], index=[x[0] for x in eq_rows], name='eq')
    exp = pd.DataFrame([(x[0], x[2], x[3], x[4]) for x in eq_rows],
                       columns=['date', 'mv', 'cash', 'nhold']).set_index('date')
    exp['eq'] = eq
    exp['exposure'] = exp['mv'] / exp['eq'].replace(0, np.nan)
    tr = pd.DataFrame(trades)
    per = pc.build_periods(eq, execs, ret, dates, rebal)
    meta = dict(n=n, rebal=rebal, trail=trail, tp=tp, capital=capital, lot=lot,
                cost_one_way=cost_one_way, run_start=run_start, phase=phase,
                n_rebalances=n_rebalances, exclude=','.join(exclude), factor=factor,
                exposure=exposure, slip=slip, sig_lag=sig_lag,
                total_cost=float(total_cost),
                cost_by_year={str(k): float(v) for k, v in cost_by_year.items()}, **stats)
    align = dict(min_bar_gap_s=(min(((eb - sb).total_seconds() for sb, eb in gaps)) if gaps else None),
                 n_overnight=stats['overnight_exec'], n_samebar=stats['samebar_exec'],
                 n_deferred=stats['deferred'], n_stale_bars=stats['stale_bars'],
                 n_missing_fallback=stats['missing_fallback'],
                 n_edge_no_nextbar=stats['edge_no_nextbar'],
                 n_hourly_exits=len(gaps))
    return HResult(eq=eq, trades=tr, periods=per, meta=meta,
                   exposure=exp['exposure'], nhold=exp['nhold'], align=align)
