#!/usr/bin/env python3
"""新 R30 设计第三轮: 更大结构杠杆。
A) full_liquidate=False (仍入选的持仓不卖, 赢家跨段持有)
B) 换选股器 (engine 因子库: triple/quad/amihud60_turnstd/动量门) — 经 XInputs 子类接入模拟器
C) 市值带平移
基线 (均衡型): 全程 +325.32 / -15.33, 1y +97.10 / -15.33。
"""
import json
import os
import sys

ROOT = os.path.expanduser("~/workspace/ashare-trade")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "team", "audit"))
os.chdir(ROOT)

import numpy as np
import pandas as pd

import engine as E
import prior_check as pc

MB = ("688", "689", "300", "301", "8", "4")
WINDOWS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252}


class XInputs(pc.Inputs):
    """在模拟器 Inputs 上扩展选股器: factor 可选
    amihud / amihud_60 / triple / quad / ami60ts;
    factor='ami60_momgate' = amihud60 排名 + 60日动量>0 的池门。"""

    def __init__(self, piv):
        super().__init__(piv)
        self._sr = (0.05, 0.30)
        self._fac = {}
        self.ret60 = self.close / self.close.shift(60) - 1.0

    def _score(self, name):
        if name not in self._fac:
            fn = {"triple": E.f_triple, "quad": E.f_quad,
                  "ami60ts": E.f_amihud60_turnstd}[name]
            self._fac[name] = fn(self.piv)
        return self._fac[name]

    def picks(self, t, n, size_range=None, min_adv=5e6, exclude=(), factor="amihud"):
        if t not in self.close.index:
            return []
        sr = self._sr if size_range is None else size_range
        if factor in ("triple", "quad", "ami60ts"):
            fac = self._score(factor)
        elif factor == "amihud_60":
            fac = self.amihud60
        else:
            fac = self.amihud
        valid = (self.seasoned.loc[t]
                 & (self.adv20.loc[t] > min_adv)
                 & self.close.loc[t].notna()
                 & fac.loc[t].notna())
        if factor == "ami60_momgate":
            valid &= (self.ret60.loc[t] > 0).fillna(False)
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


def run(inp, tag, save=True, **kw):
    args = dict(factor="amihud_60", n=4, rebal=30, take=None, stop=None,
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
    if save:
        eq.to_pickle(f"results/r30_bt/design_{tag}_equity.pkl")
        res.trades.to_pickle(f"results/r30_bt/design_{tag}_trades.pkl")
    return row


def main():
    base_inp = pc.get_inputs()
    x = XInputs(base_inp.piv)
    print("piv keys:", sorted(base_inp.piv.keys()), flush=True)
    rows = []
    # A) 不全清仓
    rows.append(run(base_inp, "L1_main_tpNone_e09_liqF", full_liquidate=False))
    rows.append(run(base_inp, "L2_main_tpNone_e085_liqF", full_liquidate=False, exposure=0.85))
    rows.append(run(base_inp, "L3_all_tpNone_e09_liqF", full_liquidate=False, exclude=()))
    rows.append(run(base_inp, "L4_main_tp45_e09_liqF", full_liquidate=False, take=0.45))
    rows.append(run(base_inp, "L5_main_tpNone_e100_liqF", full_liquidate=False, exposure=1.0))
    # B) 换选股器
    rows.append(run(x, "T1_triple_main_tpNone_e09", factor="triple"))
    rows.append(run(x, "T2_quad_main_tpNone_e09", factor="quad"))
    rows.append(run(x, "Q1_ami60ts_main_tpNone_e09", factor="ami60ts"))
    rows.append(run(x, "M1_ami60_momgate_main_tpNone_e09", factor="ami60_momgate"))
    # C) 市值带平移
    x._sr = (0.02, 0.15)
    rows.append(run(x, "S1_main_tpNone_e09_band0215"))
    x._sr = (0.10, 0.40)
    rows.append(run(x, "S2_main_tpNone_e09_band1040"))
    x._sr = (0.05, 0.30)
    with open("results/r30_bt/design_grid3.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print("BASELINE: total +325.32 / mdd -15.33 | 1y +97.10 / -15.33")


if __name__ == "__main__":
    main()
