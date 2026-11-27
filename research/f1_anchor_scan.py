"""F1 锚点敏感性扫描：因子只算一次，扫多个 shares 锚点，看历年/三关的漂移幅度"""
import os, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("ASHARE_PIVOTS", "pivots_2020_clean.pkl")
import numpy as np, pandas as pd
import engine as E, risk_control as R

FACTOR, N_HOLD, REBAL, SIZE, COST, MIN_ADV = "amihud_60", 4, 60, (0.02, 0.15), 0.005, 5e6

def run_anchor(p, fac, anchor, c, adv20, seasoned):
    p = dict(p)
    uni = pd.read_pickle(E.DATA / "universe_2020.pkl")
    fc = uni.set_index("code")["float_cap"].astype("float64")
    p["shares"] = (fc / c.loc[pd.Timestamp(anchor)]).replace([np.inf,-np.inf], np.nan).dropna().astype("float32")
    dates = c.index; rets, prev = [], set()
    for i in range(300, len(dates)-REBAL-2, REBAL):
        t, t1 = dates[i], dates[i+1]
        t2 = dates[min(i+1+REBAL, len(dates)-1)]
        valid = seasoned.loc[t] & (adv20.loc[t] > MIN_ADV) & c.loc[t].notna() & fac.loc[t].notna()
        cap = c.loc[t] * p["shares"]
        lo, hi = cap.quantile(SIZE[0]), cap.quantile(SIZE[1])
        valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
        pool = valid[valid].index
        if len(pool) < N_HOLD: continue
        picks = list(fac.loc[t, pool].nlargest(N_HOLD).index)
        seg = c.loc[t1:t2, picks].ffill()
        if len(seg) < 2: continue
        pr = seg.div(seg.iloc[0]).mean(axis=1).pct_change(fill_method=None).dropna()
        cur = set(picks); to = 1.0 if not prev else len(cur-prev)/max(len(cur),1)
        if len(pr): pr.iloc[0] -= to*2*COST
        prev = cur; rets.append(pr)
    r = pd.concat(rets).sort_index(); r = r[~r.index.duplicated(keep="first")]
    r2, _ = R.apply_index_filter(r, ma=15, cut=0.2, index_code="000852")
    def tot(a,b):
        x = r2[(r2.index>=pd.Timestamp(a))&(r2.index<=pd.Timestamp(b))]
        if not len(x): return (0.0,0.0)
        eq=(1+x).cumprod(); yrs=len(x)/252
        return (float(eq.iloc[-1]-1), float((eq/eq.cummax()-1).min()))
    def ann(a,b):
        x = r2[(r2.index>=pd.Timestamp(a))&(r2.index<=pd.Timestamp(b))]
        if not len(x): return 0.0
        eq=(1+x).cumprod(); yrs=len(x)/252
        return float(eq.iloc[-1]**(1/yrs)-1)
    out = {"anchor": anchor}
    for y in range(2020, 2027):
        out[str(y)] = tot(f"{y}-01-01", f"{y}-12-31")[0]
    out["TRAIN"] = ann("2020-01-01","2023-06-30")
    out["TEST"] = ann("2023-07-01","2024-12-31")
    out["OOS"] = ann("2025-01-01","2026-12-31")
    out["full_ann"] = ann("2011-01-01","2026-12-31")
    return out

p = E.piv(); c = p["close"].astype("float64")
adv20 = p["amount"].rolling(20, min_periods=10).mean()
seasoned = c.shift(250).notna()
print("计算 amihud_60 因子矩阵 ...", flush=True)
fac = E.FACTORS[FACTOR](p)
print("因子完成", flush=True)

_d = c.index
anchors = [str(_d[-1-k].date()) for k in (0, 1, 2, 3, 5, 8, 11, 15, 20)]
print("anchors:", anchors, flush=True)
rows = [run_anchor(p, fac, a, c, adv20, seasoned) for a in anchors]
df = pd.DataFrame(rows).set_index("anchor")
pd.set_option("display.width", 200)
print("\n=== 各锚点下的年度收益 / 三关年化 ===")
print((df[["2020","2021","2022","2023","2024","2025","2026","TRAIN","TEST","OOS","full_ann"]]*100).round(2))
print("\n=== 极差(pp) ===")
print(((df.max()-df.min())*100).round(2))
df.to_csv("results/f1_anchor_scan.csv")
print("\nsaved results/f1_anchor_scan.csv")
