import sys, time, shutil, gc
from pathlib import Path
from datetime import timedelta
import datetime as dt
import pandas as pd
import akshare as ak
BASE = Path('/Users/joker/coding/ashare-trade')
DATA = BASE / 'data'
CACHE = DATA / '_sina2020_cache'
TODAY = dt.datetime.now().strftime('%Y%m%d')
def load_codes():
    uni = pd.read_pickle(DATA / 'ashare_daily_long_2020.pkl')
    print('universe rows', len(uni), 'codes', uni['code'].nunique(), flush=True)
    return sorted(uni['code'].unique())
def symbol_of(code):
    return ('sh' if code.startswith('6') else 'sz') + code
def fetch_one(code):
    cf = CACHE / (code + '.pkl')
    try:
        old = pd.read_pickle(cf)
        old['date'] = pd.to_datetime(old['date'], errors='coerce')
        old = old.dropna(subset=['date'])
        last = old['date'].max()
    except Exception:
        return (code, 'nocache')
    s = (last + pd.Timedelta(days=1)).strftime('%Y%m%d')
    if s > TODAY:
        return (code, 'uptodate')
    try:
        df = ak.stock_zh_a_daily(symbol=symbol_of(code), start_date=s, end_date=TODAY, adjust='qfq')
    except Exception as e:
        return (code, 'fail:' + str(e)[:80])
    if df is None or len(df) == 0:
        return (code, 'empty')
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    full = pd.concat([old, df], ignore_index=True)
    full = full.drop_duplicates(subset=['date'], keep='last')
    full = full.sort_values('date').reset_index(drop=True)
    full.to_pickle(cf)
    return (code, 'ok:' + str(len(df)) + '+' + str(len(full)))
def run_fetch(codes, workers=6):
    import os
    from concurrent.futures import ProcessPoolExecutor, as_completed
    import time as _t
    print('fetch tail, workers', workers, flush=True)
    t0 = _t.time()
    stats = {}
    bad = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_one, c): c for c in codes}
        done = 0
        for fut in as_completed(futs):
            try:
                code, res = fut.result()
            except Exception as e:
                stats['crash'] = stats.get('crash', 0) + 1
                bad.append((futs[fut], str(e)[:100]))
                continue
            done += 1
            k = res.split(':')[0]
            stats[k] = stats.get(k, 0) + 1
            if done % 500 == 0:
                print('progress', done, stats, 'elapsed', round((_t.time()-t0)/60, 1), flush=True)
    print('fetch done', stats, flush=True)
    return stats
def merge_all():
    import glob as _g
    files = _g.glob(str(CACHE / '*.pkl'))
    files = [f for f in files if len(f.split('/')[-1]) == 10]
    print('cache files', len(files), flush=True)
    frames = []
    for f in files:
        code = f.split('/')[-1][:6]
        try:
            df = pd.read_pickle(f)
        except Exception:
            continue
        if df is None or len(df) == 0:
            continue
        d = df[['date','open','high','low','close','volume','amount']].copy()
        d['date'] = pd.to_datetime(d['date'], errors='coerce')
        d = d.dropna(subset=['date'])
        d['volume'] = d['volume'] / 100.0
        d['code'] = code
        frames.append(d[['code','date','open','high','low','close','volume','amount']])
    daily = pd.concat(frames, ignore_index=True).sort_values(['code','date']).reset_index(drop=True)
    print('merged rows', len(daily), 'codes', daily['code'].nunique(), flush=True)
    return daily
if __name__ == '__main__':
    import os
    codes = load_codes()
    stats = run_fetch(codes, workers=int(os.getenv('WORKERS', '6')))
    daily = merge_all()
    bk = DATA / 'backup_2020_update_live'
    bk.mkdir(exist_ok=True)
    dst = bk / 'ashare_daily_long_2020.pkl'
    if not dst.exists():
        shutil.copy2(DATA / 'ashare_daily_long_2020.pkl', dst)
        print('backed up', flush=True)
    daily.to_pickle(DATA / 'ashare_daily_long_2020.pkl')
    daily.to_pickle(DATA / 'ashare_daily_2020.pkl')
    print('saved both daily pkls', len(daily), flush=True)
