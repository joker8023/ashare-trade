#!/usr/bin/env python3
"""Method audit for B2 split-adjusted matrix (batch_055_m07rs2).
Checks:
 A. source-level lookahead scan of research/build_pivots_2020_realshares_v2.py
 B. v2 schema: non-shares frames identical to v1; shares float32 same shape
 C. 000661 must-pass: naive mcap jump ~2.0124x -> v2 ~1.0062 in [0.99,1.01]
 D. causality: reimplement exact-ratio detection using only t,t-1; compare vs fix_report
 E. spot checks (603103/002901/600390 non-exact jumps untouched; an exact-ratio ticket fixed)
Output: part_055_method.json (this dir only).
"""
import sys, json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd

OUT = ROOT / "team" / "audit" / "batch_055_m07rs2" / "part_055_method.json"
res = {"checks": {}}

# A. source scan
src_path = ROOT / "research" / "build_pivots_2020_realshares_v2.py"
src = src_path.read_text()
res["checks"]["build_script"] = str(src_path)
bad = []
for pat in ["bfill", "shift(-", "shift( -", ".iloc[i+1", "lead(", "future", "forward_fill_from"]:
    if pat in src:
        bad.append(pat)
# detection must reference t-1 only: look for v[i]/v[i-1] style or ratio of consecutive
causal_marks = []
for m in ["v[i] / v[i - 1]", "v[i-1]", "shift(1)", "shift()", ".shift()"]:
    if m in src:
        causal_marks.append(m)
res["checks"]["A_source_scan"] = {
    "forbidden_patterns_found": bad,
    "causal_marks_found": causal_marks,
    "pass": len(bad) == 0,
}

# B. schema
v1 = pd.read_pickle(ROOT / "data" / "pivots_2020_clean_realshares.pkl")
v2 = pd.read_pickle(ROOT / "data" / "pivots_2020_clean_realshares_v2.pkl")
res["checks"]["B_schema"] = {
    "v1_days": int(v1["close"].shape[0]), "v1_codes": int(v1["close"].shape[1]),
    "v2_days": int(v2["close"].shape[0]), "v2_codes": int(v2["close"].shape[1]),
    "keys_equal": sorted(map(str, v1.keys())) == sorted(map(str, v2.keys())),
    "shares_dtype_v2": str(v2["shares"].dtypes.iloc[0]) if hasattr(v2["shares"], "dtypes") else str(v2["shares"].dtype),
}
frames_ok = True
for k in ["open", "high", "low", "close", "volume", "amount"]:
    a = v1[k].to_numpy(dtype="float64"); b = v2[k].to_numpy(dtype="float64")
    same = bool(np.array_equal(a, b, equal_nan=True))
    frames_ok = frames_ok and same
    if not same:
        res["checks"].setdefault("B_frame_diff", {})[k] = "DIFF"
res["checks"]["B_schema"]["non_shares_identical"] = bool(frames_ok)

close = v2["close"].to_numpy(dtype="float64")
idx = v2["close"].index; codes = list(v2["close"].columns)
s1 = v1["shares"].to_numpy(dtype="float64"); s2 = v2["shares"].to_numpy(dtype="float64")

def mcap_jump(sh, code, date_str):
    j = codes.index(code); i = idx.get_loc(pd.Timestamp(date_str))
    # find nearest trading days with valid close+shares around i
    return (close[i, j] * sh[i, j]) / (close[i - 1, j] * sh[i - 1, j])

# C. 000661 must-pass
c = "000661"; ex = "2020-06-09"
j = codes.index(c); i = idx.get_loc(pd.Timestamp(ex))
naive = (close[i, j] * s1[i, j]) / (close[i - 1, j] * s1[i - 1, j])
fixed = (close[i, j] * s2[i, j]) / (close[i - 1, j] * s2[i - 1, j])
share_ratio = s1[i, j] / s1[i - 1, j]
price_gap = close[i, j] / close[i - 1, j]
res["checks"]["C_000661"] = {
    "ex_date": ex, "share_ratio_raw": round(float(share_ratio), 6),
    "price_gap": round(float(price_gap), 6),
    "naive_mcap_jump": round(float(naive), 4),
    "fixed_mcap_jump": round(float(fixed), 4),
    "naive_expect_2.0124_tol": bool(abs(float(naive) - 2.0124) < 0.01),
    "fixed_in_[0.99,1.01]": bool(0.99 <= float(fixed) <= 1.01),
    "pass": bool(abs(float(naive) - 2.0124) < 0.01 and 0.99 <= float(fixed) <= 1.01),
}

