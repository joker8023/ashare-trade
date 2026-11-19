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
tail = load("REG3_tail_best_equity")
d1 = load("REG3_D1_daily_equity")
combo = load("combo_w70_equity")
tail = tail.loc[combo.index]
d1 = d1.loc[combo.index]
W = [("1m", 21), ("3m", 63), ("6m", 126), ("1y", 252), ("2y", 504), ("3y", 756)]
for w in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
    bl = tail / tail.iloc[0] * w + d1 / d1.iloc[0] * (1 - w)
    bl = bl * 50000
    tot = float(bl.iloc[-1] / bl.iloc[0] - 1) * 100
    md = mdd(bl)
    ok = 0
    parts = []
    for tag, d in W:
        bs = bl.tail(d + 1)
        cs = combo.tail(d + 1)
        br = float(bs.iloc[-1] / bs.iloc[0] - 1) * 100
        cr = float(cs.iloc[-1] / cs.iloc[0] - 1) * 100
        win = br > cr
        ok = ok + (1 if win else 0)
        parts.append(tag + "=" + str(round(br,2)) + ("Y" if win else "n"))
    print("w=" + str(w) + " total=" + str(round(tot,2)) + " mdd=" + str(round(md,2)) + " nbeat=" + str(ok) + " mddwin=" + str(md > mdd(combo)) + " " + " ".join(parts))
