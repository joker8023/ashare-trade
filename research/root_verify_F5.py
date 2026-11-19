"""Root independent re-run: F5 champion F5s3_rs42_h004_dg (fresh process)."""
import sys, json
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "team" / "audit")); sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import _mdd, RUN_START, EVAL_END, MB
from search_C_stage2 import build_ns
piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
print("shadows building...", flush=True)
inpA = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0,
          lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
          eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
ra = pc.run_strategy(inpA, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
inp_b = DInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=0.7, max_win=20, sel="c_a60_turn")
CFG_B = dict(n=4, rebal=15, take=0.45, exposure=0.9)
sh_b = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B}).eq
print("shadows ready A=%d" % len(ra.trades), flush=True)
KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B,
          shadow_a=ra.eq, shadow_b=sh_b, rs_lookback=42, exclude_a=MB, exclude_b=MB,
          evalfreq="daily", brake_daily=False,
          **{k: v for k, v in CA.items() if k != "exclude"})
ns = build_ns(0.18, 0.08, 0.6, 0.04, 0, 1)
res = ns["run_strategy_switch"](inpA, lock_mode=None, **KW)
eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
eq = eq.dropna()
out = {"tag": "ROOT_F5", "total": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
       "mdd": round(_mdd(eq) * 100, 2), "trades": len(res.trades),
       "cost": round(float(res.meta["total_cost"]), 0), "mode": res.meta["final_mode"],
       "switches": len(res.meta["switch_log"]),
       "switch_log": [list(x) for x in res.meta["switch_log"]],
       "brakes": len(res.meta.get("brake_log", [])) // 2}
prev = None
for y in (2023, 2024, 2025, 2026):
    sub = eq[eq.index.year == y]
    sret = float(sub.iloc[-1] / sub.iloc[0] - 1) * 100
    out[f"y{y}_slice"] = round(sret, 2)
    out[f"y{y}_yoy"] = round(float(sub.iloc[-1] / prev - 1) * 100 if prev is not None else sret, 2)
    out[f"y{y}_mdd"] = round(_mdd(sub) * 100, 2)
    prev = float(sub.iloc[-1])
json.dump(out, open(ROOT / "results" / "r30_bt" / "verify_F5.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
