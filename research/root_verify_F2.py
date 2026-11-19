"""Root independent re-run: F2 champion famF2_T08_bx012_by005_bf04 (fresh process)."""
import sys, json
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "team" / "audit")); sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import build_ns, _mdd, RUN_START, EVAL_END, MB
piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid if d >= pd.Timestamp(RUN_START))
print("shadows building...", flush=True)
inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
inp_b = DInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=0.70, max_win=20, sel="amihud_5")
CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0,
          lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
          eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
CFG_B = dict(n=4, rebal=30, take=0.8, exposure=0.9)
ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
print("shadows ready A=%d B=%d" % (len(ra.trades), len(rb.trades)), flush=True)
KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B,
          shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=60, exclude_a=MB, exclude_b=MB,
          **{k: v for k, v in CA.items() if k != "exclude"})
ns = build_ns(0.12, 0.05, 0.4)
res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
eq = eq.dropna()
out = {"tag": "ROOT_F2", "total": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
       "mdd": round(_mdd(eq) * 100, 2), "trades": len(res.trades),
       "cost": round(float(res.meta["total_cost"]), 0), "mode": res.meta["final_mode"],
       "switches": len(res.meta["switch_log"]),
       "switch_log": [list(x) for x in res.meta["switch_log"]]}
prev = None
for y in (2023, 2024, 2025, 2026):
    sub = eq[eq.index.year == y]
    sret = float(sub.iloc[-1] / sub.iloc[0] - 1) * 100
    out[f"y{y}_slice"] = round(sret, 2)
    out[f"y{y}_yoy"] = round(float(sub.iloc[-1] / prev - 1) * 100 if prev is not None else sret, 2)
    out[f"y{y}_mdd"] = round(_mdd(sub) * 100, 2)
    prev = float(sub.iloc[-1])
json.dump(out, open(ROOT / "results" / "r30_bt" / "verify_F2.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
