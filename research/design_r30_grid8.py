#!/usr/bin/env python3
"""新 R30 第八轮: X2 的邻域稳定性 + 剩余杠杆排查。
X2 定版: 全程 +464.00 / -12.58, 1y +115.98, 3m +11.74。
测: 门阈值邻域 (-15%/-25%)、带邻域 (0.02-0.25 / 0.02-0.35)、min_adv 提高、
N=3、敞口 0.95、TP70、本金 20 万 (整手效应)、双袖错峰 (phase0+15 各半仓, 治 phase 脆弱)。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 仓库根目录, 路径可移植
sys.path.insert(0, os.path.join(ROOT, "team", "audit"))
os.chdir(ROOT)

import pandas as pd

import prior_check as pc

MB = ("688", "689", "300", "301", "8", "4")
WINDOWS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252}


class X3Inputs(pc.Inputs):
    def __init__(self, piv, band=(0.02, 0.30), gate60=-0.20, min_adv=5e6):
        super().__init__(piv)
        self.band, self.gate60, self.min_adv = band, gate60, min_adv
        self.ret60 = self.close / self.close.shift(60) - 1.0
        self.ret10 = self.close / self.close.shift(10) - 1.0

    def picks(self, t, n, size_range=None, min_adv=None, exclude=(), factor="amihud"):
        if t not in self.close.index:
            return []
        sr = self.band if size_range is None else size_range
        ma = self.min_adv if min_adv is None else min_adv
        fac = self.amihud60 if factor == "amihud_60" else self.amihud
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


def win(eq, days):
    sub = eq.tail(days + 1)
    return (round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2),
            round(float((sub / sub.cummax() - 1).min()) * 100, 2))


def metrics(eq):
    eq = eq.dropna()
    tot = round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2)
    mdd = round(float((eq / eq.cummax() - 1).min()) * 100, 2)
    w = {k: win(eq, d) for k, d in WINDOWS.items()}
    return {"total": tot, "mdd": mdd,
            "w": {k: {"ret": v[0], "mdd": v[1]} for k, v in w.items()}}


def run(inp, tag, save=True, **kw):
    args = dict(factor="amihud_60", n=4, rebal=30, take=1.0, stop=None,
                stop_exec="next", exclude=MB, capital=50_000.0, lot=100,
                cost_one_way=None, slip=0.002, run_start="2023-11-10",
                eval_start=pd.Timestamp("2025-02-13"),
                eval_end=pd.Timestamp("2026-11-10"),
                phase=0, legacy_grid=False, exposure=0.9, full_liquidate=True)
    args.update(kw)
    res = pc.run_strategy(inp, **args)
    row = {"tag": tag, **metrics(res.eq),
           "trades": int(len(res.trades)),
           "cost": round(float(res.meta.get("total_cost", 0.0)), 0)}
    print(json.dumps(row, ensure_ascii=False), flush=True)
    if save:
        res.eq.dropna().to_pickle(f"results/r30_bt/design_{tag}_equity.pkl")
    return row, res


def main():
    piv = pc.get_inputs().piv
    rows = []
    r, _ = run(X3Inputs(piv, gate60=-0.15), "X2_gate15"); rows.append(r)
    r, _ = run(X3Inputs(piv, gate60=-0.25), "X2_gate25"); rows.append(r)
    r, _ = run(X3Inputs(piv, band=(0.02, 0.25)), "X2_band0225"); rows.append(r)
    r, _ = run(X3Inputs(piv, band=(0.02, 0.35)), "X2_band0235"); rows.append(r)
    r, _ = run(X3Inputs(piv, min_adv=1e7), "X2_adv10m"); rows.append(r)
    r, _ = run(X3Inputs(piv), "X2_n3", n=3); rows.append(r)
    r, _ = run(X3Inputs(piv), "X2_e095", exposure=0.95); rows.append(r)
    r, _ = run(X3Inputs(piv), "X2_tp70", take=0.70); rows.append(r)
    r, _ = run(X3Inputs(piv), "X2_cap200k", capital=200_000.0); rows.append(r)
    # 双袖错峰: phase 0 与 15 各 25k, 净值相加
    inp = X3Inputs(piv)
    _, r0 = run(inp, "sleeve_ph0", save=False, capital=25_000.0, phase=0)
    _, r15 = run(inp, "sleeve_ph15", save=False, capital=25_000.0, phase=15)
    eq2 = (r0.eq.dropna() + r15.eq.dropna())
    row = {"tag": "X2_twosleeve_25k+25k", **metrics(eq2), "trades": -1, "cost": -1}
    print(json.dumps(row, ensure_ascii=False), flush=True)
    eq2.to_pickle("results/r30_bt/design_X2_twosleeve_equity.pkl")
    rows.append(row)
    with open("results/r30_bt/design_grid8.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print("X2 定版: total +464.00 / mdd -12.58 | 1y +115.98 / -12.58 | 3m +11.74")


if __name__ == "__main__":
    main()
