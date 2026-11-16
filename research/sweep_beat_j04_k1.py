"""K1: J04 neighborhood one-factor sweep."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
J04 = {"1m": -4.84, "3m": 15.64, "6m": 37.17, "1y": 160.27, "2y": 1449.34, "3y": 1581.48, "mdd": -27.63, "total": 1765.84}
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
def get_shadows(cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp):
    key = (cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp)
    if key in _shadow_cache:
        return _shadow_cache[key]
    inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=cut_a, max_win=win_a)
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=cut_b, max_win=win_b)
    CA = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=b_n, rebal=30, take=b_take, exposure=b_exp)
    ra = pc.run_strategy(inp_a, n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
    _shadow_cache[key] = (inp_a, inp_b, ra, rb, CA, CFG_B)
    return _shadow_cache[key]
def run_one(tag, cut_a=0.80, win_a=40, cut_b=0.80, win_b=40, stop=0.25, a_take=1.2, b_take=0.80, a_n=5, b_n=5, b_exp=0.9, rs=60, bx=0.18, by_=0.08, bf=0.6):
    inp_a, inp_b, ra, rb, CA, CFG_B = get_shadows(cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp)
    KW = dict(n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB, **{k: v for k, v in CA.items() if k != "exclude"})
    ns = get_ns(bx, by_, bf)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), "mdd": round(_mdd(eq)*100,2), "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]),0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "brakes": len(res.meta.get("brake_log",[]))//2}
    for w, d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
        out[w+"_mdd"] = round(_mdd(sub)*100,2)
    out["nbeat_j04"] = sum(1 for w in WINDOWS if out[w] > J04[w])
    out["beat_all"] = all(out[w] > J04[w] for w in WINDOWS)
    out["mdd_better"] = out["mdd"] > J04["mdd"]
    out["win_all"] = bool(out["beat_all"] and out["mdd_better"])
    return out
CFGS = [
    dict(tag="base_J04"),
    dict(tag="k01_bf07", bf=0.7),
    dict(tag="k02_bf05", bf=0.5),
    dict(tag="k03_bx15", bx=0.15),
    dict(tag="k04_bx20", bx=0.20),
    dict(tag="k05_by05", by_=0.05),
    dict(tag="k06_stop22", stop=0.22),
    dict(tag="k07_stop28", stop=0.28),
    dict(tag="k08_btake70", b_take=0.70),
    dict(tag="k09_btake90", b_take=0.90),
    dict(tag="k10_btake100", b_take=1.00),
    dict(tag="k11_atake100", a_take=1.00),
    dict(tag="k12_atake140", a_take=1.40),
    dict(tag="k13_cut82", cut_a=0.82, cut_b=0.82),
    dict(tag="k14_cut78", cut_a=0.78, cut_b=0.78),
    dict(tag="k15_win20", win_a=20, win_b=20),
    dict(tag="k16_rs45", rs=45),
    dict(tag="k17_rs75", rs=75),
    dict(tag="k18_bn4", b_n=4),
    dict(tag="k19_bexp100", b_exp=1.0),
    dict(tag="k20_an4", a_n=4),
    dict(tag="k21_asym_A80B85", cut_a=0.80, cut_b=0.85),
    dict(tag="k22_asym_A85B80", cut_a=0.85, cut_b=0.80),
    dict(tag="k23_btake90_bf07", b_take=0.90, bf=0.7),
    dict(tag="k24_stop22_btake90", stop=0.22, b_take=0.90),
    dict(tag="k25_bx15_bf05", bx=0.15, bf=0.5),
]
if __name__ == "__main__":
    rows = []
    for cfg in CFGS:
        c = dict(cfg); tag = c.pop("tag")
        try:
            r = run_one(tag, **c)
            print(json.dumps(r, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (tag, e), flush=True)
            import traceback; traceback.print_exc()
    open(ROOT/"results"/"r30_bt"/"sweep_beat_j04_k1.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
    print("saved %d rows" % len(rows), flush=True)
