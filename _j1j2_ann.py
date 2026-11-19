import pickle, pandas as pd
from pathlib import Path
ROOT = Path(".")
def load(n):
    eq = pickle.load(open(ROOT / ("results/r30_bt/" + n + ".pkl"), "rb"))
    if isinstance(eq, pd.DataFrame):
        eq = eq.iloc[:, 0]
    return eq.dropna()
def mdd(s):
    return float((s / s.cummax() - 1).min()) * 100
for tag, fn in [("J1", "REG3_J1_Bjan_half_equity"), ("J2", "REG3_J2_Bstop15_equity"), ("combo", "combo_w70_equity")]:
    eq = load(fn)
    print("=" + tag + " " + str(eq.index[0].date()) + " to " + str(eq.index[-1].date()))
    for y in [2022, 2023, 2024, 2025, 2026]:
        sub = eq[eq.index.year == y]
        if len(sub) > 1:
            r = float(sub.iloc[-1] / sub.iloc[0] - 1) * 100
            m = mdd(sub)
            print(str(y) + " ret=" + str(round(r,2)) + " mdd=" + str(round(m,2)))
        else:
            print(str(y) + " nodata bars=" + str(len(sub)))
