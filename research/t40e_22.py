#!/usr/bin/env python3
"""T40E22: 补T40策略2022缺口 (58.12 -> 60) 的25组内搜索.

基座 = research/t40_trail6.py 的 T40_asym00508 (三腿switch):
  A=c_a60_vol(n=3,rebal=30,take=0.8) B=c_a60_turn(n=6,rebal=30,take=0.8)
  C=amihud_5(n=4,rebal=30,take=0.8), rs_lookback=90, grid评估,
  build_ns3(bx=0.12, by=0.05, bf=0.4, hyst=0.02, min_hold=0, confirm=1,
            hyst_a=0.005, hyst_b=0.005, hyst_c=0.08).
公共口径 (与基座一致, 只用t及以前数据, engine保证无未来函数):
  long-only, 敞口<=1, MB剔除, slip=0.002, lot=100, stop=0.25 next,
  full_liquidate=True. 数据: data/pivots_2020_clean_realshares_v2.pkl (只读).

搜索 (单腿影子复用; switch回测共25组 = 24探索 + 1验证):
  stage1 switch-only, 复用基座三影子 (12组):
    T40_base(复现) ha0 ha10 ha20 hb0 hb10 hb20 hc05 hc12 rs60 rs120 ha10hb10hc05rs60
  stage2a 腿变体 (新影子A2/A4/A3t10/B4/B8, 复用其余腿) + 刹车bx (7组):
    legA2 legA4 legA3t10 legB4 legB8 bx010 bx015
  stage3 ha20组合 (5组):
    ha20_A3t10 ha20_rs60 ha20_B8 ha20_A4 ha20_A3t10_rs60
  verify (1组): T40E22_ha20 (与ha20同配置, 可复现校验)

结论: 最佳候选 T40E22_ha20 (仅 hyst_a 0.005->0.02):
  2022=70.26达标, 但2023=49.57未达标 -> 未晋级 (5/6).

用法:
  .venv/bin/python research/t40e_22.py --only T40E22_ha20   # 默认: 仅验证推荐配置 (1组switch + 3影子)
  .venv/bin/python research/t40e_22.py --full               # 全网格复现 (24组switch + 8影子), 写 results/r30_bt/t40e_22.json
"""
import sys, json, gc, argparse
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import _mdd, EVAL_END, MB
from switch_ns3 import build_ns3

piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
RUN_START = str(dates[0].date())
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
print(f"RUN_START={RUN_START} first_sig={first_sig.date()} EVAL_END={EVAL_END} bars={len(dates)}", flush=True)

CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
WINDOWS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}
YEARS = [2021,2022,2023,2024,2025,2026]
DEF_A3 = dict(n=3, rebal=30, take=0.8, exposure=1.0)
DEF_B6 = dict(n=6, rebal=30, take=0.8, exposure=1.0)
DEF_C4 = dict(n=4, rebal=30, take=0.8, exposure=1.0)

def make_inp(sel):
    return DInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.70, max_win=20, sel=sel)

_sh = {}
def shadow(sel, cfg):
    key = (sel, tuple(sorted(cfg.items())))
    if key not in _sh:
        rb = pc.run_strategy(make_inp(sel), phase=0, **{**CA, **cfg})
        _sh[key] = (rb.eq.iloc[:,0] if isinstance(rb.eq, pd.DataFrame) else rb.eq, len(rb.trades))
        print(f"  shadow {sel} {cfg} trades={len(rb.trades)}", flush=True)
        del rb; gc.collect()
    return _sh[key]

