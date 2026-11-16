#!/usr/bin/env python3
"""batch_054 K22 verification (reviewer agent-63).
Reads: results/r30_bt/attrib_k22.json (sibling R43),
       this-dir part_054_k22recompute.json + eq/trades slim files (independent).
Checks:
  V1 Top3 gap-month monthly diffs |dK22 - dMine| < 0.05pp (also base/cand rets).
  V2 switch/brake event lists == independent meta logs filtered to month (exact).
  V3 holdings identity sets (base_only/cand_only/shared) == active-code sets
     derived from independent slim trades (entry<=m_end & exit>=m_start).
  V4 top-driver realized rows (code/exit/shares/px/net_pnl/reason) match slim
     trades (net_pnl tol 0.15 yuan, shares/px/reason exact).
  V5 resid_check actuals == equity deltas from independent eq pickles (tol 5 yuan).
Output: part_054_k22verify.json (this dir only). Exit nonzero on any FAIL.
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
K22 = json.load(open(ROOT/"results"/"r30_bt"/"attrib_k22.json"))
MINE = json.load(open(OUT/"part_054_k22recompute.json"))
import pandas as pd
eqM = pd.read_pickle(OUT/"eq_legM.pkl"); eqK = pd.read_pickle(OUT/"eq_legK.pkl")
trM = json.load(open(OUT/"trades_legM_slim.json"))
trK = json.load(open(OUT/"trades_legK_slim.json"))
mm = {r["month"]: r for r in MINE["monthly"]}
res = {"checks": [], "ok": True}
def chk(name, ok, detail=""):
    res["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
    if not ok:
        res["ok"] = False
    print(("PASS " if ok else "FAIL ") + name + (" | "+str(detail) if detail else ""), flush=True)

# V0 file-level sanity
chk("V0_gap2y", abs(K22["meta"]["gap_2y_pp"] - MINE["gap_2y_pp"]) < 1e-9,
    "k22=%s mine=%s" % (K22["meta"]["gap_2y_pp"], MINE["gap_2y_pp"]))
chk("V0_calib", K22["meta"]["calib"]["base_all_windows_eq_M07_final"] is True
    and abs(K22["meta"]["calib"]["cand_2y_eq_k21_file"] - 1367.88) < 1e-9)

swM = MINE["meta"]["M"]["switch_log"]; swK = MINE["meta"]["K"]["switch_log"]
brM = MINE["meta"]["M"]["brake_log"]; brK = MINE["meta"]["K"]["brake_log"]

def active(tr, m):
    return {t["code"] for t in tr if t["entry"] <= m+"-31" and t["exit"] >= m+"-01"}

for i, a in enumerate(K22["top3_gap_months"]):
    m = a["month"]
    mine = mm.get(m)
    chk("V1_%s_in_window" % m, mine is not None, "diff k22=%s" % a["diff_pp"])
    if mine is None:
        continue
    chk("V1_%s_diff" % m, abs(a["diff_pp"] - mine["diff_pp"]) < 0.05,
        "k22=%.4f mine=%.4f err=%.4f" % (a["diff_pp"], mine["diff_pp"], abs(a["diff_pp"]-mine["diff_pp"])))
    chk("V1_%s_base" % m, abs(a["base_ret"] - mine["m07_ret"]) < 0.05,
        "k22=%s mine=%s" % (a["base_ret"], mine["m07_ret"]))
    chk("V1_%s_cand" % m, abs(a["cand_ret"] - mine["k_ret"]) < 0.05,
        "k22=%s mine=%s" % (a["cand_ret"], mine["k_ret"]))
    # V2 events
    e_swM = [x for x in swM if x[0][:7] == m]; e_swK = [x for x in swK if x[0][:7] == m]
    e_brM = [x for x in brM if x[0][:7] == m]; e_brK = [x for x in brK if x[0][:7] == m]
    chk("V2_%s_switch" % m,
        [[str(d), str(x)] for d, x in a["switches"]["base"]] == [[str(d), str(x)] for d, x in e_swM]
        and [[str(d), str(x)] for d, x in a["switches"]["cand"]] == [[str(d), str(x)] for d, x in e_swK],
        "base=%s cand=%s" % (e_swM, e_swK))
    chk("V2_%s_brake" % m,
        [list(x) for x in a["brakes"]["base"]] == [list(x) for x in e_brM]
        and [list(x) for x in a["brakes"]["cand"]] == [list(x) for x in e_brK],
        "base=%s cand=%s" % (e_brM, e_brK))
    # V3 holdings identity sets
    aM, aK = active(trM, m), active(trK, m)
    h = a["holdings"]
    chk("V3_%s_sets" % m,
        set(h["base_only"]) == (aM - aK) and set(h["cand_only"]) == (aK - aM)
        and set(h["shared"]) == (aM & aK),
        "base_only k22=%d mine=%d; cand_only k22=%d mine=%d; shared k22=%d mine=%d" % (
            len(h["base_only"]), len(aM-aK), len(h["cand_only"]), len(aK-aM),
            len(h["shared"]), len(aM & aK)))
    # V4 driver realized rows
    okv = True; det = []
    for drv in (a["gap_drivers_neg"] + a["gap_drivers_pos"]):
        for leg, tr in (("base", trM), ("cand", trK)):
            for rr in drv["realized"][leg]:
                hit = [t for t in tr if t["code"] == drv["code"] and t["exit"] == rr["exit"]
                         and abs(t["net_pnl"] - rr["net_pnl"]) < 0.15 and t["reason"] == rr["reason"]]
                if not hit:
                    okv = False; det.append("%s/%s/%s" % (drv["code"], leg, rr["exit"]))
    chk("V4_%s_drivers" % m, okv, "; ".join(det[:6]) if det else "%d drivers all matched" % (len(a["gap_drivers_neg"])+len(a["gap_drivers_pos"])))
    # V5 equity deltas
    idxM = eqM.index; i0 = idxM.get_indexer([d for d in idxM if d.strftime("%Y-%m") == m][0:1])
    days = [d for d in idxM if d.strftime("%Y-%m") == m]
    dM = float(eqM[days[-1]] - eqM[idxM[idxM.get_loc(days[0])-1]] if idxM.get_loc(days[0]) > 0 else eqM[days[-1]])
    daysK = [d for d in eqK.index if d.strftime("%Y-%m") == m]
    dK = float(eqK[daysK[-1]] - eqK[eqK.index[eqK.index.get_loc(daysK[0])-1]] if eqK.index.get_loc(daysK[0]) > 0 else eqK[daysK[-1]])
    rc = a["resid_check"]
    chk("V5_%s_resid" % m, abs(rc["base_actual"] - dM) < 5 and abs(rc["cand_actual"] - dK) < 5,
        "base k22=%s mine=%.1f; cand k22=%s mine=%.1f" % (rc["base_actual"], dM, rc["cand_actual"], dK))

res["k22_top3"] = [(a["month"], a["diff_pp"]) for a in K22["top3_gap_months"]]
res["mine_top3neg"] = MINE["top3_neg"]
res["top3_order_match"] = [a["month"] for a in K22["top3_gap_months"]] == MINE["top3_neg"]
json.dump(res, open(OUT/"part_054_k22verify.json", "w"), ensure_ascii=False, indent=1)
print("TOP3_ORDER_MATCH:", res["top3_order_match"])
print("SAVED part_054_k22verify.json ok=", res["ok"])
sys.exit(0 if res["ok"] else 1)
