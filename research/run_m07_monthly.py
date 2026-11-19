#!/usr/bin/env python3
"""M07 monthly-grid rerun: rebalance on first trading day of each natural month.
M07 legs verbatim except grid: 20/30-trading-day rolling grid -> calendar-month grid.
Signal = first trading day of month, execution t+1 (same convention as frozen).
A: band(0.02,0.30) gate-0.15 MAX40/cut.80 n5 take1.2 exp1.0 stop0.25
B: band(0.05,0.30) gate-1.0 MAX20/cut.80 n4 take0.8 exp0.9 stop0.25
Switch RS60 + brake bx0.18/by0.08/bf0.6 evaluated on monthly grid.
Shares: current pivots_2020_clean.pkl as-is (FLOAT). EVAL_END=2026-11-12.
Output: results/r30_bt/run_m07_monthly.json
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
assert RUN_START=="2023-01-03" and str(EVAL_END)[:10]=="2026-11-12"
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
# monthly signal indices: first trading day of each calendar month, i>=300 warmup
monthly = []
seen = set()
for k, d in enumerate(dates):
    ym = (d.year, d.month)
    if ym not in seen:
        seen.add(ym)
        if k >= 300:
            monthly.append(k)
print(f"monthly signals: {len(monthly)} from {dates[monthly[0]].date()} to {dates[monthly[-1]].date()}", flush=True)
first_sig = next(dates[i] for i in monthly if dates[i] >= pd.Timestamp(RUN_START))
print("first_sig:", first_sig.date(), flush=True)
def monthly_grid(self, rebal=20, phase=0, min_i=300, legacy=False):
    return list(monthly)
inp_a = MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=40)
inp_b = MaxInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.80, max_win=20)
import types
inp_a.grid = types.MethodType(monthly_grid, inp_a)
inp_b.grid = types.MethodType(monthly_grid, inp_b)
CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
CFG_B = dict(n=4, rebal=30, take=0.80, exposure=0.9)
ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=60, exclude_a=MB, exclude_b=MB, **{k:v for k,v in CA.items() if k!="exclude"})
ns = build_ns(0.18, 0.08, 0.6)
res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
eq = eq.dropna()
out = {"strategy":"M07-monthly: M07 legs on calendar-month grid","total":round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2),"mdd":round(_mdd(eq)*100,2),"trades":len(res.trades),"cost":round(float(res.meta["total_cost"]),0),"mode":res.meta["final_mode"],"switches":len(res.meta["switch_log"]),"switch_log":[list(x) for x in res.meta["switch_log"]],"brake_log":[list(x) for x in res.meta.get("brake_log",[])]}
for w,d in WINDOWS.items():
    sub = eq.tail(d+1)
    out[w]=round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
    out[w+"_mdd"]=round(_mdd(sub)*100,2)
tr = res.trades
pnl = tr["net_pnl"].fillna(0)
top3 = pnl.nlargest(3).sum()
out["top3_share"]=round(float(top3/pnl.sum())*100,1)
yrs = {}
for y in [2023,2024,2025,2026]:
    m = eq[eq.index.year==y]
    if len(m)>1: yrs[str(y)]=round(float(m.iloc[-1]/m.iloc[0]-1)*100,2)
out["years"]=yrs
out["n_monthly_signals"]=len(monthly)
print(json.dumps(out, ensure_ascii=False, indent=1), flush=True)
eq.to_pickle(ROOT/"results"/"r30_bt"/"run_m07_monthly_equity.pkl")
open(ROOT/"results"/"r30_bt"/"run_m07_monthly.json","w").write(json.dumps(out, ensure_ascii=False, indent=1))
print("saved run_m07_monthly.json", flush=True)
