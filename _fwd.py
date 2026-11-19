import pandas as pd, pickle
from pathlib import Path
ROOT = Path(".")
legs = {}
for tag in ["A_vol3", "B_turn6", "C_ami5"]:
    eq = pickle.load(open(ROOT / "results" / "r30_bt" / ("leg_" + tag + "_equity.pkl"), "rb"))
    if isinstance(eq, pd.DataFrame):
        eq = eq.iloc[:, 0]
    legs[tag] = eq.dropna()
piv = pd.read_pickle("data/pivots_2020_clean_realshares_v2.pkl")
close = piv["close"]
shares = piv["shares"]
rets = close.pct_change(fill_method=None)
eq_idx = (1 + rets.mean(axis=1, skipna=True).fillna(0)).cumprod()
tot = (close * shares).sum(axis=1)
midx = (1 + tot.pct_change(fill_method=None).fillna(0)).cumprod()
medcap = (close * shares).median(axis=0)
small_idx = (1 + rets[medcap.nsmallest(1500).index].mean(axis=1, skipna=True).fillna(0)).cumprod()
dates = close.index
grid = [dates[i] for i in range(300, len(dates), 30)]
print("date cap_gap small_gap eq_gap best_leg fwdA fwdB fwdC")
for i, d in enumerate(grid):
    if d < pd.Timestamp("2023-01-03"):
        continue
    if i + 1 >= len(grid):
        continue
    d2 = grid[i+1]
    # forward leg returns between d and d2 using leg eq values at nearest trading days
    fwd = {}
    for tag, eq in legs.items():
        try:
            a = eq.loc[:d].iloc[-1]
            b = eq.loc[:d2].iloc[-1]
            fwd[tag] = float(b / a - 1) * 100
        except Exception as e:
            fwd[tag] = float("nan")
    best = max(fwd, key=lambda k: fwd[k])
    cg = float(midx.loc[d] / midx.rolling(60).mean().loc[d] - 1) * 100
    sg = float(small_idx.loc[d] / small_idx.rolling(60).mean().loc[d] - 1) * 100
    eg = float(eq_idx.loc[d] / eq_idx.rolling(60).mean().loc[d] - 1) * 100
    print(str(d.date()) + " cap=" + str(round(cg,1)) + " small=" + str(round(sg,1)) + " eq=" + str(round(eg,1)) + " best=" + best + " A=" + str(round(fwd["A_vol3"],1)) + " B=" + str(round(fwd["B_turn6"],1)) + " C=" + str(round(fwd["C_ami5"],1)))