# tag -> (Asel, Acfg, Bsel, Bcfg, rs, ha, hb, hc, bx)
GRID = {
 "T40_base":             ("c_a60_vol", DEF_A3, "c_a60_turn", DEF_B6, 90, 0.005, 0.005, 0.08, 0.12),
 "T40E22_ha0":           ("c_a60_vol", DEF_A3, "c_a60_turn", DEF_B6, 90, 0.0,   0.005, 0.08, 0.12),
 "T40E22_ha10":          ("c_a60_vol", DEF_A3, "c_a60_turn", DEF_B6, 90, 0.01,  0.005, 0.08, 0.12),
 "T40E22_ha20":          ("c_a60_vol", DEF_A3, "c_a60_turn", DEF_B6, 90, 0.02,  0.005, 0.08, 0.12),
 "T40E22_hb0":           ("c_a60_vol", DEF_A3, "c_a60_turn", DEF_B6, 90, 0.005, 0.0,   0.08, 0.12),
 "T40E22_hb10":          ("c_a60_vol", DEF_A3, "c_a60_turn", DEF_B6, 90, 0.005, 0.01,  0.08, 0.12),
 "T40E22_hb20":          ("c_a60_vol", DEF_A3, "c_a60_turn", DEF_B6, 90, 0.005, 0.02,  0.08, 0.12),
 "T40E22_hc05":          ("c_a60_vol", DEF_A3, "c_a60_turn", DEF_B6, 90, 0.005, 0.005, 0.05, 0.12),
 "T40E22_hc12":          ("c_a60_vol", DEF_A3, "c_a60_turn", DEF_B6, 90, 0.005, 0.005, 0.12, 0.12),
 "T40E22_rs60":          ("c_a60_vol", DEF_A3, "c_a60_turn", DEF_B6, 60, 0.005, 0.005, 0.08, 0.12),
 "T40E22_rs120":         ("c_a60_vol", DEF_A3, "c_a60_turn", DEF_B6,120, 0.005, 0.005, 0.08, 0.12),
 "T40E22_ha10hb10hc05rs60": ("c_a60_vol", DEF_A3, "c_a60_turn", DEF_B6, 60, 0.01, 0.01, 0.05, 0.12),
 "T40E22_legA2":         ("c_a60_vol", dict(n=2,rebal=30,take=0.8,exposure=1.0), "c_a60_turn", DEF_B6, 90, 0.005, 0.005, 0.08, 0.12),
 "T40E22_legA4":         ("c_a60_vol", dict(n=4,rebal=30,take=0.8,exposure=1.0), "c_a60_turn", DEF_B6, 90, 0.005, 0.005, 0.08, 0.12),
 "T40E22_legA3t10":      ("c_a60_vol", dict(n=3,rebal=30,take=1.0,exposure=1.0), "c_a60_turn", DEF_B6, 90, 0.005, 0.005, 0.08, 0.12),
 "T40E22_legB4":         ("c_a60_vol", DEF_A3, "c_a60_turn", dict(n=4,rebal=30,take=0.8,exposure=1.0), 90, 0.005, 0.005, 0.08, 0.12),
 "T40E22_legB8":         ("c_a60_vol", DEF_A3, "c_a60_turn", dict(n=8,rebal=30,take=0.8,exposure=1.0), 90, 0.005, 0.005, 0.08, 0.12),
 "T40E22_bx010":         ("c_a60_vol", DEF_A3, "c_a60_turn", DEF_B6, 90, 0.005, 0.005, 0.08, 0.10),
 "T40E22_bx015":         ("c_a60_vol", DEF_A3, "c_a60_turn", DEF_B6, 90, 0.005, 0.005, 0.08, 0.15),
 "T40E22_ha20_A3t10":    ("c_a60_vol", dict(n=3,rebal=30,take=1.0,exposure=1.0), "c_a60_turn", DEF_B6, 90, 0.02, 0.005, 0.08, 0.12),
 "T40E22_ha20_rs60":     ("c_a60_vol", DEF_A3, "c_a60_turn", DEF_B6, 60, 0.02, 0.005, 0.08, 0.12),
 "T40E22_ha20_B8":       ("c_a60_vol", DEF_A3, "c_a60_turn", dict(n=8,rebal=30,take=0.8,exposure=1.0), 90, 0.02, 0.005, 0.08, 0.12),
 "T40E22_ha20_A4":       ("c_a60_vol", dict(n=4,rebal=30,take=0.8,exposure=1.0), "c_a60_turn", DEF_B6, 90, 0.02, 0.005, 0.08, 0.12),
 "T40E22_ha20_A3t10_rs60": ("c_a60_vol", dict(n=3,rebal=30,take=1.0,exposure=1.0), "c_a60_turn", DEF_B6, 60, 0.02, 0.005, 0.08, 0.12),
}

