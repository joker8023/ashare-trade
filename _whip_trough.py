import pickle, pandas as pd
from pathlib import Path
ROOT = Path(".")
def load(n):
    eq = pickle.load(open(ROOT / ("results/r30_bt/" + n + ".pkl"), "rb"))
    if isinstance(eq, pd.DataFrame):
        eq = eq.iloc[:, 0]
    return eq.dropna()
combo = load("combo_w70_equity")
print("combo mdd trough " + str((combo / combo.cummax() - 1).idxmin().date()))
for t in ["Q1_hyst001", "Q2_hyst002", "Q3_hyst003", "Q4_cf2", "Q5_mh60", "Q6_mh90", "Q7_rs90", "Q8_stick05", "Q9_stick08", "Q10_cf2mh60"]:
    eq = load("REG3_" + t + "_equity")
    dd = eq / eq.cummax() - 1
    print(t + " mdd=" + str(round(float(dd.min())*100,2)) + " trough=" + str(dd.idxmin().date()) + " mode-end check 1m=" + str(round(float(eq.tail(22).iloc[-1]/eq.tail(22).iloc[0]-1)*100,2)))
