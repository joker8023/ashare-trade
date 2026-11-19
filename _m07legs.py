import sys, json
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, EVAL_END, MB
RUN_START = "2023-01-03"
piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean.pkl")
dates = piv["close"].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
inpA = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
inpB = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=0.80, max_win=20)
ra = pc.run_strategy(inpA, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
rb = pc.run_strategy(inpB, n=4, rebal=30, take=0.8, exposure=0.9, phase=0, **CA)
for tag, r in [("A_MAX40_N5", ra), ("B_MAX20_N4", rb)]:
    eq = r.eq.iloc[:, 0] if isinstance(r.eq, pd.DataFrame) else r.eq
    eq = eq.dropna()
    tot = float(eq.iloc[-1] / eq.iloc[0] - 1) * 100
    print(tag + " total=" + str(round(tot,2)) + " mdd=" + str(round(float(_mdd(eq))*100,2)) + " trades=" + str(len(r.trades)))
    for y in [2023, 2024, 2025, 2026]:
        sub = eq[eq.index.year == y]
        print("  " + str(y) + " " + str(round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)))
