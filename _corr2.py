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
la = load("leg_A_vol3_equity")
lb = load("leg_B_turn6_equity")
lc = load("leg_C_ami5_equity")
reg = load("REGIME3_equity")
dfs = {"combo": combo, "m07": m07, "j04": j04, "A": la, "B": lb, "C": lc, "reg": reg}
idx = combo.index
for k in list(dfs.keys()):
    dfs[k] = dfs[k].loc[idx]
rets = pd.DataFrame({k: v.pct_change() for k, v in dfs.items()})
print(rets.corr().round(2).to_string())
print("means")
print(rets.mean().to_string())
