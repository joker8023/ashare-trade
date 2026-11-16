import json, sys
from pathlib import Path
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"research"))
import sweep_beat_m07_k7 as K7
WINS = ["1m","3m","6m","1y","2y","3y"]
M07 = json.load(open("results/r30_bt/M07_final.json"))
F = json.load(open("results/r30_bt/sweep_beat_m07_k7.json"))
F = {x["tag"]: x for x in (F if isinstance(F, list) else F.get("rows", []))}
CFGMAP = {c["tag"]: {k: v for k, v in c.items() if k != "tag"} for c in K7.CFGS}
print("CFGS:", sorted(CFGMAP.keys()), "PHASE1:", K7.PHASE1, "PHASE2:", K7.PHASE2)
repro = {}
for tag in ["g_bf080", "g_bf085", "m07_bf07"]:
    r = K7.run_one(tag, **CFGMAP[tag])
    f = F[tag]
    devs = {}
    for k in ["total","mdd","trades","cost","switches","brakes"] + WINS:
        a, b = r[k], f[k]
        devs[k] = round(abs(a-b), 2) if isinstance(a,(int,float)) else (a != b)
    maxdev = max(v for v in devs.values() if isinstance(v,(int,float)))
    repro[tag] = {"devs": devs, "maxdev": maxdev,
                  "mode_same": r["mode"] == f["mode"],
                  "switch_same": r["switch_log"] == f["switch_log"],
                  "brake_same": r["brake_log"] == f["brake_log"],
                  "nbeat_same": r["nbeat_m07"] == f["nbeat_m07"]}
    print(tag, "maxdev=", maxdev, "mode:", r["mode"], f["mode"], "nbeat:", r["nbeat_m07"], f["nbeat_m07"])
# cross-file: m07_bf07 vs K1 k01_bf07
K1 = json.load(open("results/r30_bt/sweep_beat_m07_k1.json"))
K1 = K1 if isinstance(K1, list) else K1.get("rows", [])
k01 = [x for x in K1 if x.get("tag") == "k01_bf07"][0]
mf = F["m07_bf07"]
print("m07_bf07==k01_bf07:", {k: (mf.get(k), k01.get(k)) for k in ["total","mdd","trades","cost","1m","3m","6m","1y","2y","3y","nbeat_m07"]})
# K3 g row (bf0.6) for axis table
K3 = json.load(open("results/r30_bt/sweep_beat_m07_k3.json"))
K3 = K3 if isinstance(K3, list) else K3.get("rows", [])
for t in ["g", "g_bf05", "g_bf07"]:
    hit = [x for x in K3 if x.get("tag") == t]
    print(t, {k: (hit[0].get(k) if hit else None) for k in ["total","mdd","nbeat_m07","1m","3m","6m","1y","2y","3y"]} if hit else "MISSING")
# PHASE2 gate
print("gate g_bf080 nbeat:", F["g_bf080"]["nbeat_m07"], "phase2_in_file:", [t for t in K7.PHASE2 if t in F])
Path("team/audit/batch_021_m07k7/part_k7deep.json").write_text(json.dumps({"repro": repro}, indent=1, ensure_ascii=False))
print("saved part_k7deep.json")
