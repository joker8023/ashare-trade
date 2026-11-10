"""Baostock 5分钟全历史下载：510300/510500/159915，前复权，存 data/minute_etf/"""
import os, time
import baostock as bs
import pandas as pd

OUT = "data/minute_etf"
os.makedirs(OUT, exist_ok=True)
SYMS = {"510300": "sh.510300", "510500": "sh.510500", "159915": "sz.159915"}
FIELDS = "date,time,code,open,high,low,close,volume,amount"

def fetch_year(code, y, retries=3):
    s, e = f"{y}-01-01", f"{y}-12-31"
    for r in range(retries):
        try:
            rs = bs.query_history_k_data_plus(code, FIELDS, start_date=s,
                end_date=e, frequency="5", adjustflag="2")
            if rs.error_code != "0":
                time.sleep(3 * (r + 1))
                continue
            rows = []
            while rs.next():
                rows.append(rs.get_row_data())
            if rows:
                return rows
            return []  # 空年份（如未上市），不重试
        except Exception:
            time.sleep(3 * (r + 1))
    return None

lg = bs.login()
assert lg.error_code == "0", lg.error_msg
try:
    for sym, code in SYMS.items():
        path = f"{OUT}/{sym}_5m.csv"
        done = set()
        parts = []
        if os.path.exists(path):
            try:
                old = pd.read_csv(path, usecols=["时间"], parse_dates=["时间"])
                done = set(zip(old["时间"].dt.year, old["时间"].dt.month))
                parts.append(old)
                print(f"[{sym}] resume: {len(old)}行", flush=True)
            except Exception:
                pass
        for y in range(2015, 2027):
            rows = fetch_year(code, y)
            if rows is None:
                print(f"[{sym}] {y} FAILED", flush=True)
                continue
            if rows:
                d = pd.DataFrame(rows, columns=FIELDS.split(","))
                parts.append(d)
            print(f"[{sym}] {y}: {0 if not rows else len(rows)} bars", flush=True)
            time.sleep(1)
        if parts:
            df = pd.concat(parts, ignore_index=True)
            if "time" in df.columns:  # 新拉的数据，转换格式
                new = df[df["time"].notna()].copy()
                new["时间"] = pd.to_datetime(new["time"], format="%Y%m%d%H%M%S%f")
                new = new.rename(columns={"open": "开盘", "close": "收盘",
                                          "high": "最高", "low": "最低",
                                          "volume": "成交量", "amount": "成交额"})
                keep = ["时间", "开盘", "收盘", "最高", "最低", "成交量", "成交额"]
                new = new[keep]
                for c in keep[1:]:
                    new[c] = pd.to_numeric(new[c], errors="coerce")
                olds = [p for p in parts if "时间" in p.columns and "time" not in p.columns]
                df = pd.concat(olds + [new], ignore_index=True) if olds else new
            df["时间"] = pd.to_datetime(df["时间"])
            df = df.drop_duplicates(subset=["时间"]).sort_values("时间").reset_index(drop=True)
            df.to_csv(path, index=False)
            print(f"[{sym}] SAVED {path}: {df.shape} {df['时间'].min()}~{df['时间'].max()}", flush=True)
finally:
    bs.logout()
print("DONE")
