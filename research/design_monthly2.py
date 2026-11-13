#!/usr/bin/env python3
"""月度网格优化 Stage2: 定位月末锚点问题 + 信号滞后挽救。
- 诊断A: 月中网格 (每月第 11 个交易日执行) 同参数对照 — 若它恢复 R30 水平, 病根是月末锚点。
- 挽救B: 执行日仍为每月第一个交易日, 但选股信息滞后 lag 个交易日 (绕开月末最后几天的因子污染)。
- 参数C: 在 1 号网格上试 band/gate/TP/min_adv 变体 (以 K2_N6_W60 与 K1_N4_W60 为基)。
"""
import json
import os
import sys

ROOT = os.path.expanduser("~/workspace/ashare-trade")
sys.path.insert(0, os.path.join(ROOT, "team", "audit"))
sys.path.insert(0, os.path.expanduser("~/workspace/tools"))
os.chdir(ROOT)

import pandas as pd

import prior_check as pc
from design_monthly import MInputs, run_cfg, MB


class LagInputs(MInputs):
    """picks 在 t 评估, 但因子/门/市值全部取 t-lag 个交易日的数据 (执行仍在 t+1)。"""

    def __init__(self, *a, lag=0, **kw):
        super().__init__(*a, **kw)
        self.lag = lag

    def picks(self, t, n, size_range=None, min_adv=None, exclude=(), factor="amihud_60"):
        if self.lag == 0:
            return super().picks(t, n, size_range, min_adv, exclude, factor)
        idx = self.close.index
        pos = idx.get_loc(t)
        if pos < self.lag:
            return []
        t2 = idx[pos - self.lag]
        return MInputs.picks(self, t2, n, size_range, min_adv, exclude, factor)


def monthly_sigs(dates, exec_pos):
    """exec_pos: 每月第几个交易日为执行日 (0=第一个)。返回信号日索引列表。"""
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


def main():
    base = pc.get_inputs()
    dates = base.dates
    sig_first = monthly_sigs(dates, 0)
    sig_mid = monthly_sigs(dates, 10)
    rows = []

    # 诊断A: 月中执行 (第 11 个交易日), K1 N4 W60 基线参数
    inp = MInputs(base.piv, w=60)
    rows.append(run_cfg(sig_mid, inp, 1, 4, "DIAG_midmonth_K1_N4_W60"))

    # 挽救B: 1 号执行 + 信号滞后
    for lag in (2, 3, 5):
        for K, n in ((1, 4), (2, 6)):
            inp = LagInputs(base.piv, w=60, lag=lag)
            rows.append(run_cfg(sig_first, inp, K, n, f"LAG{lag}_K{K}_N{n}_W60"))

    # 参数C: 1 号网格变体
    inp = MInputs(base.piv, w=60, band=(0.05, 0.30))
    rows.append(run_cfg(sig_first, inp, 2, 6, "C_band0530_K2_N6"))
    inp = MInputs(base.piv, w=60, band=(0.02, 0.50))
    rows.append(run_cfg(sig_first, inp, 2, 6, "C_band0250_K2_N6"))
    inp = MInputs(base.piv, w=60, gate60=-1.0)
    rows.append(run_cfg(sig_first, inp, 2, 6, "C_nogate_K2_N6"))
    inp = MInputs(base.piv, w=60, min_adv=1e7)
    rows.append(run_cfg(sig_first, inp, 2, 6, "C_adv10m_K2_N6"))

    rows.sort(key=lambda r: -r["total"])
    print("\n=== Stage2 全部 (按收益) ===", flush=True)
    for r in rows:
        print(json.dumps(r, ensure_ascii=False), flush=True)
    with open("results/r30_bt/monthly_stage2.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
