#!/usr/bin/env python3
"""新 R30 设计第四轮: 组合第三轮的两个正信号 —
市值带下扩 (0.02-0.30) 与动量混合排名 (rk(amihud60)+rk(mom60)),
外加软动量门 (只剔除 60 日跌幅 >10% 的)。
基线: 全程 +325.32 / -15.33, 1y +97.10 / -15.33。
"""
import json
import os
import sys

ROOT = os.path.expanduser("~/workspace/ashare-trade")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "team", "audit"))
os.chdir(ROOT)

import pandas as pd

import engine as E
import prior_check as pc

MB = ("688", "689", "300", "301", "8", "4")
WINDOWS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252}


class XInputs(pc.Inputs):
    def __init__(self, piv):
        super().__init__(piv)
        self._sr = (0.05, 0.30)
        self._fac = {}
        self.ret60 = self.close / self.close.shift(60) - 1.0

    def _score(self, name):
        if name not in self._fac:
            if name == "blend1":
                self._fac[name] = E._rk(E.f_amihud_60(self.piv)) + E._rk(E.f_mom60(self.piv))
            elif name == "blend05":
                self._fac[name] = E._rk(E.f_amihud_60(self.piv)) + 0.5 * E._rk(E.f_mom60(self.piv))
            else:
                raise ValueError(name)
        return self._fac[name]

    def picks(self, t, n, size_range=None, min_adv=5e6, exclude=(), factor="amihud"):
        if t not in self.close.index:
            return []
        sr = self._sr if size_range is None else size_range
        if factor in ("blend1", "blend05"):
            fac = self._score(factor)
        elif factor == "amihud_60":
            fac = self.amihud60
        else:
            fac = self.amihud
        valid = (self.seasoned.loc[t]
                 & (self.adv20.loc[t] > min_adv)
                 & self.close.loc[t].notna()
                 & fac.loc[t].notna())
        if factor == "momgate_soft":
            fac = self.amihud60
            valid &= (self.ret60.loc[t] > -0.10).fillna(False)
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


def run(inp, tag, sr=None, **kw):
    if sr is not None:
        inp._sr = sr
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
    eq.to_pickle(f"results/r30_bt/design_{tag}_equity.pkl")
    res.trades.to_pickle(f"results/r30_bt/design_{tag}_trades.pkl")
    inp._sr = (0.05, 0.30)
    return row


def main():
    x = XInputs(pc.get_inputs().piv)
    rows = []
    rows.append(run(x, "W1_band0230_tpNone_e09", sr=(0.02, 0.30)))
    rows.append(run(x, "W2_band0230_tp45_e09", sr=(0.02, 0.30), take=0.45))
    rows.append(run(x, "W3_band0215_tp45_e09", sr=(0.02, 0.15), take=0.45))
    rows.append(run(x, "B1_blend1_tpNone_e09", factor="blend1"))
    rows.append(run(x, "B2_blend05_tpNone_e09", factor="blend05"))
    rows.append(run(x, "B3_blend1_band0230_tpNone_e09", sr=(0.02, 0.30), factor="blend1"))
    rows.append(run(x, "G1_momgateSoft_tpNone_e09", factor="momgate_soft"))
    rows.append(run(x, "B4_blend05_tp45_e09", factor="blend05", take=0.45))
    with open("results/r30_bt/design_grid4.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print("BASELINE: total +325.32 / mdd -15.33 | 1y +97.10 / -15.33")


if __name__ == "__main__":
    main()
