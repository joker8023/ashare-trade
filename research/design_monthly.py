#!/usr/bin/env python3
"""月度网格优化 (Kai 定约束: 每月第一个交易日买卖)。
网格: 信号日 = 上月最后交易日, 执行日 = 每月第一个交易日。
杠杆: 队列数 K (每月交易、每队列持有 K 个月, K 袖日历错峰)、N、Amihud 窗口 W;
固定: 市值带 2-30%、精炼门 -15%、TP100、敞口 1.0、主板、5 万总本金、同模拟器成本。
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
from design_r30_grid8 import X3Inputs

MB = ("688", "689", "300", "301", "8", "4")


class MInputs(X3Inputs):
    def __init__(self, piv, band=(0.02, 0.30), gate60=-0.15, min_adv=5e6, w=60):
        super().__init__(piv, band=band, gate60=gate60, min_adv=min_adv)
        if w == 60:
            self.fac_w = self.amihud60
        elif w == 20:
            self.fac_w = self.amihud
        else:
            r = self.close.pct_change(fill_method=None).abs()
            amt = self.amount.replace(0, np.nan)
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


def stats(eq):
    eq = eq.dropna()
    tot = float(eq.iloc[-1] / eq.iloc[0] - 1) * 100
    mdd = float((eq / eq.cummax() - 1).min()) * 100
    e1y = eq.tail(253)
    r1y = float(e1y.iloc[-1] / e1y.iloc[0] - 1) * 100
    return round(tot, 2), round(mdd, 2), round(r1y, 2)


def run_cfg(sig_all, inp, K, n, tag):
    cap = 50_000.0 / K
    eqs, trades, cost = [], 0, 0.0
    for k in range(K):
        sub = sig_all[k::K]
        inp.grid = (lambda s: (lambda rebal, phase=0, legacy=False: list(s)))(sub)
        res = pc.run_strategy(inp, factor="amihud_60", n=n, rebal=30, take=1.0,
                              stop=None, stop_exec="next", exclude=MB,
                              capital=cap, lot=100, cost_one_way=None, slip=0.002,
                              run_start="2023-11-10",
                              eval_start=pd.Timestamp("2025-02-13"),
                              eval_end=pd.Timestamp("2026-11-10"),
                              phase=0, legacy_grid=False, exposure=1.0,
                              full_liquidate=True)
        eqs.append(res.eq.dropna())
        trades += len(res.trades)
        cost += float(res.meta.get("total_cost", 0.0))
    idx = eqs[0].index
    for e in eqs[1:]:
        idx = idx.union(e.index)
    comb = None
    for e in eqs:
        s = e.reindex(idx).ffill()
        s[s.index < e.index[0]] = cap
        comb = s if comb is None else comb + s
    t, m, y = stats(comb)
    row = {"tag": tag, "total": t, "mdd": m, "r1y": y, "trades": trades, "cost": round(cost)}
    print(json.dumps(row, ensure_ascii=False), flush=True)
    comb.to_pickle(f"results/r30_bt/monthly_{tag}_equity.pkl")
    return row


def main():
    base = pc.get_inputs()
    dates = base.dates
    first_td = {}
    for i, d in enumerate(dates):
        first_td.setdefault((d.year, d.month), i)
    sig_all = sorted(i - 1 for i in first_td.values() if i - 1 >= 300)
    print(f"月度信号 {len(sig_all)} 个, 首个 {dates[sig_all[0]].date()}", flush=True)

    # 同窗基准: X3 R30 phase0 / 基线, 自 2025-02-28 起
    for name, path in (("X3_R30_ph0", "results/r30_bt/phase_audit/x3_ph0.pkl"),
                       ("baseline", "results/r30_bt/n4_tp45_e09_equity.pkl")):
        eq = pd.read_pickle(path).dropna()
        eq = eq[eq.index >= pd.Timestamp("2025-02-28")]
        print(f"同窗基准 {name}: {stats(eq)}", flush=True)

    rows = []
    for K in (1, 2, 3):
        for n in (4, 6):
            for w in (20, 60, 120):
                inp = MInputs(base.piv, w=w)
                rows.append(run_cfg(sig_all, inp, K, n, f"K{K}_N{n}_W{w}"))
    rows.sort(key=lambda r: -r["total"])
    print("\n=== Stage1 TOP5 (按全程收益) ===", flush=True)
    for r in rows[:5]:
        print(json.dumps(r, ensure_ascii=False), flush=True)
    with open("results/r30_bt/monthly_stage1.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
