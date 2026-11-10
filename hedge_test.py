"""多头 + 股指对冲：r = rL - h * r_index，新对冲结构测试"""
import os
os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E, risk_control as R

rL_raw = E.returns_series("amihud", n_hold=25, rebal=40, size_range=(0.05, 0.30), cost=0.005)
print("long leg done", flush=True)
rows = []
for code in ["000905", "000852"]:
    idx = R._index_series(code)
    ri = idx.pct_change().dropna()
    ma = idx.rolling(15).mean()
    sig = (idx > ma).shift(1).astype(float)
    rL = (rL_raw * sig.reindex(rL_raw.index).ffill().fillna(0.0)).dropna()
    ix = rL.index.intersection(ri.index)
    a, b = rL.loc[ix], ri.loc[ix]
    print(f"{code} corr(long,idx)={a.corr(b):.3f}", flush=True)
    for h in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
        r = a - h * b
        # 对冲调仓成本：按月调一次 h，假设单边0.02%
        r.iloc[::21] -= 0.0002 * h
        eq = (1 + r).cumprod(); yrs = len(r) / 252
        ann = eq.iloc[-1] ** (1 / yrs) - 1; mdd = (eq / eq.cummax() - 1).min()
        vol = r.std() * np.sqrt(252); sh = r.mean() * 252 / vol
        cal = ann / abs(mdd)
        rows.append((code, h, ann, mdd, sh, cal))
        print(f"{code} h={h:.1f} ann={ann:.1%} mdd={mdd:.1%} sh={sh:.2f} cal={cal:.2f}", flush=True)
pd.DataFrame(rows, columns=["index", "h", "ann", "mdd", "sharpe", "calmar"]).to_csv("results/hedge_test.csv", index=False)
print("saved results/hedge_test.csv")
