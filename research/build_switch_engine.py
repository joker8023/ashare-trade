#!/usr/bin/env python3
"""从 prior_check.run_strategy 派生双引擎切换版引擎 (持仓层)。
引擎 A = 函数原参数 (n/rebal/take/exposure + inp); 引擎 B = inp_b + cfg_b。
规则: 仅在 A 网格信号日评估切换 — 比较两引擎独立运行的影子权益曲线
trailing-60d 收益, 高者为 desired; desired != mode 时在执行日全清并按
新引擎 picks/n/exposure 重建仓, 持仓止盈改用新引擎 take (切换必全清,
故任一时点全部持仓同属一个引擎)。desired == mode 时仅当信号日落在
当前引擎网格才调仓。lock_mode 锁死引擎做回归验证 (须与独立运行逐值一致)。
切换成本 = 引擎自身的真实费率+滑点 (全清卖出 + 全额买入), 无额外假设。
"""
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "team" / "audit" / "prior_check.py"
lines = SRC.read_text().splitlines(keepends=True)
body = "".join(lines[155:454])

body = body.replace("def run_strategy(", "def run_strategy_switch(", 1)

old = "    rank_fill: bool = True,\n"
new = ("    rank_fill: bool = True,\n"
       "    inp_b=None,                            # 引擎 B 的 Inputs\n"
       "    cfg_b=None,                            # dict(n=, rebal=, take=, exposure=)\n"
       "    shadow_a=None, shadow_b=None,          # 两引擎独立权益曲线 (RS 信号)\n"
       "    rs_lookback: int = 60,\n"
       "    lock_mode=None,                        # 'A'/'B': 锁死引擎 (回归验证)\n")
assert old in body
body = body.replace(old, new, 1)

old = """    grid = inp.grid(rebal, phase, legacy=legacy_grid)
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

    loop_start = grid[0]"""
new = """    run_ts = pd.Timestamp(run_start)
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

    loop_start = grid[0]"""
assert old in body
body = body.replace(old, new, 1)

old = """    rebal_snap = []
"""
new = """    rebal_snap = []

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
"""
assert old in body
body = body.replace(old, new, 1)

old = """    def do_rebalance(i: int, sig_i: int):
        nonlocal cash, total_cost
        day = dates[i]
        sig_day = dates[sig_i]
        n_eff = n
        if weight_cap is not None and weight_cap > 0 and rank_fill:
            n_eff = max(n, int(__import__("math").ceil(1.0 / weight_cap - 1e-9)))
        picks = inp.picks(sig_day, n_eff, exclude=exclude, factor=factor)"""
new = """    def do_rebalance(i: int, sig_i: int):
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
        picks = inp_cur.picks(sig_day, n_eff, exclude=exclude, factor=factor)"""
assert old in body
body = body.replace(old, new, 1)

# do_rebalance 的早退与结尾: 统一返回 bool (是否 append 了 executed_rebalances)
old = """        # 用剩余现金等权买入
        if not picks:
            return"""
new = """        # 用剩余现金等权买入
        if not picks:
            return True  # 已全清 (切换/调仓生效), 但无新仓; append 语义见文末"""
assert old in body
body = body.replace(old, new, 1)

old = """        if free_slots <= 0:
            return"""
new = """        if free_slots <= 0:
            return False"""
assert old in body
body = body.replace(old, new, 1)

old = """        executed_rebalances.append((i, 0.0))  # 稍后填 equity"""
new = """        executed_rebalances.append((i, 0.0))  # 稍后填 equity
        _appended = True"""
assert old in body
body = body.replace(old, new, 1)

# alloc 的 exposure 两处
assert body.count("equity_now * exposure") == 2
body = body.replace("equity_now * exposure", "equity_now * state_exposure")

# do_rebalance 结尾补 return (在 rebal_snap.append 之后, 函数结束处)
old = """        rebal_snap.append(dict(date=str(day.date()), n_positions=len(pos),
                               cash=float(cash), mv=float(_mv0),
                               alloc_per_slot=float(alloc), picked=int(len(picks))))"""
new = old + """
        return True"""
assert old in body
body = body.replace(old, new, 1)

# 调用方: 仅当 append 发生才覆写 (避开原引擎空 picks 时的元数据坑)
old = """        if i in exec_map:
            do_rebalance(i, exec_map[i])
            executed_rebalances[-1] = (i, 0.0)"""
new = """        if i in exec_map:
            if do_rebalance(i, exec_map[i]):
                executed_rebalances[-1] = (i, 0.0)"""
assert old in body
body = body.replace(old, new, 1)

# 止盈用当前引擎 take
old = '                hit_take = take is not None and px >= p.entry_px * (1.0 + take)'
new = '                hit_take = state_take is not None and px >= p.entry_px * (1.0 + state_take)'
assert old in body
body = body.replace(old, new, 1)

# meta 加 switch_log
old = "        rebalance_snapshots=rebal_snap,\n"
new = "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode,\n"
assert old in body
body = body.replace(old, new, 1)

header = '''#!/usr/bin/env python3
"""双引擎切换引擎 (由 build_switch_engine.py 从 prior_check.run_strategy 派生)。
lock_mode='A'/'B' 时须与两引擎独立运行逐值一致 (回归断言在 run_switch_backtest.py)。"""
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from prior_check import *  # noqa: F401,F403
from prior_check import _cost_buy_real, _cost_flat, _cost_sell_real  # noqa: F401

'''
out = Path(__file__).resolve().parent / "switch_engine.py"
out.write_text(header + body)
print(f"wrote {out} ({len(header + body)} chars)")
