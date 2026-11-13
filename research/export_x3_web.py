#!/usr/bin/env python3
"""导出 X3 (定版 e1.0) 的全部调仓周期数据给网页用:
每期: 买入日/卖出日/股票(代码+名称)/推荐买入价(执行日开盘)/推荐卖出价(平仓日收盘)/
模拟股数/卖出原因; 当前未平仓期另附最新收盘价。输出 results/paper/x3_web_data.json。
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
from paper_track import get_inp, holdings_snapshot

MB = ("688", "689", "300", "301", "8", "4")

res = pc.run_strategy(
    get_inp("x3"), factor="amihud_60", n=4, rebal=30, take=1.0, stop=None,
    stop_exec="next", exclude=MB, capital=50_000.0, lot=100,
    cost_one_way=None, slip=0.002, run_start="2023-11-10",
    eval_start=pd.Timestamp("2025-02-13"), eval_end=pd.Timestamp("2026-11-10"),
    phase=0, legacy_grid=False, exposure=1.0, full_liquidate=True)

uni = pd.read_pickle("data/universe.pkl")
names = dict(zip(uni["code"].astype(str), uni["name"]))

tr = res.trades.copy()
periods = []
for i, (ed, g) in enumerate(sorted(tr.groupby("entry_date"), key=lambda kv: kv[0]), 1):
    positions = []
    for r in g.itertuples():
        positions.append({
            "code": r.code, "name": names.get(r.code, ""),
            "buy_date": str(r.entry_date.date()), "buy_px": round(float(r.entry_px), 3),
            "sell_date": str(r.exit_date.date()), "sell_px": round(float(r.exit_px), 3),
            "shares": int(r.shares), "reason": r.reason,
            "sim_pnl": round(float(r.net_pnl), 0),
        })
    periods.append({"idx": i, "buy_date": str(ed.date()),
                    "sell_date": max(p["sell_date"] for p in positions),
                    "open": False, "positions": positions})

# 当前未平仓期
hs = holdings_snapshot("x3", res)
close = pc.get_inputs().close
last_day = close.index[-1]
positions = []
for p in hs["positions"]:
    c = p["code"]
    positions.append({
        "code": c, "name": names.get(c, ""),
        "buy_date": p["entry_date"], "buy_px": p["entry_px_open"],
        "sell_date": None, "sell_px": None,
        "shares": p["shares_approx"], "reason": "holding",
        "sim_pnl": None, "last_px": round(float(close.at[last_day, c]), 3),
    })
periods.append({"idx": len(periods) + 1, "buy_date": hs["exec_date"],
                "sell_date": None, "open": True, "positions": positions})

eq = res.eq.dropna()
out = {
    "strategy": "X3 定版: Amihud60 / 仅主板 / 市值带2-30% / 精炼跌势门(ret60<-15%且ret10<0剔除) / N4 / R30 / 止盈+100% / 敞口1.0",
    "capital_default": 50000,
    "as_of": str(last_day.date()),
    "sim_total_ret_pct": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
    "sim_mdd_pct": round(float((eq / eq.cummax() - 1).min()) * 100, 2),
    "periods": periods,
}
os.makedirs("results/paper", exist_ok=True)
with open("results/paper/x3_web_data.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f"periods={len(periods)} (open={periods[-1]['open']}) as_of={out['as_of']} "
      f"sim_total={out['sim_total_ret_pct']}% trades={len(tr)}")
for p in periods:
    print(p["idx"], p["buy_date"], "→", p["sell_date"] or "持有中",
          [(x["code"], x["shares"]) for x in p["positions"]])
