"""K19: 长持有期腿试点 (R enlarged: R60/R90/R120). Baseline = M07 final (ph0).
口径除腿调仓周期 R(rebal) 外与 research/run_m07_final.py 逐字一致:
  5万 / 现实费率(cost_one_way=None) / slip=0.002 / 整手lot=100 /
  RUN_START / EVAL_END / WINDOWS; brake rs=60 默认; 原生amihud_60双腿 + MAX过滤 + 刹车 + RS60切换.
M07: A leg band=(0.02,0.30) gate60=-0.15 cut=0.80 win=40 take=1.2 n=5 rebal=20 exp=1.0;
     B leg band=(0.05,0.30) gate60=-1.0 cut=0.80 win=20 take=0.8 n=4 rebal=30 exp=0.9;
     stop=0.25 stop_exec=next; brake bx=0.18/by=0.08/bf=0.6.
R enlarged 不引入未来函数: 网格信号日仍只用 t 及以前数据, 仅调仓间隔拉长
  (复用 prior_check.run_strategy 的 rebal 语义, 与 K4 R_GRID 同机制).
6 配 (A腿R20保持 vs 全改两档):
  B单腿改: r_B60_A20 / r_B90_A20 / r_B120_A20
  双腿同改: r_B60_A60 / r_B90_A90 / r_B120_A120
判定: 严格>对比 M07 ph0 六窗; win_all = beat_all and mdd > -27.05.
Schema 同 K4 + R 字段 (R_a/R_b/R) + 尾部身份字段 (top3_share/extop3_total, 与 run_m07_final.py 同口径).
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

def attrib_of(eq, res):
    """尾部身份: 与 run_m07_final.py 同口径 (trades net_pnl top3)."""
    try:
        tr = res.trades
        pnl = tr["net_pnl"].fillna(0)
        if len(pnl) == 0 or float(pnl.sum()) == 0:
            return {"top3_share": None, "extop3_total": None}
        top3 = pnl.nlargest(3).sum()
        return {"top3_share": round(float(top3/pnl.sum())*100, 1),
                "extop3_total": round(float((eq.iloc[0]+pnl.sum()-top3)/eq.iloc[0]-1)*100, 2)}
    except Exception:
        return {"top3_share": None, "extop3_total": None}

def judge(out):
    out["nbeat_m07"] = sum(1 for w in WINDOWS if out[w] > M07[w])
    out["beat_all"] = all(out[w] > M07[w] for w in WINDOWS)
    out["mdd_better"] = out["mdd"] > M07["mdd"]
    out["win_all"] = bool(out["beat_all"] and out["mdd_better"])
    return out

def single_row(tag, params, phase, kind="single"):
    eq, res = run_leg(params, phase)
    out = {"tag": tag, "kind": kind, "phases": [phase],
           "R_a": params["a_rebal"], "R_b": params["b_rebal"],
           "R": "A%d/B%d" % (params["a_rebal"], params["b_rebal"]),
           "params": dict(params, phase=phase)}
    out.update(stats_of(eq))
    out.update(attrib_of(eq, res))
    out["trades"] = len(res.trades)
    out["cost"] = round(float(res.meta["total_cost"]), 0)
    out["mode"] = res.meta["final_mode"]
    out["switches"] = len(res.meta["switch_log"])
    out["brakes"] = len(res.meta.get("brake_log", []))//2
    out["switch_log"] = [list(x) for x in res.meta["switch_log"]]
    out["brake_log"] = [list(x) for x in res.meta.get("brake_log", [])]
    out["switch_same_m07"] = (out["switch_log"] == M07_SWITCH)
    return judge(out)

# K19: R_B in {60,90,120} x {B单腿改, 双腿同改R_A=R_B} = 6 配 (无超限, R120双腿保留)
R_GRID_K19 = [
    ("r_B60_A20", dict(M07P, a_rebal=20, b_rebal=60)),
    ("r_B90_A20", dict(M07P, a_rebal=20, b_rebal=90)),
    ("r_B120_A20", dict(M07P, a_rebal=20, b_rebal=120)),
    ("r_B60_A60", dict(M07P, a_rebal=60, b_rebal=60)),
    ("r_B90_A90", dict(M07P, a_rebal=90, b_rebal=90)),
    ("r_B120_A120", dict(M07P, a_rebal=120, b_rebal=120)),
]

if __name__ == "__main__":
    rows = []
    r = single_row("base_M07", M07P, 0)
    slim = {k: r[k] for k in ("tag", "R", "total", "mdd", "trades", "cost", "switches", "1m", "3m", "6m", "1y", "2y", "3y", "nbeat_m07", "beat_all", "mdd_better", "win_all", "switch_same_m07")}
    print("BASE " + json.dumps(slim, ensure_ascii=False), flush=True)
    assert abs(r["total"]-M07["total"]) < 0.01 and abs(r["mdd"]-M07["mdd"]) < 0.01, "base_M07 calibration FAILED: %s" % slim
    rows.append(r)
    for tag, params in R_GRID_K19:
        try:
            r = single_row(tag, params, 0)
            slim = {k: r[k] for k in ("tag", "R", "total", "mdd", "trades", "cost", "switches", "top3_share", "extop3_total", "1m", "3m", "6m", "1y", "2y", "3y", "nbeat_m07", "beat_all", "mdd_better", "win_all", "switch_same_m07")}
            print(json.dumps(slim, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (tag, e), flush=True)
            import traceback; traceback.print_exc()
    open(ROOT/"results"/"r30_bt"/"sweep_beat_m07_k19.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
    print("saved %d rows -> results/r30_bt/sweep_beat_m07_k19.json" % len(rows), flush=True)
