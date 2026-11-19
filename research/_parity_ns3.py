import sys, json
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import _mdd, RUN_START, EVAL_END, MB
from switch_ns import build_ns as build_ns_old
from switch_ns3 import build_ns3 as build_ns_new
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
def run_all(ns, inpA, inp_b, cfg_b, rs, ef, bd, bx, by, bf, hyst, mh, cf):
    sh = shb(inp_b, cfg_b)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=cfg_b, shadow_a=ra.eq, shadow_b=sh, rs_lookback=rs, exclude_a=MB, exclude_b=MB, evalfreq=ef, brake_daily=bd, **{k:v for k,v in CA.items() if k != "exclude"})
    res = ns["run_strategy_switch"](inpA, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    return {"total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), "mdd": round(float(_mdd(eq))*100,2), "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]),0), "switches": len(res.meta["switch_log"]), "swlog": [[str(a),str(b)] for a,b in res.meta["switch_log"]], "brakes": len(res.meta.get("brake_log", []))//2}
inpA = MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=40)
ra = pc.run_strategy(inpA, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
shb_cache = {}
def shb(inp_b, cfg_b):
    k = (id(inp_b), tuple(sorted(cfg_b.items())))
    if k not in shb_cache:
        shb_cache[k] = pc.run_strategy(inp_b, phase=0, **{**CA, **cfg_b}).eq
    return shb_cache[k]
cases = [
  ("F1", MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=20), dict(n=5, rebal=15, take=0.45, exposure=1.0), 60, "grid", False, (0.15,0.10,0.5,0.0,0,1)),
  ("F5", DInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=0.70, max_win=20, sel="c_a60_turn"), dict(n=4, rebal=15, take=0.45, exposure=0.9), 42, "daily", False, (0.18,0.08,0.6,0.04,0,1)),
]
ok = True
for tag, inpB, cfgB, rs, ef, bd, (bx,by,bf,hyst,mh,cf) in cases:
    ns_old = build_ns_old(bx,by,bf,hyst,mh,cf)
    ns_new = build_ns_new(bx,by,bf,hyst,mh,cf)
    r0 = run_all(ns_old, inpA, inpB, cfgB, rs, ef, bd, bx, by, bf, hyst, mh, cf)
    r1 = run_all(ns_new, inpA, inpB, cfgB, rs, ef, bd, bx, by, bf, hyst, mh, cf)
    same = r0 == r1
    ok = ok and same
    print(tag, "PARITY " + ("PASS" if same else "FAIL"), flush=True)
    if not same:
        print(" OLD " + json.dumps(r0, ensure_ascii=False)[:800], flush=True)
        print(" NEW " + json.dumps(r1, ensure_ascii=False)[:800], flush=True)
print("ALL " + ("PASS" if ok else "FAIL"), flush=True)
