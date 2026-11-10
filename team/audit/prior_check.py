#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
prior_check.py — 独立对抗性复算 N5 / R30 / +12% 跟踪止损（2026 窗口）

审计员自写实现。**不 import、不 copy** engine.py / ledger_10k.py / team/harness.py。
只依赖 data/pivots_long_clean.pkl + pandas/numpy。

口径（按 team/PROTOCOL.md）:
  * 选股: amihud20 最大的 N 只（= 最不流动）
  * 池: 上市>=250 交易日, adv20>5e6, close 非空, 总市值(close*shares)在截面 5%~30% 分位
  * 信号 t 日收盘, 执行 t+1 日收盘
  * 每 R 个交易日调仓; 中途止损仓位资金留现金, 下一调仓日再投
  * 跟踪止损: 持仓期收盘最高价回撤 s
  * 成本: (a) 主口径 0.5%/边  (b) 现实费率 + 100 股整手 + 5 万本金
  * 指标: total/ann/mdd/win_period/win_trade/win_month + 逐段/逐笔

用法:
  .venv/bin/python team/audit/prior_check.py run            # 主复算 + 多口径对比
  .venv/bin/python team/audit/prior_check.py diag           # 执行可行性诊断
  .venv/bin/python team/audit/prior_check.py phase          # 30 个调仓相位扫描
  .venv/bin/python team/audit/prior_check.py all --json out/prior_all.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PIV_PATH = os.path.join(ROOT, "data", "pivots_long_clean.pkl")
OUT_DIR = os.path.join(ROOT, "team", "audit", "out")

EVAL_START = pd.Timestamp("2026-01-05")
EVAL_END = pd.Timestamp("2026-11-04")
BASE_DATE = pd.Timestamp("2025-12-31")

# 现实费率（与 ledger_10k.py 相同的公开费率，但由本文件独立实现）
COMM, MINC, STAMP, TRANS = 0.00025, 5.0, 0.0005, 0.00001


# ----------------------------------------------------------------------------
# 数据 / 因子
# ----------------------------------------------------------------------------
class Inputs:
    """从原始 pkl 独立构建因子矩阵。"""

    def __init__(self, piv: dict):
        self.piv = piv
        self.close = piv["close"].astype("float64")
        self.amount = piv["amount"].astype("float64")
        self.shares = piv["shares"].astype("float64")
        c = self.close
        r = c.pct_change(fill_method=None).abs()
        amt = self.amount.replace(0, np.nan)
        # Amihud 20 日: mean(|ret| / amount_in_100m)
        self.amihud = (r / (amt / 1e8)).rolling(20, min_periods=20).mean()
        self.amihud60 = (r / (amt / 1e8)).rolling(60, min_periods=60).mean()
        self.adv20 = self.amount.rolling(20, min_periods=10).mean()
        self.seasoned = c.shift(250).notna()
        # 注意: shares 是"当前(2026-11-04)流通股本"的静态快照, 历史市值是伪市值
        self.cap = c.mul(self.shares, axis=1)
        self.dates = c.index
        self.ret = c.pct_change(fill_method=None)
        # 执行/盯市用 ffill 价（缺价=停牌）
        self.mark = c.ffill()

    def picks(self, t: pd.Timestamp, n: int, size_range=(0.05, 0.30),
              min_adv: float = 5e6, exclude: Tuple[str, ...] = (),
              factor: str = "amihud") -> List[str]:
        c, dates = self.close, self.dates
        if t not in self.close.index:
            return []
        valid = (
            self.seasoned.loc[t]
            & (self.adv20.loc[t] > min_adv)
            & c.loc[t].notna()
            & self.amihud.loc[t].notna()
        )
        fac = self.amihud60 if factor == "amihud_60" else self.amihud
        valid &= fac.loc[t].notna()
        cap_t = self.cap.loc[t]
        lo = cap_t.quantile(size_range[0])
        hi = cap_t.quantile(size_range[1])
        valid &= ((cap_t >= lo) & (cap_t <= hi)).fillna(False)
        if exclude:
            cols = valid.index.to_series()
            valid &= ~cols.str.startswith(tuple(exclude)).values
        pool = valid[valid].index
        if len(pool) < n:
            return []
        return list(fac.loc[t, pool].nlargest(n).index)

    def grid(self, rebal: int, phase: int = 0, min_i: int = 300,
             legacy: bool = False) -> List[int]:
        """信号日索引。

        正确口径 (PROTOCOL v1.1 §10.1): 一直生成到最后一个可执行调仓日
        (i+1 < len(dates))，即 range(min_i+phase, n-1, R)。
        legacy=True 复现旧脚本 range(min_i+phase, n-R-2, R)（漏最后一个调仓日）。
        """
        n = len(self.dates)
        stop = n - rebal - 2 if legacy else n - 1
        return list(range(min_i + phase, stop, rebal))


