import pandas as pd, pickle
from pathlib import Path
ROOT = Path(".")
combo = pickle.load(open(ROOT / "results" / "r30_bt" / "combo_w70_equity.pkl", "rb"))
m07 = pickle.load(open(ROOT / "results" / "r30_bt" / "M07_equity.pkl", "rb"))
j04 = pickle.load(open(ROOT / "results" / "r30_bt" / "J04_equity.pkl", "rb"))
for name in ["leg_A_vol3_equity", "leg_B_turn6_equity", "leg_C_ami5_equity"]:
    try:
        leg = pickle.load(open(ROOT / "results" / "r30_bt" / (name + ".pkl"), "rb"))
    except:
        leg = pickle.load(open(ROOT / "results" / "r30_bt" / (name.replace("leg_", "leg_") + ".pkl"), "rb"))
    print(name + " loaded " + str(len(leg)))
