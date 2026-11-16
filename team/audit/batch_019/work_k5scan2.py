"""K5 review harness (schema-flexible). Run after sweep_beat_m07_k5.json lands.
Step 1 (no engine): schema check + recompute nbeat/beat_all/win_all vs M07 + candidate pick.
""" # noqa
import json, os, sys

M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05, "2y": 1474.08, "3y": 1677.53,
       "mdd": -27.05, "total": 1863.27}
WINS = ["1m", "3m", "6m", "1y", "2y", "3y"]
P = "results/r30_bt/sweep_beat_m07_k5.json"

if not os.path.exists(P):
    print("K5_MISSING")
    sys.exit(2)
d = json.load(open(P))
rows = d if isinstance(d, list) else d.get("rows", d)
print(f"K5 rows: {len(rows)}")
keys = sorted(set(k for r in rows for k in r.keys()))
print("schema keys:", keys)
base = [r for r in rows if "base" in str(r.get("tag", "")).lower() or r.get("kind") == "base"]
for r in base:
    print("BASE:", {k: r.get(k) for k in ("tag", "kind", "total", "mdd") + tuple(WINS)})
    dev = {w: round(r[w] - M07[w], 2) for w in WINS if isinstance(r.get(w), (int, float))}
    print("  base dev vs M07_final:", dev, "mdd dev:", round(r.get("mdd", 0) - M07["mdd"], 2))
mis = []
for r in rows:
    nb = sum(1 for w in WINS if isinstance(r.get(w), (int, float)) and r[w] > M07[w])
    ba = all(isinstance(r.get(w), (int, float)) and r[w] > M07[w] for w in WINS)
    mb = isinstance(r.get("mdd"), (int, float)) and r["mdd"] > M07["mdd"]
    if r.get("nbeat_m07", nb) != nb or bool(r.get("beat_all", ba)) != ba:
        mis.append((r.get("tag"), r.get("nbeat_m07"), nb, r.get("beat_all"), ba))
print("recompute mismatches:", mis if mis else "NONE")
cand = [r for r in rows if bool(r.get("beat_all")) or (isinstance(r.get("nbeat_m07"), int) and r["nbeat_m07"] >= 5)]
print(f"candidates (beat_all or nbeat>=5): {len(cand)}")
for r in cand:
    diff = {w: round(r[w] - M07[w], 2) for w in WINS}
    print("CAND", r.get("tag"), r.get("kind"), "total=", r.get("total"), "mdd=", r.get("mdd"),
          "nbeat=", r.get("nbeat_m07"), "beat=", r.get("beat_all"), "win=", r.get("win_all"),
          "trades=", r.get("trades"), "cost=", r.get("cost"), "switches=", r.get("switches"))
    print("  six-win diff vs M07:", diff, "total gap:", round(r.get("total", 0) - M07["total"], 2),
          "mdd gap:", round(r.get("mdd", 0) - M07["mdd"], 2))
    print("  params:", json.dumps(r.get("params", {}), ensure_ascii=False)[:800])
    print("  switch_same_m07:", r.get("switch_same_m07"), "switch_log:", json.dumps(r.get("switch_log", []), ensure_ascii=False)[:400])
ranked = sorted(rows, key=lambda r: (r.get("nbeat_m07", -1) if isinstance(r.get("nbeat_m07"), int) else -1,
                                      r.get("total", -1e18) if isinstance(r.get("total"), (int, float)) else -1e18), reverse=True)
print("TOP5 by (nbeat,total):")
for r in ranked[:5]:
    print("  ", r.get("tag"), r.get("kind"), "nbeat=", r.get("nbeat_m07"), "total=", r.get("total"),
          "mdd=", r.get("mdd"), "beat=", r.get("beat_all"))
json.dump({"n": len(rows), "ncand": len(cand),
           "cand_tags": [r.get("tag") for r in cand],
           "top5": [r.get("tag") for r in ranked[:5]],
           "mismatches": mis},
          open("team/audit/batch_019/part_k5scan.json", "w"), ensure_ascii=False, indent=1)
print("saved team/audit/batch_019/part_k5scan.json")
