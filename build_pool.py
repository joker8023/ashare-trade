"""
构建策略池 + 组合优化
====================
目标: 年化 40%+, 回撤 ~10%

思路:
  1. 生成一批差异化策略, 导出各自的逐日收益序列
  2. 计算策略间相关性
  3. 用不同权重组合, 找 收益/回撤 的最优前沿
  4. 坦白报告能到多少

杠杆说明:
  max_exposure > 1 表示使用融资杠杆 (按年化 6% 计资金成本)
"""
import argparse
import json
import os
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import engine as E
import strategy_lab as S
import combo_lab as C

BASE = Path(__file__).resolve().parent
OUT = BASE / "results" / "pool"
OUT.mkdir(parents=True, exist_ok=True)

CACHE = OUT / "series.pkl"
MARGIN_COST = 0.06


def configs():
    """策略池: 因子组合 × 入场 × 止盈 × 仓位"""
    cfgs = []
    for combo in ["amihud", "amihud+amount_level", "amount_level",
                  "amihud+vol20", "amihud+turn20+vol20", "size"]:
        for entry, tp in [(0.3, 0.8), (0.3, 1.0), (0.5, 1.0)]:
            for exp in [1.0, 0.7]:
                cfgs.append(dict(combo=combo, entry_atr=entry, tp_atr=tp, exp=exp))
    return cfgs


def key(c):
    return f"{c['combo']}|e{c['entry_atr']}|t{c['tp_atr']}|x{c['exp']}"


def build_one(cfg):
    p = E.piv()
    c = p["close"]
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    atr = C.get_atr(14)
    ratio = C.combo_rank(cfg["combo"])

    d0 = pd.Timestamp("2015-01-01")
    idx = c.index[c.index >= d0]
    cols = c.columns

    buy = (c - cfg["entry_atr"] * atr).shift(1)
    sell = buy + cfg["tp_atr"] * atr.shift(1)
    stop = buy - 10 * atr.shift(1)

    liquid = (adv20 > 20_000_000) & c.notna()
    ok = liquid & (ratio >= 0.75)

    def cut(x):
        return x.reindex(index=idx, columns=cols).where(ok.reindex(index=idx, columns=cols))

    eq, tr = S.backtest(p, cut(buy), cut(sell), cut(stop),
                        max_hold=20, max_pos=20, cost=0.0015,
                        max_exposure=cfg["exp"],
                        market_scale=C._market_scale(p), liquidate_on_off=True)
    if len(eq) < 300:
        return None
    r = eq.pct_change(fill_method=None).dropna()
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    a = ap.parse_args()

    if CACHE.exists() and not a.rebuild:
        data = pd.read_pickle(CACHE)
        print(f"复用缓存: {len(data.columns)} 条策略序列")
    else:
        cfgs = configs()
        print(f"构建策略池: {len(cfgs)} 个配置")
        series = {}
        for i, cfg in enumerate(cfgs, 1):
            k = key(cfg)
            try:
                r = build_one(cfg)
                if r is not None:
                    series[k] = r
                    print(f"  [{i}/{len(cfgs)}] {k}  年化{((1+r).prod()**(252/len(r))-1):+.1%}")
            except Exception as e:
                print(f"  [{i}/{len(cfgs)}] {k} 失败: {e}")
        data = pd.DataFrame(series)
        data.to_pickle(CACHE)
        print(f"已存 {CACHE}")

    # ---------- 单策略表现 ----------
    rows = []
    for k in data.columns:
        r = data[k].dropna()
        eq = (1 + r).cumprod()
        yrs = len(r) / 252
        ann = eq.iloc[-1] ** (1 / yrs) - 1
        mdd = (eq / eq.cummax() - 1).min()
        rows.append({"策略": k, "年化": ann, "回撤": mdd,
                     "Calmar": ann / abs(mdd) if mdd < 0 else 0,
                     "夏普": r.mean() * 252 / (r.std() * np.sqrt(252))})
    df = pd.DataFrame(rows).sort_values("Calmar", ascending=False)
    print("\n=== 单策略 Calmar 排名 (前10) ===")
    d = df.head(10).copy()
    for cc in ["年化", "回撤"]:
        d[cc] = d[cc].map(lambda x: f"{x:.1%}")
    d["Calmar"] = d["Calmar"].map(lambda x: f"{x:.2f}")
    d["夏普"] = d["夏普"].map(lambda x: f"{x:.2f}")
    print(d.to_string(index=False))
    df.to_csv(OUT / "single_metrics.csv", index=False, encoding="utf-8")


if __name__ == "__main__":
    main()
