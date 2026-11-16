import json
F = json.load(open("results/r30_bt/sweep_beat_m07_k7.json"))
for x in F:
    if x["tag"] in ("g_bf080","g_bf085","g_bf075","g_bf065"):
        print(x["tag"], {k: x[k] for k in ["total","mdd","1m","3m","6m","1y","2y","3y","nbeat_m07","mdd_better","switch_same_m07"]})
