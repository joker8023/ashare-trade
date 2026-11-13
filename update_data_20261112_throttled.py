"""Throttled incremental update to 2026-11-12 - waits 5min for eastmoney ban to clear, then slow fetch."""
import sys, time, subprocess, shutil, gc
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
print(f"existing rows: {len(daily)} codes: {len(codes)} last: {LAST.date()} fetch: {START}~{END}", flush=True)
print("respecting 5min eastmoney cooldown before retry...", flush=True)
time.sleep(310)
print("cooldown done, starting slow fetch with max_workers=2", flush=True)
bk = DATA / "backup_20261113"
bk.mkdir(exist_ok=True)
KEEP = ["date","open","high","low","close","volume","amount"]
def one(code):
    import akshare as ak
    for attempt in range(5):
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=START, end_date=END, adjust="qfq")
            if df is None or len(df)==0:
                return None
            df = df.rename(columns={"\u65e5\u671f":"date","\u5f00\u76d8":"open","\u6536\u76d8":"close","\u6700\u9ad8":"high","\u6700\u4f4e":"low","\u6210\u4ea4\u91cf":"volume","\u6210\u4ea4\u989d":"amount"})
            df = df[KEEP].copy()
            df["date"] = pd.to_datetime(df["date"])
            df["code"] = code
            df = df[df["date"] > LAST]
            time.sleep(0.9)
            return df if len(df) else None
        except Exception as e:
            msg = str(e)
            if "push2" in msg or "\u9650\u6d41" in msg or "East" in msg or "qfq" in msg.lower():
                wait = 65 if attempt<2 else 75
                print(f"LIMIT {code} attempt{attempt} sleep {wait}s: {msg[:90]}", flush=True)
                time.sleep(wait)
                continue
            if attempt==4:
                print(f"FAIL {code}: {msg[:120]}", flush=True)
                return None
            time.sleep(1.5+attempt)
    return None
fresh=[]
with ThreadPoolExecutor(max_workers=2) as ex:
    futs={ex.submit(one,c):c for c in codes}
    for i,f in enumerate(as_completed(futs),1):
        try:
            rr=f.result()
            if rr is not None and len(rr): fresh.append(rr)
        except Exception: pass
        if i%200==0:
            print(f"progress {i}/{len(codes)} with-data {len(fresh)}", flush=True)
if not fresh:
    print("ERROR no new data", flush=True); sys.exit(2)
add=pd.concat(fresh,ignore_index=True).drop_duplicates(subset=["date","code"], keep="last")
print(f"new rows {len(add)} {add["date"].min().date()}~{add["date"].max().date()}", flush=True)
merged=pd.concat([daily,add],ignore_index=True).drop_duplicates(subset=["date","code"], keep="last").sort_values(["date","code"]).reset_index(drop=True)
merged.to_pickle(DATA/"ashare_daily_long.pkl")
print(f"saved {len(merged)} last {merged["date"].max().date()}", flush=True)
del daily,merged,add,fresh; gc.collect()
print("rebuild pivots_long.pkl ...", flush=True)
rr=subprocess.run([str(BASE/".venv/bin/python"),"rebuild_pivots_long.py"],cwd=BASE,capture_output=True,text=True)
print(rr.stdout[-2000:]); print(rr.stderr[-2000:],flush=True)
if rr.returncode!=0: print("ERROR rebuild"); sys.exit(3)
print("clean ...", flush=True)
rr=subprocess.run([str(BASE/".venv/bin/python"),"clean_data.py"],cwd=BASE,capture_output=True,text=True)
print(rr.stdout[-2000:]); print(rr.stderr[-2000:],flush=True)
if rr.returncode!=0: print("ERROR clean"); sys.exit(4)
piv=pd.read_pickle(DATA/"pivots_long_clean.pkl")
print(f"clean range {piv["close"].index[0].date()}~{piv["close"].index[-1].date()} {piv["close"].shape}",flush=True)
print("DONE",flush=True)