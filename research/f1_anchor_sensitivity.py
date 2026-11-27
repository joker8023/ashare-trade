"""检查 shares 锚点对 F1 选股的敏感性：不同 anchor 下 2020-2026 各调仓期 4 只票的重合度"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("ASHARE_PIVOTS", "pivots_2020_clean.pkl")
import numpy as np, pandas as pd
import engine as E

FACTOR, DIRECTION, N_HOLD, REBAL = "amihud_60", "high", 4, 60
SIZE, MIN_ADV = (0.02, 0.15), 5e6

def picks_all(anchor):
    p = dict(E.piv())
    uni = pd.read_pickle(E.DATA / "universe_2020.pkl")
    fc = uni.set_index("code")["float_cap"].astype("float64")
    c = p["close"].astype("float64")
    p["shares"] = (fc / c.loc[pd.Timestamp(anchor)]).replace([np.inf,-np.inf], np.nan).dropna().astype("float32")
    E._PIV = p
    cc = p["close"]; adv20 = p["amount"].rolling(20, min_periods=10).mean()
    seasoned = cc.shift(250).notna(); fac = E.FACTORS[FACTOR](p)
    dates = cc.index; out = {}
    for i in range(300, len(dates)-REBAL-2, REBAL):
        t = dates[i]
        if t < pd.Timestamp("2020-01-01"): continue
        valid = seasoned.loc[t] & (adv20.loc[t] > MIN_ADV) & cc.loc[t].notna() & fac.loc[t].notna()
        cap = cc.loc[t] * p["shares"]
        lo, hi = cap.quantile(SIZE[0]), cap.quantile(SIZE[1])
        valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
        pool = valid[valid].index
        if len(pool) < N_HOLD: continue
        out[t] = set(fac.loc[t, pool].nlargest(N_HOLD).index)
    return out

A = picks_all("2026-11-24")
B = picks_all("2026-11-12")
C = picks_all("2026-11-26")
common = sorted(set(A) & set(B) & set(C))
print(f"调仓期数 2020+ : A(11-24)={len(A)} B(11-12)={len(B)} C(11-26)={len(C)} 共同={len(common)}")
for nm, X in [("A vs B", (A,B)), ("A vs C", (A,C))]:
    ov = [len(X[0][t] & X[1][t]) for t in common]
    same = sum(1 for o in ov if o==4)
    print(f"{nm}: 平均重合 {np.mean(ov):.2f}/4 只, 完全相同 {same}/{len(common)} 期 ({same/len(common):.0%})")
    by_year = {}
    for t,o in zip(common, ov):
        by_year.setdefault(t.year, []).append(o)
    print("   逐年平均重合:", {y: round(float(np.mean(v)),2) for y,v in sorted(by_year.items())})