def px_ffill_or_nan(mark: pd.DataFrame, day: pd.Timestamp, code: str) -> float:
    v = mark.at[day, code]
    return float(v) if pd.notna(v) else float("nan")


# ----------------------------------------------------------------------------
# 回测引擎
# ----------------------------------------------------------------------------
@dataclass
class Pos:
    shares: float
    entry_px: float
    entry_i: int
    high: float
    buy_cost: float
    entry_equity: float


@dataclass
class Result:
    eq: pd.Series
    trades: pd.DataFrame
    periods: pd.DataFrame
    meta: dict
    exposure: Optional[pd.Series] = None
    nhold: Optional[pd.Series] = None


def _cost_flat(notional: float, one_way: float) -> float:
    return notional * one_way


SLIP = 0.002


def _cost_buy_real(notional: float, slip: float = 0.0) -> float:
    return max(notional * COMM, MINC) + notional * (TRANS + slip)


def _cost_sell_real(notional: float, slip: float = 0.0) -> float:
    return max(notional * COMM, MINC) + notional * (STAMP + TRANS + slip)


def run_strategy(
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
) -> Result:
    c = inp.close
    mark = inp.mark
    dates = inp.dates
    ret = inp.ret
    n_dates = len(dates)

    grid = inp.grid(rebal, phase, legacy=legacy_grid)
    run_ts = pd.Timestamp(run_start)
    grid = [i for i in grid if dates[i] >= run_ts]
    if not grid:
        raise ValueError("no rebalance dates")
    # 信号 lag: 执行日 = dates[i+1+sig_lag]
    exec_map: Dict[int, int] = {}
    for i in grid:
        ei = i + 1 + sig_lag
        if ei < n_dates:
            exec_map[ei] = i

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
        nonlocal cash, total_cost
        day = dates[i]
        sig_day = dates[sig_i]
        n_eff = n
        if weight_cap is not None and weight_cap > 0 and rank_fill:
            n_eff = max(n, int(__import__("math").ceil(1.0 / weight_cap - 1e-9)))
        picks = inp.picks(sig_day, n_eff, exclude=exclude, factor=factor)
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
            return
        slots = len(picks)
        # 目标: 总权益按 N 等分；已持有的继续持有（差额模式下不再加）
        equity_now = cash + sum(
            p.shares * (px_ffill_or_nan(mark, day, cc) if pd.notna(px_ffill_or_nan(mark, day, cc)) else p.entry_px)
            for cc, p in pos.items()
            if not full_liquidate
        )
        free_slots = slots - (len(pos) if not full_liquidate else 0)
        if free_slots <= 0:
            return
        if weight_cap is not None and weight_cap > 0 and not rank_fill:
            alloc = equity_now * exposure * min(1.0 / slots, weight_cap)
        else:
            alloc = equity_now * exposure / slots
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
        _mv0 = sum(p.shares * (px_ffill_or_nan(mark, day, cc) if pd.notna(px_ffill_or_nan(mark, day, cc)) else p.entry_px)
                   for cc, p in pos.items())
        rebal_snap.append(dict(date=str(day.date()), n_positions=len(pos),
                               cash=float(cash), mv=float(_mv0),
                               alloc_per_slot=float(alloc), picked=int(len(picks))))

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
            do_rebalance(i, exec_map[i])
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
                hit_take = take is not None and px >= p.entry_px * (1.0 + take)
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
        rebalance_snapshots=rebal_snap,
    )
    return Result(eq=eq, trades=tr, periods=per, meta=meta,
                  exposure=_exp["exposure"], nhold=_exp["nhold"])


