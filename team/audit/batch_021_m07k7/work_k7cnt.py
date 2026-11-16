import json, glob
tot_new = 0
for f in sorted(glob.glob("results/r30_bt/sweep_beat_m07_k*.json")):
    d = json.load(open(f))
    rows = d if isinstance(d, list) else d.get("rows", [])
    base = [x.get("tag") for x in rows if str(x.get("tag","")).startswith("base")]
    new = len(rows) - len(base)
    tot_new += new
    print(f.split("/")[-1], "rows=", len(rows), "base=", base, "new=", new)
print("TOTAL_NEW:", tot_new)
