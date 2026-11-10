"""tanh动态权重：前半选参(2011-2020)，后半验证(2021+)，防过拟合"""
import pandas as pd, numpy as np
import risk_control as R

rL_raw = pd.read_pickle("results/pool/long_N25_untimed_05.pkl")
midx = R._index_series("000905")
sig = (midx > midx.rolling(15).mean()).shift(1).astype(float)
rL = (rL_raw * sig.reindex(rL_raw.index).ffill().fillna(0.0)).dropna()
rS = pd.read_pickle("results/pool/ls30_05.pkl")
ix = rL.index.intersection(rS.index); a, b = rL.loc[ix], rS.loc[ix]
dev = (midx / midx.rolling(15).mean() - 1).reindex(ix).fillna(0).shift(1).fillna(0)

def stats_vals(r):
    eq = (1 + r).cumprod(); yrs = len(r) / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1; mdd = (eq / eq.cummax() - 1).min()
    vol = r.std() * np.sqrt(252); sh = r.mean() * 252 / vol
    return ann, mdd, sh, ann / abs(mdd)

tr = ix < "2021-01-01"
results = []
for center in [0.3, 0.35, 0.4]:
    for amp in [0.2, 0.3, 0.4]:
        for k in [10, 20, 40]:
            w = pd.Series(center + amp * np.tanh(dev * k), index=ix).clip(0, 1)
            r = pd.Series(w.values * a.values + (1 - w.values) * b.values, index=ix)
            an, md, sh, ca = stats_vals(r[tr])
            results.append((center, amp, k, an, md, sh, ca))
df = pd.DataFrame(results, columns=["center", "amp", "k", "ann_tr", "mdd_tr", "sh_tr", "cal_tr"])
df = df.sort_values("cal_tr", ascending=False)
print("前半Top5:", flush=True)
print(df.head(5).to_string(), flush=True)
best = df.iloc[0]
w = pd.Series(best["center"] + best["amp"] * np.tanh(dev * best["k"]), index=ix).clip(0, 1)
r = pd.Series(w.values * a.values + (1 - w.values) * b.values, index=ix)
an, md, sh, ca = stats_vals(r[~tr])
print(f"后半验证( center={best['center']} amp={best['amp']} k={best['k']} ): 年化{an:.1%} 回撤{md:.1%} 夏普{sh:.2f} Calmar{ca:.2f}", flush=True)
an0, md0, sh0, ca0 = stats_vals(r)
print(f"全样本: 年化{an0:.1%} 回撤{md0:.1%} 夏普{sh0:.2f} Calmar{ca0:.2f}", flush=True)
df.to_csv("results/regime_tanh_grid.csv", index=False)
