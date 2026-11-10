"""
策略池（新择时版） + 滚动样本外验证
==================================
1. 用最优择时 (中证500 MA15) 重建策略池
2. 每年初只用历史数据挑配置, 跑下一年 (walk-forward)
3. 对比: 滚动样本外 vs 全样本最优(偷看未来)
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import engine as E
import strategy_lab as S
import combo_lab as C

BASE = Path(__file__).resolve().parent
OUT = BASE / "results" / "wf"
OUT.mkdir(parents=True, exist_ok=True)
CACHE = OUT / "pool.pkl"

COMBOS = ["amihud+amount_level", "amount_level", "amihud", "size",
          "amihud+vol20", "amihud+turn20+vol20"]
EXPS = [1.0, 0.7]
ENTRY, TP, GATE = 0.3, 0.8, 0.75
MA, IDX = 15, "000905"


def build_one(combo, exp):
    p = E.piv()
    c = p["close"]
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    atr = C.get_atr(14)
    ratio = C.combo_rank(combo)

    d0 = pd.Timestamp("2015-01-01")
    idx = c.index[c.index >= d0]
    cols = c.columns
    buy = (c - ENTRY * atr).shift(1)
    sell = buy + TP * atr.shift(1)
    stop = buy - 10 * atr.shift(1)
    ok = (adv20 > 20_000_000) & c.notna() & (ratio >= GATE)

    def cut(x):
        return x.reindex(index=idx, columns=cols).where(ok.reindex(index=idx, columns=cols))

    eq, tr = S.backtest(p, cut(buy), cut(sell), cut(stop),
                        max_hold=20, max_pos=20, cost=0.0015,
                        max_exposure=exp,
                        market_scale=C._market_scale(p, MA, IDX),
                        liquidate_on_off=True)
    return eq.pct_change(fill_method=None).dropna()


def main():
    if CACHE.exists():
        pool = pd.read_pickle(CACHE)
        print(f"复用缓存: {len(pool.columns)} 条")
    else:
        series = {}
        for combo in COMBOS:
            for exp in EXPS:
                k = f"{combo}|x{exp}"
                try:
                    r = build_one(combo, exp)
                    series[k] = r
                    ann = (1 + r).prod() ** (252 / len(r)) - 1
                    print(f"  {k:45s} 年化{ann:+7.1%}", flush=True)
                except Exception as e:
                    print(f"  {k} 失败: {str(e)[:50]}")
        pool = pd.DataFrame(series)
        pool.to_pickle(CACHE)
        print(f"已存 {CACHE}")

    def stat(r):
        eq = (1 + r).cumprod()
        yrs = len(r) / 252
        ann = eq.iloc[-1] ** (1 / yrs) - 1
        mdd = (eq / eq.cummax() - 1).min()
        vol = r.std() * np.sqrt(252)
        return ann, mdd, (r.mean() * 252 / vol if vol > 0 else 0)

    # ---------- 滚动样本外 ----------
    print("\n" + "=" * 80)
    print("滚动样本外 — 每年初只用历史数据选配置")
    print("=" * 80)
    years = sorted({d.year for d in pool.index})
    oos_parts, rows = [], []
    for y in years:
        tr_end = pd.Timestamp(f"{y}-01-01")
        te_end = pd.Timestamp(f"{y}-12-31")
        best, best_s = None, -9
        for k in pool.columns:
            s = pool[k].dropna()
            tr = s[s.index < tr_end]
            if len(tr) < 250:
                continue
            a, m, sh = stat(tr)
            cal = a / abs(m) if m < 0 else 0
            if cal > best_s:
                best_s, best = cal, k
        if best is None:
            continue
        te = pool[best].dropna()
        te = te[(te.index >= tr_end) & (te.index <= te_end)]
        if len(te) < 40:
            continue
        a, m, sh = stat(te)
        oos_parts.append(te)
        rows.append({"年份": y, "选中": best, "训练Calmar": round(best_s, 2),
                     "当年收益": round(a, 4), "当年回撤": round(m, 4)})

    df = pd.DataFrame(rows)
    print(df.to_string(index=False))

    oos = pd.concat(oos_parts).sort_index()
    oos = oos[~oos.index.duplicated(keep="first")]
    a, m, sh = stat(oos)
    print("\n" + "-" * 80)
    print(f"滚动样本外: 年化 {a:.1%}  回撤 {m:.1%}  夏普 {sh:.2f}  Calmar {a/abs(m):.2f}")
    print(f"盈利年份 {(df['当年收益']>0).sum()}/{len(df)}")
    print("-" * 80)

    # 对照: 全样本最优 (偷看未来)
    best_all, best_cal = None, -9
    for k in pool.columns:
        s = pool[k].dropna()
        aa, mm, _ = stat(s)
        cal = aa / abs(mm) if mm < 0 else 0
        if cal > best_cal:
            best_cal, best_all = cal, k
    s = pool[best_all].dropna()
    aa, mm, ssh = stat(s)
    print(f"\n对照 全样本最优(不可实现): {best_all}")
    print(f"  年化 {aa:.1%}  回撤 {mm:.1%}  夏普 {ssh:.2f}  Calmar {best_cal:.2f}")
    print(f"\n数据挖掘损耗: {best_cal - (a/abs(m)):.2f} Calmar")

    # 每个策略的全样本表现
    print("\n=== 各策略全样本表现 ===")
    rr = []
    for k in pool.columns:
        s = pool[k].dropna()
        aa, mm, ssh = stat(s)
        rr.append({"策略": k, "年化": aa, "回撤": mm, "夏普": ssh,
                   "Calmar": aa / abs(mm) if mm < 0 else 0})
    rdf = pd.DataFrame(rr).sort_values("Calmar", ascending=False)
    d = rdf.copy()
    for cc in ["年化", "回撤"]:
        d[cc] = d[cc].map(lambda x: f"{x:.1%}")
    d["夏普"] = d["夏普"].map(lambda x: f"{x:.2f}")
    d["Calmar"] = d["Calmar"].map(lambda x: f"{x:.2f}")
    print(d.to_string(index=False))
    rdf.to_csv(OUT / "pool_metrics.csv", index=False, encoding="utf-8")

    pd.DataFrame({"ret": oos}).to_csv(OUT / "oos.csv", encoding="utf-8")


if __name__ == "__main__":
    main()
