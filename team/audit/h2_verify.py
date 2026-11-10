import pandas as pd
df = pd.read_csv("team/runs/batch_035_h2_results.csv")
print("total rows:", len(df))
print("by stress:", df["stress"].value_counts().to_dict())
err = df[df.get("status", "ok").fillna("ok") == "error"]
print("error rows:", len(err))
if len(err):
    print(err[["id", "error"]].to_string())
base = df[df["stress"] == "base"]
print("base rows:", len(base), "configs:", base["spec"].nunique() if "spec" in df.columns else "?")
print(base.groupby("id".replace("id", "spec") if False else "spec").size() if "spec" in df.columns else "")
