import json, glob, re
from pathlib import Path
ROOT = Path.cwd()
M07 = json.load(open(ROOT/"results/r30_bt/M07_final.json"))
WINS = ["1m","3m","6m","1y","2y","3y"]
M = {w: M07[w] for w in WINS}
files = sorted(glob.glob(str(ROOT/"results/r30_bt/sweep_beat_m07_k*.json")))
allrows, per = [], {}
for f in files:
    d = json.load(open(f))
    rows = d if isinstance(d, list) else d.get("rows", d.get("results", []))
    per[Path(f).name] = len(rows)
    for x in rows:
        x = dict(x); x["_file"] = Path(f).name; allrows.append(x)
base_rows = [x for x in allrows if str(x.get("tag","")).startswith("base")]
new_rows = [x for x in allrows if not str(x.get("tag","")).startswith("base")]
def nb(x):
    return sum(1 for w in WINS if isinstance(x.get(w),(int,float)) and x[w] > M[w] + 1e-12)
mis = 0
for x in allrows:
    r_nb = nb(x)
    key = "nbeat_m07" if "nbeat_m07" in x else "nbeat"
    if x.get(key) != r_nb: mis += 1
    x["_re_nbeat"] = r_nb
    x["_re_beat"] = (r_nb == 6)
    x["_re_mddb"] = (x.get("mdd", 0) > M07["mdd"] + 1e-12)
    x["_re_win"] = x["_re_beat"] and x["_re_mddb"]
beat = [x for x in allrows if x["_re_beat"]]
cand = [x for x in new_rows if x["_re_beat"] or x["_re_nbeat"] >= 5]
bfpat = re.compile(r"bf[_\- ]?(0?\.\d+|\d+)", re.I)
def bfval(x):
    m = bfpat.search(str(x.get("tag","")) + " " + str(x.get("params","")))
    if not m: return None
    try:
        v = float(m.group(1)); return v if v < 2 else v/100.0
    except Exception: return None
bfrows = [(bfval(x), x) for x in allrows if bfval(x) is not None]
bfrows.sort(key=lambda t: t[0])
out = {
    "m07": {"total": M07["total"], "mdd": M07["mdd"], **M},
    "per_file": per,
    "total_rows": len(allrows), "base_rows": len(base_rows), "new_cfgs": len(new_rows),
    "recomputed_mismatch": mis,
    "beat_all_recomputed": len(beat),
    "beat_tags": [(x["_file"], x.get("tag")) for x in beat],
    "candidates_ge5": [(x["_file"], x.get("tag"), x["_re_nbeat"]) for x in cand],
    "bf_axis": [{"bf": b, "file": x["_file"], "tag": x.get("tag"), "nbeat": x["_re_nbeat"], "total": x.get("total"), "mdd": x.get("mdd")} for b, x in bfrows],
}
Path("team/audit/batch_021_m07k7/part_k7scan.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(json.dumps({k: out[k] for k in ["per_file","total_rows","new_cfgs","recomputed_mismatch","beat_all_recomputed","beat_tags","candidates_ge5"]}, indent=1, ensure_ascii=False))
print("BF_AXIS:")
for rr in out["bf_axis"]: print(rr)
