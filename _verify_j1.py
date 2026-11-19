import pickle, json, pandas as pd
from pathlib import Path
ROOT = Path(".")
def load(n):
    eq = pickle.load(open(ROOT / ("results/r30_bt/" + n + ".pkl"), "rb"))
    if isinstance(eq, pd.DataFrame):
        eq = eq.iloc[:, 0]
    return eq.dropna()
def mdd(s):
    return float((s / s.cummax() - 1).min()) * 100
j1 = load("REG3_pit_jan_best_equity")
combo = load("combo_w70_equity")
j = json.loads((ROOT / "results/r30_bt/REG3_pit_jan.json").read_text())
print("json keys=" + str(list(j.keys())))
print("json=" + json.dumps(j, ensure_ascii=False)[:3000])
ct = float(j1.iloc[-1] / j1.iloc[0] - 1) * 100
cm = mdd(j1)
bt = float(combo.iloc[-1] / combo.iloc[0] - 1) * 100
bm = mdd(combo)
print("J1 recomputed total=" + str(round(ct,2)) + " mdd=" + str(round(cm,2)))
print("combo total=" + str(round(bt,2)) + " mdd=" + str(round(bm,2)))
print("excess=" + str(round(ct-bt,2)) + " mddgap=" + str(round(cm-bm,2)))
W = [("1m", 21), ("3m", 63), ("6m", 126), ("1y", 252), ("2y", 504), ("3y", 756)]
for tag, d in W:
    bs = j1.loc[combo.index].tail(d + 1)
    cs = combo.tail(d + 1)
    br = float(bs.iloc[-1] / bs.iloc[0] - 1) * 100
    cr = float(cs.iloc[-1] / cs.iloc[0] - 1) * 100
    print(tag + " J1=" + str(round(br,2)) + " combo=" + str(round(cr,2)) + " win=" + str(br > cr))
