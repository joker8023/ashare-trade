#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""batch_011 审计员自写分批止盈引擎 (staged_take 独立实现, 不调 team/harness.py).
语义 (由 harness 逐笔反推, batch_011 G2):
  * staged level 按触发价升序, 每级每仓位只触发一次; 触发日收盘判定, t+1 收盘按当时价卖出
    当前股数 × fraction (允许非整手零股, 与 harness 733.26 对齐; 整手约束只用于新建仓).
  * staged_take 存在时 take_profit 不再生效 (harness stg 文件 111 笔中 take_profit 出现 0 次;
    baseline 同策略无 staged 时 take 正常触发 13 次) —— 实现为互斥, 并在审计中声明.
  * 调仓日全清 (含 staged 剩余), 理由 rebalance; 其余口径 (信号/执行/费用/整手/池子) 与 prior_check 一致.
只依赖 data/pivots_long_clean.pkl (经 prior_check.Inputs) + pandas/numpy.
"""
from __future__ import annotations
import os, sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import prior_check as pc

@dataclass
class SPos:
    shares: float
    entry_px: float
    entry_i: int
    buy_cost: float
    fired: set = field(default_factory=set)

def run_staged(inp: pc.Inputs, *, n=4, rebal=30, take=None,
               staged: Optional[List[Tuple[float, float]]] = None,
               capital=50000.0, lot=100, slip=0.002,
               run_start='2026-01-05', phase=0, stop_exec='next',
               exclude=(), factor='amihud_60', exposure=0.9,
               size_range=(0.05, 0.30), min_adv=5e6,
               cost_one_way=None, sig_lag=0):
    staged = sorted(staged or [], key=lambda x: x[0])
    use_take = take if not staged else None  # staged 存在时 TP 不生效 (实证: 0 次 take)
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
    cash = float(capital)
    pos: Dict[str, SPos] = {}
    eq_rows, trades, pending, execs = [], [], [], []
    total_cost, cost_by_year = 0.0, {}
    stats = dict(stale_buys=0, stale_sells=0, skipped_lot=0, staged_sells=0, rebal_sells=0)
    n_rebalances = 0

    def px(day, code):
        v = mark.at[day, code]
        return float(v) if pd.notna(v) else float('nan')

    def sell(code, i, reason, frac=1.0):
        nonlocal cash, total_cost
        day = dates[i]
        p = pos[code]
        sh = p.shares if frac >= 1.0 else p.shares * frac
        if sh <= 0:
            return
        pr = px(day, code)
        if pd.isna(pr):
            pr = p.entry_px
        stale = pd.isna(c.at[day, code]) if code in c.columns else True
        notional = sh * pr
        fee = (notional * cost_one_way) if cost_one_way is not None else pc._cost_sell_real(notional, slip)
        cash += notional - fee
        total_cost += fee
        cost_by_year[int(day.year)] = cost_by_year.get(int(day.year), 0.0) + fee
        f = sh / p.shares if p.shares > 0 else 0.0
        basis = p.entry_px * sh + p.buy_cost * f
        net_pnl = notional - fee - basis
        trades.append(dict(code=code, entry_i=p.entry_i, exit_i=i,
            entry_date=dates[p.entry_i], exit_date=day, shares=sh,
            entry_px=p.entry_px, exit_px=pr, gross_ret=pr / p.entry_px - 1.0,
            net_ret=net_pnl / basis if basis > 0 else np.nan, net_pnl=net_pnl,
            reason=reason, stale=bool(stale),
            limitdown=False, hold_days=i - p.entry_i))
        p.shares -= sh
        p.buy_cost *= (1.0 - f)
        if stale:
            stats['stale_sells'] += 1
        if reason == 'staged_take':
            stats['staged_sells'] += 1
        elif reason == 'rebalance':
            stats['rebal_sells'] += 1
        if p.shares <= 1e-9:
            del pos[code]

    def do_rebalance(i, sig_i):
        nonlocal cash, total_cost, n_rebalances
        day = dates[i]
        for code in list(pos.keys()):
            sell(code, i, 'rebalance')
        _e0 = (cash, sum(p.shares * (px(day, cc) if pd.notna(px(day, cc)) else p.entry_px) for cc, p in pos.items()))
        picks = inp.picks(dates[sig_i], n, size_range=size_range, min_adv=min_adv,
                          exclude=tuple(exclude), factor=factor)
        if not picks:
            n_rebalances += 1
            execs.append((i, float(cash)))
            return
        alloc = (cash * exposure / len(picks))
        for code in picks:
            pr = px(day, code)
            if pd.isna(pr) or pr <= 0:
                continue
            if lot and lot > 1:
                sh = int(alloc / pr // lot) * lot
                if sh <= 0:
                    stats['skipped_lot'] += 1
                    continue
            else:
                sh = alloc / pr
            notional = sh * pr
            fee = (notional * cost_one_way) if cost_one_way is not None else pc._cost_buy_real(notional, slip)
            if notional + fee > cash:
                continue
            stale = pd.isna(c.at[day, code]) if code in c.columns else True
            cash -= notional + fee
            total_cost += fee
            cost_by_year[int(day.year)] = cost_by_year.get(int(day.year), 0.0) + fee
            pos[code] = SPos(shares=sh, entry_px=pr, entry_i=i, buy_cost=fee)
            if stale:
                stats['stale_buys'] += 1
        _mv = sum(p.shares * (px(day, cc) if pd.notna(px(day, cc)) else p.entry_px) for cc, p in pos.items())
        execs.append((i, float(cash + _mv)))
        n_rebalances += 1

    for i in range(loop_start, loop_end + 1):
        day = dates[i]
        if pending:
            todo = list(pending)
            pending.clear()
            for code, kind, payload in todo:
                if code in pos:
                    if kind == 'staged':
                        sell(code, i, 'staged_take', frac=payload)
                    elif kind == 'take_full':
                        sell(code, i, 'take_profit')
        if i in exec_map:
            do_rebalance(i, exec_map[i])
        if pos:
            for code in list(pos.keys()):
                pr = px(day, code)
                p = pos[code]
                if pd.isna(pr):
                    continue
                for lv, (trig, frac) in enumerate(staged):
                    if lv not in p.fired and pr >= p.entry_px * (1.0 + trig):
                        p.fired.add(lv)
                        if stop_exec == 'same':
                            sell(code, i, 'staged_take', frac=frac)
                        else:
                            pending.append((code, 'staged', frac))
                        break
                if code in pos and use_take is not None and pr >= pos[code].entry_px * (1.0 + use_take):
                    if stop_exec == 'same':
                        sell(code, i, 'take_profit')
                    else:
                        pending.append((code, 'take_full', 1.0))
        mv = 0.0
        for code, p in pos.items():
            pr = px(day, code)
            mv += p.shares * (pr if pd.notna(pr) else p.entry_px)
        eq_rows.append((day, cash + mv, mv, cash, len(pos)))
    # pending 中 take_full 的执行 (与 staged 同队列; take 在 staged 存在时恒为 None, 保留分支以备复用)
    eq = pd.Series([x[1] for x in eq_rows], index=[x[0] for x in eq_rows], name='eq')
    exp = pd.DataFrame([(x[0], x[2], x[3], x[4]) for x in eq_rows],
                       columns=['date', 'mv', 'cash', 'nhold']).set_index('date')
    exp['eq'] = eq
    exp['exposure'] = exp['mv'] / exp['eq'].replace(0, np.nan)
    tr = pd.DataFrame(trades)
    per = pc.build_periods(eq, execs, ret, dates, rebal)
    # 期末 pending take_full 若有, 按最后一日收盘强平 (staged 实验不触发; 防御)
    meta = dict(n=n, rebal=rebal, stop=None, take=take, staged_take=list(staged),
                capital=capital, lot=lot, cost_one_way=cost_one_way, run_start=run_start, phase=phase, sig_lag=sig_lag,
                stop_exec=stop_exec, n_rebalances=n_rebalances, exclude=','.join(exclude),
                factor=factor, exposure=exposure, slip=slip,
                total_cost=float(total_cost),
                cost_by_year={str(k): float(v) for k, v in cost_by_year.items()},
                **stats)
    return pc.Result(eq=eq, trades=tr, periods=per, meta=meta,
                     exposure=exp['exposure'], nhold=exp['nhold'])
