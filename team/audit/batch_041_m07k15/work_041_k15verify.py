#!/usr/bin/env python3
"""Batch 041 verify: K15 dual-calib and flag recompute."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
M07_TOTAL = 1863.27
M07_MDD = -27.05
M07W = {"1m": -4.09, "3m": 17.28, "6m": 39.0, "1y": 164.05, "2y": 1474.08, "3y": 1677.53}
WINDOWS = ["1m", "3m", "6m", "1y", "2y", "3y"]
rows = json.loads((ROOT / "results" / "r30_bt" / "sweep_beat_m07_k15.json").read_text())
m07f = json.loads((ROOT / "results" / "r30_bt" / "M07_final.json").read_text())
k3 = json.loads((ROOT / "results" / "r30_bt" / "sweep_beat_m07_k3.json").read_text())
gk3 = [r for r in k3 if r.get("tag") == "g_bf07"]
print("K3 g_bf07 rows: " + str(len(gk3)))
print("M07_final total/mdd: " + str(m07f["total"]) + " / " + str(m07f["mdd"]))
print("K15 nrows: " + str(len(rows)))
m = {r["tag"]: r for r in rows}
for r in rows:
    wins = [w for w in WINDOWS if r[w] > M07W[w]]
    print(r["tag"] + " total=" + str(r["total"]) + " mdd=" + str(r["mdd"]) + " nbeat=" + str(r["nbeat_m07"]) + " beat_all=" + str(r["beat_all"]) + " wins=" + str(wins))
keys8 = ["total", "mdd", "1m", "3m", "6m", "1y", "2y", "3y"]
dev1 = {}
for k in keys8:
    dev1[k] = round(abs(m["base_M07"][k] - m07f[k]), 4)
print("dev base_M07 vs M07_final: " + json.dumps(dev1))
dev2 = {}
for k in keys8:
    dev2[k] = round(abs(m["base_gbf07"][k] - gk3[0][k]), 4)
print("dev base_gbf07 vs K3: " + json.dumps(dev2))
gate = max(list(dev1.values()) + list(dev2.values()))
ok_calib = not (gate > 0.01)
print("GATE maxdev=" + str(gate) + " pass=" + str(ok_calib))
allmatch = True
for r in rows:
    nb = sum(1 for w in WINDOWS if r[w] > M07W[w])
    ba = all(r[w] > M07W[w] for w in WINDOWS)
    mb = r["mdd"] > M07_MDD
    ok = (nb == r["nbeat_m07"] and ba == r["beat_all"] and mb == r["mdd_better"])
    allmatch = allmatch and ok
    print(r["tag"] + " re_nbeat=" + str(nb) + " re_beat=" + str(ba) + " re_mddb=" + str(mb) + " " + ("MATCH" if ok else "MISMATCH"))
print("flag allmatch: " + str(allmatch))
trig = [r["tag"] for r in rows if r["tag"].startswith("k15_") and (r["beat_all"] or r["nbeat_m07"] >= 4)]
print("TRIGGER_SET: " + str(trig))
print("beat_all count: " + str(sum(1 for r in rows if r["beat_all"])))
REF_SWITCH = [["2023-06-21", "B"], ["2024-08-15", "A"], ["2026-09-08", "B"]]
for r in rows:
    print(r["tag"] + " switch_same=" + str(r["switch_log"] == REF_SWITCH))
src = (ROOT / "research" / "sweep_beat_m07_k15.py").read_text()
print("lookahead shift count: " + str(src.count("shift(-"))) 
print("searchsorted count: " + str(src.count("searchsorted")))
hits = [l.strip() for l in src.splitlines() if (".iloc[" in l or ".loc[" in l)]
print("iloc-loc hits: " + str(len(hits)))
for h in hits:
    print("    " + h[:150])
out = {"dual_calib": {"base_M07_vs_M07_final": dev1, "base_gbf07_vs_K3": dev2, "gate": 0.01, "pass": ok_calib}, "flag_recompute_match": allmatch, "trigger_set": trig, "beat_all_count": sum(1 for r in rows if r["beat_all"]), "nrows": len(rows)}
outp = ROOT / "team" / "audit" / "batch_041_m07k15" / "part_041_k15verify.json"
outp.write_text(json.dumps(out, ensure_ascii=False, indent=1))
print("wrote part_041_k15verify.json")