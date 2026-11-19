import sys, json, gc
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import prior_check as pc
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import _mdd, EVAL_END, MB
piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
RUN_START = str(dates[0].date())
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
def make_inp(sel):
    return DInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=0.70, max_win=20, sel=sel)
legs = [("A_vol3", "c_a60_vol", dict(n=3, rebal=30, take=0.8, exposure=1.0)), ("B_turn6", "c_a60_turn", dict(n=6, rebal=30, take=0.8, exposure=1.0)), ("C_ami5", "amihud_5", dict(n=4, rebal=30, take=0.8, exposure=1.0))]
for tag, sel, cfg in legs:
    rb = pc.run_strategy(make_inp(sel), phase=0, **{k: v for k, v in CA.items() if k != "exclude"}, exclude=MB, **cfg)
    eq = rb.eq.iloc[:, 0] if isinstance(rb.eq, pd.DataFrame) else rb.eq
    eq = eq.dropna()
    eq.to_pickle(ROOT / "results" / "r30_bt" / ("leg_" + tag + "_equity.pkl"))
    tot = float(eq.iloc[-1] / eq.iloc[0] - 1) * 100
    print(tag + " total=" + str(round(tot,2)) + " mdd=" + str(round(float(_mdd(eq))*100,2)) + " trades=" + str(len(rb.trades)))
    del rb
    gc.collect()
print("legs done")
