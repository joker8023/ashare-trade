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
_shadow_cache = {}
_ns_cache = {}
def get_ns(bx, by, bf):
    k = (bx, by, bf)
    if k not in _ns_cache:
        _ns_cache[k] = build_ns(bx, by, bf)
    return _ns_cache[k]
def get_shadows(cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp, gate_a=-0.15, band_a_lo=0.02):
    key = (cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp, gate_a, band_a_lo)
    if key in _shadow_cache:
        return _shadow_cache[key]
    inp_a = MaxInputs(piv, band=(band_a_lo, 0.30), gate60=gate_a, max_cut=cut_a, max_win=win_a)
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=cut_b, max_win=win_b)
    CA = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=b_n, rebal=30, take=b_take, exposure=b_exp)
    ra = pc.run_strategy(inp_a, n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
    _shadow_cache[key] = (inp_a, inp_b, ra, rb, CA, CFG_B)
    return _shadow_cache[key]
def run_one(tag, cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, stop=0.25, a_take=1.2, b_take=0.80, a_n=5, b_n=4, b_exp=0.9, rs=60, bx=0.18, by_=0.08, bf=0.6, gate_a=-0.15, band_a_lo=0.02):
    inp_a, inp_b, ra, rb, CA, CFG_B = get_shadows(cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp, gate_a, band_a_lo)
    KW = dict(n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB, **{k: v for k, v in CA.items() if k != "exclude"})
    ns = get_ns(bx, by_, bf)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), "mdd": round(_mdd(eq)*100,2), "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]),0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "brakes": len(res.meta.get("brake_log",[]))//2,
           "switch_log": [list(x) for x in res.meta["switch_log"]], "brake_log": [list(x) for x in res.meta.get("brake_log", [])]}
    for w, d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
        out[w+"_mdd"] = round(_mdd(sub)*100,2)
    out["nbeat_m07"] = sum(1 for w in WINDOWS if out[w] > M07[w])
    out["beat_all"] = all(out[w] > M07[w] for w in WINDOWS)
    out["mdd_better"] = out["mdd"] > M07["mdd"]
    out["win_all"] = bool(out["beat_all"] and out["mdd_better"])
    out["switch_same_m07"] = (out["switch_log"] == M07_SWITCH)
    return out
CFGS = [
    dict(tag="base_M07"),
    # 1. bf-axis tail on g base (=by05+cut双腿0.78+bx15)
    dict(tag="g_bf065", by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.65),
    dict(tag="g_bf075", by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.75),
    dict(tag="g_bf080", by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.80),
    dict(tag="g_bf085", by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.85),
    # 3. M07 base + bf0.7 single-change (expect == K1 k01_bf07)
    dict(tag="m07_bf07", bf=0.7),
    # 2. conditional on g_bf080 nbeat_m07>=5 (run only if gate passes)
    dict(tag="g_bf080_takeB90", by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.80, b_take=0.90),
    dict(tag="g_bf080_bx20", by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.20, bf=0.80),
]
PHASE1 = ("base_M07", "g_bf065", "g_bf075", "g_bf080", "g_bf085", "m07_bf07")
PHASE2 = ("g_bf080_takeB90", "g_bf080_bx20")
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--only", default=None); ap.add_argument("--phase", default=None, choices=["1", "2"])
    args = ap.parse_args()
    rows = []
    cfgs = [c for c in CFGS if args.only is None or c["tag"] == args.only]
    if args.phase == "1":
        cfgs = [c for c in cfgs if c["tag"] in PHASE1]
    elif args.phase == "2":
        cfgs = [c for c in cfgs if c["tag"] in PHASE2]
    for cfg in cfgs:
        c = dict(cfg); tag = c.pop("tag")
        try:
            r = run_one(tag, **c)
            slim = {k: r[k] for k in ("tag","total","mdd","trades","cost","switches","brakes","1m","3m","6m","1y","2y","3y","nbeat_m07","beat_all","mdd_better","win_all","switch_same_m07")}
            print(json.dumps(slim, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (tag, e), flush=True)
            import traceback; traceback.print_exc()
    if args.only is None and args.phase is None:
        open(ROOT/"results"/"r30_bt"/"sweep_beat_m07_k7.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
        print("saved %d rows" % len(rows), flush=True)
