"""任务B: 行业动量轮动测试. 只用t及以前数据, t+1建仓."""
import os
os.environ["ASHARE_PIVOTS"] = "pivots_long_clean.pkl"
import numpy as np
import pandas as pd
import engine

COST = 0.005
START = pd.Timestamp("2015-01-01")

p = engine.piv()
close = p["close"]
dates = close.index

mp = pd.read_pickle("data/industry_map.pkl")
mp = mp[mp["code"].isin(close.columns)].copy()
print("mapped stocks:", len(mp), "industries:", mp["industry"].nunique())

# ---- 1. 行业指数: 成员个股日收益等权平均(仅当日在架), 累乘成指数 ----
ret = close.pct_change(fill_method=None)
ind_ret = {}
for ind, g in mp.groupby("industry"):
    cols = [c for c in g["code"].tolist() if c in ret.columns]
    m = ret[cols]
    # 当日在架股票平均
    ind_ret[ind] = m.mean(axis=1, skipna=True)
ind_ret = pd.DataFrame(ind_ret)  # date x 221
print("industry index shape:", ind_ret.shape)
ind_level = (1 + ind_ret.fillna(0)).cumprod()
# 注: fillna(0)仅用于全缺失日(极少, 该行业当日无在架股票则指数持平)

# ---- 2/3. 每20交易日按过去60日动量选TopK, t+1执行, 成本单边0.5% ----
sched = dates[dates >= START]
assert len(sched) > 100
# 首个决策日需有60日历史
rebal_idx = list(range(0, len(sched) - 21, 20))  # 相对sched的位置
print("rebal dates:", len(rebal_idx), sched[0].date(), "->", sched[-1].date())

def run_topk(K):
    rets, prev = [], set()
    for j in rebal_idx:
        t = sched[j]
        ti = dates.get_loc(t)
        mom = ind_level.iloc[ti] / ind_level.iloc[ti - 60] - 1  # 只用<=t数据
        mom = mom.dropna()
        top = mom.nlargest(K).index.tolist()
        picks = mp[mp["industry"].isin(top)]["code"].tolist()
        picks = [c for c in picks if c in close.columns]
        t1 = dates[ti + 1]
        t2 = dates[min(ti + 1 + 20, len(dates) - 1)]
        seg = close.loc[t1:t2, picks].ffill()
        if len(seg) < 2:
            continue
        pr = seg.div(seg.iloc[0]).mean(axis=1).pct_change(fill_method=None).dropna()
        cur = set(picks)
        to = 1.0 if not prev else len(cur - prev) / max(len(cur), 1)
        if len(pr):
            pr.iloc[0] -= to * 2 * COST  # 与engine一致: 单边cost, 按换手双边扣
        prev = cur
        rets.append(pr)
    r = pd.concat(rets).sort_index()
    return r[~r.index.duplicated(keep="first")]

def run_ew():
    """行业等权基准: 持有全部221行业(成分等权), 同样t+1/20日轮仓, 同成本规则"""
    rets, prev = [], set()
    for j in rebal_idx:
        t = sched[j]
        ti = dates.get_loc(t)
        picks = [c for c in mp["code"].tolist() if c in close.columns]
        t1 = dates[ti + 1]
        t2 = dates[min(ti + 1 + 20, len(dates) - 1)]
        seg = close.loc[t1:t2, picks].ffill()
        if len(seg) < 2:
            continue
        pr = seg.div(seg.iloc[0]).mean(axis=1).pct_change(fill_method=None).dropna()
        cur = set(picks)
        to = 1.0 if not prev else len(cur - prev) / max(len(cur), 1)
        if len(pr):
            pr.iloc[0] -= to * 2 * COST
        prev = cur
        rets.append(pr)
    r = pd.concat(rets).sort_index()
    return r[~r.index.duplicated(keep="first")]

r_top3 = run_topk(3)
r_top5 = run_topk(5)
r_ew = run_ew()
print("days:", len(r_top3), len(r_top5), len(r_ew))

# amihud多头基准 (engine口径) + 截2015起对齐
r_ami = engine.returns_series("amihud", n_hold=25, rebal=40,
                              size_range=(0.05, 0.30), cost=0.005)
r_ami = r_ami[r_ami.index >= START]
print("amihud days:", len(r_ami))

def metrics(r, name):
    r = r.sort_index()
    eq = (1 + r).cumprod()
    yrs = len(eq) / 252
    ann = float(eq.iloc[-1] ** (1 / yrs) - 1)
    vol = float(r.std() * np.sqrt(252))
    mdd = float((eq / eq.cummax() - 1).min())
    sh = float(r.mean() * 252 / vol) if vol > 0 else np.nan
    return {"strategy": name, "ann": round(ann, 4),
            "mdd": round(mdd, 4), "sharpe": round(sh, 3),
            "calmar": round(ann / abs(mdd), 3) if mdd < 0 else None,
            "period": f"{r.index[0].date()}~{r.index[-1].date()}", "days": len(r)}

tab = pd.DataFrame([metrics(r_top3, "ind_mom_Top3"),
                    metrics(r_top5, "ind_mom_Top5"),
                    metrics(r_ew, "industry_equalweight"),
                    metrics(r_ami, "amihud_long")])
tab.to_csv("results/ind_mom.csv", index=False)
print(tab.to_string(index=False))

# 相关系数 (日收益, 对齐后)
al = pd.DataFrame({"top3": r_top3, "top5": r_top5, "ami": r_ami}).dropna()
print("\ncorr(top3, amihud) =", round(float(al["top3"].corr(al["ami"])), 4))
print("corr(top5, amihud) =", round(float(al["top5"].corr(al["ami"])), 4))
print("corr(top3, indEW) =", round(float(pd.DataFrame({'a':r_top3,'b':r_ew}).dropna()['a'].corr(pd.DataFrame({'a':r_top3,'b':r_ew}).dropna()['b'])), 4))
