import pandas as pd
for s in ['159915','510300','510500']:
    df = pd.read_csv('data/minute_etf/' + s + '_5m.csv', parse_dates=['时间'])
    print(s, df.shape, df['时间'].min(), df['时间'].max())
