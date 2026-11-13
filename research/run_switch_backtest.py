#!/usr/bin/env python3
"""双引擎切换策略回测 (2020 新浪口径, ph0): 双回归门 + 正式跑 + 六窗表。

策略规格:
- 引擎 A = R20_N5: 市值带 2-30% + 精修门 (ret60<-15% 且 ret10<0 才排除) +
  Amihud60 前 5 + 主板 + 20 日网格全清 + TP+100% + 敞口 1.0。
- 引擎 B = 均衡型 N4: pc.Inputs 默认 (带 5-30%) + 前 4 + 30 日网格 + TP+45% +
  敞口 0.9。
- 切换: 两引擎各自独立跑出影子权益曲线; 仅在 A 网格信号日比较两条影子
  trailing-60 交易日收益, 高者为期望模式 (平局维持); 两影子都须 >=60 天
  历史才开始评估, 之前恒在 A。翻转时次日收盘全清 (真实费率+滑点), 按新
  引擎当日 picks/N/敞口重建仓, 止盈改用新引擎 take; 不翻转时只在当前引擎
  自身网格日调仓 (B 在位时其 30 日网格与 A 评估日每 60 天重合才动)。
- 引擎为审计引擎 prior_check.run_strategy 的派生 (build_switch_engine.py),
  先过双回归门: lock_mode='A'/'B' 须与 A/B 独立运行逐值一致 (总收益/回撤/
  曲线/成本), 不过门不许出数。

结果 (ph0, 2026-11-13 验证): 全程 +1336.06% / -43.01%, 5 次切换
(2023-06-21→B, 2024-02-21→A, 2024-05-22→B, 2024-08-15→A, 2026-09-08→B),
总成本 ¥43,310; 六窗全超 R20_N5 ph0。注意: 20 相位里只有 ph0 一个相位
六窗全胜, 相位中位数 +710.34% / -33.08% — ph0 是最顺的锚, 非期望表现。
JSON 落到 results/r30_bt/switch_backtest_ph0.json (results/ 不入 git)。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))

import pandas as pd

import prior_check as pc
from design_r30_grid8 import X3Inputs
from switch_engine import run_strategy_switch


def _mdd(s):
    return float((s / s.cummax() - 1).min())

MB = ("688", "689", "300", "301", "8", "4")
WINDOWS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}
RUN_START = "2023-01-03"
EVAL_END = pd.Timestamp("2026-11-12")
R20_TARGET = {"1m": -5.66, "3m": 10.04, "6m": 27.32, "1y": 137.41, "2y": 1210.49, "3y": 1137.60}

piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))

inp_a = X3Inputs(piv, gate60=-0.15)
inp_b = pc.Inputs(piv)
COMMON = dict(factor="amihud_60", stop=None, stop_exec="next", exclude=MB,
              capital=50_000.0, lot=100, cost_one_way=None, slip=0.002,
              run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END,
              legacy_grid=False, full_liquidate=True)
CFG_B = dict(n=4, rebal=30, take=0.45, exposure=0.9)

ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.0, exposure=1.0, phase=0, **COMMON)
rb = pc.run_strategy(inp_b, phase=0, **{**COMMON, **CFG_B})
KW = dict(n=5, rebal=20, take=1.0, exposure=1.0, phase=0,
          inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, **COMMON)

# 双回归门 (Result 只有 eq/trades/periods/meta, 总收益由曲线算)
EXP_TOT = {"A": 1070.09, "B": 396.82}
for lock, base in (("A", ra), ("B", rb)):
    r = run_strategy_switch(inp_a, lock_mode=lock, **KW)
    e = r.eq.iloc[:, 0] if isinstance(r.eq, pd.DataFrame) else r.eq
    tot = round(float(e.dropna().iloc[-1] / e.dropna().iloc[0] - 1) * 100, 2)
    assert tot == EXP_TOT[lock], (lock, tot)
    # 曲线在独立运行的索引上逐值一致; 切换版多出的前置点须为未建仓的平坦资本
    be = base.eq.iloc[:, 0] if isinstance(base.eq, pd.DataFrame) else base.eq
    aligned = e.reindex(be.index)
    assert aligned.equals(be), lock
    extra = e.drop(index=be.index, errors="ignore")
    assert (extra == base.meta.get("capital", 50_000.0)).all(), lock
    assert abs(r.meta["total_cost"] - base.meta["total_cost"]) < 1e-9, lock
    print(f"回归门 lock={lock} 通过 (total {tot:+.2f}%, cost ¥{r.meta['total_cost']:,.0f})")

res = run_strategy_switch(inp_a, lock_mode=None, **KW)
eq = res.eq
if isinstance(eq, pd.DataFrame):
    eq = eq.iloc[:, 0]
eq = eq.dropna()

tab = {"total_ret_pct": round((eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
       "full_mdd_pct": round(_mdd(eq) * 100, 2),
       "n_trades": len(res.trades), "total_cost": round(float(res.meta["total_cost"]), 0),
       "switch_log": res.meta["switch_log"], "final_mode": res.meta["final_mode"]}
for w, d in WINDOWS.items():
    sub = eq.tail(d + 1)
    tab[w] = {"ret_pct": round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2),
              "mdd_pct": round(_mdd(sub) * 100, 2)}
    print(f"{w}: {tab[w]['ret_pct']:+9.2f}%  mdd {tab[w]['mdd_pct']:7.2f}%  (R20_N5 {R20_TARGET[w]:+.2f}%)")
print(f"全程 {tab['total_ret_pct']:+.2f}% / {tab['full_mdd_pct']:.2f}%, 切换 {len(tab['switch_log'])} 次, "
      f"成本 ¥{tab['total_cost']:,.0f}, 期末模式 {tab['final_mode']}")
out = ROOT / "results" / "r30_bt" / "switch_backtest_ph0.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(tab, ensure_ascii=False, indent=1))
print(f"saved {out}")
