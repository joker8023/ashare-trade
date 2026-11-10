"""组合策略滚动样本外验证
============================
每年初只用历史数据选 blend 权重, 跑下一年。
验证 20.5%/-8.2% 不是挑出来的。
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import engine as E

BASE = Path(__file__).resolve().parent
OUT = BASE / "results" / "wf_blend"
OUT.mkdir(parents=True, exist_ok=True)
CACHE = OUT / "blend_series.pkl"


def build_series():
    import combo_lab as C
    import strategy_lab as S
    import risk_control as R

    p = E.piv()
    c = p["close"]
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    atr = C.get_atr(14)
    ratio = C.combo_rank("amihud+amount_level")
    liquid = (adv20 > 20_000_000) & c.notna()
    gate = (ratio >= 0.75) & liquid
    d0 = pd.Timestamp("2015-01-01")
    idx = c.index[c.index >= d0]
    cols = c.columns

    def cut(x):
        return x.reindex(index=idx, columns=cols).where(gate.reindex(index=idx, columns=cols))

    # 多头腿
    buy = (c - 0.3 * atr).shift(1)
    sell = buy + 0.8 * atr.shift(1)
    stop = buy - 10 * atr.shift(1)
    eqL, _ = S.backtest(p, cut(buy), cut(sell), cut(stop), cost=0.0015,
                        market_scale=C._market_scale(p, 15, "000905"), liquidate_on_off=True)
    rL = eqL.pct_change(fill_method=None).dropna()

    # 空头腿系列 (N=30/50/100)
    seasoned = c.shift(250).notna()
    fac = E.FACTORS["amihud"](p)
    out = {"long": rL}
    for n in [30, 50, 100]:
        rets = []
        pl, ps = set(), set()
        for i in range(300, len(c.index) - 60 - 2, 60):
            t = c.index[i]; t1 = c.index[i + 1]; t2 = c.index[min(i + 61, len(c.index) - 1)]
            valid = seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna() & fac.loc[t].notna()
            cap = c.loc[t] * p["shares"]
            lo, hi = cap.quantile(0.05), cap.quantile(0.30)
            valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
            pool = valid[valid].index
            if len(pool) < 2 * n:
                continue
            fv = fac.loc[t, pool]
            longs = list(fv.nlargest(n).index); shorts = list(fv.nsmallest(n).index)
            seg = c.loc[t1:t2, longs + shorts].ffill()
            if len(seg) < 2:
                continue
            rel = seg.div(seg.iloc[0])
            pr = 0.5 * rel[longs].mean(axis=1).pct_change(fill_method=None) - 0.5 * rel[shorts].mean(axis=1).pct_change(fill_method=None)
            pr = pr.dropna()
            to = 1.0 if not pl else (len(set(longs) - pl) / n + len(set(shorts) - ps) / n) / 2
            if len(pr):
                pr.iloc[0] -= to * 2 * 0.0015
            pl, ps = set(longs), set(shorts)
            rets.append(pr)
        r = pd.concat(rets).sort_index()
        r = r[~r.index.duplicated(keep_first=False)] if False else r[~r.index.duplicated(keep=False)]
        out[f"ls{n}"] = r
        print(f"  N={n}: {len(r)} 天", flush=True)
    return out


def main():
    if CACHE.exists():
        print("复用缓存")
        S = pd.read_pickle(CACHE)
    else:
        S = build_series()
        pd.to_pickle(S, CACHE)
        print(f"已存 {CACHE}")

    print("\n" + "=" * 78)
    print("组合滚动样本外: 每年初只用历史数据选 (多空N, 多头权重)")
    print("=" * 78)
    weights = [0.2, 0.3, 0.35, 0.4, 0.5, 0.6]
    lss = [k for k in S.keys() if k != "long"]
    years = sorted({d.year for d in S["long"].index})

    oos, rows = [], []
    for y in years:
        tr_end = pd.Timestamp(f"{y}-01-01")
        te_end = pd.Timestamp(f"{y}-12-31")
        best, best_s = None, -9
        for ls in lss:
            a = S["long"].copy()
            b = S[ls].copy()
            ix = a.index.intersection(b.index)
            a, b = a.loc[ix], b.loc[ix]
            for w in weights:
                r = w * a + (1 - w) * b
                tr = r[r.index < tr_end]
                if len(tr) < 250:
                    continue
                eq = (1 + tr).cumprod()
                ann = eq.iloc[-1] ** (252 / len(tr)) - 1
                mdd = (eq / eq.cummax() - 1).min()
                cal = ann / abs(mdd) if mdd < 0 else -9
                if cal > best_s:
                    best_s, best = cal, (ls, w)
        if best is None:
            continue
        ls, w = best
        a = S["long"].copy()
        b = S[ls].copy()
        ix = a.index.intersection(b.index)
        r = (w * a.loc[ix] + (1 - w) * b.loc[ix])
        te = r[(r.index >= tr_end) & (r.index <= te_end)]
        if len(te) < 40:
            continue
        eq = (1 + te).cumprod()
        ann = eq.iloc[-1] ** (252 / len(te)) - 1
        mdd = (eq / eq.cummax() - 1).min()
        oos.append(te)
        rows.append({"年份": y, "选中": f"{ls}|w={w}", "训练Calmar": round(best_s, 2),
                     "当年收益": round(ann, 4), "当年回撤": round(mdd, 4)})

    df = pd.DataFrame(rows)
    print(df.to_string(index=False))

    o = pd.concat(oos).sort_index()
    o = o[~o.index.duplicated(keep=False)]
    eq = (1 + o).cumprod()
    yrs = len(o) / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1
    mdd = (eq / eq.cummax() - 1).min()
    vol = o.std() * np.sqrt(252)
    print("\n" + "-" * 78)
    print(f"滚动样本外: 年化 {ann:.1%}  回撤 {mdd:.1%}  "
          f"夏普 {o.mean()*252/vol:.2f}  Calmar {ann/abs(mdd):.2f}")
    print(f"盈利年份 {(df['当年收益']>0).sum()}/{len(df)}")
    print("-" * 78)
    df.to_csv(OUT / "wf_blend.csv", index=False, encoding="utf-8")
    pd.DataFrame({"ret": o}).to_csv(OUT / "wf_blend_daily.csv", encoding="utf-8")


if __name__ == "__main__":
    main()
