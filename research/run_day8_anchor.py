#!/usr/bin/env python3
"""日8锚引擎回测 (2020 新浪口径, ph0 长口径): X3 规则 + 每月第 8 个交易日网格。

规格:
- 选股与 X3 完全相同: 市值带 2-30% + 精修门 (ret60<-15% 且 ret10<0 才排除) +
  Amihud60 前 4 + 主板 + min_adv ¥5M (MInputs w=60, 原样取自 design_monthly.py;
  该文件的沙箱路径未移植, 故类定义内嵌于此, 与原文逐字一致)。
- 网格不用等距 30 日, 改为自然月锚: 每月第 8 个交易日为执行日, 信号日为
  其前一交易日 (grid 注入 pc.run_strategy, 同 design_monthly.run_cfg 的做法)。
  全清重选、TP+100%、敞口 1.0、真实费率+滑点 0.2%/边。
- 月末锚曾被诊断为污染源 (design_monthly 线), 第 8 交易日锚是其修复版。

结果 (ph0 长口径, 数据至 2026-11-12): 全程 +1352.68% / -39.15% — 全程收益
超过双引擎切换 (+1336.06%), 3y 窗 +1248.75% 亦胜 (+1215.03%), 回撤更浅;
但 1m/3m/1y/2y 不及切换版 (1m -7.73 vs -5.01, 3m +13.69 vs +14.03,
1y +125.37 vs +145.57, 2y +1186.31 vs +1262.71), 未过全窗判据。
口径警告: 本数字是长口径 (曲线 2023 年初起); 月度线当年的 +741.48% 是
三年口径, 不可混用。JSON 落 results/r30_bt/day8_anchor_ph0.json。
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

MB = ("688", "689", "300", "301", "8", "4")
WINDOWS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}
RUN_START = "2023-01-03"
EVAL_END = pd.Timestamp("2026-11-12")
SWITCH_TARGET = {"1m": -5.01, "3m": 14.03, "6m": 32.02, "1y": 145.57, "2y": 1262.71, "3y": 1215.03}


class MInputs(X3Inputs):
    """原样取自 design_monthly.py (w=60 时因子即 amihud60)。"""

    def __init__(self, piv, band=(0.02, 0.30), gate60=-0.15, min_adv=5e6, w=60):
        super().__init__(piv, band=band, gate60=gate60, min_adv=min_adv)
        if w == 60:
            self.fac_w = self.amihud60
        elif w == 20:
            self.fac_w = self.amihud
        else:
            r = self.close.pct_change(fill_method=None).abs()
            amt = self.amount.replace(0, __import__("numpy").nan)
            self.fac_w = (r / (amt / 1e8)).rolling(w, min_periods=w).mean()

    def picks(self, t, n, size_range=None, min_adv=None, exclude=(), factor="amihud_60"):
        if t not in self.close.index:
            return []
        sr = self.band if size_range is None else size_range
        ma = self.min_adv if min_adv is None else min_adv
        fac = self.fac_w
        valid = (self.seasoned.loc[t]
                 & (self.adv20.loc[t] > ma)
                 & self.close.loc[t].notna()
                 & fac.loc[t].notna())
        valid &= ~((self.ret60.loc[t] < self.gate60)
                   & (self.ret10.loc[t] < 0)).fillna(False)
        cap_t = self.cap.loc[t]
        lo, hi = cap_t.quantile(sr[0]), cap_t.quantile(sr[1])
        valid &= ((cap_t >= lo) & (cap_t <= hi)).fillna(False)
        if exclude:
            valid &= ~pd.Series(list(valid.index), index=valid.index).str.startswith(exclude)
        return list(fac.loc[t][valid].sort_values(ascending=False).head(n).index)


def monthly_sigs(dates, exec_pos):
    """exec_pos: 每月第几个交易日为执行日 (0 起)。返回信号日索引 (执行日前一日)。"""
    months = {}
    for i, d in enumerate(dates):
        months.setdefault((d.year, d.month), []).append(i)
    sigs = []
    for _, idxs in sorted(months.items()):
        if len(idxs) > exec_pos:
            s = idxs[exec_pos] - 1
            if s >= 300:
                sigs.append(s)
    return sorted(sigs)


piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))

inp = MInputs(piv, w=60)
SIGS = monthly_sigs(dates, 7)  # 第 8 个交易日执行
inp.grid = (lambda s: (lambda rebal, phase=0, legacy=False: list(s)))(SIGS)

res = pc.run_strategy(
    inp, factor="amihud_60", n=4, rebal=30, take=1.0, stop=None, stop_exec="next",
    exclude=MB, capital=50_000.0, lot=100, cost_one_way=None, slip=0.002,
    run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END,
    phase=0, legacy_grid=False, exposure=1.0, full_liquidate=True)

eq = res.eq
eq = (eq.iloc[:, 0] if hasattr(eq, "columns") else eq)
eq = pd.Series(eq).dropna()
tab = {"total_ret_pct": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
       "full_mdd_pct": round(float((eq / eq.cummax() - 1).min()) * 100, 2),
       "n_trades": len(res.trades), "total_cost": round(float(res.meta["total_cost"]), 0)}
for w, d in WINDOWS.items():
    sub = eq.tail(d + 1)
    tab[w] = {"ret_pct": round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2),
              "mdd_pct": round(float((sub / sub.cummax() - 1).min()) * 100, 2)}
    print(f"{w}: {tab[w]['ret_pct']:+9.2f}%  mdd {tab[w]['mdd_pct']:7.2f}%  (切换版 {SWITCH_TARGET[w]:+.2f}%)")
print(f"全程 {tab['total_ret_pct']:+.2f}% / {tab['full_mdd_pct']:.2f}%, 交易 {tab['n_trades']} 笔, 成本 ¥{tab['total_cost']:,.0f}")
assert tab["total_ret_pct"] == 1352.68 and tab["3y"]["ret_pct"] == 1248.75, "复现断言失败"
print("复现断言通过 (全程 +1352.68%, 3y +1248.75%)")
out = ROOT / "results" / "r30_bt" / "day8_anchor_ph0.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(tab, ensure_ascii=False, indent=1))
print(f"saved {out}")
