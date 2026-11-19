import pickle, pandas as pd
from pathlib import Path
ROOT = Path(".")
def load(n):
    eq = pickle.load(open(ROOT / ("results/r30_bt/" + n + ".pkl"), "rb"))
    if isinstance(eq, pd.DataFrame):
        eq = eq.iloc[:, 0]
    return eq.dropna()
champ = load("REG3_champion_equity")
combo = load("combo_w70_equity")
for name, eq in [("champ", champ), ("combo", combo)]:
    peak = eq.cummax()
    dd = eq / peak - 1
    end = dd.idxmin()
    print(name + " mdd=" + str(round(float(dd.min())*100,2)) + " trough=" + str(end.date()))
    print(name + " peak=" + str(eq.loc[:end].idxmax().date()) + " peak_eq=" + str(round(float(eq.loc[:end].max()),2)) + " trough_eq=" + str(round(float(eq.loc[end]),2)))
print("1m window start=" + str(combo.tail(22).index[0].date()))
print("champ 1m bars ret=" + str(round(float(champ.tail(22).iloc[-1]/champ.tail(22).iloc[0]-1)*100,2)))
print("combo 1m bars ret=" + str(round(float(combo.tail(22).iloc[-1]/combo.tail(22).iloc[0]-1)*100,2)))
