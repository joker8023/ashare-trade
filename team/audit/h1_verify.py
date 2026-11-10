import pandas as pd
df = pd.read_csv("team/runs/batch_034_h1_results.csv")
print("total rows:", len(df))
print(df["stress"].value_counts().to_string())
err = df[df["status"] != "ok"] if "status" in df.columns else df.iloc[0:0]
print("error rows:", len(err))
if len(err):
    print(err[["id", "error"]].to_string())
base = df[df["stress"] == "base"]
print("base R values:", sorted(base["R"].unique().tolist()))
print("base phases per R:")
print(base.groupby("R")["phase"].apply(lambda x: sorted(x.tolist())).to_string())
print("exTOP3 rows:", len(df[df["stress"] == "exTOP3"]))
print("gross rows:", len(df[df["stress"] == "gross"]))
print("slip007 rows:", len(df[df["stress"] == "slip007"]))
