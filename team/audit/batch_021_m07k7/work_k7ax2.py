import json, glob
for f in sorted(glob.glob("results/r30_bt/sweep_beat_m07_k*.json")):
    d = json.load(open(f))
    rows = d if isinstance(d, list) else d.get("rows", [])
    for x in rows:
        if x.get("tag") == "g" or (isinstance(x.get("total"),(int,float)) and abs(x["total"]-2084.73) < 1.0):
            print(f.split("/")[-1], x.get("tag"), {k: x.get(k) for k in ["total","mdd","nbeat_m07","nbeat","1m","3m","6m","1y","2y","3y"]})
