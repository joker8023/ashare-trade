#!/usr/bin/env python3
"""
下载全A股最近三年日线 (新浪源, 前复权), 输出 ashare-trade 仓库的标准格式。

为什么用新浪源:
- Tushare token 在当前安全连接下验证未通过 (服务端返回 40101 token不对)
- 仓库自带的 AKShare 东方财富源 (download_universe.py) 在当前出口 IP 被限流
- AKShare 的新浪日线接口实测可用, 且与仓库主数据集同为前复权日线

输出 (与 download_universe.py / daily_signal.py 的口径对齐):
- data/ashare_daily.pkl       long格式: code,date,open,high,low,close,volume(手),amount(元)
- data/ashare_daily_long.pkl  同上副本 (daily_signal / rebuild_pivots_long 读这个名字)
- data/universe.pkl           code,name,mktcap,float_cap
  其中 float_cap = 最后一日 outstanding_share(流通股本) x 收盘价 (元)
  mktcap 无独立来源, 暂与 float_cap 相同, 仅作占位 (策略实际用 float_cap)

断点续跑: 每只股票的原始新浪结果缓存在 data/_sina3y_cache/<code>.pkl, 重跑自动跳过。
"""
import os
import sys
import time
import json
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

BASE = Path("/home/hatch/workspace/ashare-trade")
DATA = BASE / "data"
CACHE = DATA / "_sina3y_cache"
DATA.mkdir(exist_ok=True)
CACHE.mkdir(exist_ok=True)

START_DATE = os.getenv("START_DATE", "20231110")
END_DATE = os.getenv("END_DATE", "20261110")
# 必须用进程池: AKShare 新浪日线内部用 py_mini_racer 解密, 多线程会 Segmentation fault
WORKERS = int(os.getenv("WORKERS", "6"))
UNI_FILE = DATA / "_universe_raw.pkl"


def get_universe() -> pd.DataFrame:
    if UNI_FILE.exists():
        u = pd.read_pickle(UNI_FILE)
        print(f"复用股票列表缓存: {len(u)} 只", flush=True)
        return u
    import akshare as ak
    print("拉取沪深A股列表 (stock_info_a_code_name)...", flush=True)
    u = None
    last_err = None
    for attempt in range(1, 6):
        try:
            u = ak.stock_info_a_code_name()
            break
        except Exception as e:
            last_err = e
            print(f"股票列表第{attempt}/5次失败: {str(e)[:120]}, 15s 后重试", flush=True)
            time.sleep(15)
    if u is None:
        raise RuntimeError(f"股票列表拉取失败: {last_err}")
    u = u.rename(columns={"code": "code", "name": "name"})[["code", "name"]]
    u["code"] = u["code"].astype(str).str.zfill(6)
    # 与 download_universe.py 相同的过滤: 剔除 ST/退, 剔除 B股代码段
    u = u[~u["name"].str.contains("ST|退", na=False)]
    u = u[~u["code"].str.startswith(("2", "4", "9"))]
    u = u.drop_duplicates(subset=["code"]).reset_index(drop=True)
    u.to_pickle(UNI_FILE)
    print(f"过滤后股票池: {len(u)} 只", flush=True)
    return u


def symbol_of(code: str) -> str:
    return ("sh" if code.startswith("6") else "sz") + code


def fetch_one(code: str):
    cache_file = CACHE / f"{code}.pkl"
    if cache_file.exists():
        return code, "cached"
    import akshare as ak
    last_err = None
    for attempt in range(3):
        try:
            df = ak.stock_zh_a_daily(
                symbol=symbol_of(code),
                start_date=START_DATE,
                end_date=END_DATE,
                adjust="qfq",
            )
            if df is None or len(df) == 0:
                return code, "empty"
            df.to_pickle(cache_file)
            return code, f"ok:{len(df)}"
        except Exception as e:
            last_err = e
            time.sleep(2.0 * (attempt + 1))
    return code, f"fail:{str(last_err)[:120]}"


def main():
    u = get_universe()
    codes = u["code"].tolist()
    name_map = dict(zip(u["code"], u["name"]))
    print(f"开始下载 {len(codes)} 只, 区间 {START_DATE}~{END_DATE}, 并发 {WORKERS}", flush=True)

    t0 = time.time()
    stats = {"ok": 0, "cached": 0, "empty": 0, "fail": 0}
    failures = []
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch_one, c): c for c in codes}
        for i, fut in enumerate(as_completed(futs), 1):
            code, res = fut.result()
            if res.startswith("ok"):
                stats["ok"] += 1
            elif res == "cached":
                stats["cached"] += 1
            elif res == "empty":
                stats["empty"] += 1
            else:
                stats["fail"] += 1
                failures.append((code, res))
            if i % 100 == 0:
                el = time.time() - t0
                rate = i / el
                eta = (len(codes) - i) / rate / 60 if rate > 0 else 0
                print(f"进度 {i}/{len(codes)} 成功{stats['ok']} 缓存{stats['cached']} "
                      f"空{stats['empty']} 失败{stats['fail']} {rate:.1f}只/秒 剩余约{eta:.1f}分钟", flush=True)

    print(f"下载阶段完成: {stats}, 耗时 {(time.time()-t0)/60:.1f} 分钟", flush=True)
    if failures:
        Path(DATA / "_sina3y_failures.json").write_text(
            json.dumps(failures, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"失败 {len(failures)} 只, 明细写入 data/_sina3y_failures.json", flush=True)

    # ---- 合并为仓库标准格式 ----
    frames = []
    uni_rows = []
    for code in codes:
        f = CACHE / f"{code}.pkl"
        if not f.exists():
            continue
        try:
            df = pd.read_pickle(f)
        except Exception:
            continue
        if df is None or len(df) == 0:
            continue
        last = df.iloc[-1]
        try:
            float_cap = float(last["outstanding_share"]) * float(last["close"])
        except Exception:
            float_cap = float("nan")
        uni_rows.append({"code": code, "name": name_map.get(code, ""),
                         "mktcap": float_cap, "float_cap": float_cap})
        d = df[["date", "open", "high", "low", "close", "volume", "amount"]].copy()
        d["date"] = pd.to_datetime(d["date"])
        d["volume"] = d["volume"] / 100.0  # 新浪 volume 单位是股, 仓库口径是手
        d["code"] = code
        frames.append(d[["code", "date", "open", "high", "low", "close", "volume", "amount"]])

    daily = pd.concat(frames, ignore_index=True).sort_values(["code", "date"]).reset_index(drop=True)
    daily.to_pickle(DATA / "ashare_daily.pkl")
    daily.to_pickle(DATA / "ashare_daily_long.pkl")
    uni = pd.DataFrame(uni_rows)
    uni.to_pickle(DATA / "universe.pkl")

    print(f"已保存 data/ashare_daily.pkl + ashare_daily_long.pkl: {len(daily):,} 行, "
          f"{daily['code'].nunique()} 只, {daily['date'].min().date()} ~ {daily['date'].max().date()}", flush=True)
    print(f"已保存 data/universe.pkl: {len(uni)} 只", flush=True)


if __name__ == "__main__":
    main()
