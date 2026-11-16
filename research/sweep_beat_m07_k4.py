"""K4: 家族变量 (无阈值微调). Baseline = M07 final (ph0).
口径除 phase / R(rebal) 外与 research/run_m07_final.py 逐字一致:
  5万 / 现实费率(cost_one_way=None) / slip=0.002 / 整手lot=100 /
  RUN_START / EVAL_END / WINDOWS; brake rs=60 默认.
M07: A leg band=(0.02,0.30) gate60=-0.15 cut=0.80 win=40 take=1.2 n=5 rebal=20 exp=1.0;
     B leg band=(0.05,0.30) gate60=-1.0 cut=0.80 win=20 take=0.8 n=4 rebal=30 exp=0.9;
     stop=0.25 stop_exec=next; brake bx=0.18/by=0.08/bf=0.6.
g_bf07     = M07 + by=0.05 + cut双腿0.78 + bx=0.15 + bf=0.7 (K3 g_bf07).
g_bx15      = M07 + by=0.05 + cut双腿0.78 + bx=0.15 (bf=0.6, K2 g).
双袖/三袖方法同 research/dual_phase.py: 仅 phase 不同, 其余逐字一致;
  sleeve equity = 各腿净值等权平均 (inner对齐后mean, 起点5万, 与dual_phase.py一致);
  sleeve 六窗/mdd/total 同口径由平均净值计算, 与 M07 ph0 六窗严格>对比.
  sleeve 行 trades = 各腿之和, cost = 各腿均值(平均净值经济口径), switches/brakes = 各腿之和;
  mode = SLEEVE, 各腿明细见 legs[].
判定: 严格>对比 M07 ph0 六窗; win_all = beat_all and mdd > -27.05.
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB

M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05, "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
M07_SWITCH = [["2023-06-21", "B"], ["2024-08-15", "A"], ["2026-09-08", "B"]]

piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))

M07P = dict(cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, stop=0.25,
            a_take=1.2, b_take=0.80, a_n=5, b_n=4, b_exp=0.9,
            rs=60, bx=0.18, by_=0.08, bf=0.6, a_rebal=20, b_rebal=30)
G_BF07 = dict(M07P, by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.7)
G_BX15 = dict(M07P, by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15)

_shadow_cache = {}
_ns_cache = {}

def get_ns(bx, by, bf):
    k = (bx, by, bf)
    if k not in _ns_cache:
        _ns_cache[k] = build_ns(bx, by, bf)
    return _ns_cache[k]

def run_leg(params, phase):
    """单相位完整 M07-switch 腿: shadows 与 switch 均用同一 phase, 其余逐字一致."""
    key = (tuple(sorted(params.items())), phase)
    if key in _shadow_cache:
        return _shadow_cache[key]
    p = params
    inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=p["cut_a"], max_win=p["win_a"])
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=p["cut_b"], max_win=p["win_b"])
    CA = dict(factor="amihud_60", stop=p["stop"], stop_exec="next", exclude=MB, capital=50000.0,
              lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
              eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=p["b_n"], rebal=p["b_rebal"], take=p["b_take"], exposure=p["b_exp"])
    ra = pc.run_strategy(inp_a, n=p["a_n"], rebal=p["a_rebal"], take=p["a_take"],
                         exposure=1.0, phase=phase, **CA)
    rb = pc.run_strategy(inp_b, phase=phase, **{**CA, **CFG_B})
    KW = dict(n=p["a_n"], rebal=p["a_rebal"], take=p["a_take"], exposure=1.0, phase=phase,
              inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=p["rs"],
              exclude_a=MB, exclude_b=MB, **{k: v for k, v in CA.items() if k != "exclude"})
    ns = get_ns(p["bx"], p["by_"], p["bf"])
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    _shadow_cache[key] = (eq, res)
    return eq, res

def stats_of(eq):
    s = {}
    s["total"] = round(float(eq.iloc[-1]/eq.iloc[0]-1)*100, 2)
    s["mdd"] = round(_mdd(eq)*100, 2)
    for w, d in WINDOWS.items():
        sub = eq.tail(d+1)
        s[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100, 2)
        s[w+"_mdd"] = round(_mdd(sub)*100, 2)
    return s

def judge(out):
    out["nbeat_m07"] = sum(1 for w in WINDOWS if out[w] > M07[w])
    out["beat_all"] = all(out[w] > M07[w] for w in WINDOWS)
    out["mdd_better"] = out["mdd"] > M07["mdd"]
    out["win_all"] = bool(out["beat_all"] and out["mdd_better"])
    return out

def single_row(tag, params, phase, kind="single"):
    eq, res = run_leg(params, phase)
    out = {"tag": tag, "kind": kind, "phases": [phase], "params": dict(params, phase=phase)}
    out.update(stats_of(eq))
    out["trades"] = len(res.trades)
    out["cost"] = round(float(res.meta["total_cost"]), 0)
    out["mode"] = res.meta["final_mode"]
    out["switches"] = len(res.meta["switch_log"])
    out["brakes"] = len(res.meta.get("brake_log", []))//2
    out["switch_log"] = [list(x) for x in res.meta["switch_log"]]
    out["brake_log"] = [list(x) for x in res.meta.get("brake_log", [])]
    out["switch_same_m07"] = (out["switch_log"] == M07_SWITCH)
    return judge(out)

def sleeve_row(tag, params, phases, kind=None):
    kind = kind or ("sleeve%d" % len(phases))
    legs = []
    eqs = []
    for ph in phases:
        eq, res = run_leg(params, ph)
        eqs.append(eq)
        leg = {"phase": ph}
        leg.update(stats_of(eq))
        leg["trades"] = len(res.trades)
        leg["cost"] = round(float(res.meta["total_cost"]), 0)
        leg["mode"] = res.meta["final_mode"]
        leg["switches"] = len(res.meta["switch_log"])
        leg["switch_log"] = [list(x) for x in res.meta["switch_log"]]
        legs.append(leg)
    combo = pd.concat(eqs, axis=1, join="inner").mean(axis=1).dropna()
    out = {"tag": tag, "kind": kind, "phases": list(phases), "params": dict(params),
           "legs": legs,
           "leg_total_spread": round(max(l["total"] for l in legs)-min(l["total"] for l in legs), 2),
           "leg_nbeat_ge4": sum(1 for l in legs if sum(1 for w in WINDOWS if l[w] > M07[w]) >= 4)}
    out.update(stats_of(combo))
    out["trades"] = sum(l["trades"] for l in legs)
    out["cost"] = round(sum(l["cost"] for l in legs)/len(legs), 0)
    out["mode"] = "SLEEVE"
    out["switches"] = sum(l["switches"] for l in legs)
    out["brakes"] = None
    out["switch_log"] = [l["switch_log"] for l in legs]
    out["switch_same_m07"] = all(l["switch_log"] == M07_SWITCH for l in legs)
    return judge(out)

SLEEVE_GROUPS = [
    ("sleeve_m07_p0_p15", M07P, [0, 15]),
    ("sleeve_m07_pm8_pp8", M07P, [-8, 8]),
    ("sleeve_m07_pm5_pp5", M07P, [-5, 5]),
    ("sleeve_gbf07_p0_p15", G_BF07, [0, 15]),
    ("sleeve_gbf07_pm8_pp8", G_BF07, [-8, 8]),
    ("sleeve_gbf07_pm5_pp5", G_BF07, [-5, 5]),
    ("sleeve_gbx15_p0_p15", G_BX15, [0, 15]),
    ("sleeve_gbx15_pm8_pp8", G_BX15, [-8, 8]),
    ("sleeve_gbx15_pm5_pp5", G_BX15, [-5, 5]),
    ("sleeve3_m07_m8_0_p8", M07P, [-8, 0, 8]),
    ("sleeve3_gbf07_m8_0_p8", G_BF07, [-8, 0, 8]),
]

R_GRID = [
    ("r_A15B30", dict(M07P, a_rebal=15, b_rebal=30)),
    ("r_A25B30", dict(M07P, a_rebal=25, b_rebal=30)),
    ("r_A20B20", dict(M07P, a_rebal=20, b_rebal=20)),
    ("r_A20B40", dict(M07P, a_rebal=20, b_rebal=40)),
    ("r_A15B20", dict(M07P, a_rebal=15, b_rebal=20)),
    ("r_A25B40", dict(M07P, a_rebal=25, b_rebal=40)),
]

if __name__ == "__main__":
    rows = []
    r = single_row("base_M07", M07P, 0)
    slim = {k: r[k] for k in ("tag", "total", "mdd", "trades", "cost", "switches", "1m", "3m", "6m", "1y", "2y", "3y", "nbeat_m07", "beat_all", "mdd_better", "win_all", "switch_same_m07")}
    print("BASE " + json.dumps(slim, ensure_ascii=False), flush=True)
    assert abs(r["total"]-M07["total"]) < 0.01 and abs(r["mdd"]-M07["mdd"]) < 0.01, "base_M07 calibration FAILED: %s" % slim
    rows.append(r)
    for tag, params, phases in SLEEVE_GROUPS:
        try:
            r = sleeve_row(tag, params, phases)
            slim = {k: r[k] for k in ("tag", "kind", "phases", "total", "mdd", "trades", "cost", "1m", "3m", "6m", "1y", "2y", "3y", "nbeat_m07", "beat_all", "mdd_better", "win_all")}
            print(json.dumps(slim, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (tag, e), flush=True)
            import traceback; traceback.print_exc()
    r_rows = []
    for tag, params in R_GRID:
        try:
            r = single_row(tag, params, 0)
            slim = {k: r[k] for k in ("tag", "total", "mdd", "trades", "cost", "switches", "1m", "3m", "6m", "1y", "2y", "3y", "nbeat_m07", "beat_all", "mdd_better", "win_all", "switch_same_m07")}
            print(json.dumps(slim, ensure_ascii=False), flush=True)
            rows.append(r); r_rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (tag, e), flush=True)
            import traceback; traceback.print_exc()
    qual = sorted([x for x in r_rows if x["nbeat_m07"] >= 4], key=lambda x: (-x["nbeat_m07"], -x["total"]))
    if qual:
        for i, q in enumerate(qual[:2]):
            tag = "sleeve_%s_p0_p15" % q["tag"]
            try:
                r = sleeve_row(tag, q["params"], [0, 15])
                slim = {k: r[k] for k in ("tag", "kind", "phases", "total", "mdd", "trades", "cost", "1m", "3m", "6m", "1y", "2y", "3y", "nbeat_m07", "beat_all", "mdd_better", "win_all")}
                print(json.dumps(slim, ensure_ascii=False), flush=True)
                rows.append(r)
            except Exception as e:
                print("FAIL %s: %s" % (tag, e), flush=True)
                import traceback; traceback.print_exc()
        print("NOTE R+sleeve: %d R-grid rows nbeat>=4, added %d sleeve combos" % (len(qual), min(2, len(qual))), flush=True)
    else:
        print("NOTE R+sleeve SKIPPED: no single R-grid row with nbeat_m07>=4 (best=%s)" % (
            max([x["nbeat_m07"] for x in r_rows]) if r_rows else None), flush=True)
    open(ROOT/"results"/"r30_bt"/"sweep_beat_m07_k4.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
    print("saved %d rows -> results/r30_bt/sweep_beat_m07_k4.json" % len(rows), flush=True)
