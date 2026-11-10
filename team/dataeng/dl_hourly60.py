"""Baostock 60min downloader for R7 pool (resume-capable)."""
import os, sys, json, time
import pandas as pd
import baostock as bs

POOL = "team/dataeng/pool_list.csv"
OUT = "data/hourly_60m"
PROG = os.path.join(OUT, "progress.json")
MANI = os.path.join(OUT, "manifest.csv")
LOG = "team/dataeng/dl_hourly60.log"
START = "2024-01-01"
END = "2026-11-04"
YEARS = [2024, 2025, 2026]
FIELDS = "date,time,code,open,high,low,close,volume,amount"

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def bs_code(code):
    code = str(code).zfill(6)
    return ("sh." if code[0] == "6" else "sz.") + code

def fetch_year(code, y, retries=3):
    s = f"{y}-01-01"
    e = f"{y}-12-31" if y < 2026 else END
    for r in range(retries):
        try:
            rs = bs.query_history_k_data_plus(code, FIELDS, start_date=s, end_date=e, frequency="60", adjustflag="2")
            if rs.error_code != "0":
                log(f"{code} {y} err={rs.error_code} {rs.error_msg} retry {r+1}")
                time.sleep(3 * (r + 1))
                continue
            rows = []
            while rs.next():
                rows.append(rs.get_row_data())
            return rows
        except Exception as ex:
            log(f"{code} {y} EXC {ex} retry {r+1}")
            time.sleep(3 * (r + 1))
    return None

def tushare_fallback(code6, start=START, end=END):
    """fallback for codes with no baostock data; returns DataFrame or None."""
    try:
        import tushare as ts
        tok = None
        try:
            with open(".env") as f:
                for ln in f:
                    if "TUSHARE_TOKEN" in ln and "=" in ln:
                        tok = ln.split("=", 1)[1].strip().strip("'\"") 
                        break
        except Exception:
            pass
        if not tok:
            return None, "no token"
        pro = ts.pro_api(tok)
        tscode = code6 + (".SH" if code6[0] == "6" else ".SZ")
        df = pro.stk_mins(ts_code=tscode, start_date=start.replace("-","")+" 09:30:00", end_date=end.replace("-","")+" 15:00:00", freq="60min")
        return df, "ok" if df is not None else "empty"
    except Exception as ex:
        return None, f"tushare exc: {ex}"

def main():
    os.makedirs(OUT, exist_ok=True)
    pool = pd.read_csv(POOL, dtype=str)
    codes = pool["code"].str.zfill(6).tolist()
    log(f"pool {len(codes)} codes")
    prog = {}
    if os.path.exists(PROG):
        try:
            prog = json.load(open(PROG))
            log(f"resume: {len(prog)} done in progress.json")
        except Exception as ex:
            log(f"progress read fail {ex}")
    done = set(k for k, v in prog.items() if v.get("status") == "done")
    # also treat existing csv as done if bars>0
    results = []
    lg = bs.login()
    assert lg.error_code == "0", lg.error_msg
    try:
        for i, c6 in enumerate(codes):
            if c6 in done and os.path.exists(f"{OUT}/{c6}.csv"):
                try:
                    d = pd.read_csv(f"{OUT}/{c6}.csv")
                    results.append(dict(code=c6, bs=bs_code(c6), bars=len(d), start=d["datetime"].min() if len(d) else "", end=d["datetime"].max() if len(d) else "", source=prog[c6].get("source","baostock"), note="resume-skip"))
                    continue
                except Exception:
                    pass
            bsc = bs_code(c6)
            allrows = []
            failed = False
            for y in YEARS:
                rows = fetch_year(bsc, y)
                if rows is None:
                    failed = True
                    log(f"[{i+1}/{len(codes)}] {c6} {y} FAILED")
                    continue
                if rows:
                    allrows.extend(rows)
                log(f"[{i+1}/{len(codes)}] {c6} {y}: {len(rows)} bars")
                time.sleep(1)
            if not allrows:
                # try tushare fallback once
                tdf, why = tushare_fallback(c6)
                if tdf is not None and len(tdf):
                    tdf.to_csv(f"{OUT}/{c6}.csv", index=False)
                    results.append(dict(code=c6, bs=bsc, bars=len(tdf), start="", end="", source="tushare", note="baostock-empty+tushare"))
                    prog[c6] = {"status": "done", "bars": len(tdf), "source": "tushare"}
                else:
                    results.append(dict(code=c6, bs=bsc, bars=0, start="", end="", source="none", note=f"baostock-empty; tushare:{why}"))
                    prog[c6] = {"status": "missing", "bars": 0, "source": "none", "note": f"baostock-empty; tushare:{why}"}
                    log(f"{c6} MISSING baostock-empty tushare:{why}")
                json.dump(prog, open(PROG, "w"), indent=1)
                continue
            cols = FIELDS.split(",")
            df = pd.DataFrame(allrows, columns=cols)
            df["datetime"] = pd.to_datetime(df["time"], format="%Y%m%d%H%M%S%f", errors="coerce")
            for cc in ["open","high","low","close","volume","amount"]:
                df[cc] = pd.to_numeric(df[cc], errors="coerce")
            df = df.dropna(subset=["datetime"]).sort_values("datetime").drop_duplicates(subset=["datetime"])
            df = df[(df["datetime"] >= START) & (df["datetime"] <= END + " 23:59:59")]
            out = df[["datetime","open","high","low","close","volume","amount"]].reset_index(drop=True)
            out.to_csv(f"{OUT}/{c6}.csv", index=False)
            results.append(dict(code=c6, bs=bsc, bars=len(out), start=str(out['datetime'].min()) if len(out) else "", end=str(out['datetime'].max()) if len(out) else "", source="baostock", note=""))
            prog[c6] = {"status": "done", "bars": len(out), "source": "baostock"}
            json.dump(prog, open(PROG, "w"), indent=1)
            log(f"{c6} SAVED {len(out)} bars {out['datetime'].min() if len(out) else ''}~{out['datetime'].max() if len(out) else ''}")
    finally:
        bs.logout()
    mani = pd.DataFrame(results)
    mani.to_csv(MANI, index=False)
    json.dump(prog, open(PROG, "w"), indent=1)
    log(f"DONE manifest {mani.shape} total_bars={mani['bars'].sum()}")

if __name__ == "__main__":
    main()
