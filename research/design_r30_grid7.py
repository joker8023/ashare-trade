#!/usr/bin/env python3
"""新 R30 设计第七轮: 诊断结论 — X1 的 ret60>-20% 硬门在 2026-08 段误杀已企稳反弹的
深跌股 (600165 等, ret10 +7~8%), 是 3m 收益落后的全部原因; 而在 09-11 月段它又
正确挡住仍在下跌的 603813 (ret10 -6.5%/-11.5%)。
精炼门 gate_v2: 只剔除「深跌 (ret60<-20%) 且仍在跌」的票。
X1 基准: 全程 +433.03 / -12.63, 1y +104.12, 3m +6.08。
"""
import json
import os
import sys

ROOT = os.path.expanduser("~/workspace/ashare-trade")
sys.path.insert(0, os.path.join(ROOT, "team", "audit"))
os.chdir(ROOT)

import pandas as pd

import prior_check as pc

MB = ("688", "689", "300", "301", "8", "4")
WINDOWS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252}


class X2Inputs(pc.Inputs):
    """X1 配置 (band 0.02-0.30) + 精炼门: mode =
    v1: ret60<-20% 且 ret10<0 剔除 | v2: ret60<-20% 且 ret10<-3% 剔除 |
    v3: ret60<-20% 且 close<MA20 剔除 | hard: 原硬门 ret60<=-20% 剔除 (对照)"""

    def __init__(self, piv, mode="v1"):
        super().__init__(piv)
        self.mode = mode
        self.ret60 = self.close / self.close.shift(60) - 1.0
        self.ret10 = self.close / self.close.shift(10) - 1.0
        self.ma20 = self.close.rolling(20).mean()

    def picks(self, t, n, size_range=None, min_adv=5e6, exclude=(), factor="amihud"):
        if t not in self.close.index:
            return []
        sr = (0.02, 0.30) if size_range is None else size_range
        fac = self.amihud60 if factor == "amihud_60" else self.amihud
        valid = (self.seasoned.loc[t]
                 & (self.adv20.loc[t] > min_adv)
                 & self.close.loc[t].notna()
                 & fac.loc[t].notna())
        deep = self.ret60.loc[t] < -0.20
        if self.mode == "hard":
            valid &= ~deep.fillna(False)
        elif self.mode == "v1":
            valid &= ~(deep & (self.ret10.loc[t] < 0)).fillna(False)
        elif self.mode == "v2":
            valid &= ~(deep & (self.ret10.loc[t] < -0.03)).fillna(False)
        elif self.mode == "v3":
            valid &= ~(deep & (self.close.loc[t] < self.ma20.loc[t])).fillna(False)
        cap_t = self.cap.loc[t]
        lo, hi = cap_t.quantile(sr[0]), cap_t.quantile(sr[1])
        valid &= ((cap_t >= lo) & (cap_t <= hi)).fillna(False)
        if exclude:
            valid &= ~pd.Series(list(valid.index), index=valid.index).str.startswith(exclude)
        return list(fac.loc[t][valid].sort_values(ascending=False).head(n).index)


def win(eq, days):
    sub = eq.tail(days + 1)
    return (round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2),
            round(float((sub / sub.cummax() - 1).min()) * 100, 2))


def run(inp, tag, **kw):
    args = dict(factor="amihud_60", n=4, rebal=30, take=1.0, stop=None,
                stop_exec="next", exclude=MB, capital=50_000.0, lot=100,
                cost_one_way=None, slip=0.002, run_start="2023-11-10",
                eval_start=pd.Timestamp("2025-02-13"),
                eval_end=pd.Timestamp("2026-11-10"),
                phase=0, legacy_grid=False, exposure=0.9, full_liquidate=True)
    args.update(kw)
    res = pc.run_strategy(inp, **args)
    eq = res.eq.dropna()
    tot = round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2)
    mdd = round(float((eq / eq.cummax() - 1).min()) * 100, 2)
    w = {k: win(eq, d) for k, d in WINDOWS.items()}
    row = {"tag": tag, "total": tot, "mdd": mdd,
           "w": {k: {"ret": v[0], "mdd": v[1]} for k, v in w.items()},
           "trades": int(len(res.trades)),
           "cost": round(float(res.meta.get("total_cost", 0.0)), 0)}
    print(json.dumps(row, ensure_ascii=False), flush=True)
    eq.to_pickle(f"results/r30_bt/design_{tag}_equity.pkl")
    res.trades.to_pickle(f"results/r30_bt/design_{tag}_trades.pkl")
    return row


def main():
    piv = pc.get_inputs().piv
    rows = []
    for mode in ("v1", "v2", "v3"):
        rows.append(run(X2Inputs(piv, mode), f"X2_gate{mode}_band0230_tp100_e09"))
    with open("results/r30_bt/design_grid7.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print("X1(硬门): total +433.03 / mdd -12.63 | 1y +104.12 | 3m +6.08")
    print("BASELINE: total +325.32 / mdd -15.33 | 1y +97.10 | 3m +11.60")


if __name__ == "__main__":
    main()
