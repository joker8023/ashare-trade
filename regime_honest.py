"""动态权重 × 诚实成本双腿（无未来函数：信号shift(1)，分位数expanding）"""
import os
os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E, risk_control as R

COST = 0.005
# 多头：无择时序列（已存）+ MA15 择时
rL_raw = pd.read_pickle("results/pool/long_N25_untimed_05.pkl")
midx = R._index_series("000905")
sig = (midx > midx.rolling(15).mean()).shift(1).astype(float)
rL = (rL_raw * sig.reindex(rL_raw.index).ffill().fillna(0.0)).dropna()

# 空头腿 N=30, R=60, cost=0.005
p = E.piv(); c = p["close"]
adv20 = p["amount"].rolling(20, min_periods=10).mean()
seasoned = c.shift(250).notna(); fac = E.FACTORS["amihud"](p)
rets = []; prev_l = set(); prev_s = set()
for i in range(300, len(c.index) - 60 - 2, 60):
    t = c.index[i]; t1 = c.index[i + 1]; t2 = c.index[min(i + 61, len(c.index) - 1)]
    valid = seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna() & fac.loc[t].notna()
    cap = c.loc[t] * p["shares"]; lo, hi = cap.quantile(0.05), cap.quantile(0.30)
    valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
    pool = valid[valid].index
    if len(pool) < 60:
        continue
    fv = fac.loc[t, pool]
    longs = list(fv.nlargest(30).index); shorts = list(fv.nsmallest(30).index)
    seg = c.loc[t1:t2, longs + shorts].ffill()
    if len(seg) < 2:
        continue
    rel = seg.div(seg.iloc[0])
    pr = 0.5 * rel[longs].mean(axis=1).pct_change(fill_method=None) - 0.5 * rel[shorts].mean(axis=1).pct_change(fill_method=None)
    pr = pr.dropna()
    to = 1.0 if not prev_l else (len(set(longs) - prev_l) / 30 + len(set(shorts) - prev_s) / 30) / 2
    if len(pr):
        pr.iloc[0] -= to * COST
    prev_l, prev_s = set(longs), set(shorts)
    rets.append(pr)
rS = pd.concat(rets).sort_index()
rS = rS[~rS.index.duplicated(keep="first")]
rS.to_pickle("results/pool/ls30_05.pkl")
print(f"legs ready: long {len(rL)}, short {len(rS)}", flush=True)

ix = rL.index.intersection(rS.index); a, b = rL.loc[ix], rS.loc[ix]
dev = (midx / midx.rolling(15).mean() - 1).reindex(ix).fillna(0).shift(1).fillna(0)

def stats(r, label):
    eq = (1 + r).cumprod(); yrs = len(r) / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1; mdd = (eq / eq.cummax() - 1).min()
    vol = r.std() * np.sqrt(252); sh = r.mean() * 252 / vol
    print(f"{label:24s} 年化{ann:6.1%} 回撤{mdd:7.1%} 夏普{sh:5.2f} Calmar{ann/abs(mdd):5.2f}", flush=True)
    return ann, mdd, sh, ann / abs(mdd)

rows = []
for w in [0.3, 0.4, 0.5]:
    r = w * a + (1 - w) * b
    an, md, sh, ca = stats(r, f"固定w={w}")
    rows.append(("fixed_" + str(w), an, md, sh, ca))

w = pd.Series(np.where(dev > 0, 0.7, 0.3), index=ix)
r = pd.Series(w.values * a.values + (1 - w.values) * b.values, index=ix)
an, md, sh, ca = stats(r, "牛0.7熊0.3(shift1)")
rows.append(("bullbear", an, md, sh, ca))

exp_q10 = dev.expanding(min_periods=252).quantile(0.1)
exp_q90 = dev.expanding(min_periods=252).quantile(0.9)
norm = ((dev - exp_q10) / (exp_q90 - exp_q10)).clip(0, 1).fillna(0.5)
w = 0.2 + 0.6 * norm
r = pd.Series(w.values * a.values + (1 - w.values) * b.values, index=ix)
an, md, sh, ca = stats(r, "连续偏离度(expanding)")
rows.append(("continuous", an, md, sh, ca))

w = 0.35 + 0.3 * np.tanh(dev * 20)
w = pd.Series(w, index=ix)
r = pd.Series(w.values * a.values + (1 - w.values) * b.values, index=ix)
an, md, sh, ca = stats(r, "tanh平滑切换")
rows.append(("tanh", an, md, sh, ca))

pd.DataFrame(rows, columns=["rule", "ann", "mdd", "sharpe", "calmar"]).to_csv("results/regime_honest.csv", index=False)
print("saved results/regime_honest.csv")
