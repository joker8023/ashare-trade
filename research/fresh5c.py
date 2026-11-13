#!/usr/bin/env python3
"""第三批五套 (Kai 三度指令: 目标超过 X3)。
只用前两批验证过的最强元素做新组合, 设计跑前定死:
T1 冷门度: 主板+市值带2-30% 内按 20日换手率最低排名 (纯交易冷门, 不含价格冲击项), 精炼门-15%, N4, TP100, R30。
T2 S1 精修: 市值最小 15% 内 Amihud60 + 精炼门-15%, N6, 主板, TP100, R30。
T3 X3×S1 双袖组合: 已存净值 25k+25k 合成 (无新回测, 纯组合)。
T4 S1 × 月度第 8 交易日锚: S1 选股搬到已验证的月度高原锚点 (含第 7/9 日邻域验证)。
T5 低价非流动性: 股价最低 30% ∩ 市值带 2-30% 内按 Amihud60 排名, 精炼门-15%, N4, 主板, TP100, R30。
R30 组跑 phase 0/10/20; T4 与月度同窗基准 (X3 同窗 +631.4 / X3第8日 +741.48) 比。
"""
import json
import os
import sys

ROOT = os.path.expanduser("~/workspace/ashare-trade")
sys.path.insert(0, os.path.join(ROOT, "team", "audit"))
sys.path.insert(0, os.path.expanduser("~/workspace/tools"))
os.chdir(ROOT)

import numpy as np
import pandas as pd

import prior_check as pc
from design_monthly import stats, MB
from design_monthly2 import monthly_sigs
from fresh5b import F2


class F3(pc.Inputs):
    def __init__(self, piv, mode):
        super().__init__(piv)
        self.mode = mode
        c = self.close
        self.ret60 = c / c.shift(60) - 1.0
        self.ret10 = c / c.shift(10) - 1.0
        self.turn20 = (self.piv["volume"] / self.shares.replace(0, np.nan)).rolling(20, min_periods=20).mean()

    def _gate(self, v, t):
        return v & ~((self.ret60.loc[t] < -0.15) & (self.ret10.loc[t] < 0)).fillna(False)

    def _band(self, v, t, lo, hi, frame=None):
        f = self.cap.loc[t] if frame is None else frame.loc[t]
        a, b = f.quantile(lo), f.quantile(hi)
        return v & ((f >= a) & (f <= b)).fillna(False)

    def _excl(self, v, exclude):
        if exclude:
            v = v & ~pd.Series(list(v.index), index=v.index).str.startswith(exclude)
        return v

    def picks(self, t, n, size_range=None, min_adv=None, exclude=(), factor="amihud_60"):
        if t not in self.close.index:
            return []
        v = (self.seasoned.loc[t] & (self.adv20.loc[t] > 5e6) & self.close.loc[t].notna())
        if self.mode == "T1":
            v = self._band(v, t, 0.02, 0.30)
            v = self._gate(v, t)
            v = self._excl(v, exclude)
            s = self.turn20.loc[t]
            return list(s[v & s.notna()].sort_values().head(n).index)
        if self.mode == "T2":
            v = self._band(v, t, 0.0, 0.15)
            v = self._gate(v, t)
            v = self._excl(v, exclude)
            s = self.amihud60.loc[t]
            return list(s[v & s.notna()].sort_values(ascending=False).head(n).index)
        # T5
        v = self._band(v, t, 0.0, 0.30, frame=self.close)
        v = self._band(v, t, 0.02, 0.30)
        v = self._gate(v, t)
        v = self._excl(v, exclude)
        s = self.amihud60.loc[t]
        return list(s[v & s.notna()].sort_values(ascending=False).head(n).index)


def run_r30(inp, tag, n, phase):
    res = pc.run_strategy(inp, factor="amihud_60", n=n, rebal=30, take=1.0,
                          stop=None, stop_exec="next", exclude=MB,
                          capital=50_000.0, lot=100, cost_one_way=None, slip=0.002,
                          run_start="2023-11-10",
                          eval_start=pd.Timestamp("2025-02-13"),
                          eval_end=pd.Timestamp("2026-11-10"),
                          phase=phase, legacy_grid=False, exposure=1.0,
                          full_liquidate=True)
    eq = res.eq.dropna()
    t, m, y = stats(eq)
    row = {"tag": tag, "phase": phase, "total": t, "mdd": m, "r1y": y}
    if phase == 0:
        row["h2025"] = stats(eq[eq.index <= "2025-12-31"])[0]
        row["h2026"] = stats(eq[eq.index >= "2025-12-31"])[0]
        eq.to_pickle(f"results/r30_bt/fresh5c_{tag}_equity.pkl")
    print(json.dumps(row, ensure_ascii=False), flush=True)
    return row


def main():
    base = pc.get_inputs()
    piv, dates = base.piv, base.dates
    rows = []
    for mode, n in (("T1", 4), ("T2", 6), ("T5", 4)):
        inp = F3(piv, mode)
        for ph in (0, 10, 20):
            rows.append(run_r30(inp, mode, n, ph))

    # T3: X3 × S1 双袖 (已存净值合成)
    x3 = pd.read_pickle("results/r30_bt/phase_audit/x3_ph0.pkl").dropna()
    s1 = pd.read_pickle("results/r30_bt/fresh5b_S1_equity.pkl").dropna()
    comb = (x3 + s1) / 2
    t, m, y = stats(comb)
    print(json.dumps({"tag": "T3_X3xS1_combo", "total": t, "mdd": m, "r1y": y},
                     ensure_ascii=False), flush=True)
    comb.to_pickle("results/r30_bt/fresh5c_T3_equity.pkl")

    # T4: S1 选股 × 月度第 7/8/9 交易日锚
    inp = F2(piv, "S1")
    for k in (7, 8, 9):
        sig = monthly_sigs(dates, k - 1)
        inp.grid = (lambda s: (lambda rebal, phase=0, legacy=False: list(s)))(sig)
        res = pc.run_strategy(inp, factor="amihud_60", n=5, rebal=30, take=1.0,
                              stop=None, stop_exec="next", exclude=MB,
                              capital=50_000.0, lot=100, cost_one_way=None, slip=0.002,
                              run_start="2023-11-10",
                              eval_start=pd.Timestamp("2025-02-13"),
                              eval_end=pd.Timestamp("2026-11-10"),
                              phase=0, legacy_grid=False, exposure=1.0,
                              full_liquidate=True)
        eq = res.eq.dropna()
        t, m, y = stats(eq)
        print(json.dumps({"tag": f"T4_S1_day{k}", "total": t, "mdd": m, "r1y": y},
                         ensure_ascii=False), flush=True)
        if k == 8:
            eq.to_pickle("results/r30_bt/fresh5c_T4_day8_equity.pkl")
    print("基准: X3 R30ph0 +640.68/-13.56 | X3 同窗(月度) +631.4 | X3 第8日 +741.48/-13.46", flush=True)


if __name__ == "__main__":
    main()
