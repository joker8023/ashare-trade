"""增量更新到 2026-11-05 收盘（不含 11-06 盘中），重建 pivots 并清洗"""
import os, sys, time, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import pandas as pd

BASE = Path('/Users/joker/coding/ashare-trade')
DATA = BASE / 'data'
LAST = pd.Timestamp('2026-11-04')
END = '20261105'
START = '20261101'

daily = pd.read_pickle(DATA / 'ashare_daily_long.pkl')
codes = sorted(daily['code'].unique())
print(f'现有 {len(daily):,} 行, {len(codes)} 只, 最新 {daily["date"].max().date()}', flush=True)

def one(code):
    import akshare as ak
    for attempt in range(3):
        try:
            df = ak.stock_zh_a_hist(symbol=code, period='daily', start_date=START,
                                    end_date=END, adjust='qfq')
            if df is None or len(df) == 0:
                return None
            df = df.rename(columns={'日期':'date','开盘':'open','收盘':'close','最高':'high',
                                    '最低':'low','成交量':'volume','成交额':'amount'})
            df = df[['date','open','high','low','close','volume','amount']]
            df['date'] = pd.to_datetime(df['date'])
            df['code'] = code
            df = df[df['date'] > LAST]
            return df if len(df) else None
        except Exception:
            if attempt == 2:
                return None
            time.sleep(1.0 + attempt)
    return None

fresh = []
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = {ex.submit(one, c): c for c in codes}
    for i, f in enumerate(as_completed(futs), 1):
        try:
            r = f.result()
            if r is not None and len(r):
                fresh.append(r)
        except Exception:
            pass
        if i % 500 == 0:
            print(f'  {i}/{len(codes)} 成功 {len(fresh)}', flush=True)
            time.sleep(0.2)

if not fresh:
    print('ERROR: 没有拉到任何新数据', flush=True)
    sys.exit(2)
add = pd.concat(fresh, ignore_index=True).drop_duplicates(subset=['date','code'], keep='last')
print(f'新增 {len(add):,} 行, 日期 {add["date"].min().date()} ~ {add["date"].max().date()}', flush=True)
merged = pd.concat([daily, add], ignore_index=True)
merged = merged.drop_duplicates(subset=['date','code'], keep='last').sort_values(['date','code']).reset_index(drop=True)
merged.to_pickle(DATA / 'ashare_daily_long.pkl')
print(f'已保存 ashare_daily_long.pkl: {len(merged):,} 行, 最新 {merged["date"].max().date()}', flush=True)

print('重建 pivots_long.pkl ...', flush=True)
r = subprocess.run([str(BASE/'.venv/bin/python'), 'rebuild_pivots_long.py'], cwd=BASE, capture_output=True, text=True)
print(r.stdout[-3000:]); print(r.stderr[-3000:], flush=True)
if r.returncode != 0:
    print('ERROR rebuild_pivots_long', r.returncode, flush=True); sys.exit(3)
print('清洗 pivots_long_clean.pkl ...', flush=True)
r = subprocess.run([str(BASE/'.venv/bin/python'), 'clean_data.py'], cwd=BASE, capture_output=True, text=True)
print(r.stdout[-3000:]); print(r.stderr[-3000:], flush=True)
if r.returncode != 0:
    print('ERROR clean_data', r.returncode, flush=True); sys.exit(4)
print('DONE', flush=True)