def build_periods(eq: pd.Series, execs: List[Tuple[int, float]], ret: pd.DataFrame,
                  dates: pd.DatetimeIndex, rebal: int) -> pd.DataFrame:
    """逐段: 两个调仓执行日之间的组合净收益 (盘后权益口径)。

    complete = 该段起点 + R 个交易日 <= 数据末端 (PROTOCOL v1.1 §10.1)。
    末段 partial 计入净值/total，但不计入 win_period 分母。
    """
    rows = []
    for k in range(len(execs) - 1):
        i, e0 = execs[k]
        j, e1 = execs[k + 1]
        if e0 <= 0 or e1 <= 0:
            continue
        rows.append(dict(
            start=dates[i], end=dates[j], n_days=j - i,
            ret=e1 / e0 - 1.0, complete=bool(j - i == rebal),
        ))
    if execs:
        i, e0 = execs[-1]
        last_i = int(dates.get_loc(eq.index[-1])) if len(eq) else i
        if e0 > 0 and len(eq):
            rows.append(dict(start=dates[i], end=eq.index[-1],
                             n_days=last_i - i, ret=eq.iloc[-1] / e0 - 1.0,
                             complete=False))
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# 指标
# ----------------------------------------------------------------------------
def metrics(res: Result, eval_start=EVAL_START, eval_end=EVAL_END,
            base_date=BASE_DATE, mdd_include_base=True) -> dict:
    eq = res.eq
    base_candidates = eq.loc[:base_date]
    if len(base_candidates) == 0:
        # 2026 起跑的变体: 2025-12-31 基数为本金(现金)
        base = float(res.meta.get("capital", 50000.0))
        base_candidates = pd.Series([base], index=[base_date])
    base = float(base_candidates.iloc[-1])
    win = eq.loc[eval_start:eval_end]
    if len(win) == 0:
        raise ValueError("empty eval window")
    end = float(win.iloc[-1])
    total = end / base - 1.0
    n_days = len(win)
    ann = (1.0 + total) ** (252.0 / n_days) - 1.0 if total > -1 else -1.0
    curve = pd.concat([pd.Series([base], index=[base_candidates.index[-1]]), win])
    if not mdd_include_base:
        curve = win
    mdd = float((curve / curve.cummax() - 1.0).min())

    # 月度
    mm = eq.loc[:eval_end].resample("ME").last()
    _b = eq.loc[:base_date]
    dec = float(_b.iloc[-1]) if len(_b) else float(res.meta.get("capital", 50000.0))
    all_m = pd.concat([pd.Series([dec], index=[pd.Timestamp("2025-12-31")]), mm.loc["2026-01-01":]])
    all_m = all_m[~all_m.index.duplicated(keep="last")].sort_index()
    mret = all_m.pct_change().dropna()
    mret = mret.loc[:pd.Timestamp("2026-10-31")]  # 11 月不完整, 不计入
    win_month = int((mret > 0).sum())
    n_month = int(len(mret))

    # 段
    per = res.periods
    if len(per):
        closed = per[per["complete"].fillna(False).astype(bool)]
    else:
        closed = per
    # 只保留完全落在 eval 窗口内的段
    if len(closed):
        closed = closed[(closed["start"] >= eval_start) & (closed["end"] <= eval_end)]
    n_periods = int(len(closed))
    wp = float((closed["ret"] > 0).mean()) if n_periods else float("nan")
    period_rets = [round(float(x), 6) for x in closed["ret"]] if n_periods else []
    partial = per[(~per["complete"].fillna(False).astype(bool))
                  & (per["start"] >= eval_start) & (per["start"] <= eval_end)] if len(per) else per
    last_partial_ret = float(partial["ret"].iloc[-1]) if len(partial) else np.nan
    last_partial_days = int(partial["n_days"].iloc[-1]) if len(partial) else 0

    # 笔
    tr = res.trades
    if len(tr):
        wtr = tr[(tr["exit_date"] >= eval_start) & (tr["exit_date"] <= eval_end)].copy()
    else:
        wtr = tr
    n_trades = int(len(wtr))
    wt = float((wtr["net_ret"] > 0).mean()) if n_trades else float("nan")

    # 逐日收益 / 风险
    dret = win.pct_change()
    dret.iloc[0] = win.iloc[0] / base - 1.0
    vol = float(dret.std() * np.sqrt(252)) if len(dret) > 2 else np.nan
    sharpe = float(dret.mean() * 252 / vol) if vol and vol > 0 else np.nan
    calmar = float(ann / abs(mdd)) if mdd < 0 else np.nan
    return dict(
        total_2026=total, ann_2026=ann, mdd_2026=mdd,
        win_period=wp, n_periods=n_periods, period_rets=period_rets,
        last_partial_ret=last_partial_ret, last_partial_days=last_partial_days,
        win_month=win_month / n_month if n_month else np.nan,
        win_month_n=f"{win_month}/{n_month}",
        monthly_rets={str(k.date()): round(float(v), 6) for k, v in mret.items()},
        win_trade=wt, n_trades=n_trades,
        avg_win=float(wtr.loc[wtr.net_ret > 0, "net_ret"].mean()) if n_trades and (wtr.net_ret > 0).any() else np.nan,
        avg_loss=float(wtr.loc[wtr.net_ret <= 0, "net_ret"].mean()) if n_trades and (wtr.net_ret <= 0).any() else np.nan,
        profit_factor=float(wtr.loc[wtr.net_ret > 0, "net_pnl"].sum() / -wtr.loc[wtr.net_ret <= 0, "net_pnl"].sum())
        if n_trades and (wtr.net_ret <= 0).any() and wtr.loc[wtr.net_ret <= 0, "net_pnl"].sum() != 0 else np.nan,
        vol=vol, sharpe=sharpe, calmar=calmar,
        n_days=n_days, base_equity=base, end_equity=end,
        cost_total=float(res.meta.get("total_cost", 0.0)),
        cost_pct_of_capital=float(res.meta.get("total_cost", 0.0)) / base,
        trade_win_n=int((wtr.net_ret > 0).sum()) if n_trades else 0,
        meta=res.meta,
    )


