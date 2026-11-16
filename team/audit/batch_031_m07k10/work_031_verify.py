"""batch_031: K10 composite sweep independent file-level verification.
Writes part_031_verify.json. No engine rerun; strict > vs M07_final."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RES = ROOT / "results" / "r30_bt"
M07F = json.loads((RES / "M07_final.json").read_text())
K10 = json.loads((RES / "sweep_beat_m07_k10.json").read_text())
WINS = ["1m", "3m", "6m", "1y", "2y", "3y"]
M07 = {w: M07F[w] for w in WINS} | {"mdd": M07F["mdd"], "total": M07F["total"]}

out = {"m07_ref": M07, "rows": [], "mismatch": [], "base_check": {},
       "dedup": {}, "trigger_set": []}
for r in K10:
    nb = sum(1 for w in WINS if r[w] > M07F[w])
    ba = all(r[w] > M07F[w] for w in WINS)
    mb = r["mdd"] > M07F["mdd"]
    wa = bool(ba and mb)
    ok = (nb == r["nbeat_m07"] and ba == r["beat_all"]
          and mb == r["mdd_better"] and wa == r["win_all"])
    if not ok:
        out["mismatch"].append(r["tag"])
    out["rows"].append({"tag": r["tag"], "selector": r["selector"],
        "legs": r["legs"], "total": r["total"], "mdd": r["mdd"],
        "wins": [r[w] for w in WINS], "nbeat_re": nb,
        "beat_re": ba, "mdd_better_re": mb, "win_all_re": wa,
        "trades": r["trades"], "switches": r["switches"],
        "switch_same_m07": r["switch_same_m07"], "match": ok})
    if ba or nb >= 4:
        out["trigger_set"].append(r["tag"])

base = next(r for r in K10 if r["tag"] == "base_M07")
bc = {}
for k in ["total", "mdd", "trades", *WINS]:
    bc[k] = {"file": base[k], "m07": M07F[k],
             "dev": round(base[k] - M07F[k], 6)}
bc["switch_log"] = (base["switch_log"] == M07F["switch_log"])
bc["brake_log"] = (base["brake_log"] == M07F["brake_log"])
bc["all_zero"] = all(v["dev"] == 0 for k, v in bc.items()
                       if isinstance(v, dict) and "dev" in v) and bc["switch_log"] and bc["brake_log"]
out["base_check"] = bc

seen = {}
for fn in [f"sweep_beat_m07_k{i}.json" for i in range(1, 10)]:
    p = RES / fn
    if p.exists():
        for r in json.loads(p.read_text()):
            seen.setdefault(r.get("tag"), fn)
new_tags = [r["tag"] for r in K10 if r["tag"] != "base_M07"]
out["dedup"] = {"new_n": len(new_tags),
    "overlap": [t for t in new_tags if t in seen], "overlap_n": 0,
    "k10_files_expected_rows": 7, "actual_rows": len(K10)}
out["dedup"]["overlap"] = [t for t in new_tags if t in seen]
out["dedup"]["overlap_n"] = len(out["dedup"]["overlap"])
out["summary"] = {
    "beat_all_n": sum(1 for r in K10 if r["beat_all"]),
    "max_nbeat_new": max(r["nbeat_m07"] for r in K10 if r["tag"] != "base_M07"),
    "mdd_better_new": [r["tag"] for r in K10
                         if r["tag"] != "base_M07" and r["mdd_better"]],
    "win_all_n": sum(1 for r in K10 if r["win_all"]),
    "trigger_n": len(out["trigger_set"])}

(ROOT / "team" / "audit" / "batch_031_m07k10" / "part_031_verify.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out["summary"], ensure_ascii=False))
print("mismatch:", out["mismatch"])
print("base_all_zero:", bc["all_zero"])
print("dedup_overlap:", out["dedup"]["overlap"])
for r in out["rows"]:
    print(r["tag"], r["total"], r["mdd"], r["wins"], "nbeat=", r["nbeat_re"],
          "beat=", r["beat_re"], "mdd_better=", r["mdd_better_re"], "match=", r["match"])
