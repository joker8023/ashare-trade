"""空头腿改良 sweep: N x rebal x timing, cost=0.005, 与固定多头混合."""
import os
os.environ["ASHARE_PIVOTS"] = "pivots_long_clean.pkl"
import pandas as pd, numpy as np
import engine as E
import risk_control as R

COST = 0.005
p = E.piv(); c = p["close"]
adv20 = p["amount"].rolling(20, min_periods=10).mean()
seasoned = c.shift(250).notna()
fac = E.FACTORS["amihud"](p)
shares = p["shares"]
dates = c.index

# timing 信号: 中证500 > MA15, shift(1) 防未来
try:
    idx = R._index_series("000905")
    ma = idx.rolling(15).mean()
    sig = (idx > ma).shift(1).astype(float).reindex(dates).ffill().fillna(0.0)
    print("timing信号: 000905 缓存命中", flush=True)
except Exception as e:
    print(f"timing指数读取失败({e}), 用本地宽基替代", flush=True)
    mkt = c.median(axis=1)
    sig = (mkt > mkt.rolling(15).mean()).shift(1).astype(float).fillna(0.0)

# 多头腿固定
import pathlib
lp = pathlib.Path("results/pool/long_N25.pkl")
if lp.exists():
    rL_full = pd.read_pickle(lp)
    print(f"多头复用 {lp} len={len(rL_full)}", flush=True)
else:
    r = E.returns_series("amihud", n_hold=25, rebal=40, size_range=(0.05, 0.30), cost=COST)
    on = sig.reindex(r.index).ffill().fillna(0.0)
    rL_full = (r * on).dropna()
    rL_full.to_pickle(lp)

def build_short(N, rebal):
    rets = []; prev_l = set(); prev_s = set()
    for i in range(300, len(dates) - rebal - 2, rebal):
        t, t1 = dates[i], dates[i+1]
        t2 = dates[min(i+1+rebal, len(dates)-1)]
        valid = seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna() & fac.loc[t].notna()
        cap = c.loc[t] * shares
        lo, hi = cap.quantile(0.05), cap.quantile(0.30)
        valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
        pool = valid[valid].index
        if len(pool) < 2*N:
            continue
        fv = fac.loc[t, pool]
        longs = list(fv.nlargest(N).index); shorts = list(fv.nsmallest(N).index)
        seg = c.loc[t1:t2, longs+shorts].ffill()
        if len(seg) < 2:
            continue
        rel = seg.div(seg.iloc[0])
        pr = 0.5*rel[longs].mean(axis=1).pct_change(fill_method=None) - 0.5*rel[shorts].mean(axis=1).pct_change(fill_method=None)
        pr = pr.dropna()
        if len(pr) == 0:
            continue
        if not prev_l:
            to = 2.0  # 首建双腿全仓
        else:
            to = len(set(longs)-prev_l)/N + len(set(shorts)-prev_s)/N
        pr.iloc[0] -= to * COST  # 单边0.5% × 换手(双腿加总)
        prev_l, prev_s = set(longs), set(shorts)
        rets.append(pr)
    rS = pd.concat(rets).sort_index() if rets else pd.Series(dtype=float)
    return rS[~rS.index.duplicated(keep="first")].sort_index()

def metrics(r):
    r = r.dropna()
    eq = (1+r).cumprod(); yrs = len(r)/252
    ann = float(eq.iloc[-1]**(1/yrs)-1)
    mdd = float((eq/eq.cummax()-1).min())
    vol = float(r.std()*np.sqrt(252))
    sh = float(r.mean()*252/vol) if vol > 0 else 0.0
    cal = float(ann/abs(mdd)) if mdd < 0 else 0.0
    return ann, mdd, sh, cal

rows = []
for N in [20, 30, 50]:
    for rebal in [20, 40]:
        rS0 = build_short(N, rebal)
        print(f"short N={N} R={rebal} len={len(rS0)}", flush=True)
        for tm in ["off", "on"]:
            rS = rS0 if tm == "off" else (rS0 * sig.reindex(rS0.index).ffill().fillna(0.0))
            ix = rL_full.index.intersection(rS.index)
            a = rL_full.loc[ix]; b = rS.loc[ix]
            corr = float(a.corr(b))
            for w in [0.3, 0.4, 0.5]:
                r = w*a + (1-w)*b
                ann, mdd, sh, cal = metrics(r)
                rows.append(dict(short_N=N, short_rebal=rebal, timing=tm, w=w,
                                 ann=round(ann,4), mdd=round(mdd,4),
                                 sharpe=round(sh,3), calmar=round(cal,3),
                                 corr=round(corr,3), n_days=len(r)))
df = pd.DataFrame(rows).sort_values(["calmar"], ascending=False)
df.to_csv("results/shortleg_test.csv", index=False, encoding="utf-8")
print(df.to_string(index=False))
print("saved results/shortleg_test.csv")
