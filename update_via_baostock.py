import sys, subprocess, shutil, gc, time
from pathlib import Path
import pandas as pd
import baostock as bs
BASE = Path("/Users/joker/coding/ashare-trade")
DATA = BASE / "data"
END = "20261112"
daily = pd.read_pickle(DATA / "ashare_daily_long.pkl")
LAST = daily["date"].max()
START = (LAST + pd.Timedelta(days=1)).strftime("%Y%m%d")
codes = sorted(daily["code"].unique())
print(f"existing {len(daily)} codes {len(codes)} last {LAST.date()} fetch {START}~{END} via baostock", flush=True)
bs.login()
# format for baostock: sh.<code> if startswith 6 else sz.<code>
def bcode(c):
    return ("sh." if c.startswith("6") else "sz.") + c
fresh=[]
# baostock date format is YYYY-MM-DD, we use YYYY-MM-DD via query string YYYY-MM-DD
start_d = START[:4]+"-"+START[4:6]+"-"+START[6:8]
end_d = END[:4]+"-"+END[4:6]+"-"+END[6:8]
# alternative query uses YYYY-MM-DD directly
for i, code in enumerate(codes, 1):
    bc = bcode(code)
    rs = bs.query_history_k_data_plus(bc, "date,open,high,low,close,volume,amount", start_date=start_d, end_date=end_d, frequency="d", adjustflag="2")
    rows=[]
    while rs.error_code=="0" and rs.next():
        rows.append(rs.get_row_data())
    if not rows:
        continue
    df = pd.DataFrame(rows, columns=["date","open","high","low","close","volume","amount"])
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open","high","low","close","volume","amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # volume scaling: baostock volume is shares, our store is /100 (to match akshare)
    df["volume"] = df["volume"] / 100.0
    df["code"] = code
    df = df[df["date"] > LAST]
    if len(df):
        fresh.append(df)
    if i % 500 == 0:
        print(f"progress {i}/{len(codes)} with-data {len(fresh)}", flush=True)
bs.logout()
if not fresh:
    print("ERROR no new data via baostock", flush=True)
    sys.exit(2)
add = pd.concat(fresh, ignore_index=True).drop_duplicates(subset=["date","code"], keep="last")
print(f"new rows {len(add)} {add['date'].min().date()}~{add['date'].max().date()}", flush=True)
merged = pd.concat([daily, add], ignore_index=True).drop_duplicates(subset=["date","code"], keep="last").sort_values(["date","code"]).reset_index(drop=True)
merged.to_pickle(DATA / "ashare_daily_long.pkl")
print(f"saved {len(merged)} last {merged['date'].max().date()}", flush=True)
del daily, merged, add, fresh; gc.collect()
print("rebuild pivots_long.pkl ...", flush=True)
rr = subprocess.run([str(BASE / ".venv/bin/python"), "rebuild_pivots_long.py"], cwd=BASE, capture_output=True, text=True)
print(rr.stdout[-2000:])
print(rr.stderr[-2000:], flush=True)
if rr.returncode != 0:
    print("ERROR rebuild", flush=True); sys.exit(3)
print("clean ...", flush=True)
rr = subprocess.run([str(BASE / ".venv/bin/python"), "clean_data.py"], cwd=BASE, capture_output=True, text=True)
print(rr.stdout[-2000:])
print(rr.stderr[-2000:], flush=True)
if rr.returncode != 0:
    print("ERROR clean", flush=True); sys.exit(4)
piv = pd.read_pickle(DATA / "pivots_long_clean.pkl")
print(f"clean range {piv['close'].index[0].date()}~{piv['close'].index[-1].date()} {piv['close'].shape}", flush=True)
print("DONE", flush=True)
