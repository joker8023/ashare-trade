import pandas as pd, pickle
from pathlib import Path
ROOT = Path(".")
def load(n):
    eq = pickle.load(open(ROOT / ("results/r30_bt/" + n + ".pkl"), "rb"))
    if isinstance(eq, pd.DataFrame):
        eq = eq.iloc[:, 0]
    return eq.dropna()
combo70 = load("combo_w70_equity")
combo50 = load("combo_w50_equity")
m07 = load("M07_equity")
j04 = load("J04_equity")
# try blend m07 and j04? they are almost identical, blend wont change much
# try blend m07 with cash (exposure): eq_blended = eq/eq0 * w + (1-w) in levels? Actually exposure scales returns, not levels linearly, but approximate
# For exposure w, equity path with constant exposure w vs 100 percent: roughly eq_w = eq_full * w + cash * (1-w)? No, exposure scales position size, so returns scale by w, drawdowns scale too. Approx eq_w(t) = eq0 * exp(w * log(eq_full/eq0))? Not linear.
# Simpler: check if combo70 / combo50 ratio matches exposure scaling
print("combo50 last " + str(combo50.iloc[-1]))
print("combo70 last " + str(combo70.iloc[-1]))
print("m07 last " + str(m07.loc[combo70.index].iloc[-1]))
print("j04 last " + str(j04.loc[combo70.index].iloc[-1]))
# normalized to start
for n, eq in [("c50", combo50), ("c70", combo70), ("m07", m07.loc[combo70.index]), ("j04", j04.loc[combo70.index])]:
    tot = float(eq.iloc[-1] / eq.iloc[0] - 1) * 100
    print(n + " tot " + str(round(tot,2)))
# try linear blend of m07 and t40?
try:
    t40 = load("T40_equity")
    t40s = t40.loc[combo70.index]
    for w in [0.5, 0.6, 0.7, 0.8]:
        bl = m07.loc[combo70.index] / m07.loc[combo70.index].iloc[0] * w + t40s / t40s.iloc[0] * (1 - w)
        bl = bl * 50000
        diff = float((bl - combo70).abs().mean())
        print("blend m07+t40 w=" + str(w) + " meandiff=" + str(round(diff,2)) + " last=" + str(round(bl.iloc[-1],2)))
except Exception as e:
    print("blend fail " + str(e))
