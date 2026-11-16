import json, glob
decl_beat = decl_win = 0
ge5 = []
for f in sorted(glob.glob("results/r30_bt/sweep_beat_m07_k*.json")):
    d = json.load(open(f))
    rows = d if isinstance(d, list) else d.get("rows", [])
    for x in rows:
        if x.get("beat_all"): decl_beat += 1
        if x.get("win_all"): decl_win += 1
        nb = x.get("nbeat_m07", x.get("nbeat"))
        if isinstance(nb,(int,float)) and nb >= 5 and not str(x.get("tag","")).startswith("base"):
            ge5.append((f.split("/")[-1], x.get("tag"), nb))
print("file-declared beat_all=True:", decl_beat, "win_all=True:", decl_win)
print("non-base nbeat>=5:", ge5)
