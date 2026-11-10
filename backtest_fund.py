"""基本面月频回测: t月末截面选股, t+1月持有, 等权, 单边成本0.5%按换手扣.
组合: PE最低30 / PB最低30 (/股息率最高30, 仅tushare源), 全池 + 市值5%-30%分位池.
数据源 (--src auto|tushare|value_em, 默认auto优先value_em):
  - tushare: data/fund_daily_basic.pkl (fetch_fund.py, PE/PB/股息率/total_mv)
  - value_em: data/value_em.pkl (ak.stock_value_em, PE-TTM/市净率/市销率自2018起,
              无股息率→跳过DIV组; 规模池用 流通市值=close*shares, 与engine一致)
输出: results/<--out>, 默认 fund_monthly.csv + 与amihud多头日收益相关系数
用法: ASHARE_PIVOTS=pivots_long_clean.pkl .venv/bin/python backtest_fund.py [--src value_em] [--out fund_monthly.csv]
"""
import os
import numpy as np
import pandas as pd

import pathlib
BASE = pathlib.Path(__file__).resolve().parent
DATA = BASE / "data"
OUT = BASE / "results"
TS_CACHE = DATA / "fund_daily_basic.pkl"
EM_CACHE = DATA / "value_em.pkl"
N = 30
COST = 0.005

def ts2code(s):
    return str(s).split(".")[0].zfill(6)

def metrics_from_monthly(mret: pd.Series):
    mret = mret.dropna()
    if len(mret) < 12:
        return None
    eq = (1 + mret).cumprod()
    total = eq.iloc[-1] - 1
    ann = float(eq.iloc[-1] ** (12 / len(mret)) - 1)
    vol = float(mret.std() * np.sqrt(12))
    sharpe = float(mret.mean() / mret.std() * np.sqrt(12)) if mret.std() > 0 else np.nan
    mdd = float((eq / eq.cummax() - 1).min())
    calmar = float(ann / abs(mdd)) if mdd < 0 else np.nan
    return dict(n_months=len(mret), ann=ann, vol=vol, sharpe=sharpe,
                mdd=mdd, calmar=calmar, total=total,
                period=f"{mret.index[0].date()}~{mret.index[-1].date()}")

def month_end_dates(close, start="2018-01-01", end="2026-10-31"):
    s = pd.Series(close.index, index=close.index)
    me = s.groupby(s.index.to_period("M")).max().sort_values()
    me = me[(me >= start) & (me <= end)]
    return [d.strftime("%Y%m%d") for d in me]

def picks_from_tushare(cache, months, close):
    """返回 picks_hist(含DIV)"""
    ports = ["PE_all", "PB_all", "DIV_all", "PE_sz", "PB_sz", "DIV_sz"]
    picks = {k: {} for k in ports}
    for d in months:
        df = cache[d].copy()
        df["code"] = df["ts_code"].apply(ts2code)
        df = df[df["code"].isin(close.columns)].dropna(subset=["close"])
        if len(df) < 100:
            continue
        lo, hi = df["total_mv"].quantile(0.05), df["total_mv"].quantile(0.30)
        sz = df[(df["total_mv"] >= lo) & (df["total_mv"] <= hi)]
        picks["PE_all"][d] = df[(df["pe"].notna()) & (df["pe"] > 0)].nsmallest(N, "pe")["code"].tolist()
        picks["PB_all"][d] = df[(df["pb"].notna()) & (df["pb"] > 0)].nsmallest(N, "pb")["code"].tolist()
        picks["DIV_all"][d] = df[df["dv_ratio"].notna()].nlargest(N, "dv_ratio")["code"].tolist()
        picks["PE_sz"][d] = sz[(sz["pe"].notna()) & (sz["pe"] > 0)].nsmallest(N, "pe")["code"].tolist()
        picks["PB_sz"][d] = sz[(sz["pb"].notna()) & (sz["pb"] > 0)].nsmallest(N, "pb")["code"].tolist()
        picks["DIV_sz"][d] = sz[sz["dv_ratio"].notna()].nlargest(N, "dv_ratio")["code"].tolist()
    return picks

def picks_from_valueem(vem, months, close, dmap, shares):
    """EM估值: 月末as-of取值(无未来函数); 无股息率, 规模池用流通市值."""
    ports = ["PE_all", "PB_all", "PE_sz", "PB_sz"]
    picks = {k: {} for k in ports}
    codes = [c for c in vem if c in close.columns]
    print(f"EM覆盖 {len(codes)} 只(与价格序列交集)")
    for d in months:
        t = dmap[d]
        pe_s, pb_s = {}, {}
        for c in codes:
            df = vem[c]
            if t < df.index[0]:
                continue
            try:
                row = df.loc[:t].iloc[-1]
            except Exception:
                continue
            pe, pb = row["PE(TTM)"], row["市净率"]
            if pd.notna(pe) and pe > 0:
                pe_s[c] = pe
            if pd.notna(pb) and pb > 0:
                pb_s[c] = pb
        if len(pe_s) < 100:
            continue
        pe_ser, pb_ser = pd.Series(pe_s), pd.Series(pb_s)
        cap = close.loc[t] * shares
        def in_pool(s):
            cc = cap.reindex(s.index).dropna()
            lo, hi = cc.quantile(0.05), cc.quantile(0.30)
            return set(cc[(cc >= lo) & (cc <= hi)].index)
        pe_pool, pb_pool = in_pool(pe_ser), in_pool(pb_ser)
        picks["PE_all"][d] = pe_ser.nsmallest(N).index.tolist()
        picks["PB_all"][d] = pb_ser.nsmallest(N).index.tolist()
        picks["PE_sz"][d] = pe_ser.loc[list(pe_pool)].nsmallest(N).index.tolist()
        picks["PB_sz"][d] = pb_ser.loc[list(pb_pool)].nsmallest(N).index.tolist()
    return picks