# ----------------------------------------------------------------------------
# 加载
# ----------------------------------------------------------------------------
_CACHE: Dict[str, Inputs] = {}


def get_inputs() -> Inputs:
    if "x" not in _CACHE:
        _CACHE["x"] = Inputs(pd.read_pickle(PIV_PATH))
    return _CACHE["x"]


# ----------------------------------------------------------------------------
# 报告
# ----------------------------------------------------------------------------
def fmt_pct(x: float) -> str:
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x*100:.2f}%"


def run_main() -> dict:
    """主表: PROTOCOL §10/§11 v1.2 口径。"""
    inp = get_inputs()
    out = {}
    W = dict(capital=50_000.0, phase=0, legacy_grid=False)
    scenarios = {
        # ===== 主口径: 正确网格 + 2024 预热 + stop next =====
        "A_MAIN_0.5_cost": dict(W, cost_one_way=0.005, lot=1, run_start="2024-01-01", stop_exec="next"),
        "B_MAIN_realfee50k": dict(W, cost_one_way=None, lot=100, run_start="2024-01-01", stop_exec="next"),
        "C_MAIN_retail_0.5": dict(W, cost_one_way=0.005, lot=1, run_start="2024-01-01",
                                  stop_exec="next", exclude=("688", "689", "8", "4")),
        "D_MAIN_retail_realfee": dict(W, cost_one_way=None, lot=100, run_start="2024-01-01",
                                      stop_exec="next", exclude=("688", "689", "8", "4")),
        "E_MAIN_mainboard_0.5": dict(W, cost_one_way=0.005, lot=1, run_start="2024-01-01",
                                     stop_exec="next", exclude=("688", "689", "300", "301", "8", "4")),
        # ===== 2026 空仓起步 =====
        "F_fresh_0.5": dict(W, cost_one_way=0.005, lot=1, run_start="2026-01-05", stop_exec="next"),
        "G_fresh_realfee": dict(W, cost_one_way=None, lot=100, run_start="2026-01-05", stop_exec="next"),
        # ===== 敏感性 =====
        "H_same_close_0.5": dict(W, cost_one_way=0.005, lot=1, run_start="2024-01-01", stop_exec="same"),
        "I_same_close_realfee": dict(W, cost_one_way=None, lot=100, run_start="2024-01-01", stop_exec="same"),
        "J_cost08": dict(W, cost_one_way=0.008, lot=1, run_start="2024-01-01", stop_exec="next"),
        "K_sig_lag1": dict(W, cost_one_way=None, lot=100, run_start="2024-01-01", stop_exec="next", sig_lag=1),
        "L_no_stop": dict(W, cost_one_way=None, lot=100, run_start="2024-01-01", stop_exec="next", stop=None),
        "M_10k": dict(W, cost_one_way=None, lot=100, run_start="2024-01-01", stop_exec="next", capital=10_000.0),
        # ===== 旧网格复现 (ledger CSV) =====
        "N_legacy_same_realfee_2025start": dict(capital=50_000.0, phase=0, legacy_grid=True,
                                                cost_one_way=None, lot=100, run_start="2025-01-01",
                                                stop_exec="same"),
        "O_legacy_same_realfee_2024warm": dict(capital=50_000.0, phase=0, legacy_grid=True,
                                               cost_one_way=None, lot=100, run_start="2024-01-01",
                                               stop_exec="same"),
        "P_legacy_same_0.5_2024warm": dict(capital=50_000.0, phase=0, legacy_grid=True,
                                           cost_one_way=0.005, lot=1, run_start="2024-01-01",
                                           stop_exec="same"),
        "Q_doc44.9_repro": dict(capital=50_000.0, phase=0, legacy_grid=True,
                                cost_one_way=None, lot=100, run_start="2026-01-05",
                                stop_exec="same"),
    }
    for name, kw in scenarios.items():
        r = run_strategy(inp, **kw)
        m = metrics(r)
        m["_eq"] = r.eq
        m["_trades"] = r.trades
        m["_periods"] = r.periods
        m["_exposure"] = r.exposure
        out[name] = m
    eq = out["B_MAIN_realfee50k"]["_eq"]
    for yr in (2024, 2025):
        seg = eq.loc[f"{yr}-01-01":f"{yr}-12-31"]
        b = eq.loc[:f"{yr-1}-12-31"]
        base = float(b.iloc[-1]) if len(b) else 50_000.0
        per = out["B_MAIN_realfee50k"]["_periods"]
        p = per[(per.start >= pd.Timestamp(f"{yr}-01-01")) & (per.end <= pd.Timestamp(f"{yr}-12-31")) & per.complete] if len(per) else per
        tr = out["B_MAIN_realfee50k"]["_trades"]
        t = tr[(tr.exit_date >= pd.Timestamp(f"{yr}-01-01")) & (tr.exit_date <= pd.Timestamp(f"{yr}-12-31"))]
        mm = eq.loc[:f"{yr}-12-31"].resample("ME").last()
        allm = pd.concat([pd.Series([base], index=[pd.Timestamp(f"{yr-1}-12-31")]), mm.loc[f"{yr}-01-01":]])
        allm = allm[~allm.index.duplicated(keep="last")].sort_index()
        mr = allm.pct_change().dropna()
        out[f"OOS_{yr}"] = dict(
            total=float(seg.iloc[-1] / base - 1),
            mdd=float((seg / seg.cummax() - 1).min()),
            win_period=float((p.ret > 0).mean()) if len(p) else np.nan,
            n_periods=int(len(p)),
            win_trade=float((t.net_ret > 0).mean()) if len(t) else np.nan,
            win_month=f"{int((mr>0).sum())}/{int(len(mr))}",
            n_days=len(seg), base=base,
        )
    return out


