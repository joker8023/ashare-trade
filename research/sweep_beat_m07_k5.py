"""K5: 新机制 (非阈值微调). Baseline = M07 final (ph0).
口径除机制外与 research/run_m07_final.py 逐字一致:
  ph0 / RUN_START=2023-01-03 / EVAL_END=2026-11-12 / 5万 /
  现实费率(cost_one_way=None) / slip=0.002 / 整手lot=100 /
  legacy_grid=False / full_liquidate=True / stop_exec=next / factor=amihud_60 / MB排除.
M07: A band=(0.02,0.30) gate60=-0.15 cut=0.80 win=40 take=1.2 n=5 rebal=20 exp=1.0;
     B band=(0.05,0.30) gate60=-1.0 cut=0.80 win=20 take=0.8 n=4 rebal=30 exp=0.9;
     stop=0.25; brake bx=0.18/by=0.08/bf=0.6; RS trailing-60 (ra>=rb->A else B).
g_bf07 = M07 + by=0.05 + cut双腿0.78 + bx=0.15 + bf=0.7 (K3 g_bf07).
机制 (全为引擎原生参数, 无手写回测器, 无未来函数):
  legA_only/legB_only: pc.run_strategy 单腿独立运行 (无switch/无刹车, 引擎原生单策略路径).
  lockA/lockB: run_strategy_switch(lock_mode=A/B) (switch_engine.py原生支持).
  nobrake_*: bx=10.0 (drawdown>=1000%才触发=永不触发, 原生brake参数).
  rs30/rs120: rs_lookback=30/120 (RS45-90禁碰区之外的值; unanimous/反转逻辑引擎无原生支持, 跳过).
  pair_hi/lo: B腿take+全局stop成对联动 (take1.00+stop0.20 / take0.70+stop0.30; K3只有单改对照).
  swap_*: A/B腿N/R角色互换 (慢腿快腿对调; takes/exp保持或互换).
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

M07P = dict(cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, stop=0.25,
            a_take=1.2, b_take=0.80, a_n=5, b_n=4, a_exp=1.0, b_exp=0.9,
            rs=60, bx=0.18, by_=0.08, bf=0.6, a_rebal=20, b_rebal=30)
G_BF07 = dict(M07P, by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.7)

piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))

_shadow_cache = {}
_ns_cache = {}

def get_ns(bx, by, bf):
    k = (bx, by, bf)
    if k not in _ns_cache:
        _ns_cache[k] = build_ns(bx, by, bf)
    return _ns_cache[k]

def get_shadows(p):
    key = tuple(sorted(p.items()))
    if key in _shadow_cache:
        return _shadow_cache[key]
    inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=p["cut_a"], max_win=p["win_a"])
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=p["cut_b"], max_win=p["win_b"])
    CA = dict(factor="amihud_60", stop=p["stop"], stop_exec="next", exclude=MB, capital=50000.0,
              lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
              eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=p["b_n"], rebal=p["b_rebal"], take=p["b_take"], exposure=p["b_exp"])
    ra = pc.run_strategy(inp_a, n=p["a_n"], rebal=p["a_rebal"], take=p["a_take"],
                         exposure=p["a_exp"], phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
    _shadow_cache[key] = (inp_a, inp_b, ra, rb, CA, CFG_B)
    return _shadow_cache[key]

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

def run_switch(tag, params, lock_mode=None, mechanism=""):
    p = params
    inp_a, inp_b, ra, rb, CA, CFG_B = get_shadows(p)
    KW = dict(n=p["a_n"], rebal=p["a_rebal"], take=p["a_take"], exposure=p["a_exp"], phase=0,
              inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=p["rs"],
              exclude_a=MB, exclude_b=MB, **{k: v for k, v in CA.items() if k != "exclude"})
    ns = get_ns(p["bx"], p["by_"], p["bf"])
    res = ns["run_strategy_switch"](inp_a, lock_mode=lock_mode, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "kind": "switch", "mechanism": mechanism,
           "params": dict(p, lock_mode=lock_mode)}
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

def run_leg(tag, params, leg, mechanism):
    """单腿独立运行: 复用M07口径pc.run_strategy (phase=0, 无switch/无刹车)."""
    p = params
    _, _, ra, rb, _, _ = get_shadows(p)
    res = ra if leg == "A" else rb  # shadow腿即M07口径单腿独立运行, 直接复用Result
    res_eq = res.eq
    eq = res_eq.iloc[:, 0] if isinstance(res_eq, pd.DataFrame) else res_eq
    eq = eq.dropna()
    out = {"tag": tag, "kind": "single_leg_" + leg, "mechanism": mechanism,
           "params": dict(p, leg=leg)}
    out.update(stats_of(eq))
    out["trades"] = len(res.trades)
    out["cost"] = round(float(res.meta["total_cost"]), 0)
    out["mode"] = leg
    out["switches"] = 0
    out["brakes"] = 0
    out["switch_log"] = []
    out["brake_log"] = []
    out["switch_same_m07"] = False
    return judge(out)

CFGS = [
    ("base_M07", dict(M07P), None, "switch", "M07逐字复现校准行"),
    # 1. 单腿
    ("legA_only", dict(M07P), None, "singleA", "A腿单跑N5/R20/take1.2/win40, pc.run_strategy独立, 无switch无刹车"),
    ("legB_only", dict(M07P), None, "singleB", "B腿单跑N4/R30/take0.80/win20, pc.run_strategy独立, 无switch无刹车"),
    # 2. 锁定模式 (原生lock_mode)
    ("lockA", dict(M07P), "A", "switch", "lock_mode=A锁定A腿全程(含刹车)"),
    ("lockB", dict(M07P), "B", "switch", "lock_mode=B锁定B腿全程(含刹车)"),
    ("lockA_gbf07", dict(G_BF07), "A", "switch", "g_bf07基座+lock_mode=A"),
    ("lockB_gbf07", dict(G_BF07), "B", "switch", "g_bf07基座+lock_mode=B"),
    # 3. 去刹车 (bx=10永不触发, 原生参数)
    ("nobrake_M07", dict(M07P, bx=10.0), None, "switch", "M07去刹车: bx=10(永不触发), by/bf保持"),
    ("nobrake_gbf07", dict(G_BF07, bx=10.0), None, "switch", "g_bf07去刹车: bx=10(永不触发)"),
    # 4. RS切换: 禁碰区(45-90)之外原生最小改动; unanimous/反转引擎无原生支持故跳过
    ("rs30", dict(M07P, rs=30), None, "switch", "rs_lookback=30 (禁碰45-90之外短窗)"),
    ("rs120", dict(M07P, rs=120), None, "switch", "rs_lookback=120 (禁碰45-90之外长窗)"),
    ("g_rs30", dict(G_BF07, rs=30), None, "switch", "g_bf07基座+rs_lookback=30"),
    ("g_rs120", dict(G_BF07, rs=120), None, "switch", "g_bf07基座+rs_lookback=120"),
    # 5. 止盈止损绑定套餐 (B take + 全局stop联动; K3只有单改对照)
    ("pair_hi", dict(M07P, b_take=1.00, stop=0.20), None, "switch", "联动套餐: B take1.00+stop0.20 (对照K3 b_takeB100/b_stop20单改)"),
    ("pair_lo", dict(M07P, b_take=0.70, stop=0.30), None, "switch", "联动套餐: B take0.70+stop0.30 (对照K3 b_takeB70/b_stop30单改)"),
    ("g_pair_hi", dict(G_BF07, b_take=1.00, stop=0.20), None, "switch", "g_bf07基座+联动套餐 take1.00+stop0.20"),
    ("g_pair_lo", dict(G_BF07, b_take=0.70, stop=0.30), None, "switch", "g_bf07基座+联动套餐 take0.70+stop0.30"),
    # 6. A/B角色互换 (慢腿快腿对调)
    ("swap_NR", dict(M07P, a_n=4, a_rebal=30, b_n=5, b_rebal=20), None, "switch", "角色互换N/R: A用R30N4, B用R20N5+MAX20保持, takes/exp保持"),
    ("swap_full", dict(M07P, a_n=4, a_rebal=30, b_n=5, b_rebal=20, a_take=0.80, a_exp=0.9, b_take=1.2, b_exp=1.0), None, "switch", "角色互换N/R+takes/exp: A=R30N4/take0.8/exp0.9, B=R20N5/take1.2/exp1.0"),
    ("g_swap_NR", dict(G_BF07, a_n=4, a_rebal=30, b_n=5, b_rebal=20), None, "switch", "g_bf07基座+角色互换N/R"),
]

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--only", default=None)
    args = ap.parse_args()
    rows = []
    for tag, params, lock, kind, mech in CFGS:
        if args.only and tag != args.only:
            continue
        try:
            if kind in ("singleA", "singleB"):
                r = run_leg(tag, params, "A" if kind == "singleA" else "B", mech)
            else:
                r = run_switch(tag, params, lock_mode=lock, mechanism=mech)
            slim = {k: r[k] for k in ("tag", "total", "mdd", "trades", "cost", "switches", "brakes", "1m", "3m", "6m", "1y", "2y", "3y", "nbeat_m07", "beat_all", "mdd_better", "win_all")}
            print(("BASE " if tag == "base_M07" else "") + json.dumps(slim, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (tag, e), flush=True)
            import traceback; traceback.print_exc()
    if not args.only:
        base = rows[0]
        assert abs(base["total"]-M07["total"]) < 0.01 and abs(base["mdd"]-M07["mdd"]) < 0.01, "base_M07 calibration FAILED: %s" % base
        for w in WINDOWS:
            assert abs(base[w]-M07[w]) < 0.01, "base window %s mismatch" % w
        open(ROOT/"results"/"r30_bt"/"sweep_beat_m07_k5.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
        print("saved %d rows -> results/r30_bt/sweep_beat_m07_k5.json" % len(rows), flush=True)
