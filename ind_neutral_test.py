"""行业中性化 amihud vs 基准对比 (自写行业中性版, 参考engine.py returns_series逻辑)."""
import pickle
import numpy as np
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent
P = pickle.load(open(BASE / "data" / "pivots_long_clean.pkl", "rb"))
CLOSE, AMOUNT, SHARES = P["close"], P["amount"], P["shares"]
IMAP = pd.read_pickle(BASE / "data" / "industry_map.pkl")
IND = dict(zip(IMAP["code"].astype(str), IMAP["industry"].astype(str)))
COL_IND = pd.Series([IND.get(str(c), "UNKNOWN") for c in CLOSE.columns], index=CLOSE.columns)

# amihud = mean(|日收益|/成交额), 20日均, 只用t及以前
ret = CLOSE.pct_change(fill_method=None).abs()
amt = AMOUNT.replace(0, np.nan)
AMIHUD = (ret / (amt / 1e8)).rolling(20).mean()

ADV20 = AMOUNT.rolling(20, min_periods=10).mean()
SEASONED = CLOSE.shift(250).notna()
DATES = CLOSE.index
START = pd.Timestamp("2015-01-01")
COST, SIZE_RANGE, MIN_ADV = 0.005, (0.05, 0.30), 5e6


def zscore_neutral(f_t):
    """行业内z-score: (x-行业均值)/行业std; 小组/std=0则z=0"""
    df = pd.DataFrame({"f": f_t, "ind": COL_IND})
    df = df[df["f"].notna()]
    g = df.groupby("ind")["f"]
    mu = g.transform("mean")
    sd = g.transform("std").replace(0, np.nan)
    z = (df["f"] - mu) / sd
    z = z.fillna(0.0)  # 单样本组/std=0 -> 0
    return z


def run(n_hold, rebal, neutral):
    prev = set()
    port_rets, turns = [], []
    for i in range(300, len(DATES) - rebal - 2, rebal):
        t, t1 = DATES[i], DATES[i + 1]
        t2 = DATES[min(i + 1 + rebal, len(DATES) - 1)]
        f_t = AMIHUD.loc[t]
        valid = SEASONED.loc[t] & (ADV20.loc[t] > MIN_ADV) & CLOSE.loc[t].notna() & f_t.notna()
        cap = CLOSE.loc[t] * SHARES  # Series按code对齐
        lo, hi = cap.quantile(SIZE_RANGE[0]), cap.quantile(SIZE_RANGE[1])
        valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
        pool = valid[valid].index
        if len(pool) < max(n_hold, 100):
            continue
        fv = f_t.loc[pool]
        if neutral:
            fv = zscore_neutral(fv)
        picks = list(fv.nlargest(n_hold).index)  # top N (高amihud=非流动性溢价)
        seg = CLOSE.loc[t1:t2, picks].ffill()
        if len(seg) < 2:
            continue
        pr = seg.div(seg.iloc[0]).mean(axis=1).pct_change(fill_method=None).dropna()
        cur = set(picks)
        to = 1.0 if not prev else len(cur - prev) / max(len(cur), 1)
        turns.append(to)
        if len(pr):
            pr.iloc[0] -= to * 2 * COST
        prev = cur
        port_rets.append(pr)
    r = pd.concat(port_rets).sort_index()
    r = r[~r.index.duplicated(keep="first")]
    r = r[r.index >= START]
    eq = (1 + r).cumprod()
    yrs = len(eq) / 252
    ann = float(eq.iloc[-1] ** (1 / yrs) - 1)
    vol = float(r.std() * np.sqrt(252))
    mdd = float((eq / eq.cummax() - 1).min())
    sharpe = float(r.mean() * 252 / vol) if vol > 0 else np.nan
    calmar = float(ann / abs(mdd)) if mdd < 0 else np.nan
    return dict(n_hold=n_hold, rebal=rebal, ann=round(ann, 4), vol=round(vol, 4),
                sharpe=round(sharpe, 3), mdd=round(mdd, 4), calmar=round(calmar, 3),
                turnover=round(float(np.mean(turns)), 3), days=int(len(r)),
                period=f"{r.index[0].date()}~{r.index[-1].date()}")


rows = []
for n in (25, 50):
    for rb in (40, 60):
        b = run(n, rb, neutral=False); b["version"] = "baseline"
        z = run(n, rb, neutral=True); z["version"] = "ind_neutral"
        z["calmar_gain"] = round(z["calmar"] - b["calmar"], 3)
        rows += [b, z]
        print(f"N={n} rebal={rb}: base ann={b['ann']} mdd={b['mdd']} calmar={b['calmar']} | "
              f"neutral ann={z['ann']} mdd={z['mdd']} calmar={z['calmar']} gain={z['calmar_gain']}", flush=True)
df = pd.DataFrame(rows, columns=["n_hold", "rebal", "version", "ann", "vol", "sharpe",
                                 "mdd", "calmar", "calmar_gain", "turnover", "days", "period"])
df.to_csv(BASE / "results" / "ind_neutral.csv", index=False, encoding="utf-8")
print(df.to_string(index=False))
