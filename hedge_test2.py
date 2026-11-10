"""无择时多头 + 做空指数对冲（对冲承担全部择时职能）"""
import os
os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E, risk_control as R

rL_raw = E.returns_series("amihud", n_hold=25, rebal=40, size_range=(0.05, 0.30), cost=0.005)
rL_raw.to_pickle("results/pool/long_N25_untimed_05.pkl")
print("long leg done", flush=True)
rows = []
for code in ["000300", "000905", "000852"]:
    idx = R._index_series(code)
    ri = idx.pct_change().dropna()
    ix = rL_raw.index.intersection(ri.index)
    a, b = rL_raw.loc[ix], ri.loc[ix]
    print(f"{code} corr(untimed_long,idx)={a.corr(b):.3f}", flush=True)
    for h in [0.3, 0.5, 0.7, 0.9, 1.0]:
        r = a - h * b
        r.iloc[::21] -= 0.0002 * h
        eq = (1 + r).cumprod(); yrs = len(r) / 252
        ann = eq.iloc[-1] ** (1 / yrs) - 1; mdd = (eq / eq.cummax() - 1).min()
        vol = r.std() * np.sqrt(252); sh = r.mean() * 252 / vol
        rows.append((code, h, ann, mdd, sh, ann / abs(mdd)))
        print(f"{code} h={h:.1f} ann={ann:.1%} mdd={mdd:.1%} sh={sh:.2f} cal={ann/abs(mdd):.2f}", flush=True)
pd.DataFrame(rows, columns=["index", "h", "ann", "mdd", "sharpe", "calmar"]).to_csv("results/hedge_test2.csv", index=False)
print("saved results/hedge_test2.csv")
