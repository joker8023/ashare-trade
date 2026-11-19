import sys, json
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, RUN_START, EVAL_END, MB
from switch_ns import build_ns
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
print("RUN_START=%s first_sig=%s" % (RUN_START, first_sig.date()), flush=True)
inpA = MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=40)
inpB = MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=20)
CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
ra = pc.run_strategy(inpA, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
rb = pc.run_strategy(inpB, n=5, rebal=15, take=0.45, exposure=1.0, phase=0, **CA)
print("shadows ready A=%d B=%d" % (len(ra.trades), len(rb.trades)), flush=True)
KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inpB, cfg_b=dict(n=5, rebal=15, take=0.45, exposure=1.0), shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=60, exclude_a=MB, exclude_b=MB, evalfreq="grid", brake_daily=False, **{k:v for k,v in CA.items() if k != "exclude"})
ns = build_ns(0.15, 0.10, 0.5, 0.0, 0, 1)
res = ns["run_strategy_switch"](inpA, lock_mode=None, **KW)
eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
eq = eq.dropna()
out = {"total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), "mdd": round(float(_mdd(eq))*100,2), "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]),0), "switches": len(res.meta["switch_log"]), "switch_log": [[str(a),str(b)] for a,b in res.meta["switch_log"]]}
print(json.dumps(out, ensure_ascii=False), flush=True)
exp = {"total": 1349.24, "mdd": -23.42, "trades": 280, "cost": 51018.0, "switches": 8}
ok = all(abs(out[k]-exp[k])<1e-9 for k in exp)
print("PARITY " + ("PASS" if ok else "FAIL vs "+json.dumps(exp, ensure_ascii=False)), flush=True)
