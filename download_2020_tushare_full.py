import sys, subprocess, gc, time, pathlib
from pathlib import Path
import pandas as pd
import tushare as ts
BASE = Path("/Users/joker/coding/ashare-trade")
DATA = BASE / "data"
print("loading existing daily", flush=True)
daily = pd.read_pickle(DATA / "ashare_daily_long.pkl")
print(f"existing rows {len(daily)} range {daily['date'].min().date()}~{daily['date'].max().date()}", flush=True)
txt = pathlib.Path(BASE / ".env").read_text()
tok = txt.split("TUSHARE_TOKEN=")[1].split()[0].strip().strip('"').strip("'")
pro = ts.pro_api(tok)
# generate all calendar dates 2020-01-01 to 2026-11-12, fetch daily and skip holidays (no trade_cal to avoid 1/min limit)
all_dates = pd.date_range('2020-01-01', '2026-11-12', freq='D')
all_trade_candidates = [d for d in all_dates if d.weekday() < 5]
trade_dates = [d.strftime('%Y%m%d') for d in all_trade_candidates]
print(f"generated {len(trade_dates)} calendar dates, will fetch daily and skip holidays", flush=True)
frames=[]
for idx, d in enumerate(trade_dates, 1):
    # skip weekends quickly to reduce calls? But Tushare daily for weekend returns empty quickly, still counts as call. Keep all to be safe, but weekends are 2/7 = 715 extra calls. We keep all and rely on empty check.
    try:
        df = pro.daily(trade_date=d)
        if df is None or len(df)==0:
            if idx % 200 == 0:
                print(f"skip {d} holiday {idx}/{len(trade_dates)}", flush=True)
            time.sleep(1.20) # holiday skip
            continue
            continue
        df["code"] = df["ts_code"].str.split(".").str[0]
        df["date"] = pd.to_datetime(d)
        df["volume"] = pd.to_numeric(df["vol"], errors="coerce")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce") * 1000.0
        for c in ["open","high","low","close"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        keep = df[["date","open","high","low","close","volume","amount","code"]].copy()
        keep = keep.dropna(subset=["close"])
        frames.append(keep)
        if len(frames) % 100 == 0 or idx==len(trade_dates):
            print(f"progress {idx}/{len(trade_dates)} {d} rows {len(df)} total {sum(len(f) for f in frames)} trading_days {len(frames)}", flush=True)
        time.sleep(2.00)
    except Exception as e:
        msg=str(e)
        if "frequency" in msg.lower() or "per minute" in msg.lower() or "\u9891\u7387" in msg:
            print(f"{d} rate limit, sleep 65s", flush=True)
            time.sleep(65)
            try:
                df = pro.daily(trade_date=d)
                if df is not None and len(df):
                    df["code"] = df["ts_code"].str.split(".").str[0]
                    df["date"] = pd.to_datetime(d)
                    df["volume"] = pd.to_numeric(df["vol"], errors="coerce")
                    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")*1000.0
                    for c in ["open","high","low","close"]:
                        df[c]=pd.to_numeric(df[c], errors="coerce")
                    keep=df[["date","open","high","low","close","volume","amount","code"]].copy().dropna(subset=["close"])
                    frames.append(keep)
            except Exception as e2:
                print(f"{d} retry failed {e2}", flush=True)
            time.sleep(0.5)
        else:
            print(f"{d} failed {e}", flush=True)
            time.sleep(1)
if not frames:
    print("ERROR no data fetched", flush=True); sys.exit(2)
add = pd.concat(frames, ignore_index=True)
print(f"fetched 2020+ rows {len(add)} {add['date'].min().date()}~{add['date'].max().date()} trading_days {len(frames)} codes {add['code'].nunique()}", flush=True)
pre = daily[daily['date'] < '2020-01-01'].copy()
print(f"pre-2020 rows {len(pre)} range {pre['date'].min().date() if len(pre) else 'none'}~{pre['date'].max().date() if len(pre) else 'none'}", flush=True)
merged = pd.concat([pre, add], ignore_index=True)
merged = merged.drop_duplicates(subset=["date","code"], keep="last").sort_values(["date","code"]).reset_index(drop=True)
merged.to_pickle(DATA / "ashare_daily_long.pkl")
print(f"saved merged {len(merged)} range {merged['date'].min().date()}~{merged['date'].max().date()}", flush=True)
del daily, pre, add, frames; gc.collect()
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
print("DONE 2020-full", flush=True)