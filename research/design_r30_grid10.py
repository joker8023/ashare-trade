#!/usr/bin/env python3
"""phase 敏感性量化 + 错峰多袖组合 (X3 定版: gate15/TP100/e1.0/带2-30/主板/N4/R30)。
跑全部 30 个 phase 的独立 5 万模拟, 输出收益/回撤分布;
再把若干 phase 的净值等权合成「多袖组合」, 看 phase 抽签被平均掉之后的收益/回撤。
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
OUT = "results/r30_bt/phase_audit"
os.makedirs(OUT, exist_ok=True)


def stats(eq):
    eq = eq.dropna()
    tot = float(eq.iloc[-1] / eq.iloc[0] - 1) * 100
    mdd = float((eq / eq.cummax() - 1).min()) * 100
    e1y = eq.tail(253)
    r1y = float(e1y.iloc[-1] / e1y.iloc[0] - 1) * 100
    return tot, mdd, r1y


def main():
    inp = X3Inputs(pc.get_inputs().piv, gate60=-0.15)
    rows, eqs = [], {}
    for ph in range(30):
        res = pc.run_strategy(inp, factor="amihud_60", n=4, rebal=30, take=1.0,
                              stop=None, stop_exec="next", exclude=MB,
                              capital=50_000.0, lot=100, cost_one_way=None, slip=0.002,
                              run_start="2023-11-10",
                              eval_start=pd.Timestamp("2025-02-13"),
                              eval_end=pd.Timestamp("2026-11-10"),
                              phase=ph, legacy_grid=False, exposure=1.0,
                              full_liquidate=True)
        eq = res.eq.dropna()
        eqs[ph] = eq
        eq.to_pickle(f"{OUT}/x3_ph{ph}.pkl")
        t, m, y = stats(eq)
        rows.append({"phase": ph, "total": round(t, 2), "mdd": round(m, 2), "r1y": round(y, 2)})
        print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    print("\n=== 单 phase 分布 (30 个调仓相位) ===")
    for col in ("total", "mdd", "r1y"):
        s = df[col]
        print(f"{col}: 均值 {s.mean():.1f} 中位 {s.median():.1f} 最差 {s.min():.1f} 最好 {s.max():.1f} 标准差 {s.std():.1f}")
    print(f"收益为正的 phase: {(df.total > 0).sum()}/30 | 跑赢基线收益 +325 的: {(df.total > 325.32).sum()}/30 "
          f"| 回撤优于基线 -15.33 的: {(df.mdd > -15.33).sum()}/30 | 双超基线: {((df.total > 325.32) & (df.mdd > -15.33)).sum()}/30")

    print("\n=== 多袖错峰组合 (等权合成, 每袖独立 5 万) ===")
    combos = {"2袖 0/15": [0, 15], "3袖 0/10/20": [0, 10, 20],
              "5袖 0/6/12/18/24": [0, 6, 12, 18, 24], "全30袖平均": list(range(30))}
    out = {}
    for name, phs in combos.items():
        comb = sum(eqs[p] for p in phs) / len(phs)
        t, m, y = stats(comb)
        out[name] = {"total": round(t, 2), "mdd": round(m, 2), "r1y": round(y, 2)}
        print(f"{name}: 全程 {t:+.2f}% 回撤 {m:.2f}% 1y {y:+.2f}%")
    with open(f"{OUT}/x3_phase_audit.json", "w", encoding="utf-8") as f:
        json.dump({"per_phase": rows, "combos": out}, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