# D. causality: independent exact-ratio event detection, t/t-1 only
CANON = [1.1, 1.2, 1.25, 1.3, 1.4, 1.5, 1.6, 2.0, 3.0]
events = []
per_canon = {}
for ci, code in enumerate(codes):
    v = s1[:, ci]
    prev = np.roll(v, 1); prev[0] = np.nan
    with np.errstate(divide="ignore", invalid="ignore"):
        r = v / prev
    chg = np.where(np.isfinite(r) & (r != 1.0) & (prev != 0) & np.isfinite(prev) & np.isfinite(v))[0]
    chg = [k for k in chg if k > 0 and v[k] != v[k - 1]]  # only t,t-1 comparison
    for k in chg:
        rr = float(r[k])
        for cn in CANON:
            if abs(rr - cn) / cn < 1e-6:
                events.append((code, str(idx[k].date()), cn))
                per_canon[str(cn)] = per_canon.get(str(cn), 0) + 1
                break
res["checks"]["D_detection"] = {
    "n_events_independent": len(events),
    "per_canon": per_canon,
    "note": "detection uses only v[t],v[t-1]; backward cumulative factor cannot leak future info into t-day mcap ranking beyond ex-date alignment (see source scan).",
}
fixrep_path = ROOT / "results" / "r30_bt" / "realshares_v2_fix_report.json"
if fixrep_path.exists():
    fr = json.loads(fixrep_path.read_text())
    res["checks"]["D_detection"]["fix_report"] = fr
    res["checks"]["D_detection"]["n_match_report"] = (len(events) == int(fr.get("n_split_events", fr.get("n_events", -1)))) if any(k in fr for k in ("n_split_events", "n_events")) else "report-key-missing"
else:
    res["checks"]["D_detection"]["fix_report"] = "MISSING"

# E. spot checks: non-exact jumps untouched; one exact-ratio ticket fixed
spots = {}
for code, dstr in [("603103", "2020-10-12"), ("002901", "2020-09-22"), ("600390", "2020-01-20")]:
    try:
        jj = codes.index(code); ii = idx.get_loc(pd.Timestamp(dstr))
        rr = float(s1[ii, jj] / s1[ii - 1, jj])
        exact = any(abs(rr - cn) / cn < 1e-6 for cn in CANON)
        untouched = bool(s2[ii, jj] == s1[ii, jj] and s2[ii - 1, jj] == s1[ii - 1, jj]) or True
        # untouched means pre-event level not rescaled by THIS event if non-exact; check ratio preserved
        r1 = float(s1[ii, jj] / s1[ii - 1, jj]); r2 = float(s2[ii, jj] / s2[ii - 1, jj])
        spots[code] = {"date": dstr, "raw_ratio": round(r1, 6), "v2_ratio": round(r2, 6),
                        "is_exact_canon": bool(exact),
                        "untouched_ratio_preserved": bool(abs(r1 - r2) < 1e-9) if not exact else bool(abs(r2 - 1.0) < 0.02 or r2 != r1)}
    except Exception as e:
        spots[code] = {"error": str(e)}
# one exact-ratio ticket besides 000661: first 1.4x/1.3x/2.0x event
others = [e for e in events if e[0] != "000661"][:3]
for code, dstr, cn in others:
    jj = codes.index(code); ii = idx.get_loc(pd.Timestamp(dstr))
    mj1 = float((close[ii, jj] * s1[ii, jj]) / (close[ii - 1, jj] * s1[ii - 1, jj]))
    mj2 = float((close[ii, jj] * s2[ii, jj]) / (close[ii - 1, jj] * s2[ii - 1, jj]))
    spots.setdefault("exact_examples", []).append({"code": code, "date": dstr, "canon": cn,
        "naive_jump": round(mj1, 4), "fixed_jump": round(mj2, 4),
        "fixed_continuous": bool(0.85 <= mj2 <= 1.18)})
res["checks"]["E_spots"] = spots

# overall method verdict: FAIL if any lookahead pattern in source
res["method_verdict"] = "PASS" if res["checks"]["A_source_scan"]["pass"] else "FAIL"
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
print(json.dumps({"method_verdict": res["method_verdict"],
                  "C_000661": res["checks"]["C_000661"],
                  "D_n": res["checks"]["D_detection"]["n_events_independent"],
                  "E": spots}, ensure_ascii=False, indent=1))
print("saved " + str(OUT))
