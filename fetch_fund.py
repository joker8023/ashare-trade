"""Tushare daily_basic 月频拉取: 2021-11 ~ 2026-10 每月末交易日(近5年, lead定夺).
实测该账号限频 1次/小时, 每次调用后 sleep 3720s, 失败重试3次, 增量缓存.
攒够24个月自动跑中期回测(results/fund_monthly_interim.csv), 跑满自动跑最终版.
用法: .venv/bin/python fetch_fund.py [--test]  (--test 只拉3个月验证)
输出: data/fund_daily_basic.pkl  {YYYYMMDD: DataFrame}
日志: logs/fund_fetch.log
"""
import os, sys, time, pickle, argparse
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
LOGS = BASE / "logs"
LOGS.mkdir(exist_ok=True)
CACHE = DATA / "fund_daily_basic.pkl"

def month_ends():
    df = pd.read_pickle(DATA / "ashare_daily_long.pkl", compression="infer") \
        if (DATA / "ashare_daily_long.pkl").exists() else None
    if df is not None:
        df = df[["date"]].copy()
        df["date"] = pd.to_datetime(df["date"])
        me = df.groupby(df["date"].dt.to_period("M"))["date"].max().sort_values()
        me = me[(me >= "2021-11-01") & (me <= "2026-10-31")]
        return [d.strftime("%Y%m%d") for d in me]
    # 兜底: 用交易日历近似(每月最后一天, tushare会按实际返回)
    out, d = [], pd.Timestamp("2015-01-31")
    while d <= pd.Timestamp("2026-10-31"):
        out.append(d.strftime("%Y%m%d"))
        d = (d + pd.offsets.MonthEnd(1))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="只拉最近3个月验证")
    a = ap.parse_args()
    from dotenv import load_dotenv
    load_dotenv()
    import tushare as ts
    tok = os.getenv("TUSHARE_TOKEN")
    if not tok:
        print("缺少 TUSHARE_TOKEN", flush=True); sys.exit(1)
    ts.set_token(tok)
    pro = ts.pro_api()

    dates = month_ends()
    if a.test:
        dates = dates[-3:]
    print(f"共 {len(dates)} 个月: {dates[0]}~{dates[-1]}", flush=True)

    cache = {}
    if CACHE.exists():
        try:
            cache = pd.read_pickle(CACHE)
            print(f"已缓存 {len(cache)} 个月", flush=True)
        except Exception as e:
            print(f"缓存读取失败重建: {e}", flush=True)

    todo = [d for d in dates if d not in cache]
    # 实测该账号 daily_basic 限频为 1次/小时(非1次/分钟), 每次调用后睡 3720s;
    # 倒序拉取(最新月份优先), 增量缓存可随时中断续跑
    todo = sorted(todo, reverse=True)
    SLEEP = 65 if a.test else 3720
    print(f"待拉 {len(todo)} 个月, 预计 {len(todo)*SLEEP/3600:.1f} 小时", flush=True)

    for i, d in enumerate(todo):
        ok = False
        for att in range(3):
            try:
                df = pro.daily_basic(trade_date=d,
                    fields="ts_code,close,pe,pb,ps,dv_ratio,total_mv")
                if df is None or len(df) == 0:
                    print(f"[{i+1}/{len(todo)}] {d} 空结果 att={att+1}", flush=True)
                    time.sleep(10)
                    continue
                cache[d] = df
                pd.to_pickle(cache, CACHE)
                print(f"[{i+1}/{len(todo)}] {d} ok 行数={len(df)}", flush=True)
                ok = True
                # 攒够24个月首次触发中期回测
                if len(cache) >= 24 and not (BASE / "results" / "fund_monthly_interim.csv").exists():
                    print("缓存达24个月, 跑中期回测...", flush=True)
                    import subprocess
                    r = subprocess.run(
                        [sys.executable, str(BASE / "backtest_fund.py"),
                         "--out", "fund_monthly_interim.csv"],
                        capture_output=True, text=True, timeout=1800,
                        env={**os.environ, "ASHARE_PIVOTS": "pivots_long_clean.pkl"})
                    print(r.stdout[-2000:] if r.stdout else "", flush=True)
                    if r.returncode != 0:
                        print(f"中期回测失败: {r.stderr[-500:]}", flush=True)
                break
            except Exception as e:
                msg = str(e)
                print(f"[{i+1}/{len(todo)}] {d} 失败 att={att+1}: {msg}", flush=True)
                time.sleep(SLEEP if "频率超限" in msg else 15)
        if not ok:
            print(f"{d} 3次失败, 跳过(稍后补拉)", flush=True)
        # 限频: 每次调用后 sleep (最后一个可不睡)
        if i < len(todo) - 1:
            time.sleep(SLEEP)
    print(f"完成, 缓存共 {len(cache)} 个月 -> {CACHE}", flush=True)
    if len(cache) >= 24:
        print("跑最终回测...", flush=True)
        import subprocess
        r = subprocess.run(
            [sys.executable, str(BASE / "backtest_fund.py"),
             "--out", "fund_monthly.csv"],
            capture_output=True, text=True, timeout=1800,
            env={**os.environ, "ASHARE_PIVOTS": "pivots_long_clean.pkl"})
        print(r.stdout[-2000:] if r.stdout else "", flush=True)

if __name__ == "__main__":
    main()