def run_picks(picks, close, tdates, dmap):
    """picks_hist -> {mrets, drets}"""
    mrets, drets = {}, {}
    for k, h in picks.items():
        ds = sorted(h)
        prev = set()
        mrows, dsegs = [], []
        for d in ds:
            t = dmap[d]
            i = tdates.get_loc(t)
            fut = [x for x in ds if dmap[x] > t]
            tend = dmap[fut[0]] if fut else tdates[-1]
            j = tdates.get_loc(tend)
            if j <= i + 1:
                continue
            seg = close.iloc[i + 1:j + 1][h[d]].ffill().dropna(axis=1)
            if seg.shape[1] < 10:
                continue
            mret = float(seg.iloc[-1].div(seg.iloc[0]).mean() - 1)
            cur = set(h[d])
            to = 1.0 if not prev else len(cur - prev) / max(len(cur), 1)
            mret -= to * 2 * COST
            mrows.append((tend, mret))
            dr = seg.div(seg.iloc[0]).mean(axis=1).pct_change().dropna()
            if len(dr):
                dr.iloc[0] -= to * 2 * COST
                dsegs.append(dr)
            prev = cur
        if not mrows:
            continue
        ms = pd.Series({pd.Timestamp(t): v for t, v in mrows}).sort_index()
        ds_ = pd.concat(dsegs).sort_index()
        ds_ = ds_[~ds_.index.duplicated(keep="first")]
        mrets[k], drets[k] = ms, ds_
        pm = metrics_from_monthly(ms)
        print(k, {kk: round(v, 4) if isinstance(v, float) else v for kk, v in pm.items()} if pm else None)
    return mrets, drets

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="fund_monthly.csv")
    ap.add_argument("--src", default="auto", choices=["auto", "tushare", "value_em"])
    a = ap.parse_args()
    os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
    import engine

    src = a.src
    if src == "auto":
        src = "value_em" if EM_CACHE.exists() else "tushare"
    print(f"数据源: {src}")

    piv = pd.read_pickle(DATA / os.getenv("ASHARE_PIVOTS", "pivots_long_clean.pkl"))
    close = piv["close"]
    tdates = close.index
    dmap = {d.strftime("%Y%m%d"): d for d in tdates}

    if src == "value_em":
        import pickle
        if not EM_CACHE.exists():
            print("data/value_em.pkl 尚未落盘, 等待 dl_value_em.py")
            return
        with open(EM_CACHE, "rb") as f:
            vem = pickle.load(f)
        months = [d for d in month_end_dates(close) if d in dmap and dmap[d] != tdates[-1]]
        print(f"formation 月: {len(months)} ({months[0]}~{months[-1]})")
        picks = picks_from_valueem(vem, months, close, dmap, piv["shares"])
    else:
        if not TS_CACHE.exists():
            print("无缓存 data/fund_daily_basic.pkl, fetch_fund.py 仍在拉取中")
            return
        cache = pd.read_pickle(TS_CACHE)
        print(f"Tushare缓存 {len(cache)} 个月")
        if len(cache) < 12:
            print("月份不足12个, 暂不回测"); return
        months = sorted([d for d in cache if d in dmap and dmap[d] != tdates[-1]])
        print(f"formation 月: {len(months)} ({months[0]}~{months[-1]})")
        picks = picks_from_tushare(cache, months, close)

    mrets, drets = run_picks(picks, close, tdates, dmap)
    if not mrets:
        print("无有效组合"); return

    print("amihud 多头序列(engine)...")
    am = engine.returns_series("amihud", n_hold=25, rebal=40,
                               size_range=(0.05, 0.30), cost=COST)
    rows = []
    for k in mrets:
        pm = metrics_from_monthly(mrets[k])
        a_, b_ = am.reindex(drets[k].index).dropna(), drets[k].reindex(am.index).dropna()
        idx = a_.index.intersection(b_.index)
        corr = float(pd.Series(a_.loc[idx]).corr(pd.Series(b_.loc[idx]))) if len(idx) > 50 else np.nan
        rows.append(dict(strategy=k, src=src, corr_amihud=round(corr, 3),
                         **{kk: (round(v, 4) if isinstance(v, float) else v)
                             for kk, v in pm.items()}))
    res = pd.DataFrame(rows)
    OUT.mkdir(exist_ok=True)
    res.to_csv(OUT / a.out, index=False, encoding="utf-8")
    print(res.to_string(index=False))
    tag = " (样本期短, 中期结果仅供参考)" if "interim" in a.out else ""
    print(f"-> results/{a.out}{tag}")

if __name__ == "__main__":
    main()
