import sys
sys.path.insert(0, '.'); sys.path.insert(0, 'team/audit'); sys.path.insert(0, 'research')
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import RUN_START, EVAL_END, MB
piv = pd.read_pickle('data/pivots_2020_clean_realshares_v2.pkl')
dates = piv['close'].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
ib = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=0.80, max_win=20)
for t in [first_sig, dates[400], dates[600], dates[900]]:
    print(t.date(), len(ib.picks(t, 4, exclude=MB, factor='amihud_60')))
CA = dict(factor='amihud_60', stop=0.25, stop_exec='next', exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
rb = pc.run_strategy(ib, phase=0, **dict(CA, **dict(n=4, rebal=30, take=0.80, exposure=0.9)))
print('direct B trades:', len(rb.trades))
eq = rb.eq.iloc[:, 0] if isinstance(rb.eq, pd.DataFrame) else rb.eq
print('direct B eq0/eq1:', float(eq.dropna().iloc[0]), float(eq.dropna().iloc[-1]))