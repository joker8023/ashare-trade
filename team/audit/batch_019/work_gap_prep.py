import json
M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05, "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
WINS = ["1m", "3m", "6m", "1y", "2y", "3y"]
out = {}
for k in [1, 2, 3, 4]:
    d = json.load(open("results/r30_bt/sweep_beat_m07_k" + str(k) + ".json"))
    rows = d if isinstance(d, list) else d.get("rows", d)
    ranked = sorted(rows, key=lambda r: (r.get("nbeat_m07", -1), r.get("total", -1e18)), reverse=True)
    top = []
    for r in ranked[:4]:
        diff = {}
        for w in WINS:
            if isinstance(r.get(w), (int, float)):
                diff[w] = round(r[w] - M07[w], 2)
        rec = {"tag": r.get("tag"), "nbeat": r.get("nbeat_m07"), "total": r.get("total"), "mdd": r.get("mdd"), "diff": diff}
        rec["total_gap"] = round(r.get("total", 0) - M07["total"], 2)
        rec["mdd_gap"] = round(r.get("mdd", 0) - M07["mdd"], 2)
        top.append(rec)
        print("K" + str(k), r.get("tag"), "nbeat=", r.get("nbeat_m07"), "total=", r.get("total"), "mdd=", r.get("mdd"))
        print("   diff=", diff, "total_gap=", rec["total_gap"], "mdd_gap=", rec["mdd_gap"])
    out["K" + str(k)] = top
json.dump(out, open("team/audit/batch_019/part_gap_prep.json", "w"), ensure_ascii=False, indent=1)
print("saved part_gap_prep.json")
