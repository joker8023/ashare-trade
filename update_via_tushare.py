import sys, subprocess, gc, time, pathlib
from pathlib import Path
import pandas as pd
import tushare as ts
BASE = Path("/Users/joker/coding/ashare-trade")
DATA = BASE / "data"
END_STR = "20261112"
daily = pd.read_pickle(DATA / "ashare_daily_long.pkl")
LAST = daily["date"].max()
print(f"existing {len(daily)} codes {daily['code'].nunique()} last {LAST.date()}", flush=True)
# read token without regex to avoid escaping hell
txt = pathlib.Path(BASE / ".env").read_text()
tok = txt.split("TUSHARE_TOKEN=")[1].split()[0].strip().strip('"').strip("'")
print(f"token prefix {tok[:8]}... len {len(tok)}", flush=True)
pro = ts.pro_api(tok)
start = LAST + pd.Timedelta(days=1)
end = pd.Timestamp(END_STR)
dates = pd.date_range(start, end, freq="D")
trade_dates = [d.strftime("%Y%m%d") for d in dates]
print(f"fetch trade_dates {trade_dates}", flush=True)
frames=[]
for d in trade_dates:
    try:
        df = pro.daily(trade_date=d)
        if df is None or len(df)==0:
            print(f"{d} no data (holiday)", flush=True)
            continue
        print(f"{d} rows {len(df)}", flush=True)
        df["code"] = df["ts_code"].str.split(".").str[0]
        df["date"] = pd.to_datetime(d)
        df["volume"] = pd.to_numeric(df["vol"], errors="coerce")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce") * 1000.0
        df["open"] = pd.to_numeric(df["open"], errors="coerce")
        df["high"] = pd.to_numeric(df["high"], errors="coerce")
        df["low"] = pd.to_numeric(df["low"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        keep = df[["date","open","high","low","close","volume","amount","code"]].copy()
        keep = keep.dropna(subset=["close"])
        frames.append(keep)
        time.sleep(0.3)
    except Exception as e:
        print(f"{d} failed {e}", flush=True)
        time.sleep(1)
        continue
if not frames:
    print("ERROR no new data via tushare", flush=True); sys.exit(2)
add = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["date","code"], keep="last")
print(f"new rows {len(add)} {add['date'].min().date()}~{add['date'].max().date()} unique codes {add['code'].nunique()}", flush=True)
merged = pd.concat([daily, add], ignore_index=True)
merged = merged.drop_duplicates(subset=["date","code"], keep="last").sort_values(["date","code"]).reset_index(drop=True)
merged.to_pickle(DATA / "ashare_daily_long.pkl")
print(f"saved {len(merged)} last {merged['date'].max().date()}", flush=True)
del daily, merged, add, frames; gc.collect()
print("rebuild pivots_long.pkl ...", flush=True)
rr = subprocess.run([str(BASE / ".venv/bin/python"), "rebuild_pivots_long.py"], cwd=BASE, capture_output=True, text=True)
print(rr.stdout[-3000:])
print(rr.stderr[-3000:], flush=True)
if rr.returncode != 0:
    print("ERROR rebuild", flush=True); sys.exit(3)
print("clean ...", flush=True)
rr = subprocess.run([str(BASE / ".venv/bin/python"), "clean_data.py"], cwd=BASE, capture_output=True, text=True)
print(rr.stdout[-3000:])
print(rr.stderr[-3000:], flush=True)
if rr.returncode != 0:
    print("ERROR clean", flush=True); sys.exit(4)
piv = pd.read_pickle(DATA / "pivots_long_clean.pkl")
print(f"clean range {piv['close'].index[0].date()}~{piv['close'].index[-1].date()} shape {piv['close'].shape}", flush=True)
print("DONE", flush=True)
