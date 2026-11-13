#!/usr/bin/env python3
"""双引擎切换引擎 (由 build_switch_engine.py 从 prior_check.run_strategy 派生)。
lock_mode='A'/'B' 时须与两引擎独立运行逐值一致 (回归断言在 run_switch_backtest.py)。"""
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from prior_check import *  # noqa: F401,F403
from prior_check import _cost_buy_real, _cost_flat, _cost_sell_real  # noqa: F401

def run_strategy_switch(
    inp: Inputs,
    *,
    n: int = 5,
    rebal: int = 30,
    stop: Optional[float] = 0.12,
    take: Optional[float] = None,
    capital: float = 50_000.0,
    lot: int = 100,
    cost_one_way: Optional[float] = None,     # 0.005 => 主口径; None => 现实费率
    run_start: str = "2024-01-01",
    eval_start: pd.Timestamp = EVAL_START,
    eval_end: pd.Timestamp = EVAL_END,
    phase: int = 0,
    stop_exec: str = "same",                  # same | next  （止损触发后当日收盘 vs 次日收盘）
    ffill_exec: bool = True,                  # 停牌日是否允许按停牌前价成交
    sig_lag: int = 0,                         # 信号整体后移交易日数（前视检验）
    full_liquidate: bool = True,              # True=每次调仓全清再买; False=只交易差额
    mark_stale_fill: bool = True,
    record: bool = True,
    legacy_grid: bool = False,
    exclude: Tuple[str, ...] = (),
    factor: str = "amihud",
    exposure: float = 1.0,
    slip: float = 0.0,
    weight_cap: Optional[float] = None,
    rank_fill: bool = True,
    inp_b=None,                            # 引擎 B 的 Inputs
    cfg_b=None,                            # dict(n=, rebal=, take=, exposure=)
    shadow_a=None, shadow_b=None,          # 两引擎独立权益曲线 (RS 信号)
    rs_lookback: int = 60,
    lock_mode=None,                        # 'A'/'B': 锁死引擎 (回归验证)
) -> Result:
    c = inp.close
    mark = inp.mark
    dates = inp.dates
    ret = inp.ret
    n_dates = len(dates)

    run_ts = pd.Timestamp(run_start)
    grid = inp.grid(rebal, phase, legacy=legacy_grid)
    grid = [i for i in grid if dates[i] >= run_ts]
    if not grid:
        raise ValueError("no rebalance dates")
    grid_b = []
    if inp_b is not None:
        grid_b = inp_b.grid(cfg_b["rebal"], phase, legacy=legacy_grid)
        grid_b = [i for i in grid_b if dates[i] >= run_ts]
    sig_a, sig_b = set(grid), set(grid_b)
    # 信号 lag: 执行日 = dates[i+1+sig_lag]
    exec_map: Dict[int, int] = {}
    for i in grid + grid_b:
        ei = i + 1 + sig_lag
        if ei < n_dates:
            exec_map.setdefault(ei, i)

    loop_start = grid[0]
    end_i = int(dates.searchsorted(eval_end, side="right") - 1)
    # 需要跑到 eval_end 之后（预热/持仓），但不超过数据末
    loop_end = min(end_i, n_dates - 1)

    cash = float(capital)
    pos: Dict[str, Pos] = {}
    eq_rows: List[Tuple[pd.Timestamp, float]] = []
    trades: List[dict] = []
    pending_stop: List[Tuple[str, int, str]] = []   # stop_exec == next: (code, trigger_i, reason)
    total_cost = 0.0
    cost_by_year: Dict[int, float] = {}
    executed_rebalances: List[Tuple[int, float]] = []  # (idx, post-trade equity)
    stats = {"stale_buys": 0, "stale_sells": 0, "limitdown_sells": 0,
             "limitup_buys": 0, "stop_sells": 0, "rebal_sells": 0,
             "skipped_lot": 0}
    rebal_snap = []

    # --- 双引擎切换状态 (切换必全清, 故持仓恒属当前引擎) ---
    mode = lock_mode or "A"
    state_take = take if mode == "A" else cfg_b["take"]
    state_n = n if mode == "A" else cfg_b["n"]
    state_exposure = exposure if mode == "A" else cfg_b["exposure"]
    switch_log: List[Tuple[str, str]] = []

    def _rs(eq_s, s_idx: int):
        if eq_s is None:
            return None
        j = int(eq_s.index.searchsorted(dates[s_idx], side="right") - 1)
        if j < rs_lookback:
            return None
        return float(eq_s.iloc[j] / eq_s.iloc[j - rs_lookback] - 1.0)

    def board_limit(code: str) -> float:
        if code.startswith(("688", "689", "300", "301")):
            return 0.20
        if code.startswith(("4", "8")):
            return 0.30
        return 0.10

    def is_limit_down(day: pd.Timestamp, code: str) -> bool:
        r = ret.at[day, code] if code in ret.columns else np.nan
        if pd.isna(r):
            return False
        return r <= -(board_limit(code) - 0.003) - 0.0005

    def buy_cost(notional: float) -> float:
        return _cost_flat(notional, cost_one_way) if cost_one_way is not None else _cost_buy_real(notional, slip)

    def sell_cost(notional: float) -> float:
        return _cost_flat(notional, cost_one_way) if cost_one_way is not None else _cost_sell_real(notional, slip)

    def close_pos(code: str, i: int, reason: str, qty: Optional[float] = None):
        nonlocal cash, total_cost
        day = dates[i]
        p = pos[code]
        sh = p.shares if qty is None else min(qty, p.shares)
        if sh <= 0:
            return
        px = px_ffill_or_nan(mark, day, code)
        if pd.isna(px) and not ffill_exec:
            return  # 停牌/缺价，卖不掉，占位不成交（下一日再来）
        stale = pd.isna(c.at[day, code]) if code in c.columns else True
        if pd.isna(px):
            px = p.entry_px
            stale = True
        notional = sh * px
        fee = sell_cost(notional)
        cash += notional - fee
        total_cost += fee
        cost_by_year[int(day.year)] = cost_by_year.get(int(day.year), 0.0) + fee
        frac = sh / p.shares if p.shares > 0 else 0.0
        cost_basis = p.entry_px * sh + p.buy_cost * frac
        net_pnl = notional - fee - cost_basis
        trades.append(dict(
            code=code, entry_i=p.entry_i, exit_i=i,
            entry_date=dates[p.entry_i], exit_date=day,
            shares=sh, entry_px=p.entry_px, exit_px=px,
            gross_ret=px / p.entry_px - 1.0,
            net_ret=net_pnl / cost_basis if cost_basis > 0 else np.nan,
            net_pnl=net_pnl, reason=reason,
            stale=bool(stale),
            limitdown=bool(is_limit_down(day, code)),
            hold_days=i - p.entry_i,
        ))
        p.shares -= sh
        if stale:
            stats["stale_sells"] += 1
        if reason == "stop":
            stats["stop_sells"] += 1
            if is_limit_down(day, code):
                stats["limitdown_sells"] += 1
        elif reason == "rebalance":
            stats["rebal_sells"] += 1
        if p.shares <= 1e-12:
            del pos[code]

    def do_rebalance(i: int, sig_i: int):
        nonlocal cash, total_cost, mode, state_take, state_n, state_exposure
        day = dates[i]
        sig_day = dates[sig_i]
        # 切换评估: 仅 A 网格信号日, 影子曲线 trailing RS 定 desired
        desired = mode
        if lock_mode is None and inp_b is not None and sig_i in sig_a:
            ra = _rs(shadow_a, sig_i)
            rb = _rs(shadow_b, sig_i)
            if ra is not None and rb is not None:
                desired = "A" if ra >= rb else "B"
        switching = desired != mode
        on_grid = (sig_i in sig_a) if desired == "A" else (sig_i in sig_b)
        if not switching and not on_grid:
            return False
        if switching:
            mode = desired
            state_take = take if mode == "A" else cfg_b["take"]
            state_n = n if mode == "A" else cfg_b["n"]
            state_exposure = exposure if mode == "A" else cfg_b["exposure"]
            switch_log.append((str(sig_day.date()), mode))
        inp_cur = inp if mode == "A" else inp_b
        n_eff = state_n
        if weight_cap is not None and weight_cap > 0 and rank_fill:
            n_eff = max(state_n, int(__import__("math").ceil(1.0 / weight_cap - 1e-9)))
        picks = inp_cur.picks(sig_day, n_eff, exclude=exclude, factor=factor)
        # 先处理掉所有仓位（全清 or 差额）
        if full_liquidate:
            for code in list(pos.keys()):
                close_pos(code, i, "rebalance")
        else:
            for code in list(pos.keys()):
                if code not in picks:
                    close_pos(code, i, "rebalance")
        # 用剩余现金等权买入
        if not picks:
            return True  # 已全清 (切换/调仓生效), 但无新仓; append 语义见文末
        slots = len(picks)
        # 目标: 总权益按 N 等分；已持有的继续持有（差额模式下不再加）
        equity_now = cash + sum(
            p.shares * (px_ffill_or_nan(mark, day, cc) if pd.notna(px_ffill_or_nan(mark, day, cc)) else p.entry_px)
            for cc, p in pos.items()
            if not full_liquidate
        )
        free_slots = slots - (len(pos) if not full_liquidate else 0)
        if free_slots <= 0:
            return False
        if weight_cap is not None and weight_cap > 0 and not rank_fill:
            alloc = equity_now * state_exposure * min(1.0 / slots, weight_cap)
        else:
            alloc = equity_now * state_exposure / slots
        for code in picks:
            if code in pos:
                continue
            px = px_ffill_or_nan(mark, day, code)
            if pd.isna(px) or px <= 0:
                continue
            if lot and lot > 1:
                sh = int(alloc / px // lot) * lot
                if sh <= 0:
                    stats["skipped_lot"] += 1
                    continue
            else:
                sh = alloc / px
            notional = sh * px
            fee = buy_cost(notional)
            if notional + fee > cash:
                if lot and lot > 1:
                    sh = int(max(cash - fee, 0.0) / px // lot) * lot
                else:
                    sh = max(cash - fee, 0.0) / px
                if sh <= 0:
                    stats["skipped_lot"] += 1
                    continue
                notional = sh * px
                fee = buy_cost(notional)
                if notional + fee > cash:
                    continue
            stale = pd.isna(c.at[day, code]) if code in c.columns else True
            is_lu = False
            if code in ret.columns and pd.notna(ret.at[day, code]):
                is_lu = ret.at[day, code] >= board_limit(code) - 0.003
            cash -= notional + fee
            total_cost += fee
            cost_by_year[int(day.year)] = cost_by_year.get(int(day.year), 0.0) + fee
            pos[code] = Pos(shares=sh, entry_px=px, entry_i=i, high=px,
                            buy_cost=fee, entry_equity=equity_now)
            if stale:
                stats["stale_buys"] += 1
            if is_lu:
                stats["limitup_buys"] += 1
        executed_rebalances.append((i, 0.0))  # 稍后填 equity
        _appended = True
        _mv0 = sum(p.shares * (px_ffill_or_nan(mark, day, cc) if pd.notna(px_ffill_or_nan(mark, day, cc)) else p.entry_px)
                   for cc, p in pos.items())
        rebal_snap.append(dict(date=str(day.date()), n_positions=len(pos),
                               cash=float(cash), mv=float(_mv0),
                               alloc_per_slot=float(alloc), picked=int(len(picks))))
        return True

    for i in range(loop_start, loop_end + 1):
        day = dates[i]

        # (0) 上一日触发的止损, 次日收盘执行
        if pending_stop:
            todo = [x for x in pending_stop]
            pending_stop.clear()
            for code, _, reason in todo:
                if code in pos:
                    if pd.notna(c.at[day, code]) or ffill_exec:
                        close_pos(code, i, reason)
                    else:
                        pending_stop.append((code, i, reason))

        # (1) 调仓
        if i in exec_map:
            if do_rebalance(i, exec_map[i]):
                executed_rebalances[-1] = (i, 0.0)

        # (2) 止损/止盈判断（当日收盘）
        if pos:
            for code in list(pos.keys()):
                px = px_ffill_or_nan(mark, day, code)
                p = pos[code]
                if pd.isna(px):
                    continue
                if px > p.high:
                    p.high = px
                hit_stop = stop is not None and px < p.high * (1.0 - stop)
                hit_take = state_take is not None and px >= p.entry_px * (1.0 + state_take)
                if hit_stop:
                    if stop_exec == "same":
                        close_pos(code, i, "stop")
                    else:
                        pending_stop.append((code, i, "stop"))
                elif hit_take:
                    if stop_exec == "same":
                        close_pos(code, i, "take")
                    else:
                        pending_stop.append((code, i, "take"))

        # (3) 盯市
        mv = 0.0
        for code, p in pos.items():
            px = px_ffill_or_nan(mark, day, code)
            if pd.isna(px):
                px = p.entry_px
            mv += p.shares * px
        eq_rows.append((day, cash + mv, mv, cash, len(pos)))
        # 记录调仓日盘后权益
        if executed_rebalances and executed_rebalances[-1][0] == i:
            executed_rebalances[-1] = (i, cash + mv)

    eq = pd.Series([x[1] for x in eq_rows], index=[x[0] for x in eq_rows], name="eq")
    _exp = pd.DataFrame([(x[0], x[2], x[3], x[4]) for x in eq_rows],
                        columns=["date", "mv", "cash", "nhold"]).set_index("date")
    _exp["eq"] = eq
    _exp["exposure"] = _exp["mv"] / _exp["eq"].replace(0, np.nan)
    tr = pd.DataFrame(trades)
    per = build_periods(eq, executed_rebalances, ret, dates, rebal)

    # 期末仍持仓: 给"含期末卖出成本"的清算口径
    liq_eq = None
    if pos:
        mv = 0.0
        fee_all = 0.0
        last = dates[loop_end]
        for code, p in pos.items():
            px = px_ffill_or_nan(mark, last, code)
            if pd.isna(px):
                px = p.entry_px
            notional = p.shares * px
            fee_all += sell_cost(notional)
            mv += notional
        liq_eq = cash + mv - fee_all

    meta = dict(
        n=n, rebal=rebal, stop=stop, take=take, capital=capital, lot=lot,
        cost_one_way=cost_one_way, run_start=run_start, phase=phase,
        stop_exec=stop_exec, sig_lag=sig_lag, full_liquidate=full_liquidate,
        n_rebalances=len(executed_rebalances), exclude=",".join(exclude),
        factor=factor, exposure=exposure, slip=slip, weight_cap=weight_cap, rank_fill=rank_fill,
        total_cost=float(total_cost),
        cost_by_year={str(k): float(v) for k, v in cost_by_year.items()},
        liq_eq_eval_end=float(liq_eq) if liq_eq is not None else None,
        **stats,
        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode,
    )
    return Result(eq=eq, trades=tr, periods=per, meta=meta,
                  exposure=_exp["exposure"], nhold=_exp["nhold"])