def print_main(res: dict):
    keys = ["total_2026", "ann_2026", "mdd_2026", "win_period", "n_periods",
            "win_month_n", "win_trade", "n_trades", "cost_total", "cost_pct_of_capital",
            "n_days"]
    print(f"{'scenario':42s} " + " ".join(f"{k:>12s}" for k in keys))
    for name, m in res.items():
        if "total_2026" not in m:
            continue
        vals = []
        for k in keys:
            v = m[k]
            if isinstance(v, (int, np.integer)):
                vals.append(f"{v:>12d}")
            elif k in ("total_2026", "ann_2026", "mdd_2026", "win_period", "win_trade",
                       "cost_pct_of_capital"):
                vals.append(f"{fmt_pct(v):>12s}")
            else:
                vals.append(f"{v:>12.2f}" if isinstance(v, float) else f"{str(v):>12s}")
        print(f"{name:42s} " + " ".join(vals))
    print()
    for name, m in res.items():
        if "total_2026" not in m:
            print(f"[{name}] {m}")
            continue
        print(f"[{name}] period_rets={[f'{x*100:.2f}%' for x in m['period_rets']]}")
        print(f"    monthly={ {k: f'{v*100:.2f}%' for k,v in m['monthly_rets'].items()} }")


def _seg_stats(eq: pd.Series, exec_days: List[pd.Timestamp], eval_start=EVAL_START,
               eval_end=EVAL_END) -> Tuple[int, int, List[float]]:
    """按协议口径统计段胜率。"""
    ds = [d for d in exec_days if eval_start <= d <= eval_end]
    wins = n = 0
    rets = []
    for k in range(len(ds) - 1):
        a, b = ds[k], ds[k + 1]
        if a < eval_start or b > eval_end:
            continue
        r = eq.loc[b] / eq.loc[a] - 1.0
        rets.append(r)
        n += 1
        wins += int(r > 0)
    return wins, n, rets


def _month_stats(eq: pd.Series) -> Tuple[int, int]:
    mm = eq.loc[:EVAL_END].resample("ME").last()
    dec = float(eq.loc[:BASE_DATE].iloc[-1])
    all_m = pd.concat([pd.Series([dec], index=[pd.Timestamp("2025-12-31")]), mm.loc["2026-01-01":]])
    all_m = all_m[~all_m.index.duplicated(keep="last")].sort_index()
    mr = all_m.pct_change().dropna().loc[:pd.Timestamp("2026-10-31")]
    return int((mr > 0).sum()), int(len(mr))


