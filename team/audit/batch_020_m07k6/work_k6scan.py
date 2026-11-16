"""K6 full-file scan: recompute nbeat/beat_all/win_all/mdd_better + base dev vs M07_final."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
M07 = json.load(open(ROOT/"results"/"r30_bt"/"M07_final.json"))
W = ["1m","3m","6m","1y","2y","3y"]
rows = json.load(open(ROOT/"results"/"r30_bt"/"sweep_beat_m07_k6.json"))
out = {"n": len(rows), "base_dev": {}, "mismatches": [], "rows": []}
for r in rows:
    nb = sum(1 for w in W if r[w] > M07[w])
    ba = all(r[w] > M07[w] for w in W)
    mb = r["mdd"] > M07["mdd"]
    wa = bool(ba and mb)
    if (nb, ba, mb, wa) != (r["nbeat_m07"], r["beat_all"], r["mdd_better"], r["win_all"]):
        out["mismatches"].append(r["tag"])
    if r["tag"] == "base_M07":
        out["base_dev"] = {w: round(r[w]-M07[w],2) for w in W} | {"total": round(r["total"]-M07["total"],2), "mdd": round(r["mdd"]-M07["mdd"],2)}
    out["rows"].append({"tag": r["tag"], "factor_a": r.get("factor_a"), "factor_b": r.get("factor_b"),
        "cut_a": r.get("cut_a"), "cut_b": r.get("cut_b"), "total": r["total"], "mdd": r["mdd"],
        "trades": r["trades"], "cost": r["cost"], "mode": r["mode"], "switches": r["switches"],
        "nbeat": nb, "beat": ba, "mdd_b": mb, "win": wa, "same": r["switch_same_m07"],
        "d": [round(r[w]-M07[w],2) for w in W]})
new = [x for x in out["rows"] if x["tag"] != "base_M07"]
out["max_nbeat_new"] = max(x["nbeat"] for x in new)
out["n_beat_all"] = sum(1 for x in out["rows"] if x["beat"])
out["n_win_all"] = sum(1 for x in out["rows"] if x["win"])
open(Path(__file__).parent/"part_k6scan.json","w").write(json.dumps(out, ensure_ascii=False, indent=1))
print("rows:", out["n"], "mismatches:", out["mismatches"] or "NONE", "base_dev:", out["base_dev"])
print("max_nbeat_new:", out["max_nbeat_new"], "beat_all:", out["n_beat_all"], "win_all:", out["n_win_all"])
for x in sorted(new, key=lambda z: -z["nbeat"]):
    print(x["tag"], "nbeat", x["nbeat"], "total", x["total"], "mdd", x["mdd"], "d", x["d"], "same", x["same"])
