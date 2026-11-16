"""batch_049: K19 independent recompute (auditor-run, output stays in this dir).
Imports research/sweep_beat_m07_k19 as a module (no writes at import) and
re-runs base_M07 + 6 R-grid rows via single_row(). Saves part json HERE.
Does NOT touch results/r30_bt/.
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import sweep_beat_m07_k19 as K19

M07 = K19.M07
out = {"m07_baseline": M07, "rows": [], "checks": {}}
# base calibration
base = K19.single_row("base_M07", K19.M07P, 0)
ok_cal = abs(base["total"]-M07["total"]) < 0.01 and abs(base["mdd"]-M07["mdd"]) < 0.01 and base["switch_log"] == K19.M07_SWITCH
out["checks"]["base_calib_exact"] = bool(ok_cal)
out["checks"]["base_row"] = {k: base[k] for k in ("tag","R","total","mdd","trades","cost","switches","1m","3m","6m","1y","2y","3y","nbeat_m07","beat_all","mdd_better","win_all","switch_same_m07")}
out["rows"].append(base)
for tag, params in K19.R_GRID_K19:
    r = K19.single_row(tag, params, 0)
    out["rows"].append(r)
    print(json.dumps({k: r[k] for k in ("tag","R","total","mdd","trades","cost","switches","top3_share","extop3_total","1m","3m","6m","1y","2y","3y","nbeat_m07","beat_all","mdd_better","win_all","switch_same_m07")}, ensure_ascii=False), flush=True)
# reasonableness: turnover/cost monotonic in R within each family arm
def fam(rows, a):
    return sorted([r for r in rows if r["params"]["a_rebal"]==a], key=lambda r: r["params"]["b_rebal"])
chk = {}
for a in (20, 60, 90, 120):
    fr = fam(out["rows"], a)
    if len(fr) >= 2:
        tr = [r["trades"] for r in fr]; co = [r["cost"] for r in fr]
        chk[f"armA{a}_trades_nonincr"] = bool(all(b<=a_ for a_,b in zip(tr, tr[1:])))
        chk[f"armA{a}_cost_nonincr"] = bool(all(b<=a_ for a_,b in zip(co, co[1:])))
        chk[f"armA{a}_tags"] = [(r["tag"], r["trades"], r["cost"], r["switches"]) for r in fr]
out["checks"].update(chk)
Path(__file__).with_name("part_049_k19.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print("SAVED part_049_k19.json rows=%d" % len(out["rows"]), flush=True)
