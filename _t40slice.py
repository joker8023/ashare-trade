import pandas as pd, pickle
from pathlib import Path
ROOT = Path(".")
def load(n):
    eq = pickle.load(open(ROOT / ("results/r30_bt/" + n + ".pkl"), "rb"))
    if isinstance(eq, pd.DataFrame):
        eq = eq.iloc[:, 0]
    return eq.dropna()
def mdd(s):
    return float((s / s.cummax() - 1).min()) * 100
t40 = load("T40_equity")
combo = load("combo_w70_equity")
t40s = t40.loc[combo.index]
print("t40 sliced tot=" + str(round(float(t40s.iloc[-1]/t40s.iloc[0]-1)*100,2)) + " mdd=" + str(round(mdd(t40s),2)))
# compare to implied 1066
# also load legs C sliced?
lc = load("leg_C_ami5_equity")
lcs = lc.loc[combo.index]
print("C sliced tot=" + str(round(float(lcs.iloc[-1]/lcs.iloc[0]-1)*100,2)))
