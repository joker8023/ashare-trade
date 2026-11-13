#!/usr/bin/env python3
"""诊断: X1 为何近 3 个月 (最后 63 个交易日) 收益 (+6.08%) 低于基线 (+11.60%)。
拆: 窗口起止日、逐调仓段净值收益 (X1 vs 基线)、每段选股差异、个股段内涨幅、中证1000 同期。
"""
import os
import sys

ROOT = os.path.expanduser("~/workspace/ashare-trade")
sys.path.insert(0, os.path.join(ROOT, "team", "audit"))
sys.path.insert(0, os.path.expanduser("~/workspace/tools"))
os.chdir(ROOT)

import pandas as pd

import prior_check as pc
from design_r30_grid5 import XInputs

eq_x1 = pd.read_pickle("results/r30_bt/design_X1_band0230_gate20_tp100_e09_equity.pkl")
eq_bs = pd.read_pickle("results/r30_bt/n4_tp45_e09_equity.pkl")
w = eq_x1.tail(64)
print(f"3m 窗口: {w.index[0].date()} ~ {w.index[-1].date()} ({len(w)-1} 个交易日)")
print(f"X1 {float(w.iloc[-1]/w.iloc[0]-1)*100:+.2f}% | 基线 "
      f"{float(eq_bs.loc[w.index[0]:].iloc[-1]/eq_bs.loc[w.index[0]:].iloc[0]-1)*100:+.2f}%")

# 中证1000 同期
try:
    idx = pd.read_pickle("results/_cache/index_000852.pkl")
    s = idx.loc[w.index[0]:w.index[-1], "close"]
    print(f"中证1000 同期: {float(s.iloc[-1]/s.iloc[0]-1)*100:+.2f}%  "
          f"窗口内最大回撤 {float((s/s.cummax()-1).min())*100:.2f}%")
except Exception as e:
    print("index cache:", e)

# 调仓段边界: 信号日 idx 300 起每 30 日, 执行日 +1
close = pc.get_inputs().close
dates = close.index
sig = list(range(300, len(dates) - 1, 30))
bounds = [dates[i + 1] for i in sig] + [dates[-1]]
print("\n逐段净值收益 (执行日 → 下个执行日):")
for a, b in zip(bounds[-5:], bounds[-4:] + [bounds[-1]]):
    if a >= w.index[0] or b >= w.index[0]:
        rx = float(eq_x1.loc[a:b].iloc[-1] / eq_x1.loc[a:b].iloc[0] - 1) * 100
        rb = float(eq_bs.loc[a:b].iloc[-1] / eq_bs.loc[a:b].iloc[0] - 1) * 100
        print(f"  {a.date()} → {b.date()}: X1 {rx:+.2f}% | 基线 {rb:+.2f}%")

# 窗口内各段选股对比
inp = pc.get_inputs()
x = XInputs(inp.piv)
x._gate = -0.20
x._sr = (0.02, 0.30)
print("\n窗口内信号日选股 (执行日次日开盘买入, 段内涨幅 = 执行日→段末收盘):")
for i in sig:
    sd, ed = dates[i], dates[i + 1]
    if ed < w.index[0]:
        continue
    end_i = min(i + 31, len(dates) - 1)
    end = dates[end_i]
    px1 = x.picks(sd, 4, exclude=("688", "689", "300", "301", "8", "4"), factor="amihud_60")
    pb = inp.picks(sd, 4, exclude=("688", "689", "300", "301", "8", "4"), factor="amihud_60")

    def seg_ret(codes):
        out = []
        for c in codes:
            try:
                r = float(close.at[end, c] / close.at[ed, c] - 1) * 100
                out.append(f"{c}({r:+.0f}%)")
            except Exception:
                out.append(f"{c}(?)")
        return " ".join(out)

    print(f"  信号日 {sd.date()} 执行 {ed.date()} → {end.date()}")
    print(f"    X1 : {seg_ret(px1)}")
    print(f"    基线: {seg_ret(pb)}")

# 门/带到底剔掉了谁: 基线入选但 X1 没入选的, 看其信号日 ret60
print("\n被 X1 剔除的基线股 (信号日 ret60):")
for i in sig:
    sd, ed = dates[i], dates[i + 1]
    if ed < w.index[0]:
        continue
    pb = set(inp.picks(sd, 4, exclude=("688", "689", "300", "301", "8", "4"), factor="amihud_60"))
    px1 = set(x.picks(sd, 4, exclude=("688", "689", "300", "301", "8", "4"), factor="amihud_60"))
    for c in pb - px1:
        r60 = float(x.ret60.at[sd, c]) * 100 if c in x.ret60.columns else float("nan")
        cap_pct = float((inp.cap.loc[sd] <= inp.cap.at[sd, c]).mean()) * 100
        print(f"  {sd.date()} {c}: ret60={r60:+.1f}% 市值分位={cap_pct:.0f}%")
