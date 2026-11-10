#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""batch_014 审计员自写隔夜引擎 (sniper: t+1 收盘买 → t+2 开盘卖, 只吃隔夜缺口).
语义 (spec execution + harness 逐笔反推验证: 买价=t+1收盘, 卖价=t+2开盘, 无前视):
  * R7 网格出名单 (dates[300] 起, t 日收盘信号); 名单每 R 日更新, 每日滚动买入当前名单、次日开盘全平.
  * 涨停日买不进顺延 (skip 并计数); 跌停日卖不出顺延到下一开盘 (计数).
  * 整手 100 股、现实费率、等权 exposure; 日结平仓计益 (flat book 主要时段).
  * 捕获: 每笔买价是否 == t+1 收盘 / 卖价是否 == t+2 开盘 (前视检查用).
只依赖 data/pivots_long_clean.pkl + pandas/numpy.
"""
from __future__ import annotations
import os, sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional
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
class ONPos:
    shares: float
    entry_px: float
    entry_day: pd.Timestamp
    buy_cost: float
    sig_day: pd.Timestamp

def run_overnight(inp: pc.Inputs, *, n=4, rebal=7, capital=50000.0, lot=100,
                  slip=0.002, run_start='2026-01-05', phase=0,
                  exclude=(), factor='amihud_60', exposure=0.9,
                  cost_one_way=None):
    c, mark, dates, ret, opn = inp.close, inp.mark, inp.dates, inp.ret, inp.piv['open'].astype('float64')
    n_dates = len(dates)
    grid = inp.grid(rebal, phase, legacy=False)
    run_ts = pd.Timestamp(run_start)
    grid = [i for i in grid if dates[i] >= run_ts]
    loop_start = grid[0]
    end_i = int(dates.searchsorted(pc.EVAL_END, side='right') - 1)
    loop_end = min(end_i, n_dates - 1)
    ld = {}
    lu = {}
    for code in c.columns:
        bl = board_limit(code)
        ld[code] = (ret[code] <= -(bl - 0.003) - 0.0005)
        lu[code] = (ret[code] >= (bl - 0.003))
    cash = float(capital)
    pos: Dict[str, ONPos] = {}
    eq_rows, trades, execs = [], [], []
    total_cost, cost_by_year = 0.0, {}
    stats = dict(buy_skip_limitup=0, sell_defer_limitdown=0, skipped_lot=0,
                 stale_buys=0, stale_sells=0)
    cur_picks: List[str] = []
    cur_sig = None
    n_buys = 0

    def buy_cost(notional):
        return (notional * cost_one_way) if cost_one_way is not None else pc._cost_buy_real(notional, slip)

    def sell_cost(notional):
        return (notional * cost_one_way) if cost_one_way is not None else pc._cost_sell_real(notional, slip)

    for i in range(loop_start, loop_end + 1):
        day = dates[i]
        if i in grid:
            cur_picks = inp.picks(day, n, exclude=tuple(exclude), factor=factor)
            cur_sig = day
        # (0) morning sell at open (positions bought previous close)
        for code in list(pos.keys()):
            p = pos[code]
            opx = float(opn.at[day, code]) if (code in opn.columns and day in opn.index and pd.notna(opn.at[day, code])) else float('nan')
            if pd.isna(opx):
                continue  # 停牌: 继续持有到下一开盘
            if bool(ld.get(code, {}).get(day, False)):
                stats['sell_defer_limitdown'] += 1
                continue
            notional = p.shares * opx
            fee = sell_cost(notional)
            cash += notional - fee
            total_cost += fee
            cost_by_year[int(day.year)] = cost_by_year.get(int(day.year), 0.0) + fee
            basis = p.entry_px * p.shares + p.buy_cost
            net_pnl = notional - fee - basis
            trades.append(dict(code=code, entry_day=p.entry_day, exit_day=day,
                shares=p.shares, entry_px=p.entry_px, exit_px=opx,
                gross_ret=opx / p.entry_px - 1.0,
                net_ret=net_pnl / basis if basis > 0 else np.nan, net_pnl=net_pnl,
                reason='overnight', sig_day=cur_sig))
            del pos[code]
        # (1) evening buy at close (current weekly picks)
        if cur_picks and i + 1 < n_dates:
            alloc = cash * exposure / len(cur_picks)
            for code in cur_picks:
                if code in pos:
                    continue
                if bool(lu.get(code, {}).get(day, False)):
                    stats['buy_skip_limitup'] += 1
                    continue
                pr = float(mark.at[day, code]) if (code in mark.columns and day in mark.index) else float('nan')
                if pd.isna(pr) or pr <= 0:
                    stats['stale_buys'] += 1
                    continue
                sh = int(alloc / pr // lot) * lot if lot and lot > 1 else alloc / pr
                if sh <= 0:
                    stats['skipped_lot'] += 1
                    continue
                notional = sh * pr
                fee = buy_cost(notional)
                if notional + fee > cash:
                    continue
                cash -= notional + fee
                total_cost += fee
                cost_by_year[int(day.year)] = cost_by_year.get(int(day.year), 0.0) + fee
                pos[code] = ONPos(shares=sh, entry_px=pr, entry_day=day,
                                  buy_cost=fee, sig_day=cur_sig)
                n_buys += 1
        mv = sum(p.shares * (float(mark.at[day, cc]) if (cc in mark.columns and day in mark.index and pd.notna(mark.at[day, cc])) else p.entry_px) for cc, p in pos.items())
        eq_rows.append((day, cash + mv, mv, cash, len(pos)))
        if i in [g + 1 for g in grid if g + 1 < n_dates]:
            execs.append((i, float(cash + mv)))
    eq = pd.Series([x[1] for x in eq_rows], index=[x[0] for x in eq_rows], name='eq')
    exp = pd.DataFrame([(x[0], x[2], x[3], x[4]) for x in eq_rows],
                       columns=['date', 'mv', 'cash', 'nhold']).set_index('date')
    exp['eq'] = eq
    exp['exposure'] = exp['mv'] / exp['eq'].replace(0, np.nan)
    tr = pd.DataFrame(trades)
    if len(tr):
        tr['entry_date'] = pd.to_datetime(tr['entry_day'])
        tr['exit_date'] = pd.to_datetime(tr['exit_day'])
    meta = dict(n=n, rebal=rebal, capital=capital, lot=lot, cost_one_way=cost_one_way,
                run_start=run_start, phase=phase, exclude=','.join(exclude), factor=factor,
                exposure=exposure, slip=slip, total_cost=float(total_cost),
                cost_by_year={str(k): float(v) for k, v in cost_by_year.items()},
                n_buys=n_buys, **stats)
    align = dict(n_limitup_skip=stats['buy_skip_limitup'], n_limitdown_defer=stats['sell_defer_limitdown'])
    per = pc.build_periods(eq, execs, ret, dates, 7)
    res = pc.Result(eq=eq, trades=tr, periods=per, meta=meta,
                    exposure=exp['exposure'], nhold=exp['nhold'])
    res.align = align
    return res
