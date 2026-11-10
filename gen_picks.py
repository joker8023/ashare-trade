"""严格选股预计算：strictA(三因子交集)/strictC(超跌企稳)，R30网格，存CSV"""
import os; os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import pandas as pd
import engine as E

p = E.piv(); c = p["close"]
adv20 = p["amount"].rolling(20, min_periods=10).mean()
seasoned = c.shift(250).notna()
dates = c.index
amihud = E.FACTORS["amihud"](p)
vol20 = c.pct_change().rolling(20).std()
rev20 = -(c / c.shift(20) - 1)
hi60 = c.rolling(60).max()
near_high = c / hi60

def base_pool(t):
    valid = seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna()
    cap = c.loc[t] * p["shares"]
    lo, hi = cap.quantile(0.05), cap.quantile(0.30)
    valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
    return valid[valid].index

def sA(t, pool):
    f1 = amihud.loc[t, pool].nlargest(max(len(pool) // 10, 30)).index
    f2 = vol20.loc[t, f1].nsmallest(max(len(f1) // 2, 25)).index
    return list(rev20.loc[t, f2].nlargest(3).index)

def sC(t, pool):
    deep = rev20.loc[t, pool].nsmallest(max(len(pool) // 20, 30)).index
    ret5 = c.loc[t, deep] / c.shift(5).loc[t, deep] - 1
    firm = ret5[ret5 > -0.03].index
    if len(firm) < 3:
        return []
    return list(amihud.loc[t, firm].nlargest(3).index)

for name, func in [("strictA", sA), ("strictC", sC)]:
    rows = []
    for i in range(300, len(dates) - 30 - 2, 30):
        t = dates[i]
        pool = base_pool(t)
        if len(pool) < 60:
            continue
        try:
            picks = func(t, pool)
        except Exception:
            picks = []
        rows.append((t.date(), ",".join(picks)))
    df = pd.DataFrame(rows, columns=["date", "picks"])
    df.to_csv(f"results/picks_{name}_R30.csv", index=False)
    print(name, len(df), flush=True)
