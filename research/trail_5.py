#!/usr/bin/env python3
"""Trail windows 1/3/6m 1/2/3y for 5 champions (calendar trailing from eq end)."""
import sys, json
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import _mdd, RUN_START, EVAL_END, MB
from search_C_stage2 import build_ns as build_ns_C
from sweep_beat_h1_v4 import build_ns as build_ns_F2

piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
print("RUN", RUN_START, EVAL_END, "first_sig", first_sig.date(), flush=True)

CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0,
         lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
         eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)

# shared A leg
inpA = MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=40)
ra = pc.run_strategy(inpA, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
print("shadow A ready trades=%d"%len(ra.trades), flush=True)

def get_rb(sel_class, sel, band, gate, cut, win, n, R, take, exp):
    if sel_class=="MAX":
        inp_b = MaxInputs(piv, band=band, gate60=gate, max_cut=cut, max_win=win)
    else:
        inp_b = DInputs(piv, band=band, gate60=gate, max_cut=cut, max_win=win, sel=sel)
    rb = pc.run_strategy(inp_b, phase=0, **{**CA, **dict(n=n, rebal=R, take=take, exposure=exp)})
    return inp_b, rb

def run_one(tag, inp_b, cfg_b, rs, ns, evalfreq="grid", brake_daily=False):
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=cfg_b,
              shadow_a=ra.eq, shadow_b=pc.run_strategy if False else None, rs_lookback=rs,
              exclude_a=MB, exclude_b=MB, evalfreq=evalfreq, brake_daily=brake_daily,
              **{k:v for k,v in CA.items() if k!="exclude"})
    # shadow_b eq: recompute from inp_b+cfg_b to avoid stale (cheap, cached below)
    return KW, ns

# cache shadow_b eqs
_shb = {}
def shb_eq(inp_b, cfg_b):
    key = (id(inp_b), tuple(sorted(cfg_b.items())))
    if key not in _shb:
        _shb[key] = pc.run_strategy(inp_b, phase=0, **{**CA, **cfg_b}).eq
    return _shb[key]

def do_switch(tag, inp_b, cfg_b, rs, ns, evalfreq="grid", brake_daily=False):
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=cfg_b,
              shadow_a=ra.eq, shadow_b=shb_eq(inp_b, cfg_b), rs_lookback=rs,
              exclude_a=MB, exclude_b=MB,
              **{k:v for k,v in CA.items() if k!="exclude"})
    # F2 classic engine has no evalfreq/brake_daily params
    try:
        import inspect as _ins
        _params = _ins.signature(ns["run_strategy_switch"]).parameters
        if "evalfreq" in _params:
            KW["evalfreq"] = evalfreq
        if "brake_daily" in _params:
            KW["brake_daily"] = brake_daily
    except Exception:
        KW["evalfreq"] = evalfreq; KW["brake_daily"] = brake_daily
    res = ns["run_strategy_switch"](inpA, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
    return eq.dropna(), res

def trail(eq):
    end = eq.index[-1]
    def win(days):
        cutoff = end - pd.Timedelta(days=days)
        sub = eq[eq.index > cutoff]
        if len(sub)==0: return None
        # anchor first bar in window
        r = float(sub.iloc[-1]/sub.iloc[0]-1)*100
        m = float((sub/sub.cummax()-1).min())*100
        return dict(ret=round(r,2), mdd=round(m,2), start=str(sub.index[0].date()), bars=int(len(sub)))
    return {
      "end": str(end.date()),
      "m1": win(31), "m3": win(93), "m6": win(182),
      "y1": win(365), "y2": win(730), "y3": win(1095),
      "full_ret": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2),
      "full_mdd": round(float(_mdd(eq))*100,2),
    }

out = {}
# F1 C2 grid
inpB1, _ = get_rb("MAX", None, (0.02,0.30), -0.15, 0.80, 20, 5, 15, 0.45, 1.0)
ns1 = build_ns_C(0.15, 0.10, 0.5, 0.0, 0, 1)
eq1, res1 = do_switch("F1", inpB1, dict(n=5, rebal=15, take=0.45, exposure=1.0), 60, ns1, "grid", False)
out["C2_grid_mh0_bx0.15_by0.1_bf0.5"] = trail(eq1)
print("F1 done", out["C2_grid_mh0_bx0.15_by0.1_bf0.5"], flush=True)
# F2
inpB2, _ = get_rb("D", "amihud_5", (0.05,0.30), -1.0, 0.70, 20, 4, 30, 0.8, 0.9)
ns2 = build_ns_F2(0.12, 0.05, 0.4)
eq2, res2 = do_switch("F2", inpB2, dict(n=4, rebal=30, take=0.8, exposure=0.9), 60, ns2, "grid", False)
out["famF2_T08_bx012_by005_bf04"] = trail(eq2)
print("F2 done", out["famF2_T08_bx012_by005_bf04"], flush=True)
# F4
inpB4, _ = get_rb("D", "c_a60_a5", (0.05,0.30), -1.0, 0.70, 20, 5, 30, 0.8, 0.9)
ns4 = build_ns_C(0.12, 0.06, 0.5, 0.0, 0, 1)
eq4, res4 = do_switch("F4", inpB4, dict(n=5, rebal=30, take=0.8, exposure=0.9), 13, ns4, "grid", False)
out["F4_c_a60_a5_N5_R30_T08_rs13_b01200605_grid"] = trail(eq4)
print("F4 done", out["F4_c_a60_a5_N5_R30_T08_rs13_b01200605_grid"], flush=True)
# F5
inpB5, _ = get_rb("D", "c_a60_turn", (0.05,0.30), -1.0, 0.70, 20, 4, 15, 0.45, 0.9)
ns5 = build_ns_C(0.18, 0.08, 0.6, 0.04, 0, 1)
eq5, res5 = do_switch("F5", inpB5, dict(n=4, rebal=15, take=0.45, exposure=0.9), 42, ns5, "daily", False)
out["F5s3_rs42_h004_dg"] = trail(eq5)
print("F5 done", out["F5s3_rs42_h004_dg"], flush=True)
# F7
inpB7, _ = get_rb("D", "c_a60_amt", (0.05,0.30), -1.0, 0.70, 20, 4, 15, 0.45, 0.78)
ns7 = build_ns_C(0.22, 0.05, 0.5, 0.035, 0, 1)
eq7, res7 = do_switch("F7", inpB7, dict(n=4, rebal=15, take=0.45, exposure=0.78), 47, ns7, "daily", False)
out["F7sF_rs47_h0035_exp078"] = trail(eq7)
print("F7 done", out["F7sF_rs47_h0035_exp078"], flush=True)

Path(ROOT/"results"/"r30_bt"/"trail_5m_y.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out, ensure_ascii=False, indent=1))
