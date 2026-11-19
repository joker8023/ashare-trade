import pandas as pd, pickle
from pathlib import Path
ROOT = Path(".")
def mdd(s):
    return float((s / s.cummax() - 1).min())
for tag in ["A_vol3", "B_turn6", "C_ami5"]:
    eq = pickle.load(open(ROOT / "results" / "r30_bt" / ("leg_" + tag + "_equity.pkl"), "rb"))
    if isinstance(eq, pd.DataFrame):
        eq = eq.iloc[:, 0]
    eq = eq.dropna()
    print("=" + tag)
    for y in [2021, 2022, 2023, 2024, 2025, 2026]:
        sub = eq[eq.index.year == y]
        if len(sub) > 1:
            r = float(sub.iloc[-1] / sub.iloc[0] - 1) * 100
            m = float(mdd(sub)) * 100
            print(str(y) + " ret=" + str(round(r,2)) + " mdd=" + str(round(m,2)))
    # sliced 2023-01-19
    eqs = eq[eq.index >= pd.Timestamp("2023-01-19")]
    tot = float(eqs.iloc[-1] / eqs.iloc[0] - 1) * 100
    print("sliced2023 total=" + str(round(tot,2)) + " mdd=" + str(round(float(mdd(eqs))*100,2)))
