import json
for k in [1, 2, 3, 4]:
    p = f"results/r30_bt/sweep_beat_m07_k{k}.json"
    try:
        d = json.load(open(p))
        rows = d if isinstance(d, list) else d.get("rows", d)
        n = len(rows)
        nb = [r.get("nbeat_m07", r.get("nbeat")) for r in rows]
        ba = sum(1 for r in rows if r.get("beat_all"))
        wa = sum(1 for r in rows if r.get("win_all"))
        mx = max(x for x in nb if x is not None)
        print(f"K{k}: n={n} beat_all={ba} win_all={wa} max_nbeat={mx}")
        s = sorted(rows, key=lambda r: (r.get("nbeat_m07", -1) if r.get("nbeat_m07") is not None else -1), reverse=True)[:3]
        for r in s:
            print("   ", r.get("tag"), "nbeat=", r.get("nbeat_m07"), "total=", r.get("total"), "mdd=", r.get("mdd"), "beat=", r.get("beat_all"))
    except Exception as e:
        print(f"K{k}: ERROR {e}")
import os
print("K5 exists:", os.path.exists("results/r30_bt/sweep_beat_m07_k5.json"))
