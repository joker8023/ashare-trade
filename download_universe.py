"""
全A股日线批量下载 (AKShare, 免费无限频)
- 多线程并发 + 重试 + 断点续跑
- 输出: data/ashare_daily.pkl  (long format: code,date,open,high,low,close,volume,amount)
"""
import os
import sys
import time
import pickle
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)

START_DATE = os.getenv("START_DATE", "20200101")
END_DATE = datetime.now().strftime("%Y%m%d")
WORKERS = int(os.getenv("WORKERS", "8"))

UNIVERSE_PKL = DATA / os.getenv("UNI_NAME", "universe.pkl")
OUT_PKL = DATA / os.getenv("OUT_NAME", "ashare_daily.pkl")
META_PKL = DATA / "ashare_meta.pkl"

_lock = threading.Lock()
_done = {}


def get_universe() -> pd.DataFrame:
    import akshare as ak
    if UNIVERSE_PKL.exists():
        u = pd.read_pickle(UNIVERSE_PKL)
        print(f"复用股票列表缓存: {len(u)} 只")
        return u
    print("拉取全市场股票列表...")
    spot = ak.stock_zh_a_spot_em()
    u = spot[["代码", "名称", "总市值", "流通市值"]].copy()
    u.columns = ["code", "name", "mktcap", "float_cap"]
    # 剔除 ST / 退市 / B股
    u = u[~u["name"].str.contains("ST|退", na=False)]
    u = u[~u["code"].str.startswith(("2", "4", "9"))]  # 去除B股/北交所老代码段, 保留沪深主板创业科创
    u = u.dropna(subset=["mktcap"])
    u = u[u["mktcap"] > 0]
    u.to_pickle(UNIVERSE_PKL)
    print(f"过滤后股票池: {len(u)} 只")
    return u


def fetch_one(code: str, name: str, retries: int = 3):
    import akshare as ak
    for attempt in range(retries):
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                    start_date=START_DATE, end_date=END_DATE, adjust="qfq")
            if df is None or len(df) == 0:
                return code, None
            df = df.rename(columns={"日期": "date", "开盘": "open", "收盘": "close",
                                    "最高": "high", "最低": "low",
                                    "成交量": "volume", "成交额": "amount"})
            df = df[["date", "open", "high", "low", "close", "volume", "amount"]]
            df["date"] = pd.to_datetime(df["date"])
            df["code"] = code
            return code, df
        except Exception:
            if attempt == retries - 1:
                return code, None
            time.sleep(1.5 * (attempt + 1))
    return code, None


def main():
    u = get_universe()
    codes = list(zip(u["code"], u["name"]))

    # 断点续跑
    if OUT_PKL.exists():
        frames = pd.read_pickle(OUT_PKL)
        done_codes = set(frames["code"].unique())
        codes = [c for c in codes if c[0] not in done_codes]
        print(f"续跑: 已有 {len(done_codes)} 只, 待下载 {len(codes)} 只")
    else:
        frames = None
        print(f"开始下载 {len(codes)} 只, 区间 {START_DATE}~{END_DATE}, 并发 {WORKERS}")

    if not codes:
        print("全部已下载完成")
        return

    results = []
    ok = fail = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch_one, c, n): c for c, n in codes}
        for i, fut in enumerate(as_completed(futs), 1):
            code, df = fut.result()
            if df is not None and len(df) > 0:
                results.append(df)
                ok += 1
            else:
                fail += 1
            if i % 100 == 0:
                el = time.time() - t0
                rate = i / el
                eta = (len(codes) - i) / rate if rate > 0 else 0
                print(f"进度 {i}/{len(codes)}  成功{ok} 失败{fail}  "
                      f"{rate:.1f}只/秒  剩余约{eta/60:.1f}分钟", flush=True)
            # 每 500 只落盘一次
            if i % 500 == 0 and results:
                _flush(frames, results)
                frames = pd.read_pickle(OUT_PKL)
                results = []

    if results:
        _flush(frames, results)

    final = pd.read_pickle(OUT_PKL)
    print(f"\n完成: 共 {final['code'].nunique()} 只股票, {len(final):,} 行")
    print(f"区间: {final['date'].min().date()} ~ {final['date'].max().date()}")
    print(f"输出: {OUT_PKL}")


def _flush(existing, new_frames):
    add = pd.concat(new_frames, ignore_index=True)
    if existing is not None and len(existing) > 0:
        add = pd.concat([existing, add], ignore_index=True)
    add.to_pickle(OUT_PKL)
    print(f"  已落盘 {add['code'].nunique()} 只 / {len(add):,} 行", flush=True)


if __name__ == "__main__":
    main()
