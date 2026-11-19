#!/usr/bin/env python3
"""Build data/pivots_2020_clean_realshares_v2.pkl (B2).

B1 artifact: close is split-ADJUSTED (qianfuquan) but shares are RAW
contemporaneous values, so naive mcap jumps at ex-div (000661: 2.0124x).
Fix on the SHARES side (prices kept bit-identical): scale pre-split history
up by the cumulative FORWARD split factor -> close_adj * adj_shares is
continuous across ex-div. Standard split-adjustment definition.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

SRC = ROOT / "data" / "pivots_2020_clean_realshares.pkl"
DST = ROOT / "data" / "pivots_2020_clean_realshares_v2.pkl"
REPORT = ROOT / "results" / "r30_bt" / "realshares_v2_fix_report.json"

CANON = [1.1, 1.2, 1.25, 1.3, 1.4, 1.5, 1.6, 2.0, 3.0]
TOL = 1e-6

piv = pd.read_pickle(SRC)
raw = piv["shares"]
close = piv["close"]
print("src: %d days x %d codes" % raw.shape, flush=True)

events = []
adj = raw.copy()
n_codes = raw.shape[1]
for j, code in enumerate(raw.columns):
    v = raw[code].to_numpy(dtype="float64")
    prev = np.roll(v, 1)
    chg = np.where((v != prev) & np.isfinite(v) & np.isfinite(prev) & (prev != 0.0))[0]
    chg = chg[chg > 0]
    fac = np.ones(len(v))
    for i in chg:
        r = v[i] / prev[i]
        for c in CANON:
            if abs(r - c) / c < TOL:
                fac[i] = c
                events.append((code, str(raw.index[i].date()), c, int(i)))
                break
    if (fac != 1.0).any():
        cum = np.ones(len(v))
        acc = 1.0
        for i in range(len(v) - 1, -1, -1):
            cum[i] = acc
            acc *= fac[i]
        col = v * cum
        col[np.isnan(v)] = np.nan
        adj[code] = col.astype("float32")
    if (j + 1) % 1000 == 0:
        print("  ... %d/%d codes, events=%d" % (j + 1, n_codes, len(events)), flush=True)
print("split events detected: %d" % len(events), flush=True)
# acceptance scan: mcap continuity at every detected event
naive_ratios, corr_ratios = [], []
for code, dstr, f, i in events:
    t = raw.index[i]
    t1 = raw.index[i - 1]
    p0, p1 = float(close.loc[t1, code]), float(close.loc[t, code])
    if not (np.isfinite(p0) and np.isfinite(p1) and p0 != 0):
        continue
    s0, s1 = float(raw.loc[t1, code]), float(raw.loc[t, code])
    a0, a1 = float(adj.loc[t1, code]), float(adj.loc[t, code])
    naive_ratios.append((p1 * s1) / (p0 * s0))
    corr_ratios.append((p1 * a1) / (p0 * a0))
naive_ratios = np.array(naive_ratios)
corr_ratios = np.array(corr_ratios)

# gate case 000661 ex-div 2020-06-09
GCODE, GDATE = "000661", "2020-06-09"
gi = int(raw.index.get_loc(GDATE))
gp0 = float(close.loc[raw.index[gi - 1], GCODE])
gp1 = float(close.loc[GDATE, GCODE])
gs0 = float(raw.loc[raw.index[gi - 1], GCODE])
gs1 = float(raw.loc[GDATE, GCODE])
ga0 = float(adj.loc[raw.index[gi - 1], GCODE])
ga1 = float(adj.loc[GDATE, GCODE])
gate = {
    "code": GCODE,
    "exdiv": GDATE,
    "price_gap": round(gp1 / gp0, 6),
    "share_ratio_raw": round(gs1 / gs0, 6),
    "mcap_ratio_naive": round((gp1 * gs1) / (gp0 * gs0), 6),
    "mcap_ratio_corrected": round((gp1 * ga1) / (gp0 * ga0), 6),
}
print("gate 000661: " + json.dumps(gate, ensure_ascii=False), flush=True)
assert 0.99 <= gate["mcap_ratio_corrected"] <= 1.01, gate
# distribution stats
codes_post2023 = sorted({c for c, d, f, i in events if d >= "2023-01-01"})
by_factor = {}
for c, d, f, i in events:
    by_factor[str(f)] = by_factor.get(str(f), 0) + 1
report = {
    "src": "data/pivots_2020_clean_realshares.pkl",
    "dst": "data/pivots_2020_clean_realshares_v2.pkl",
    "method": "exact-ratio split detection, causal t/t-1 only; backward cumulative forward-factor scaling of pre-split shares; non-exact jumps untouched; prices bit-identical to B1",
    "canon": CANON,
    "tol": TOL,
    "n_split_events": len(events),
    "events_by_factor": by_factor,
    "codes_with_events": len({c for c, d, f, i in events}),
    "codes_with_events_from_2023": len(codes_post2023),
    "gate_000661": gate,
    "gate_pass": True,
    "mcap_ratio_at_events": {
        "naive_median": round(float(np.median(naive_ratios)), 6),
        "naive_max": round(float(np.max(naive_ratios)), 6),
        "corrected_median": round(float(np.median(corr_ratios)), 6),
        "corrected_min": round(float(np.min(corr_ratios)), 6),
        "corrected_max": round(float(np.max(corr_ratios)), 6),
        "corrected_frac_in_099_101": round(float(np.mean((corr_ratios >= 0.99) & (corr_ratios <= 1.01))), 6),
    },
    "lookahead_note": "Detection uses only t/t-1 (causal). Backward factor propagation is the split-adjustment definition itself, synchronous with the qianfuquan price adjustment; no trading-signal lookahead beyond what adjusted prices already contain.",
}
print(json.dumps(report, ensure_ascii=False, indent=1), flush=True)

# persist v2 (prices untouched, shares replaced)
piv_v2 = dict(piv)
piv_v2["shares"] = adj
assert piv_v2["shares"].shape == raw.shape
for k in ("open", "high", "low", "close", "volume", "amount"):
    assert piv_v2[k].equals(piv[k]), k
pd.to_pickle(piv_v2, DST)
print("saved " + str(DST), flush=True)
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1))
print("saved " + str(REPORT), flush=True)
