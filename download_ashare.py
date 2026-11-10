"""
全A股近3个月分钟线后台下载 (Tushare)
- 范围: 全部上市A股 (stock_basic list_status=L)
- 周期: 近90天分钟线, 默认 5min (可用环境变量 MIN_FREQ=1min/5min/15min/30min/60min 切换)
- 存储: data/ashare_minute_<freq>/<ts_code>.csv + progress.json + manifest.csv
- 断点续跑: 已下载过的跳过; 日志写 logs/download.log
- Token: 从 ./.env (TUSHARE_TOKEN=...) 或环境变量读取, 不打印
"""
import os
import sys
import time
import json
import traceback
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA_ROOT = BASE / "data"
LOG_DIR = BASE / "logs"
ENV_FILE = BASE / ".env"

FREQ = os.getenv("MIN_FREQ", "5min").strip() or "5min"
DAYS_BACK = int(os.getenv("DAYS_BACK", "90"))

DATA_DIR = DATA_ROOT / f"ashare_minute_{FREQ.replace('min','m')}"
PROGRESS_FILE = DATA_DIR / "progress.json"
MANIFEST_FILE = DATA_DIR / "manifest.csv"
LOG_FILE = LOG_DIR / "download.log"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_token() -> str:
    tok = os.getenv("TUSHARE_TOKEN", "").strip()
    if tok:
        return tok
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("TUSHARE_TOKEN"):
                _, _, v = line.partition("=")
                v = v.strip().strip('"').strip("'")
                if v:
                    return v
    return ""


def main():
    token = load_token()
    if not token:
        log("ERROR: 未找到 TUSHARE_TOKEN, 请在 .env 里设置 TUSHARE_TOKEN=... 后重跑")
        sys.exit(2)

    import pandas as pd
    import tushare as ts

    pro = ts.pro_api(token)

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=DAYS_BACK)
    start_date = start_dt.strftime("%Y%m%d %H:%M:%S") if False else start_dt.strftime("%Y%m%d")
    # Tushare stk_mins 接受 YYYYMMDD 或带时间的格式, 这里用 YYYYMMDD
    end_date = end_dt.strftime("%Y%m%d")

    log(f"开始下载: FREQ={FREQ} 范围={start_date}~{end_date} (近{DAYS_BACK}天) 输出={DATA_DIR}")

    # 1. 全A股列表 (带缓存+重试, stock_basic 同样 1次/分钟)
    BASIC_CACHE = DATA_DIR / "stock_basic.csv"
    basic = None
    if BASIC_CACHE.exists() and BASIC_CACHE.stat().st_size > 1000:
        try:
            basic = pd.read_csv(BASIC_CACHE, dtype=str)
            log(f"使用缓存股票列表: {len(basic)} 只 ({BASIC_CACHE.name})")
        except Exception as e:
            log(f"缓存列表读取失败, 重新拉取: {e}")
            basic = None
    for attempt in range(1, 7):
        if basic is not None and len(basic) > 0:
            break
        try:
            basic = pro.stock_basic(exchange="", list_status="L",
                                    fields="ts_code,symbol,name,area,industry,list_date")
            basic.to_csv(BASIC_CACHE, index=False, encoding="utf-8")
            break
        except Exception as e:
            log(f"stock_basic 获取失败(第{attempt}/6次): {e}, 65s后重试")
            traceback.print_exc()
            if attempt >= 6:
                sys.exit(3)
            time.sleep(65)

    if basic is None or len(basic) == 0:
        log("ERROR: stock_basic 返回为空")
        sys.exit(3)

    codes = basic["ts_code"].tolist()
    log(f"上市A股共 {len(codes)} 只, 示例: {codes[:5]}")

    # 断点续跑
    done = set()
    if PROGRESS_FILE.exists():
        try:
            done = set(json.loads(PROGRESS_FILE.read_text(encoding="utf-8")))
            log(f"断点续跑: 已完成 {len(done)} 只")
        except Exception:
            done = set()

    # manifest
    if not MANIFEST_FILE.exists():
        with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
            f.write("ts_code,rows,file,start_date,end_date,freq,downloaded_at\n")

    ok, fail = 0, 0
    for i, code in enumerate(codes, 1):
        if code in done:
            continue
        out = DATA_DIR / f"{code.replace('.', '_')}.csv"
        # 文件已存在且非空也跳过
        if out.exists() and out.stat().st_size > 100:
            done.add(code)
            continue
        try:
            df = pro.stk_mins(ts_code=code, freq=FREQ,
                              start_date=start_date, end_date=end_date)
            if df is None or len(df) == 0:
                log(f"[{i}/{len(codes)}] {code} 无数据(可能停牌), 跳过")
                done.add(code)
                continue
            df.to_csv(out, index=False, encoding="utf-8")
            with open(MANIFEST_FILE, "a", encoding="utf-8") as f:
                f.write(f"{code},{len(df)},{out.name},{start_date},{end_date},{FREQ},{datetime.now():%Y-%m-%d %H:%M:%S}\n")
            done.add(code)
            ok += 1
            if i % 20 == 0 or ok % 20 == 0:
                log(f"进度 {i}/{len(codes)} 已下载 {ok} 失败 {fail} 当前 {code} {len(df)}行")
                PROGRESS_FILE.write_text(json.dumps(sorted(done)), encoding="utf-8")
            # 限速: 该 Token 的 stk_mins 限频 1次/分钟, 必须 >=65s 间隔
            time.sleep(65)
        except Exception as e:
            msg = str(e)
            # 积分/权限不足时直接停, 避免空转烧配额
            if "权限" in msg or "积分" in msg or "每分钟" in msg or "rate" in msg.lower() or "频率超限" in msg:
                log(f"[{i}/{len(codes)}] {code} 接口受限: {msg[:200]}, 休眠65s后继续")
                time.sleep(65)
            else:
                log(f"[{i}/{len(codes)}] {code} 失败: {msg[:200]}")
            fail += 1
            time.sleep(1.0)
            if fail % 50 == 0:
                PROGRESS_FILE.write_text(json.dumps(sorted(done)), encoding="utf-8")

        # 定期落盘 progress
        if (ok + fail) % 10 == 0:
            PROGRESS_FILE.write_text(json.dumps(sorted(done)), encoding="utf-8")

    PROGRESS_FILE.write_text(json.dumps(sorted(done)), encoding="utf-8")
    log(f"全部完成: 成功 {ok} 失败/空 {fail} 总计 {len(codes)} 输出目录 {DATA_DIR}")


if __name__ == "__main__":
    main()
