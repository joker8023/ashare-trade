#!/usr/bin/env python3
"""五套全新策略 (Kai 指令: 抛开 X3 束缚, 重新实现, 目标超过 X3)。
反过拟合纪律: 每套 = 一个经典因子家族 + 教科书参数, 一次成型不调参;
统一底盘 (R30 网格、N=4、全清仓、无止盈止损、敞口 1.0、真实费率+0.2% 滑点、同模拟器);
放开: 选股逻辑、市值带、板块限制 (全沪深, 仅保留上市≥250日 + 20日均成交额>500万的可交易性底线)。
五套: MOM 中期动量 (涨幅 t-120→t-20) / REV 短期反转 (20日跌幅最大) /
      LVOL 低波动 (60日波动最小) / BRK 新高接近度 (距 120日高点最近) / SIZE 微盘 (流通市值最小)。
每套跑 phase 0/10/20 三个相位 + 分半, 防单点抽奖。
"""
import json
import os
import sys

ROOT = os.path.expanduser("~/workspace/ashare-trade")
sys.path.insert(0, os.path.join(ROOT, "team", "audit"))
os.chdir(ROOT)

import pandas as pd

import prior_check as pc


class FreshInputs(pc.Inputs):
    def __init__(self, piv, mode):
        super().__init__(piv)
        self.mode = mode
        c, r = self.close, self.ret
        self.mom = c.shift(20) / c.shift(120) - 1.0
        self.rev = -(c / c.shift(20) - 1.0)
        self.vol60 = r.rolling(60, min_periods=60).std()
        self.hi120 = c / c.rolling(120, min_periods=120).max()

    def _score(self, t):
        if self.mode == "MOM":
            return self.mom.loc[t]
        if self.mode == "REV":
            return self.rev.loc[t]
        if self.mode == "LVOL":
            return -self.vol60.loc[t]
        if self.mode == "BRK":
            return self.hi120.loc[t]
        return -self.cap.loc[t]  # SIZE

    def picks(self, t, n, size_range=None, min_adv=None, exclude=(), factor="amihud"):
        if t not in self.close.index:
            return []
        s = self._score(t)
        valid = (self.seasoned.loc[t] & (self.adv20.loc[t] > 5e6)
                 & self.close.loc[t].notna() & s.notna())
        return list(s[valid].sort_values(ascending=False).head(n).index)


def stats(eq):
    eq = eq.dropna()
    tot = float(eq.iloc[-1] / eq.iloc[0] - 1) * 100
    mdd = float((eq / eq.cummax() - 1).min()) * 100
    e1y = eq.tail(253)
    r1y = float(e1y.iloc[-1] / e1y.iloc[0] - 1) * 100
    return round(tot, 2), round(mdd, 2), round(r1y, 2)


def run(inp, mode, phase):
    res = pc.run_strategy(inp, factor="amihud", n=4, rebal=30, take=None, stop=None,
                          stop_exec="next", exclude=(), capital=50_000.0, lot=100,
                          cost_one_way=None, slip=0.002, run_start="2023-11-10",
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
        eq.to_pickle(f"results/r30_bt/fresh5_{mode}_equity.pkl")
    print(json.dumps(row, ensure_ascii=False), flush=True)
    return row


def main():
    piv = pc.get_inputs().piv
    rows = []
    for mode in ("MOM", "REV", "LVOL", "BRK", "SIZE"):
        inp = FreshInputs(piv, mode)
        for ph in (0, 10, 20):
            rows.append(run(inp, mode, ph))
    with open("results/r30_bt/fresh5.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print("X3 基准: ph0 +640.68/-13.56 | 相位中位 +449/-16.5", flush=True)


if __name__ == "__main__":
    main()
