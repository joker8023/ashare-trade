import pandas as pd
s = pd.read_csv('f1_train_picks_sina.csv', dtype={'code': str})
p = pd.read_pickle('data/pivots_long_clean.pkl')
rows = []
for _, r in s.iterrows():
    t = pd.Timestamp(r['signal_date']); code = r['code'].zfill(6)
    rows.append({'signal_date': r['signal_date'], 'code': code,
                 'close_tushare_qfq': float(p['close'].loc[t, code]),
                 'amount_tushare': float(p['amount'].loc[t, code])})
pd.DataFrame(rows).to_csv('f1_train_picks_tushare.csv', index=False)
print('done', len(rows))
