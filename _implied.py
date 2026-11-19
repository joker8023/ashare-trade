import pandas as pd, pickle
from pathlib import Path
ROOT = Path(".")
def load(n):
    eq = pickle.load(open(ROOT / ("results/r30_bt/" + n + ".pkl"), "rb"))
    if isinstance(eq, pd.DataFrame):
        eq = eq.iloc[:, 0]
    return eq.dropna()
combo = load("combo_w70_equity")
m07 = load("M07_equity")
j04 = load("J04_equity")
# align
m07a = m07.loc[combo.index]
j04a = j04.loc[combo.index]
for w in [0.5, 0.6, 0.7, 0.8]:
    impl = (combo - m07a * w) / (1 - w)
    # impl should be positive equity-like; check stats
    print("w=" + str(w) + " impl last=" + str(round(impl.iloc[-1],2)) + " min=" + str(round(impl.min(),2)) + " start=" + str(round(impl.iloc[0],2)))
    # total from start
    tot = float(impl.iloc[-1] / impl.iloc[0] - 1) * 100
    print("  tot=" + str(round(tot,2)))
# try with j04
for w in [0.7]:
    impl = (combo - j04a * w) / (1 - w)
    print("j04 w=0.7 impl last=" + str(round(impl.iloc[-1],2)) + " tot=" + str(round(float(impl.iloc[-1]/impl.iloc[0]-1)*100,2)))
