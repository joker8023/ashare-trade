"""M07 K3 local-opt check + cross-phase validation (ph5/7/10/14/15)."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
J04 = {"1m": -4.84, "3m": 15.64, "6m": 37.17, "1y": 160.27, "2y": 1449.34, "3y": 1581.48, "mdd": -27.63}
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
_shadow_cache = {}
_ns0 = build_ns(0.18, 0.08, 0.6)
def get_shadows(cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp, ph):
    key = (cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp, ph)
    if key in _shadow_cache:
        return _shadow_cache[key]
    inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=cut_a, max_win=win_a)
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=cut_b, max_win=win_b)
    CA = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=b_n, rebal=30, take=b_take, exposure=b_exp)
    ra = pc.run_strategy(inp_a, n=a_n, rebal=20, take=a_take, exposure=1.0, phase=ph, **CA)
    rb = pc.run_strategy(inp_b, phase=ph, **{**CA, **CFG_B})
    _shadow_cache[key] = (inp_a, inp_b, ra, rb, CA, CFG_B)
    return _shadow_cache[key]
def run_one(tag, cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, stop=0.25, a_take=1.2, b_take=0.80, a_n=5, b_n=4, b_exp=0.9, rs=60, bx=0.18, by_=0.08, bf=0.6, ph=0):
    inp_a, inp_b, ra, rb, CA, CFG_B = get_shadows(cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp, ph)
    KW = dict(n=a_n, rebal=20, take=a_take, exposure=1.0, phase=ph, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB, **{k: v for k, v in CA.items() if k != "exclude"})
    ns = _ns0 if (bx, by_, bf) == (0.18, 0.08, 0.6) else build_ns(bx, by_, bf)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), "mdd": round(_mdd(eq)*100,2), "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]),0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"])}
    for w, d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
    if ph == 0:
        out["nbeat_j04"] = sum(1 for w in WINDOWS if out[w] > J04[w])
        out["beat_all"] = all(out[w] > J04[w] for w in WINDOWS)
        out["win_all"] = bool(out["beat_all"] and out["mdd"] > J04["mdd"])
    return out
K3 = [
    dict(tag="kM07_baseline"),
    dict(tag="k31_winB15", win_b=15),
    dict(tag="k32_winB25", win_b=25),
    dict(tag="k33_winB30", win_b=30),
    dict(tag="k34_bn3", b_n=3),
    dict(tag="k35_winB15_bn4", win_b=15, b_n=4),
    dict(tag="k36_winB25_bn4", win_b=25, b_n=4),
    dict(tag="k37_winB20_bn3", win_b=20, b_n=3),
    dict(tag="k38_winB20_bx15", win_b=20, bx=0.15),
]
PH = [dict(tag="ph5", ph=5), dict(tag="ph7", ph=7), dict(tag="ph10", ph=10), dict(tag="ph14", ph=14), dict(tag="ph15", ph=15)]
if __name__ == "__main__":
    rows = []
    for cfg in K3:
        c = dict(cfg); tag = c.pop("tag")
        try:
            r = run_one(tag, **c)
            print(json.dumps(r, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (tag, e), flush=True)
    for cfg in PH:
        c = dict(cfg); tag = "m07_" + c.pop("tag")
        try:
            r = run_one(tag, **c)
            print(json.dumps(r, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (tag, e), flush=True)
    open(ROOT/"results"/"r30_bt"/"valid_m07_k3ph.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
    print("saved %d rows" % len(rows), flush=True)
