import pandas as pd
x = pd.read_pickle("results/r30_bt/cmp2020_x3_equity.pkl")
n = pd.read_pickle("results/r30_bt/cmp2020_n4_equity.pkl")
print("x3", x.index[0].date(), x.index[-1].date(), len(x))
print("n4", n.index[0].date(), n.index[-1].date(), len(n))
idx = x.index.intersection(n.index)
x, n = x.loc[idx], n.loc[idx]
rx = x.resample("ME").last().pct_change()
rn = n.resample("ME").last().pct_change()
df = pd.DataFrame({"x3": rx, "n4": rn})
df["diff"] = df["x3"] - df["n4"]
print(df.loc["2025-01":].round(4).to_string())
print()
print("worst x3-n4 months:")
print(df.loc["2025-01":].nsmallest(6, "diff").round(4).to_string())
print()
print("best x3-n4 months:")
print(df.loc["2025-01":].nlargest(6, "diff").round(4).to_string())
