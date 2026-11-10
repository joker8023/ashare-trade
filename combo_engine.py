"""
价位策略 × 因子 的结合
=====================
价位策略回答"在哪买/在哪卖", 因子回答"买哪只"。两者互补:

  1. 因子门控 (gate): 只在因子排名前 X% 的股票上挂单
  2. 因子排序 (rank): 同时有多个信号时, 优先买因子值最高的
  3. 两者叠加

对照组:
  - 同池等权买入持有 (必须跑赢的基准)
  - 纯价位策略 (无因子)
  - 纯因子组合策略 (amihud 定期调仓)
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long.pkl")
import engine as E
import risk_control as R
import level_engine as L

BASE = Path(__file__).resolve().parent
OUT = BASE / "results" / "levels"
OUT.mkdir(parents=True, exist_ok=True)

START = "2015-01-01"
MIN_ADV = 20_000_000
COST = 0.0015


def perf(eq, label, extra=""):
    yrs = len(eq) / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1
    r = eq.pct_change(fill_method=None).dropna()
    vol = r.std() * np.sqrt(252)
    mdd = (eq / eq.cummax() - 1).min()
    return {
        "方案": label,
        "年化": ann,
        "夏普": r.mean() * 252 / vol if vol > 0 else 0,
        "最大回撤": mdd,
        "总收益": eq.iloc[-1] - 1,
        "交易数": extra,
    }


def fmt(rows):
    d = pd.DataFrame(rows)
    out = d.copy()
    for c in ["年化", "最大回撤", "总收益"]:
        out[c] = out[c].map(lambda x: f"{x:+.1%}")
    out["夏普"] = out["夏普"].map(lambda x: f"{x:.2f}")
    return out


def main():
    p = E.piv()
    c = p["close"]
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    liquid = (adv20 > MIN_ADV) & c.notna()

    # 因子: Amihud 非流动性 (越大越优先)
    fac = E.FACTORS["amihud"](p)
    fac_rank = fac.rank(axis=1, pct=True)     # 0~1, 越大越不流动

    d0 = pd.Timestamp(START)
    rows = []

    # ---------- 基准: 同池等权买入持有 ----------
    rr = c.where(liquid).pct_change(fill_method=None).mean(axis=1).dropna()
    rr = rr[rr.index >= d0]
    beq = (1 + rr).cumprod()
    rows.append(perf(beq, "【基准】同池等权持有", "-"))

    # ---------- 纯因子组合 (前面几轮的策略) ----------
    try:
        fr = R.cached_base("amihud", 50, 60, (0.05, 0.30), 0.005)
        fr = fr[fr.index >= d0]
        rows.append(perf((1 + fr).cumprod(), "【参考】纯因子组合(N=50,R=60)", "-"))
    except Exception as e:
        print(f"纯因子组合跳过: {e}")

    # ---------- 价位策略 ----------
    configs = [
        ("固定幅度 跌3%买/涨5%卖", lambda: L.strat_fixed_pct(p, 0.03, 0.05)),
        ("网格 ±3%", lambda: L.strat_grid(p, 0.03)),
        ("布林带 2σ", lambda: L.strat_bollinger(p, 2.0)),
    ]
    gates = [0.0, 0.70, 0.90]   # 0=无门控, 0.70=因子前30%, 0.90=前10%

    for name, fn in configs:
        buy0, sell0 = fn()
        buy0 = buy0.loc[d0:]
        sell0 = sell0.loc[d0:]
        for g in gates:
            if g > 0:
                gate = (fac_rank >= g).reindex(index=buy0.index, columns=buy0.columns)
                buy = buy0.where(gate & liquid)
                sell = sell0.where(gate & liquid)
            else:
                buy = buy0.where(liquid)
                sell = sell0.where(liquid)

            for use_rank in ([False, True] if g > 0 else [False]):
                pri = fac.reindex(index=buy.index, columns=buy.columns) if use_rank else None
                eq, tr = L.backtest(p, buy, sell, priority=pri)
                if len(eq) < 100:
                    continue
                tag = name
                if g > 0:
                    tag += f" +门控前{int((1-g)*100)}%"
                if use_rank:
                    tag += " +排序"
                rows.append(perf(eq, tag, len(tr)))
                print(f"  {tag}: {len(tr)} 笔")

    print("\n" + "=" * 100)
    print(f"价位策略 × 因子 结合对比 ({START} ~ 2026, 单边成本{COST:.2%}, 最多20仓)")
    print("=" * 100)
    print(fmt(rows).to_string(index=False))

    # 分年度: 最优 vs 基准
    pd.DataFrame(rows).to_csv(OUT / "combo_compare.csv", index=False, encoding="utf-8")
    print(f"\n结果: {OUT / 'combo_compare.csv'}")


if __name__ == "__main__":
    main()
