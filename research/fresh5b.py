#!/usr/bin/env python3
"""第二批五套 (Kai 指令: 目标就是超过 X3)。
设计在跑之前定死 (见下), 每套一个不同机制, 都建立在已验证的实证之上
(非流动性溢价真实存在 / SIZE 是唯一稳定的经典因子 / 主板与市值带在 X 家族里反复有效)。
统一: R30 网格、TP+100%、全清仓、敞口 1.0、真实成本、上市≥250日、adv20>500万。
S1 非流动性×微盘交集: 市值最小 20% 池内按 Amihud60 排名, N=5, 主板。
S2 换手枯竭: 换手率 20日均/120日均 最低 (相对自身历史卖压枯竭), 且股价在 60日均线 ±10% 内, N=4, 全市场。
S3 洗盘底: 成交额缩至 120日均的 70% 以下 且 距 120日低点最近, 且 ret10>0 (已转头), N=4, 全市场。
S4 微盘动量: 市值最小 30% 池内按 ret60 排名, N=4, 全市场。
S5 多窗口非流动性共识: Amihud 20/60/120 三个窗口名次求和, 市值带 2-30%, 无门, N=4, 主板。
每套跑 phase 0/10/20 + ph0 分半。
"""
import json
import os
import sys

ROOT = os.path.expanduser("~/workspace/ashare-trade")
sys.path.insert(0, os.path.join(ROOT, "team", "audit"))
os.chdir(ROOT)

import numpy as np
import pandas as pd

import prior_check as pc

MB = ("688", "689", "300", "301", "8", "4")


class F2(pc.Inputs):
    def __init__(self, piv, mode):
        super().__init__(piv)
        self.mode = mode
        c, r = self.close, self.ret
        self.ret60 = c / c.shift(60) - 1.0
        self.ret20 = c / c.shift(20) - 1.0
        self.ret10 = c / c.shift(10) - 1.0
        turn = self.piv["volume"] / self.shares.replace(0, np.nan)
        self.dry = turn.rolling(20, min_periods=20).mean() / turn.rolling(120, min_periods=120).mean()
        self.pos60 = c / c.rolling(60, min_periods=60).mean()
        self.amt_r = self.adv20 / self.amount.rolling(120, min_periods=120).mean()
        self.lowpos = c / c.rolling(120, min_periods=120).min() - 1.0
        rr = c.pct_change(fill_method=None).abs()
        amt = self.amount.replace(0, np.nan)
        self.amihud120 = (rr / (amt / 1e8)).rolling(120, min_periods=120).mean()

    def _valid0(self, t):
        return (self.seasoned.loc[t] & (self.adv20.loc[t] > 5e6)
                & self.close.loc[t].notna())

    def _band(self, valid, t, lo, hi):
        cap_t = self.cap.loc[t]
        a, b = cap_t.quantile(lo), cap_t.quantile(hi)
        return valid & ((cap_t >= a) & (cap_t <= b)).fillna(False)

    def _excl(self, valid, exclude):
        if exclude:
            valid = valid & ~pd.Series(list(valid.index), index=valid.index).str.startswith(exclude)
        return valid

    def picks(self, t, n, size_range=None, min_adv=None, exclude=(), factor="amihud"):
        if t not in self.close.index:
            return []
        v = self._valid0(t)
        if self.mode == "S1":
            v = self._band(v, t, 0.0, 0.20)
            v = self._excl(v, exclude)
            s = self.amihud60.loc[t]
            return list(s[v & s.notna()].sort_values(ascending=False).head(n).index)
        if self.mode == "S2":
            v = v & (self.pos60.loc[t].between(0.9, 1.1)).fillna(False)
            v = self._excl(v, exclude)
            s = self.dry.loc[t]
            return list(s[v & s.notna()].sort_values().head(n).index)
        if self.mode == "S3":
            v = v & (self.amt_r.loc[t] < 0.7).fillna(False) & (self.ret10.loc[t] > 0).fillna(False)
            v = self._excl(v, exclude)
            s = self.lowpos.loc[t]
            return list(s[v & s.notna()].sort_values().head(n).index)
        if self.mode == "S4":
            v = self._band(v, t, 0.0, 0.30)
            v = self._excl(v, exclude)
            s = self.ret60.loc[t]
            return list(s[v & s.notna()].sort_values(ascending=False).head(n).index)
        # S5 多窗口共识
        v = self._band(v, t, 0.02, 0.30)
        v = self._excl(v, exclude)
        pool = v[v].index
        score = None
        for f in (self.amihud, self.amihud60, self.amihud120):
            rk = f.loc[t, pool].rank(ascending=True)
            score = rk if score is None else score + rk
        return list(score.nsmallest(n).index)


def stats(eq):
    eq = eq.dropna()
    tot = float(eq.iloc[-1] / eq.iloc[0] - 1) * 100
    mdd = float((eq / eq.cummax() - 1).min()) * 100
    e1y = eq.tail(253)
    r1y = float(e1y.iloc[-1] / e1y.iloc[0] - 1) * 100
    return round(tot, 2), round(mdd, 2), round(r1y, 2)


CFG = {"S1": dict(n=5, exclude=MB), "S2": dict(n=4, exclude=()),
       "S3": dict(n=4, exclude=()), "S4": dict(n=4, exclude=()),
       "S5": dict(n=4, exclude=MB)}


def run(inp, mode, phase):
    cfg = CFG[mode]
    res = pc.run_strategy(inp, factor="amihud_60", n=cfg["n"], rebal=30, take=1.0,
                          stop=None, stop_exec="next", exclude=cfg["exclude"],
                          capital=50_000.0, lot=100, cost_one_way=None, slip=0.002,
                          run_start="2023-11-10",
                          eval_start=pd.Timestamp("2025-02-13"),
                          eval_end=pd.Timestamp("2026-11-10"),
                          phase=phase, legacy_grid=False, exposure=1.0,
                          full_liquidate=True)
    eq = res.eq.dropna()
    t, m, y = stats(eq)
    row = {"mode": mode, "phase": phase, "total": t, "mdd": m, "r1y": y,
           "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]))}
    if phase == 0:
        row["h2025"] = stats(eq[eq.index <= "2025-12-31"])[0]
        row["h2026"] = stats(eq[eq.index >= "2025-12-31"])[0]
        eq.to_pickle(f"results/r30_bt/fresh5b_{mode}_equity.pkl")
    print(json.dumps(row, ensure_ascii=False), flush=True)
    return row


def main():
    piv = pc.get_inputs().piv
    rows = []
    for mode in ("S1", "S2", "S3", "S4", "S5"):
        inp = F2(piv, mode)
        for ph in (0, 10, 20):
            rows.append(run(inp, mode, ph))
    with open("results/r30_bt/fresh5b.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print("X3 基准: ph0 +640.68/-13.56, 1y +144.16 | 相位中位 +449/-16.5", flush=True)


if __name__ == "__main__":
    main()
