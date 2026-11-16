"""独立复算: inventory_k38.json vs BEAT_M07_SUMMARY.md \u00a71 (K1-K19)."""
import json, pathlib
ROOT = pathlib.Path("/Users/joker/coding/ashare-trade")
R = ROOT / "results" / "r30_bt"
inv = json.loads((R / "inventory_k38.json").read_text())
rows_by_k, base_by_k, new_by_k, maxnb_new, beat_ct, win_ct = {}, {}, {}, {}, {}, {}
all_new_tags, calib_rows = [], {}
for k in range(1, 20):
    d = json.loads((R / f"sweep_beat_m07_k{k}.json").read_text())
    rows = d if isinstance(d, list) else d.get("rows", [])
    rows_by_k[k] = len(rows)
    bases = [r for r in rows if r.get("tag") == "base_M07"]
    gbf = [r for r in rows if r.get("tag") == "base_gbf07"]
    new = [r for r in rows if r.get("tag") not in ("base_M07", "base_gbf07")]
    base_by_k[k] = (len(bases), len(gbf))
    new_by_k[k] = len(new)
    maxnb_new[k] = max([r.get("nbeat_m07", -1) for r in new], default=-1)
    maxnb_all = max([r.get("nbeat_m07", -1) for r in rows])
    beat_ct[k] = sum(1 for r in rows if r.get("beat_all") is True)
    win_ct[k] = sum(1 for r in rows if r.get("win_all") is True)
    all_new_tags += [r["tag"] for r in new]
    calib_rows[k] = [r["tag"] for r in rows if r.get("tag") in ("base_M07", "base_gbf07")]
    print(f"K{k}: n={len(rows)} base_M07={len(bases)} base_gbf07={len(gbf)} new={len(new)} maxnb_new={maxnb_new[k]} maxnb_all={maxnb_all} beat={beat_ct[k]} win={win_ct[k]}")
print("TOTAL_ROWS =", sum(rows_by_k.values()))
print("TOTAL_NEW_EXCL_CALIB =", len(all_new_tags), "DISTINCT =", len(set(all_new_tags)))
from collections import Counter
print("DUP_NEW_TAGS =", [t for t, c in Counter(all_new_tags).items() if c > 1])
print("INV =", json.dumps(inv, ensure_ascii=False))
# base_M07 numeric identity
NUM = ["total","mdd","trades","cost","1m","1m_mdd","3m","3m_mdd","6m","6m_mdd","1y","1y_mdd","2y","2y_mdd","3y","3y_mdd","nbeat_m07","switches","brakes"]
b0 = None
for k in range(1, 20):
    d = json.loads((R / f"sweep_beat_m07_k{k}.json").read_text())
    b = next(r for r in d if r.get("tag") == "base_M07")
    if b0 is None: b0 = {kk: b[kk] for kk in NUM}
    assert {kk: b[kk] for kk in NUM} == b0, f"K{k} base numeric mismatch"
print("BASE_M07_NUMERIC_IDENTICAL_ALL_K: True")
# global best
best = None
for k in range(1, 20):
    d = json.loads((R / f"sweep_beat_m07_k{k}.json").read_text())
    for r in d:
        if best is None or r["total"] > best[2]: best = (k, r["tag"], r["total"], r["nbeat_m07"])
print("GLOBAL_BEST =", best)
# K1 tie / K8 detail
d1 = json.loads((R / "sweep_beat_m07_k1.json").read_text())
print("K1_TOP =", sorted([(r["tag"], r["total"], r["mdd"], r["nbeat_m07"]) for r in d1 if r.get("nbeat_m07") == 4], key=lambda x: -x[1]))
d8 = json.loads((R / "sweep_beat_m07_k8.json").read_text())
print("K8_WINROW =", [(r["tag"], r["total"], r["mdd"], r["nbeat_m07"], r["1m"], r["3m"]) for r in d8 if r["tag"] == "g_bf07_winA30"])
