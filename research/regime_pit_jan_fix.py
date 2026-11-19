#!/usr/bin/env python3
"""J1 FIX runner: 消融 + sweep + placebo + parity (可交易化).
输出: results/r30_bt/REG3_pit_jan_fix.json
"""
import sys, json, gc
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, WINDOWS, RUN_START, EVAL_END, MB
from _fix_builder import build_ns3_fixed
import pickle as pk

print("RUN_START", RUN_START, "EVAL_END", EVAL_END, flush=True)
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
CA0 = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
CFG_A = dict(n=5, rebal=20, take=1.2, exposure=1.0)
CFG_B = dict(n=4, rebal=30, take=0.8, exposure=0.9)
mkA = MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=40)
mkB = MaxInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.80, max_win=20)
mkC = MaxInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.80, max_win=20)

_SH = {}
def shadow_of(mk, cfg, stop, tag):
    key = (tag, tuple(sorted(cfg.items())), stop)
    if key not in _SH:
        CA = dict(CA0); CA["stop"] = stop
        r = pc.run_strategy(mk, phase=0, **{**CA, **cfg})
        _SH[key] = (r.eq.iloc[:,0] if isinstance(r.eq, pd.DataFrame) else r.eq, r)
        print("  shadow %s exp=%s stop=%s trades=%d" % (tag, cfg.get("exposure"), stop, len(r.trades)), flush=True)
        del r; gc.collect()
    return _SH[key][0]

print("building shadows...", flush=True)
sha = shadow_of(mkA, CFG_A, 0.25, "A")
shb = shadow_of(mkB, CFG_B, 0.25, "B")
CFG_C0 = dict(n=4, rebal=30, take=0.8, exposure=0.3)
shc = shadow_of(mkC, CFG_C0, 0.25, "C0")

combo = pk.load(open(ROOT/"results"/"r30_bt"/"combo_w70_equity.pkl","rb"))
if isinstance(combo, pd.DataFrame): combo = combo.iloc[:,0]
combo = combo.dropna()
combo_windows = {}
for w,d in WINDOWS.items():
    sub = combo.tail(d+1)
    combo_windows[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
combo_mdd = round(float(_mdd(combo))*100,2)
combo_total = round(float(combo.iloc[-1]/combo.iloc[0]-1)*100,2)
print("combo total=%s mdd=%s" % (combo_total, combo_mdd), flush=True)

def run_one(tag, jan_month, jan_mult, force_from, extra=None):
    ns = build_ns3_fixed(confirm=2, min_hold=0, jan_month=jan_month, jan_mult=jan_mult, _tag=tag)
    KW = dict(n=CFG_A["n"], rebal=CFG_A["rebal"], take=CFG_A["take"], exposure=CFG_A["exposure"],
              phase=0, inp_b=mkB, cfg_b=CFG_B, inp_c=mkC, cfg_c=dict(CFG_C0),
              shadow_a=sha, shadow_b=shb, shadow_c=shc, rs_lookback=60,
              exclude_a=MB, exclude_b=MB, exclude_c=MB, evalfreq="grid", brake_daily=False,
              force_c_from=force_from, gap_s=None, gap_cut=None, gap_thr=None,
              fuse_ms=None, fuse_mult=0.5, stop_c=0.25, stop_b=None,
              **{k:v for k,v in CA0.items() if k != "exclude"})
    res = ns["run_strategy_switch"](mkA, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2),
           "mdd": round(float(_mdd(eq))*100,2), "trades": int(len(res.trades)),
           "cost": round(float(res.meta["total_cost"]),0), "mode": res.meta["final_mode"],
           "switches": len(res.meta["switch_log"]), "switch_log": [list(x) for x in res.meta["switch_log"]],
           "brakes": len(res.meta.get("brake_log",[])),
           "jan_month": jan_month, "jan_mult": jan_mult,
           "force": None if force_from is None else str(force_from.date())}
    for w,d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
        out[w+"_mdd"] = round(float(_mdd(sub))*100,2)
    for y in [2023,2024,2025,2026]:
        m = eq[eq.index.year==y]
        if len(m)>1: out["ann_"+str(y)] = round(float(m.iloc[-1]/m.iloc[0]-1)*100,2)
    # 1月归因: 当年1月段收益 (持仓 month==1 的权益子序列近似用 eq 年月切片)
    for y in [2023,2024,2025,2026]:
        m = eq[(eq.index.year==y)&(eq.index.month==1)]
        if len(m)>1: out["jan_"+str(y)] = round(float(m.iloc[-1]/m.iloc[0]-1)*100,2)
    out["vs_combo"] = {w: round(out[w]-combo_windows[w],2) for w in WINDOWS}
    out["excess_total"] = round(out["total"]-combo_total,2)
    out["mdd_gap"] = round(out["mdd"]-combo_mdd,2)
    out["nbeat"] = int(sum(1 for w in WINDOWS if out[w] > combo_windows[w]))
    out["six_win"] = bool(out["nbeat"]==6)
    out["full_win"] = bool(out["six_win"] and out["mdd"]>combo_mdd and out["total"]>combo_total)
    if extra: out.update(extra)
    return out, eq, res

