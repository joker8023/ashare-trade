import json
from pathlib import Path
d = json.load(open("results/r30_bt/sweep_beat_m07_k7.json"))
rows = d if isinstance(d, list) else d.get("rows", d.get("results", []))
print("NROWS:", len(rows))
print("KEYS:", sorted(rows[0].keys()))
for x in rows:
    print({k: x.get(k) for k in ["tag","total","mdd","trades","cost","mode","switches","brakes","1m","3m","6m","1y","2y","3y","nbeat","nbeat_m07","beat_all","mdd_better","win_all","switch_same","switch_same_m07"] if k in x})
