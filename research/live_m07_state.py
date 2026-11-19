"""M07 live state: realshares_v2 caliber (time-varying true shares).
Usage: .venv/bin/python research/live_m07_state.py  (eval_end = latest data)
Writes results/r30_bt/M07_live.json (never touches M07_final.json).
Dec-eve workflow: update_2020_sina_to_today.py -> build B1 -> B2 (realshares_v2) -> this script.
"""
import sys, json
from pathlib import Path
ROOT = Path("/Users/joker/coding/ashare-trade")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, WINDOWS, RUN_START, MB
from clean_data import clean_pivots as _unused
piv = pd.read_pickle(ROOT / "data/pivots_2020_clean_realshares_v2.pkl")
END = piv["close"].index[-1]
print("DATA_END:" + str(END.date()), flush=True)
print("shares = realshares_v2 time-varying; live caliber == backtest caliber", flush=True)
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=0.80, max_win=20)
CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=END, legacy_grid=False, full_liquidate=True)
CFG_B = dict(n=4, rebal=30, take=0.80, exposure=0.9)
ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, exclude_a=MB, exclude_b=MB, **{k: v for k, v in CA.items() if k != "exclude"})
ns = build_ns(0.18, 0.08, 0.6)
res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
eq = eq.dropna()
out = dict(total=round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2), mdd=round(float((eq / eq.cummax() - 1).min()) * 100, 2), trades=len(res.trades), mode=res.meta.get("final_mode"), switches=len(res.meta.get("switch_log", [])))
out["switch_log"] = [[str(x) for x in s] for s in res.meta.get("switch_log", [])]
out["brake_log"] = [[str(x) for x in s] for s in res.meta.get("brake_log", [])]
for w, d in WINDOWS.items():
    sub = eq.tail(d + 1)
    out[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
    out[w + "_mdd"] = round(float((sub / sub.cummax() - 1).min()) * 100, 2)
open(out_path := str(ROOT / "results" / "r30_bt" / "M07_live.json"), "w").write(json.dumps(out, ensure_ascii=False, indent=1))
print("saved M07_live.json total=" + str(out["total"]) + " mode=" + str(out["mode"]), flush=True)
