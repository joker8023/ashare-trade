import json
rows = json.load(open("results/r30_bt/REG3_round4.json"))
print("tag total mdd nbeat mddwin sw 1m 3m 6m 1y 2y 3y")
for r in rows:
    print(r["tag"], r["total"], r["mdd"], r["nbeat"], r["beats_mdd"], r["switches"], r["1m"], r["3m"], r["6m"], r["1y"], r["2y"], r["3y"])
