"""Incremental update to 2026-11-12 close, rebuild pivots and clean."""
import sys, time, subprocess, shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import pandas as pd

BASE = Path("/Users/joker/coding/ashare-trade")
DATA = BASE / "data"
END = "20261112"

daily = pd.read_pickle(DATA / "ashare_daily_long.pkl")
LAST = daily["date"].max()
START = (LAST + pd.Timedelta(days=1)).strftime("%Y%m%d")
codes = sorted(daily["code"].unique())
print("existing rows:", len(daily), "codes:", len(codes), flush=True)
print("last:", LAST.date(), "fetch:", START, "~", END, flush=True)

bk = DATA / "backup_20261113"
bk.mkdir(exist_ok=True)
if not (bk / "ashare_daily_long.pkl").exists():
    shutil.copy2(DATA / "ashare_daily_long.pkl", bk / "ashare_daily_long.pkl")
    print("backed up to backup_20261113", flush=True)
else:
    print("backup already exists, skip copy", flush=True)

KEEP = ["date", "open", "high", "low", "close", "volume", "amount"]

def one(code):
    import akshare as ak
    for attempt in range(3):
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=START, end_date=END, adjust="qfq")
            if df is None or len(df) == 0:
                return None
            df = df.rename(columns={"\u65e5\u671f": "date", "\u5f00\u76d8": "open", "\u6536\u76d8": "close", "\u6700\u9ad8": "high", "\u6700\u4f4e": "low", "\u6210\u4ea4\u91cf": "volume", "\u6210\u4ea4\u989d": "amount"})
            df = df[KEEP].copy()
            df["date"] = pd.to_datetime(df["date"])
            df["code"] = code
            df = df[df["date"] > LAST]
            return df if len(df) else None
        except Exception as e:
            if attempt == 2:
                print("FAIL " + code + ": " + str(e)[:120], flush=True)
                return None
            time.sleep(1.0 + attempt)
    return None

fresh = []
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = {ex.submit(one, c): c for c in codes}
    for i, f in enumerate(as_completed(futs), 1):
        try:
            rr = f.result()
            if rr is not None and len(rr):
                fresh.append(rr)
        except Exception:
            pass
        if i % 500 == 0:
            print("progress:", i, "/", len(codes), "with-data:", len(fresh), flush=True)
            time.sleep(0.2)

if not fresh:
    print("ERROR: no new data fetched", flush=True)
    sys.exit(2)
add = pd.concat(fresh, ignore_index=True).drop_duplicates(subset=["date", "code"], keep="last")
print("new rows:", len(add), "from:", add["date"].min().date(), "to:", add["date"].max().date(), flush=True)
merged = pd.concat([daily, add], ignore_index=True)
merged = merged.drop_duplicates(subset=["date", "code"], keep="last").sort_values(["date", "code"]).reset_index(drop=True)
merged.to_pickle(DATA / "ashare_daily_long.pkl")
print("saved rows:", len(merged), "last:", merged["date"].max().date(), flush=True)
del daily, merged, add, fresh

print("rebuild pivots_long.pkl ...", flush=True)
rr = subprocess.run([str(BASE / ".venv/bin/python"), "rebuild_pivots_long.py"], cwd=BASE, capture_output=True, text=True)
print(rr.stdout[-2000:])
print(rr.stderr[-2000:], flush=True)
if rr.returncode != 0:
    print("ERROR rebuild", flush=True)
    sys.exit(3)
print("clean ...", flush=True)
rr = subprocess.run([str(BASE / ".venv/bin/python"), "clean_data.py"], cwd=BASE, capture_output=True, text=True)
print(rr.stdout[-2000:])
print(rr.stderr[-2000:], flush=True)
if rr.returncode != 0:
    print("ERROR clean", flush=True)
    sys.exit(4)
piv = pd.read_pickle(DATA / "pivots_long_clean.pkl")
print("clean range:", piv["close"].index[0].date(), "~", piv["close"].index[-1].date(), piv["close"].shape, flush=True)
print("DONE", flush=True)