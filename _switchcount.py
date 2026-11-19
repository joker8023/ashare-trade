import pandas as pd
piv = pd.read_pickle("data/pivots_2020_clean.pkl")
close = piv["close"]
rets = close.pct_change(fill_method=None)
eq_idx = (1 + rets.mean(axis=1, skipna=True).fillna(0)).cumprod()
dates = close.index
gridA = [dates[i] for i in range(300, len(dates), 20)]
gridB = [dates[i] for i in range(300, len(dates), 30)]
for lb, ma in [(20, 60), (30, 90), (20, 120)]:
    ma_s = eq_idx.rolling(lb).mean()
    ma_l = eq_idx.rolling(ma).mean()
    for thr in [0.01, 0.02, 0.03, 0.05]:
        regs = []
        for d in sorted(set(gridA) | set(gridB)):
            if d < pd.Timestamp("2023-01-03"):
                continue
            a = ma_s.loc[d]
            b = ma_l.loc[d]
            if pd.isna(a) or pd.isna(b):
                regs.append("SIDE")
            else:
                g = float(a / b - 1)
                if g > thr:
                    regs.append("BULL")
                elif g < -thr:
                    regs.append("BEAR")
                else:
                    regs.append("SIDE")
        sw = sum(1 for i in range(1, len(regs)) if regs[i] != regs[i-1])
        from collections import Counter
        print("lb" + str(lb) + " ma" + str(ma) + " thr" + str(thr) + " sw=" + str(sw) + " " + str(dict(Counter(regs))))
