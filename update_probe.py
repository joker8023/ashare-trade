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

KEEP = ["date", "open", "high", "low", "close", "volume", "amount"]

def one(code):
    import akshare as ak
    for attempt in range(3):
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=START, end_date=END, adjust="qfq")
            if df is None or len(df) == 0:
                return None
            df.columns = [str(c) for c in df.columns]
            ren = {}
            for c in df.columns:
                t = c.strip()
                if t.startswith("D") or t == "\u0044":
                    ren[c] = "date"
            df = df.rename(columns=ren)
            df["code"] = code
            return df
        except Exception:
            if attempt == 2:
                return None
            time.sleep(1.0 + attempt)
    return None

print("columns:", list(pd.read_pickle(DATA / "ashare_daily_long.pkl").columns), flush=True)