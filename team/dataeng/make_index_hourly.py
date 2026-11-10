import os
import pandas as pd
SRC = 'data/minute_etf'
OUT = 'data/hourly_60m'
MAP = {'159915': '159915', '510300': '510300', '510500': '510500'}
COLS = {'时间': 'ts', '开盘': 'open', '收盘': 'close', '最高': 'high', '最低': 'low', '成交量': 'volume', '成交额': 'amount'}

def bucket(t):
    hm = t.hour * 60 + t.minute
    if hm <= 10 * 60 + 30:
        return '10:30:00'
    if hm <= 11 * 60 + 30:
        return '11:30:00'
    if hm <= 14 * 60:
        return '14:00:00'
    return '15:00:00'

os.makedirs(OUT, exist_ok=True)
for sym, code in MAP.items():
    p = f'{SRC}/{sym}_5m.csv'
    df = pd.read_csv(p)
    df = df.rename(columns=COLS)
    df['ts'] = pd.to_datetime(df['ts'])
    df['date'] = df['ts'].dt.date
    df['bar'] = df['ts'].apply(bucket)
    df['datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['bar'])
    g = df.sort_values('ts').groupby('datetime')
    out = g.agg(open=('open', 'first'), high=('high', 'max'), low=('low', 'min'), close=('close', 'last'), volume=('volume', 'sum'), amount=('amount', 'sum')).reset_index()
    out = out[['datetime', 'open', 'high', 'low', 'close', 'volume', 'amount']]
    out.to_csv(f'{OUT}/{code}.csv', index=False)
    print(f'{code}: {len(out)} hourly bars {out["datetime"].min()}~{out["datetime"].max()}', flush=True)
print('INDEX DONE')
