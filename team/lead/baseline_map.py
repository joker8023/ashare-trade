"""Lead 独立基准图：2026 各类选股/周期的月度与分段胜率（无止损，0.5%单边）"""
import os
os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import numpy as np, pandas as pd
import engine as E
import risk_control as R

p = E.piv(); c = p["close"]; dates = c.index
adv20 = p["amount"].rolling(20, min_periods=10).mean()
seasoned = c.shift(250).notna()
cap = c * p["shares"]
amihud = E.FACTORS["amihud"](p)

def cohort_returns(fac, N, REB, cost=0.005):
    rows = []
    prev = set()
    for i in range(300, len(dates) - REB - 2, REB):
        t, t1 = dates[i], dates[i+1]; t2 = dates[i+1+REB]
        valid = seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna() & fac.loc[t].notna()
        lo, hi = cap.loc[t].quantile(0.05), cap.loc[t].quantile(0.30)
        valid &= ((cap.loc[t] >= lo) & (cap.loc[t] <= hi)).fillna(False)
        pool = valid[valid].index
        if len(pool) < N: continue
        picks = list(fac.loc[t, pool].nlargest(N).index)
        seg = c.loc[t1:t2, picks].ffill()
        if len(seg) < 2: continue
        nav = seg.div(seg.iloc[0]).mean(axis=1)
        ret = nav.pct_change(fill_method=None).dropna()
        cur = set(picks); to = 1.0 if not prev else len(cur - prev) / max(len(cur), 1)
        if len(ret): ret.iloc[0] -= to * 2 * cost
        rows.append(pd.DataFrame({"date": ret.index, "ret": ret.values, "cohort": t1}))
        prev = cur
    df = pd.concat(rows).sort_values("date")
    df = df[~df["date"].duplicated(keep="first")]
    return df.set_index("date")

def metrics(df, start="2026-01-05", base="2025-12-31"):
    r = df["ret"]
    r = r[r.index >= pd.Timestamp(start)]
    # 基数：2025-12-31 前最后一个净值
    pre = df[df.index <= pd.Timestamp(base)]["ret"]
    eq0 = (1 + pre).prod() if len(pre) else 1.0
    eq = eq0 * (1 + r).cumprod()
    total = eq.iloc[-1] / eq0 - 1
    n = len(r); ann = (1 + total) ** (252 / n) - 1 if n else np.nan
    mdd = (eq / eq.cummax() - 1).min()
    monthly = eq.resample("ME").last().pct_change().dropna()
    # 首月补基数
    first_m = eq[eq.index.month == 1]
    if len(first_m):
        monthly.iloc[0] = first_m.iloc[-1] / eq0 - 1
    seg = df[df.index >= pd.Timestamp(start)].groupby("cohort")["ret"].apply(lambda x: (1 + x).prod() - 1)
    return dict(total=total, ann=ann, mdd=mdd, n=n,
                win_month=(monthly > 0).sum() / len(monthly), n_month=len(monthly),
                win_period=(seg > 0).sum() / len(seg), n_period=len(seg),
                win_day=(r > 0).sum() / len(r))

if __name__ == "__main__":
    out = []
    for name in ["amihud", "vol20", "rev20", "turn20", "size", "amount_level"]:
        fac = E.FACTORS[name](p)
        for N in [2, 3, 5, 8, 12, 25]:
            for REB in [7, 15, 30]:
                try:
                    df = cohort_returns(fac, N, REB)
                    m = metrics(df)
                    m.update(selector=name, N=N, REB=REB)
                    out.append(m)
                except Exception as e:
                    print("ERR", name, N, REB, e, flush=True)
    res = pd.DataFrame(out)
    res = res[["selector","N","REB","total","ann","mdd","win_period","n_period","win_month","n_month","win_day"]]
    res.to_csv("team/lead/baseline_map.csv", index=False)
    pd.set_option("display.width", 200)
    print(res.sort_values("total", ascending=False).head(30).to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print("\n=== 按 2026 total 排序，同时 mdd<=0.15 且 win_period>=0.8 ===")
    sel = res[(res.mdd >= -0.15) & (res.win_period >= 0.8)]
    print(sel.sort_values("total", ascending=False).to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print("\n=== 2026 月收益分布（等权小微盘 amihud N25 R7）===")
    df = cohort_returns(amihud, 25, 7)
    r = df["ret"]; r = r[r.index >= "2026-01-05"]
    eq = (1 + r).cumprod(); m = eq.resample("ME").last().pct_change().dropna()
    first = eq[eq.index.month == 1]
    if len(first): m.iloc[0] = first.iloc[-1] - 1
    print((m * 100).round(2).to_string())