def diag_execution(inp: Inputs) -> dict:
    """执行可行性诊断: 用可复现 CSV 的现实账本参数逐笔检查。"""
    r = run_strategy(inp, cost_one_way=None, lot=100, capital=50_000.0,
                     run_start="2025-01-01", stop_exec="same", phase=0,
                     legacy_grid=True)
    tr = r.trades.copy()
    ev = tr[(tr.exit_date >= EVAL_START) & (tr.exit_date <= EVAL_END)]
    out = dict(
        n_trades_all=int(len(tr)), n_trades_2026=int(len(ev)),
        stop_sells_2026=int((ev.reason == "stop").sum()),
        rebal_sells_2026=int((ev.reason == "rebalance").sum()),
        take_sells_2026=int((ev.reason == "take").sum()),
        stale_sells_2026=int(ev.stale.sum()),
        limitdown_sells_2026=int(ev.limitdown.sum()),
        stop_and_limitdown_2026=int(((ev.reason == "stop") & ev.limitdown).sum()),
        stop_and_stale_2026=int(((ev.reason == "stop") & ev.stale).sum()),
        limitup_buys_2026=int(r.meta.get("limitup_buys", 0)),
        stale_buys_2026=int(r.meta.get("stale_buys", 0)),
        max_holding_days=int(ev.hold_days.max()) if len(ev) else 0,
        median_holding_days=float(ev.hold_days.median()) if len(ev) else np.nan,
        holding_days_by_reason=ev.groupby("reason")["hold_days"].median().to_dict() if len(ev) else {},
        # 止损当日跌幅分布
        stop_returns=[round(float(x), 4) for x in ev.loc[ev.reason == "stop", "gross_ret"]],
        win_trade_2026=float((ev.net_ret > 0).mean()) if len(ev) else np.nan,
        avg_win=float(ev.loc[ev.net_ret > 0, "net_ret"].mean()) if (ev.net_ret > 0).any() else np.nan,
        avg_loss=float(ev.loc[ev.net_ret <= 0, "net_ret"].mean()) if (ev.net_ret <= 0).any() else np.nan,
    )
    # 日期级: 持仓中停牌日占比
    eq = r.eq
    return out


def compare_csv(inp: Inputs, csv_path: str) -> dict:
    """把我的 ledger 复现口径与 results/signals CSV 逐日对齐。"""
    r = run_strategy(inp, cost_one_way=None, lot=100, capital=50_000.0,
                     run_start="2025-01-01", stop_exec="same", phase=0,
                     legacy_grid=True)
    mine = r.eq
    old = pd.read_csv(csv_path, parse_dates=["date"]).set_index("date")["eq"].sort_index()
    common = mine.index.intersection(old.index)
    diff = (mine.loc[common] - old.loc[common]).abs()
    rel = diff / old.loc[common].abs()
    out = dict(n_common=int(len(common)), first=str(common.min().date()), last=str(common.max().date()),
               max_abs_diff=float(diff.max()), max_rel_diff=float(rel.max()),
               mine_end=float(mine.iloc[-1]), csv_end=float(old.iloc[-1]),
               mine_2025_12_31=float(mine.loc[:BASE_DATE].iloc[-1]),
               csv_2025_12_31=float(old.loc[:BASE_DATE].iloc[-1]))
    return out


def phase_sweep(inp: Inputs, cost_one_way: Optional[float] = 0.005, lot: int = 1,
                run_start="2024-01-01") -> pd.DataFrame:
    rows = []
    for ph in range(30):
        try:
            r = run_strategy(inp, cost_one_way=cost_one_way, lot=lot, capital=50_000.0,
                             run_start=run_start, stop_exec="same", phase=ph)
            m = metrics(r)
            rows.append(dict(phase=ph, total=m["total_2026"], ann=m["ann_2026"],
                             mdd=m["mdd_2026"], wp=m["win_period"], n_periods=m["n_periods"],
                             wm=m["win_month"], wt=m["win_trade"], n_trades=m["n_trades"],
                             cost=m["cost_total"]))
        except Exception as e:
            rows.append(dict(phase=ph, total=np.nan, err=str(e)))
    return pd.DataFrame(rows)


def stop_sweep(inp: Inputs, cost_one_way=0.005, run_start="2024-01-01") -> pd.DataFrame:
    rows = []
    for s in [0.00, 0.06, 0.08, 0.10, 0.11, 0.12, 0.13, 0.14, 0.16, 0.18, 0.20, 0.25]:
        r = run_strategy(inp, stop=None if s == 0.0 else s, cost_one_way=cost_one_way,
                         lot=1, capital=50_000.0, run_start=run_start, stop_exec="same", phase=0)
        m = metrics(r)
        rows.append(dict(stop=s, total=m["total_2026"], ann=m["ann_2026"], mdd=m["mdd_2026"],
                         wp=m["win_period"], n_periods=m["n_periods"], wm=m["win_month"],
                         wt=m["win_trade"]))
    return pd.DataFrame(rows)


def cost_sweep(inp: Inputs, run_start="2024-01-01") -> pd.DataFrame:
    rows = []
    for c1 in [0.0, 0.001, 0.002, 0.003, 0.005, 0.008]:
        r = run_strategy(inp, cost_one_way=c1, lot=1, capital=50_000.0,
                         run_start=run_start, stop_exec="same", phase=0)
        m = metrics(r)
        rows.append(dict(one_way=c1, total=m["total_2026"], ann=m["ann_2026"],
                         mdd=m["mdd_2026"], wp=m["win_period"], wm=m["win_month"],
                         wt=m["win_trade"], cost=m["cost_total"]))
    return pd.DataFrame(rows)