rows = []
eqs = {}

# --- ABLATION ---
print("== ABLATION ==", flush=True)
for tag, jm, jx, force in [
    ("A0_Q4_nolock", None, 1.0, None),
    ("A1_Q4_lock0908", None, 1.0, pd.Timestamp("2026-09-08")),
    ("B0_J1FIX_nolock_j05", 1, 0.5, None),
    ("B1_J1_lock_j05", 1, 0.5, pd.Timestamp("2026-09-08")),
]:
    out, eq, res = run_one(tag, jm, jx, force)
    rows.append(out); eqs[tag]=eq
    print("%s total=%s mdd=%s nbeat=%d full=%s switches=%s mode=%s" % (tag, out["total"], out["mdd"], out["nbeat"], out["full_win"], out["switches"], out["mode"]), flush=True)

# --- SWEEP jan_mult (全 nolock, 可交易) ---
print("== SWEEP jan_mult ==", flush=True)
for jx in [0.0, 0.3, 0.5, 0.7, 1.0]:
    tag = "S_jan%.1f_nolock" % jx
    if tag in eqs: continue
    out, eq, res = run_one(tag, 1, jx, None)
    rows.append(out); eqs[tag]=eq
    print("%s total=%s mdd=%s nbeat=%d full=%s jan24=%s jan25=%s jan26=%s" % (tag, out["total"], out["mdd"], out["nbeat"], out["full_win"], out.get("jan_2024"), out.get("jan_2025"), out.get("jan_2026")), flush=True)

# --- PLACEBO Feb ---
print("== PLACEBO ==", flush=True)
out, eq, res = run_one("P_feb05_nolock", 2, 0.5, None)
rows.append(out); eqs["P_feb05_nolock"]=eq
print("P_feb05 total=%s mdd=%s nbeat=%d full=%s" % (out["total"], out["mdd"], out["nbeat"], out["full_win"]), flush=True)

# --- PARITY ---
print("== PARITY ==", flush=True)
# parity1: jan_mult=1.0 == jan_month=None (无补丁)
_, eq_none, _ = run_one("parity_none", None, 1.0, None)
_, eq_one, _ = run_one("parity_one", 1, 1.0, None)
import numpy as np
par1 = bool(np.allclose(eq_none.values, eq_one.values))
print("parity jan1.0==none: %s maxdiff=%s" % (par1, float(np.max(np.abs(eq_none.values-eq_one.values)))), flush=True)
# parity2: A0 vs A1 (锁冗余?) — 若path相同则equity应相同
par2 = bool(np.allclose(eqs["A0_Q4_nolock"].values, eqs["A1_Q4_lock0908"].values))
print("parity nolock==lock(Q4): %s" % par2, flush=True)
par3 = bool(np.allclose(eqs["B0_J1FIX_nolock_j05"].values, eqs["B1_J1_lock_j05"].values))
print("parity nolock==lock(J1): %s" % par3, flush=True)

open(ROOT/"results"/"r30_bt"/"REG3_pit_jan_fix.json","w").write(json.dumps(
    {"combo": {"total": combo_total, "mdd": combo_mdd, "windows": combo_windows},
     "parity": {"jan1_eq_none": par1, "q4_lock_redundant": par2, "j1_lock_redundant": par3},
     "rows": rows}, ensure_ascii=False, indent=1))
print("SAVED REG3_pit_jan_fix.json", flush=True)
# 推荐可交易解: B0
b0 = [r for r in rows if r["tag"]=="B0_J1FIX_nolock_j05"][0]
eqs["B0_J1FIX_nolock_j05"].to_pickle(ROOT/"results"/"r30_bt"/"REG3_J1FIX_nolock_equity.pkl")
print("RECOMMEND B0_J1FIX total=%s mdd=%s nbeat=%d full=%s" % (b0["total"], b0["mdd"], b0["nbeat"], b0["full_win"]), flush=True)
print("FOLLOW: 冻结参数, 2026-11-12后留白跟踪; 实盘去掉force_c_from, 下次信号2026-12-09/执行2026-12-10, C腿预期.", flush=True)
