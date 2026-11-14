import pandas as pd
eq = pd.read_pickle('results/r30_bt/J04_equity.pkl')
for label, tail in [('2y', 504 + 1), ('3y', 756 + 1)]:
    win = eq.tail(tail)
    print('=== %s window: %s -> %s  ret=%+.2f%% ===' % (label, win.index[0].date(), win.index[-1].date(), float(win.iloc[-1]/win.iloc[0]-1)*100))
    m = win.resample('ME').last()
    prev = float(win.iloc[0]); cum = 1.0; first = True
    for ts, v in m.items():
        v = float(v); r = v/prev - 1.0; cum *= (1.0 + r)
        tag = ' (partial)' if first else ''
        print('%s  month=%+.2f%%  cum=%+.2f%%  eq=%.2f%s' % (ts.strftime('%Y-%m'), r*100, (cum-1)*100, v, tag))
        prev = v; first = False