def index_benchmark() -> dict:
    """中证 1000 / 全指 2026 表现（独立读取）。"""
    out = {}
    for code in ["000852", "000905", "000985", "000300"]:
        try:
            s = pd.read_pickle(os.path.join(ROOT, "results", "_cache", f"index_{code}.pkl"))
            s.index = pd.to_datetime(s.index)
            s = s.sort_index()
            s26 = s.loc[EVAL_START:EVAL_END]
            b = float(s.loc[:BASE_DATE].iloc[-1])
            total = float(s26.iloc[-1] / b - 1)
            mdd = float((s26 / s26.cummax() - 1).min())
            out[code] = dict(total_2026=total, mdd_2026=mdd)
        except Exception as e:
            out[code] = f"ERR {e}"
    return out


def ew_universe_benchmark(inp: Inputs) -> dict:
    """同合格池等权日收益（seasoned + adv20>5e6 + 市值5-30%），0 成本、无止损、每日再平衡。

    这是"2026 小微盘 beta"的独立复算。
    """
    c = inp.close
    r = inp.ret
    dates = inp.dates
    win = dates[(dates >= EVAL_START) & (dates <= EVAL_END)]
    daily = []
    for t in win:
        valid = (inp.seasoned.loc[t] & (inp.adv20.loc[t] > 5e6) & c.loc[t].notna())
        cap_t = inp.cap.loc[t]
        lo, hi = cap_t.quantile(0.05), cap_t.quantile(0.30)
        valid &= ((cap_t >= lo) & (cap_t <= hi)).fillna(False)
        pool = valid[valid].index
        rr = r.loc[t, pool].dropna()
        daily.append(float(rr.mean()) if len(rr) else 0.0)
    dr = pd.Series(daily, index=win)
    eq = (1 + dr).cumprod()
    m = eq.resample("ME").last()
    mret = m.pct_change().dropna().loc[:"2026-10-31"]
    # 30 日段胜率，与策略同相位 (dates[300::30] 的 2026 段)
    seg = []
    g = inp.grid(30, 0)
    for k in range(len(g) - 1):
        i, j = g[k], g[k + 1]
        if dates[i + 1] < EVAL_START or dates[j + 1] > EVAL_END:
            continue
        d = dr.loc[dates[i + 1]:dates[j + 1]]
        if len(d):
            seg.append(float((1 + d).prod() - 1))
    return dict(
        ew_total_2026=float(eq.iloc[-1] - 1),
        ew_mdd_2026=float((eq / eq.cummax() - 1).min()),
        ew_month_win=int((mret > 0).sum()), ew_month_n=int(len(mret)),
        ew_seg_win=int(sum(x > 0 for x in seg)), ew_seg_n=len(seg),
        ew_monthly={str(k.date()): round(float(v), 6) for k, v in mret.items()},
        ew_seg_rets=[round(x, 6) for x in seg],
    )


