import json
K3 = json.load(open("results/r30_bt/sweep_beat_m07_k3.json"))
K3 = K3 if isinstance(K3, list) else K3.get("rows", [])
for x in K3:
    if abs(x.get("total",0)-2084.73) < 1.0:
        print(x.get("tag"), {k: x.get(k) for k in ["total","mdd","nbeat_m07","1m","3m","6m","1y","2y","3y","switch_same_m07"]})
print("ALL_TAGS:", [x.get("tag") for x in K3])
