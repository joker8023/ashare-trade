"""K3: M07 orthogonal sweep (dims K1/K2 did not touch, 1-2 at a time).
Baseline = M07 final (ph0). Same caliber as run_m07_final.py / sweep_beat_m07_k1/k2.py.
M07: J04 + B-MAX20 (A40/B20) + B-N4; brake bx0.18/by0.08/bf0.6; rs60.
  A leg M07: band=(0.02,0.30) gate60=-0.15 max_cut=0.80 max_win=40 take=1.2 n=5 rebal=20
  B leg M07: band=(0.05,0.30) gate60=-1.0 max_cut=0.80 max_win=20 take=0.8 n=4 rebal=30 exp=0.9 stop=0.25
K3 dims: winA 30/50; cutA asym 0.78/0.82 (B keeps 0.80/20); takeA 1.0/1.4;
  gateA -0.10/-0.20; bandA lo 0.03; takeB 0.70/0.90/1.00; stop 0.20/0.30;
  expB 0.95; RS 50/70/80; brake on g(=by05+cut78+bx15): bf0.5/0.7, bx0.20;
  combos: g+takeB90, g+takeA100, g+stop22 (+4 extra 2-factor: g+takeB100, g+expB95, g+rs70, g+winA30).
NOT repeated (K1/K2 falsified): B N3/N5, bexp1.0 single, A N4, RS45/75/90,
  winB10/15/25/30 singles, stop +- singles(22/28), symmetric cut 0.77-0.79,
  by0.04-0.06 singles, bf0.7 single, bx0.15 single.
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
    # A leg: winA
    dict(tag="a_winA30", win_a=30),
    dict(tag="a_winA50", win_a=50),
    # A leg: cutA asymmetric (B keeps cut0.80/win20)
    dict(tag="a_cutA78_asym", cut_a=0.78, cut_b=0.80),
    dict(tag="a_cutA82_asym", cut_a=0.82, cut_b=0.80),
    # A leg: takeA
    dict(tag="a_takeA100", a_take=1.0),
    dict(tag="a_takeA140", a_take=1.4),
    # A leg: gateA
    dict(tag="a_gateA_m10", gate_a=-0.10),
    dict(tag="a_gateA_m20", gate_a=-0.20),
    # A leg: band lower edge 0.03
    dict(tag="a_bandA_lo003", band_a_lo=0.03),
    # B leg: takeB / stop / expB
    dict(tag="b_takeB70", b_take=0.70),
    dict(tag="b_takeB90", b_take=0.90),
    dict(tag="b_takeB100", b_take=1.00),
    dict(tag="b_stop20", stop=0.20),
    dict(tag="b_stop30", stop=0.30),
    dict(tag="b_expB95", b_exp=0.95),
    # switch RS
    dict(tag="s_rs50", rs=50),
    dict(tag="s_rs70", rs=70),
    dict(tag="s_rs80", rs=80),
    # brake on g (=by05+cut78 both+bx15)
    dict(tag="g_bf05", by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.5),
    dict(tag="g_bf07", by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.7),
    dict(tag="g_bx20", by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.20, bf=0.6),
    # combos on g
    dict(tag="g_takeB90", by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, b_take=0.90),
    dict(tag="g_takeA100", by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, a_take=1.0),
    dict(tag="g_stop22", by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, stop=0.22),
    # extra 2-factor (non-falsified)
    dict(tag="g_takeB100", by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, b_take=1.00),
    dict(tag="g_expB95", by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, b_exp=0.95),
    dict(tag="g_rs70", by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, rs=70),
    dict(tag="g_winA30", by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, win_a=30),
]
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--only", default=None)
    args = ap.parse_args()
    rows = []
    cfgs = [c for c in CFGS if args.only is None or c["tag"] == args.only]
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
    if args.only is None:
        open(ROOT/"results"/"r30_bt"/"sweep_beat_m07_k3.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
        print("saved %d rows" % len(rows), flush=True)