def attribution(inp: Inputs, run_kw: dict) -> dict:
    """2026 收益归因: 逐票 PnL、逐月、集中度、被整手丢弃的标的。"""
    r = run_strategy(inp, **run_kw)
    eq = r.eq
    m = metrics(r)
    base = m["base_equity"]
    tr = r.trades
    ev = tr[(tr.exit_date >= EVAL_START) & (tr.exit_date <= EVAL_END)].copy()
    pnl_by_code = ev.groupby("code")["net_pnl"].sum().sort_values(ascending=False)
    tot_pnl = float(ev["net_pnl"].sum())
    top3 = pnl_by_code.head(3)
    out = dict(
        total_2026=m["total_2026"], pnl_2026=float(pnl_by_code.sum()),
        pnl_pct_of_base=tot_pnl / base,
        top1_code=str(top3.index[0]), top1_pnl=float(top3.iloc[0]),
        top3_codes=list(top3.index), top3_pnl=float(top3.sum()),
        top3_share_of_pnl=float(top3.sum() / tot_pnl) if tot_pnl else np.nan,
        top5_share_of_pnl=float(pnl_by_code.head(5).sum() / tot_pnl) if tot_pnl else np.nan,
        n_codes=int(len(pnl_by_code)),
        top10=pnl_by_code.head(10).round(1).to_dict(),
        bottom5=pnl_by_code.tail(5).round(1).to_dict(),
        monthly=m["monthly_rets"],
        picks_history=[],
    )
    # 逐调仓日 picks（含名称/价格/整手可行性）
    import pandas as _pd
    uni = _pd.read_pickle(os.path.join(ROOT, "data", "universe.pkl")).set_index("code")
    g = inp.grid(30, 0)
    for i in g:
        t = inp.dates[i]
        if not (pd.Timestamp("2026-01-01") <= t <= EVAL_END):
            continue
        picks = inp.picks(t, 5)
        ei = i + 1
        if ei >= len(inp.dates):
            continue
        day = inp.dates[ei]
        rows = []
        for code in picks:
            px = float(inp.mark.at[day, code])
            nm = uni["name"].get(code, "?")
            rows.append(dict(code=code, name=nm, px=round(px, 2),
                             lot_shares=int(10000 // px // 100 * 100) if px > 0 else 0))
        out["picks_history"].append(dict(signal=str(t.date()), exec=str(day.date()), picks=rows))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", nargs="?", default="run")
    ap.add_argument("--json", default="")
    ap.add_argument("--csv", default="results/signals/ledger_N5_R30_STOP0.12_TAKENone.csv")
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    payload = {}

    if args.what in ("run", "all"):
        res = run_main()
        print_main(res)
        payload["run"] = {name: {k: v for k, v in m.items() if not k.startswith("_")}
                          for name, m in res.items()}
        # 逐笔/逐段落盘 (主口径 A)
        for nm in ("A_total2026_protocol05", "B_total2026_realfee50k"):
            if nm in res:
                res[nm]["_trades"].to_csv(os.path.join(OUT_DIR, f"{nm}_trades.csv"), index=False)
                res[nm]["_periods"].to_csv(os.path.join(OUT_DIR, f"{nm}_periods.csv"), index=False)
                res[nm]["_eq"].rename("eq").to_csv(os.path.join(OUT_DIR, f"{nm}_equity.csv"))

    inp = None
    if args.what in ("diag", "phase", "cost", "stop", "bench", "compare", "attrib", "all"):
        inp = get_inputs()

    if args.what in ("diag", "all"):
        d = diag_execution(inp)
        print("\n=== 执行可行性诊断 (现实账本 5万/整手, 2025-01-01 起) ===")
        for k, v in d.items():
            print(f"  {k}: {v}")
        payload["diag"] = d

    if args.what in ("compare", "all"):
        cp = compare_csv(inp, os.path.join(ROOT, args.csv))
        print("\n=== 与 results/signals CSV 逐日对齐 ===")
        for k, v in cp.items():
            print(f"  {k}: {v}")
        payload["compare"] = cp

    if args.what in ("phase", "all"):
        for label, c1, lot in [("flat0.5", 0.005, 1), ("realfee", None, 100)]:
            df = phase_sweep(inp, cost_one_way=c1, lot=lot)
            print(f"\n=== 调仓相位扫描 (0..29) [{label}] ===")
            print(df.describe().loc[["min", "25%", "50%", "75%", "max"]][
                ["total", "ann", "mdd", "wp", "wm", "wt"]].to_string())
            print("  total 排名前5:", df.nlargest(5, "total")[["phase", "total", "mdd", "wp", "wm"]].to_dict("records"))
            print("  total 排名后5:", df.nsmallest(5, "total")[["phase", "total", "mdd", "wp", "wm"]].to_dict("records"))
            print(f"  total>=60% 的相位: {int((df['total']>=0.60).sum())}/30 ; mdd>=-15%: {int((df['mdd']>=-0.15).sum())}/30 ; wp>=0.8: {int((df['wp']>=0.8).sum())}/30 ; 三线全过: {int(((df['total']>=0.60)&(df['mdd']>=-0.15)&(df['wp']>=0.8)).sum())}/30")
            payload[f"phase_{label}"] = df.to_dict("records")

    if args.what in ("cost", "all"):
        df = cost_sweep(inp)
        print("\n=== 成本敏感性 (协议成本, 分数股) ===")
        print(df.to_string(index=False))
        payload["cost"] = df.to_dict("records")

    if args.what in ("stop", "all"):
        df = stop_sweep(inp)
        print("\n=== 止损档敏感性 (协议成本 0.5%/边) ===")
        print(df.to_string(index=False))
        payload["stop"] = df.to_dict("records")

    if args.what in ("bench", "all"):
        b = index_benchmark()
        u = ew_universe_benchmark(inp)
        print("\n=== 基准 (独立复算) ===")
        print("  指数:", json.dumps(b, ensure_ascii=False, default=str))
        print("  合格池等权:", json.dumps(u, ensure_ascii=False, default=str))
        payload["bench"] = {"index": b, "universe_ew": u}

    if args.what in ("attrib", "all"):
        att = attribution(inp, dict(cost_one_way=None, lot=100, capital=50_000.0,
                                    run_start="2024-01-01", stop_exec="same"))
        print("\n=== 2026 收益归因 ===")
        print(json.dumps({k: v for k, v in att.items() if k != "picks_history"}, ensure_ascii=False, indent=1, default=str))
        print("\n  picks:")
        for h in att["picks_history"]:
            print("   ", h["signal"], "->", h["exec"], [(p["code"], p["name"], p["px"], p["lot_shares"]) for p in h["picks"]])
        payload["attrib"] = att

    if args.json:
        with open(args.json, "w") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        print("\nwrote", args.json)


# ============================================================================
# 诊断 / 攻击
# ============================================================================
