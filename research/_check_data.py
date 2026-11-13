import pandas as pd
piv=pd.read_pickle('data/pivots_long_clean.pkl')
print(list(piv.keys()))
c=piv['close']
print(c.shape)
print(c.index[0], c.index[-1])
print('idx300', c.index[300])
print('len dates', len(c.index))
