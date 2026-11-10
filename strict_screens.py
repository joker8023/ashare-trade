"""严格选股三策略：全部t-1收盘信号、t+1执行、允许空仓(MA15+债券)、成本0.5%+切换0.3%"""
import os; os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E
import risk_control as R

p = E.piv(); c = p["close"]
adv20 = p["amount"].rolling(20, min_periods=10).mean()
seasoned = c.shift(250).notna()
dates = c.index
midx = R._index_series("000905")
sig = (midx > midx.rolling(15).mean()).shift(1)
df = pd.read_pickle("data/bond_511880.pkl")
b = df.set_index(pd.to_datetime(df["date"])).sort_index()["close"].astype(float)
rb = (b.pct_change() + 0.03 / 252)

amihud = E.FACTORS["amihud"](p)
vol20 = c.pct_change().rolling(20).std()
rev20 = -(c / c.shift(20) - 1)
hi60 = c.rolling(60).max()
near_high = c / hi60

def base_pool(t):
    valid = seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna()
    cap = c.loc[t] * p["shares"]
    lo, hi = cap.quantile(0.05), cap.quantile(0.30)
    valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
    return valid[valid].index

def screen_A(t, pool):  # 流动性top + 低波 + 反转
    f1 = amihud.loc[t, pool].nlargest(max(len(pool) // 10, 30)).index
    f2 = vol20.loc[t, f1].nsmallest(max(len(f1) // 2, 25)).index
    return list(rev20.loc[t, f2].nlargest(25).index)

def screen_B(t, pool):  # 接近60日高点的突破质量股
    nh = near_high.loc[t, pool]
    cand = nh[(nh > 0.97) & (nh <= 1.0)].index
    if len(cand) < 10:
        return []
    return list(amihud.loc[t, cand].nlargest(25).index)

def screen_C(t, pool):  # 深度超跌 + 企稳
    deep = rev20.loc[t, pool].nlargest(max(len(pool) // 20, 30)).index
    ret5 = c.loc[t, deep] / c.shift(5).loc[t, deep] - 1
    firm = ret5[ret5 > -0.03].index
    if len(firm) < 10:
        return []
    return list(amihud.loc[t, firm].nlargest(25).index)

N, REB = 25, 40
for name, func in [("A三因子交集", screen_A), ("B高点突破", screen_B), ("C超跌企稳", screen_C)]:
    rets = []; holds = []; wins = 0; holds_n = 0
    prev = set()
    for i in range(300, len(dates) - REB - 2, REB):
        t, t1 = dates[i], dates[i + 1]; t2 = dates[min(i + 1 + REB, len(dates) - 1)]
        pool = base_pool(t)
        if len(pool) < 60:
            continue
        try:
            picks = func(t, pool)
        except Exception:
            picks = []
        cur = set(picks)
        to = 1.0 if not prev else len(cur - prev) / max(len(cur), 1)
        seg = c.loc[t1:t2, list(cur)].ffill() if cur else pd.DataFrame()
        if len(seg) < 2 or not cur:
            pr = pd.Series(0.0, index=c.loc[t1:t2].index).pct_change().fillna(0.0)
            pr.iloc[0] = 0.0
        else:
            pr = seg.div(seg.iloc[0]).mean(axis=1).pct_change(fill_method=None).dropna()
            hret = (1 + pr).prod() - 1
            holds.append(hret); holds_n += 1; wins += (hret > 0)
            if len(pr):
                pr.iloc[0] -= to * 0.005
        prev = cur
        rets.append(pr)
    r = pd.concat(rets).sort_index(); r = r[~r.index.duplicated(keep="first")]
    e = sig.reindex(r.index).ffill().fillna(0.0)
    off = rb.reindex(r.index).ffill().fillna(0.0)
    rr = r * e + off * (1 - e) - e.diff().abs().fillna(0) * 0.003
    eq = (1 + rr).cumprod(); yrs = len(rr) / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1; mdd = (eq / eq.cummax() - 1).min()
    vol = rr.std() * np.sqrt(252); sh = rr.mean() * 252 / vol
    wr = wins / holds_n if holds_n else 0
    print(f"{name}: 年化{ann:.1%} 回撤{mdd:.1%} 夏普{sh:.2f} Calmar{ann/abs(mdd):.2f} "
          f"持仓段胜率{wr:.1%}({wins}/{holds_n})", flush=True)
