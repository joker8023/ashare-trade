#!/usr/bin/env python3
"""Build data/pivots_2020_clean_realshares.pkl.
Mirrors research/rebuild_pivots_2020.py (pivot caliber + clean_data.clean_pivots)
with ONE change: shares is a date-aligned DataFrame of daily outstanding_share
from data/_sina2020_cache/. Rules: same-day value, ffill only, full-missing ->
snapshot fallback (float_cap/last_close) + recorded. Read-only inputs otherwise.
"""
import gc
import json
import os
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
sys.path.insert(0, str(BASE))
os.chdir(BASE)
import numpy as np
import pandas as pd
daily = pd.read_pickle(DATA / "ashare_daily_long_2020.pkl")
uni = pd.read_pickle(DATA / "universe_2020.pkl")
print("raw: %d rows, %d codes" % (len(daily), daily["code"].nunique()), flush=True)
piv = {}
for col in ["open", "high", "low", "close", "volume", "amount"]:
    p = daily.pivot_table(index="date", columns="code", values=col).sort_index()
    piv[col] = p.astype("float32")
    gc.collect()
del daily
gc.collect()
close = piv["close"].where(piv["close"] > 0)
last_close = close.iloc[-1]
snap = (uni.set_index("code")["float_cap"] / last_close).replace(
    [float("inf"), float("-inf")], float("nan")).dropna()
piv["close"] = close
idx = close.index
codes = list(close.columns)
cache_dir = DATA / "_sina2020_cache"
shares = pd.DataFrame(index=idx, columns=codes, dtype="float32")
fallback_codes = []
ffill_cells = 0
native_cells = 0
time_varying = 0
for code in codes:
    fp = cache_dir / (code + ".pkl")
    s = None
    if fp.exists():
        try:
            df = pd.read_pickle(fp)
            if "outstanding_share" in df.columns:
                d = pd.to_datetime(df["date"])
                ser = pd.Series(df["outstanding_share"].to_numpy(dtype="float64"),
                                index=d).astype("float64")
                ser = ser[~ser.index.duplicated(keep="last")]
                s = ser.reindex(idx)
        except Exception as e:
            print("warn %s: %s" % (code, e), flush=True)
            s = None
    if s is None or bool(s.isna().all()):
        v = float(snap[code]) if code in snap.index else float("nan")
        shares[code] = np.float32(v)
        fallback_codes.append(code)
    else:
        filled = s.ffill()
        native_cells += int(filled.notna().sum())
        ffill_cells += int((filled.notna() & s.isna()).sum())
        if filled.dropna().nunique() > 1:
            time_varying += 1
        shares[code] = filled.astype("float32").to_numpy()
    del s
piv["shares"] = shares
print("pivots: %d days x %d codes, fallback %d" % (
    close.shape[0], len(codes), len(fallback_codes)), flush=True)
from clean_data import clean_pivots
piv_clean, cstats = clean_pivots(piv)
assert piv_clean["shares"].shape == shares.shape
pd.to_pickle(piv_clean, DATA / "pivots_2020_clean_realshares.pkl")
print("saved data/pivots_2020_clean_realshares.pkl", flush=True)
print(cstats, flush=True)
old = pd.read_pickle(DATA / "pivots_2020_clean.pkl")
old_shares = old["shares"]
new_shares = piv_clean["shares"]
common = [c for c in new_shares.columns if c in old_shares.index]
rl = (new_shares.loc[new_shares.index[-1], common]
      / old_shares.loc[common].astype("float64")).to_numpy(dtype="float64")
old_b = new_shares.columns.to_series().map(
    old_shares.astype("float64")).to_numpy(dtype="float64")
new_all = new_shares.to_numpy(dtype="float64")
with np.errstate(divide="ignore", invalid="ignore"):
    r = new_all / old_b[None, :]
valid = np.isfinite(r)
report = {
    "pivot_days": int(len(idx)),
    "pivot_codes": int(len(codes)),
    "first_day": str(idx[0].date()),
    "last_day": str(idx[-1].date()),
    "codes_with_cache_series": int(len(codes) - len(fallback_codes)),
    "fallback_codes": fallback_codes,
    "fallback_ratio": round(len(fallback_codes) / len(codes), 6),
    "native_dated_cells": int(native_cells),
    "ffilled_cells": int(ffill_cells),
    "leading_nan_cells": int(int(new_shares.isna().sum().sum())),
    "total_cells": int(new_shares.size),
    "time_varying_codes": int(time_varying),
    "ratio_last_day": {
        "median": round(float(np.nanmedian(rl)), 6),
        "p5": round(float(np.nanquantile(rl, 0.05)), 6),
        "p95": round(float(np.nanquantile(rl, 0.95)), 6),
        "mean": round(float(np.nanmean(rl)), 6),
    },
    "ratio_all_cells": {
        "median": round(float(np.median(r[valid])), 6),
        "p5": round(float(np.quantile(r[valid], 0.05)), 6),
        "p95": round(float(np.quantile(r[valid], 0.95)), 6),
        "frac_within_1pct": round(float(np.mean(np.abs(r[valid] - 1.0) <= 0.01)), 6),
        "frac_changed_gt5pct": round(float(np.mean(np.abs(r[valid] - 1.0) > 0.05)), 6),
    },
    "clean_stats": {k: int(v) for k, v in cstats.items()},
    "note": "shares[t]=same-day outstanding_share; ffill only; leading NaN kept; fallback=snapshot float_cap/last_close; universe untouched; no lookahead.",
}
open(BASE / "results" / "r30_bt" / "build_realshares_report.json", "w").write(
    json.dumps(report, ensure_ascii=False, indent=1))
print(json.dumps(report, ensure_ascii=False, indent=1))
print("report saved", flush=True)
