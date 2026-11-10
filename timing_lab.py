"""
强化择时 — 专门压回撤
====================
基础版: 指数 < MA15 → 清仓 (回撤 -20.7%)
强化思路: 增加「恐慌退出」和「波动退出」条件, 更早离场

规则组合:
  base    : 指数 > MA15
  panic3  : + 指数3日跌幅 > 4% → 退出
  panic5  : + 指数5日跌幅 > 6% → 退出
  volspike: + 指数波动率飙升 → 退出
  strict  : 指数 > MA15 且 > MA60 (双确认)
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import engine as E
import strategy_lab as S
import risk_control as R

BASE = Path(__file__).resolve().parent
OUT = BASE / "results" / "timing"
OUT.mkdir(parents=True, exist_ok=True)

IDX = "000905"
COMBO = "amihud+amount_level"
ENTRY, TP, GATE = 0.3, 0.8, 0.75


def build_signal(name, ma=15):
    idx = R._index_series(IDX)
    above_ma = idx > idx.rolling(ma).mean()
    sig = above_ma.astype(float)

    if "panic3" in name:
        ret3 = idx / idx.shift(3) - 1
        sig = sig * (ret3 > -0.04).astype(float)
    if "panic5" in name:
        ret5 = idx / idx.shift(5) - 1
        sig = sig * (ret5 > -0.06).astype(float)
    if "volspike" in name:
        rv = idx.pct_change(fill_method=None).rolling(10).std()
        med = rv.rolling(120).median()
        sig = sig * (rv < med * 1.8).astype(float)
    if name == "strict":
        ma60 = idx.rolling(60).mean()
        sig = sig * (idx > ma60).astype(float)

    return sig.shift(1).astype(float)


def run(signal_name, exposure=1.0):
    import combo_lab as C
    p = E.piv()
    c = p["close"]
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    atr = C.get_atr(14)
    ratio = C.combo_rank(COMBO)

    d0 = pd.Timestamp("2015-01-01")
    idxd = c.index[c.index >= d0]
    cols = c.columns

    buy = (c - ENTRY * atr).shift(1)
    sell = buy + TP * atr.shift(1)
    stop = buy - 10 * atr.shift(1)
    liquid = (adv20 > 20_000_000) & c.notna()
    ok = liquid & (ratio >= GATE)

    def cut(x):
        return x.reindex(index=idxd, columns=cols).where(ok.reindex(index=idxd, columns=cols))

    sig = build_signal(signal_name)
    eq, tr = S.backtest(p, cut(buy), cut(sell), cut(stop),
                        max_hold=20, max_pos=20, cost=0.0015,
                        max_exposure=exposure,
                        market_scale=sig, liquidate_on_off=True)
    r = eq.pct_change(fill_method=None).dropna()
    yrs = len(eq) / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1
    mdd = (eq / eq.cummax() - 1).min()
    vol = r.std() * np.sqrt(252)
    return dict(name=f"{signal_name}|x{exposure}", ann=ann, mdd=mdd,
                sharpe=r.mean() * 252 / vol if vol > 0 else 0,
                calmar=ann / abs(mdd) if mdd < 0 else 0,
                win=(tr["ret"] > 0).mean() if len(tr) else 0,
                trades=len(tr))


def main():
    names = ["base", "panic3", "panic5", "volspike", "panic3+volspike",
             "panic5+volspike", "strict", "strict+panic3"]
    rows = []
    for nm in names:
        for exp in [1.0, 0.7]:
            try:
                r = run(nm, exp)
                rows.append(r)
                print(f"{r['name']:<24} 年化{r['ann']:6.1%} 回撤{r['mdd']:7.1%} "
                      f"夏普{r['sharpe']:5.2f} Calmar{r['calmar']:5.2f} 胜率{r['win']:5.1%}")
            except Exception as e:
                print(f"{nm}|x{exp} 失败: {str(e)[:60]}")

    df = pd.DataFrame(rows).sort_values("calmar", ascending=False)
    df.to_csv(OUT / "timing_compare.csv", index=False, encoding="utf-8")

    print("\n=== 按 Calmar 排序 ===")
    d = df.head(8).copy()
    d["ann"] = d["ann"].map(lambda x: f"{x:.1%}")
    d["mdd"] = d["mdd"].map(lambda x: f"{x:.1%}")
    d["sharpe"] = d["sharpe"].map(lambda x: f"{x:.2f}")
    d["calmar"] = d["calmar"].map(lambda x: f"{x:.2f}")
    d["win"] = d["win"].map(lambda x: f"{x:.1%}")
    print(d.to_string(index=False))

    print("\n=== 回撤最小的方案 ===")
    d2 = df.nsmallest(3, "mdd")[["name", "ann", "mdd", "sharpe", "win"]].copy()
    d2["ann"] = d2["ann"].map(lambda x: f"{x:.1%}")
    d2["mdd"] = d2["mdd"].map(lambda x: f"{x:.1%}")
    d2["sharpe"] = d2["sharpe"].map(lambda x: f"{x:.2f}")
    d2["win"] = d2["win"].map(lambda x: f"{x:.1%}")
    print(d2.to_string(index=False))


if __name__ == "__main__":
    main()