def run_one(tag, with_log=False):
    Asel, Acfg, Bsel, Bcfg, rs, ha, hb, hc, bx = GRID[tag]
    sha = shadow(Asel, Acfg); shb = shadow(Bsel, Bcfg); shc = shadow("amihud_5", DEF_C4)
    nsT = build_ns3(bx, 0.05, 0.4, 0.02, 0, 1, hyst_a=ha, hyst_b=hb, hyst_c=hc)
    inpA = make_inp(Asel); inpB = make_inp(Bsel)
    KW = dict(n=Acfg["n"], rebal=Acfg["rebal"], take=Acfg["take"], exposure=1.0, phase=0,
              inp_b=inpB, cfg_b=Bcfg, inp_c=make_inp("amihud_5"), cfg_c=DEF_C4,
              shadow_a=sha[0], shadow_b=shb[0], shadow_c=shc[0], rs_lookback=rs,
              exclude_a=MB, exclude_b=MB, exclude_c=MB, evalfreq="grid", brake_daily=False,
              **{k: v for k, v in CA.items() if k != "exclude"})
    res = nsT["run_strategy_switch"](inpA, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "rs": rs, "hyst_a": ha, "hyst_b": hb, "hyst_c": hc, "brake_bx": bx,
           "Acfg": Acfg, "Bcfg": Bcfg,
           "total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2),
           "mdd": round(float(_mdd(eq))*100,2),
           "trades": int(len(res.trades)), "cost": round(float(res.meta["total_cost"]),0),
           "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"])}
    for w, d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
        out[w+"_mdd"] = round(float(_mdd(sub))*100,2)
    for y in YEARS:
        sub = eq[eq.index.year==y]
        if len(sub) > 1:
            out["ann_"+str(y)] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
            out["ann_"+str(y)+"_mdd"] = round(float(_mdd(sub))*100,2)
    if with_log:
        out["switch_log"] = [[str(a), str(b)] for a, b in res.meta["switch_log"]]
    del res, eq, inpA, inpB, KW; gc.collect()
    return out

def check(row):
    c = [("2022>60", row["ann_2022"] > 60), ("2023>60", row["ann_2023"] > 60),
         ("2025>60", row["ann_2025"] > 60), ("2026>60", row["ann_2026"] > 60),
         ("2024>=40", row["ann_2024"] >= 40), ("mdd>-20", row["mdd"] > -20)]
    return c

def leg_attrib():
    print("--- single-leg annual slices (attribution, shadows reused) ---", flush=True)
    for sel, cfg in [("c_a60_vol", DEF_A3), ("c_a60_turn", DEF_B6), ("amihud_5", DEF_C4)]:
        eq, ntr = shadow(sel, cfg)
        s = {y: round(float(eq[eq.index.year==y].iloc[-1]/eq[eq.index.year==y].iloc[0]-1)*100,2) for y in YEARS if len(eq[eq.index.year==y]) > 1}
        print(f"  {sel} {cfg}: {s} trades={ntr}", flush=True)

ap = argparse.ArgumentParser()
ap.add_argument("--full", action="store_true")
ap.add_argument("--only", default="T40E22_ha20")
a = ap.parse_args()
if a.full:
    rows = []
    for tag in GRID:
        r = run_one(tag, with_log=True)
        rows.append(r)
        print(f"DONE {tag}: 2022={r['ann_2022']} 2023={r['ann_2023']} 2024={r['ann_2024']} 2025={r['ann_2025']} 2026={r['ann_2026']} total={r['total']} mdd={r['mdd']} sw={r['switches']}", flush=True)
    open(ROOT/"results"/"r30_bt"/"t40e_22.json","w").write(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f"wrote results/r30_bt/t40e_22.json ({len(rows)} rows)", flush=True)
else:
    r = run_one(a.only, with_log=True)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    leg_attrib()
    print("--- hard-constraint check ---", flush=True)
    for k, ok in check(r):
        print(f"  {k}: {'PASS' if ok else 'FAIL'}", flush=True)
