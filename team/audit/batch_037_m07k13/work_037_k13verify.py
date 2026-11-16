"""batch_037 K13 mechanism verification (reviewer-executed).
1) rerun all 7 K13 rows via sweep_beat_m07_k13.run_one -> file compare;
2) base_M07 vs M07_final 12-key exact;
3) dyn_log margins recomputed from t-and-before shadow trailing-60 RS;
4) dly_log state-machine validation (pending->confirmed/cancelled, 2-consecutive).
Repro: .venv/bin/python team/audit/batch_037_m07k13/work_037_k13verify.py
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "team" / "audit")); sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import sweep_beat_m07_k13 as K13
from sweep_beat_h1_v4 import WINDOWS

M07 = json.load(open(ROOT / "results" / "r30_bt" / "M07_final.json"))
WINS = list(WINDOWS.keys())
rows = json.load(open(ROOT / "results" / "r30_bt" / "sweep_beat_m07_k13.json"))
file_by_tag = {r["tag"]: r for r in rows}
out = {"checks": {}}
# 1) rerun all rows via module
maxdev = 0; per = {}
for cfg in K13.CFGS:
    r = K13.run_one(cfg["tag"], cfg["combo"], cfg["mechanism"], cfg["legs"], cfg["thresh"], cfg["direction"])
    f = file_by_tag[cfg["tag"]]
    devs = {}
    for k in ["total", "mdd", "cost"] + WINS + [w + "_mdd" for w in WINS]:
        devs[k] = round(r[k] - f[k], 6)
        maxdev = max(maxdev, abs(devs[k]))
    meta_ok = all(r[k] == f[k] for k in ["trades", "mode", "switches", "brakes"])
    log_ok = (r["switch_log"] == f["switch_log"]) and (r.get("dyn_log") == f.get("dyn_log"))
    per[cfg["tag"]] = {"maxdev": max(abs(v) for v in devs.values()), "meta_ok": meta_ok, "log_ok": log_ok,
                         "nbeat": r["nbeat_m07"], "beat_all": r["beat_all"], "mdd_better": r["mdd_better"],
                         "switch_same_m07": r["switch_same_m07"], "switch_log": r["switch_log"]}
out["checks"]["rerun_maxdev"] = maxdev
out["checks"]["rerun_per_row"] = per
# 2) base vs M07
b = file_by_tag["base_M07"]
out["checks"]["base_dev"] = {k: b[k] - M07[k] for k in ["total", "mdd"] + WINS}
# 3) dyn margins recompute from shadows (t-and-before only)
_, ra, _ = K13.get_shadow("M07", "A", 5, 20, 1.2, 1.0)
_, rb, _ = K13.get_shadow("M07", "B", 4, 30, 0.80, 0.9)
ea, eb = ra.eq, rb.eq
def rs(eq, T):
    j = int(eq.index.searchsorted(T, side="right") - 1)
    return float(eq.iloc[j] / eq.iloc[j - 60] - 1.0)
dyn = {}
for tag in ["k13_dynT05_B", "k13_dynT05_both", "k13_dynT10_B", "k13_dynT10_both"]:
    f = file_by_tag[tag]
    T = float(tag[8:10]) / 100 if "T05" in tag else 0.10
    legs = "both" if tag.endswith("both") else "B"
    worst = 0; rule_bad = []
    for d, na, nb, m in f["dyn_log"]:
        Ts = pd.Timestamp(d)
        recom = abs(rs(ea, Ts) - rs(eb, Ts))
        worst = max(worst, abs(recom - m))
        exp = 3 if recom > T else 5
        chk = (nb == exp) if legs == "B" else (na == exp and nb == exp)
        if legs == "B" and na != 5:
            chk = False
        if not chk:
            rule_bad.append([d, na, nb, m, round(recom, 4)])
    dyn[tag] = {"n_log": len(f["dyn_log"]), "n_conc": f["n_conc"], "margin_maxdev": worst, "rule_violations": rule_bad}
out["checks"]["dyn"] = dyn
# 4) dly state machine: rebuild KW like run_one, keep meta.dly_log
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import MB, RUN_START, EVAL_END
piv = K13.piv; dates = K13.dates; first_sig = K13.first_sig
dly = {}
for tag, direction in [("k13_dly_enterB", "enterB"), ("k13_dly_exitB", "exitB")]:
    inp_a, ra2, CA = K13.get_shadow("M07", "A", 5, 20, 1.2, 1.0)
    inp_b, rb2, _CB = K13.get_shadow("M07", "B", 4, 30, 0.80, 0.9)
    CFG_B = dict(n=4, rebal=30, take=0.80, exposure=0.9)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra2.eq, shadow_b=rb2.eq, rs_lookback=60, exclude_a=MB, exclude_b=MB, factor="amihud_60", **{k: v for k, v in CA.items() if k not in ("exclude", "factor")})
    res = K13.NS_DLY(direction)["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    log = [list(x) for x in res.meta["dly_log"]]
    # validate: confirmed only after pending same dir; pending only on delayed votes; cancel only clears outstanding pend
    pend = None; bad = []
    for d, raw, act in log:
        if act == "pending":
            if pend is not None:
                bad.append([d, raw, act, "pending-while-pending"])
            pend = raw
        elif act == "confirmed":
            if pend != raw:
                bad.append([d, raw, act, "confirm-without-pend"])
            pend = None
        elif act == "cancelled":
            if pend is None:
                bad.append([d, raw, act, "cancel-without-pend"])
            pend = None
    dly[tag] = {"n_log": len(log), "bad": bad,
                "counts": {"pending": sum(1 for x in log if x[2] == "pending"), "confirmed": sum(1 for x in log if x[2] == "confirmed"), "cancelled": sum(1 for x in log if x[2] == "cancelled")},
                "log": log}
out["checks"]["dly"] = dly
open(ROOT / "team" / "audit" / "batch_037_m07k13" / "part_037_k13verify.json", "w").write(json.dumps(out, ensure_ascii=False, indent=1, default=str))
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
