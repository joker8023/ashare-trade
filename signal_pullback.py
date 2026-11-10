"""金叉后回踩买入 — 追突破改等回踩"""
import os
from pathlib import Path
import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import engine as E
import tech_signals as T
import signal_strategies as S

BASE = Path(__file__).resolve().parent
OUT = BASE / "results" / "signals"

def sig_pullback(p, fast=5, slow=20, window=10, tol=0.02):
    """金叉后window天内, 价格回到快线±tol即买入; 死叉卖出"""
    c = p["close"]
    ma_f = c.rolling(fast).mean(); ma_s = c.rolling(slow).mean()
    cross = T.ma_cross(ma_f, ma_s)
    armed = (cross == 1).rolling(window, min_periods=1).max() > 0
    near = (c.shift(1) / ma_f.shift(1) - 1).abs() <= tol
    buy = (armed & near).astype(int)
    buy = buy.where(buy > 0, 0)
    sell = (cross == -1).astype(int) * -1
    out = buy.where(buy > 0, sell).fillna(0)
    return out

def sig_cross_trend(p, fast=5, slow=20, ma_n=60):
    """金叉+价格在长均线上方才买(顺势过滤)"""
    c = p["close"]
    cross = T.ma_cross(c.rolling(fast).mean(), c.rolling(slow).mean())
    above = (c.shift(1) > c.rolling(ma_n).mean().shift(1)).astype(int)
    buy = ((cross == 1) & (above == 1)).astype(int)
    sell = (cross == -1).astype(int) * -1
    return buy.where(buy > 0, sell).fillna(0)

def sig_macd_hist(p):
    """MACD柱翻红买入/翻绿卖出(比金叉更灵敏)"""
    _, _, hist = T.macd_line(p["close"])
    h = hist.shift(1)
    buy = ((h > 0) & (h.shift(1) <= 0)).astype(int)
    sell = ((h < 0) & (h.shift(1) >= 0)).astype(int) * -1
    return buy.where(buy > 0, sell).fillna(0)

VARIANTS = {
    "pullback_5_20": ("金叉后回踩MA5(±2%,10天窗)", lambda p: sig_pullback(p, 5, 20, 10, 0.02)),
    "pullback_10_20": ("金叉后回踩MA10(±2%,10天窗)", lambda p: sig_pullback(p, 10, 20, 10, 0.02)),
    "cross_trend60": ("金叉+MA60顺势", lambda p: sig_cross_trend(p, 5, 20, 60)),
    "macd_hist": ("MACD柱翻红/翻绿", sig_macd_hist),
}

if __name__ == "__main__":
    import sys
    only = sys.argv[1] if len(sys.argv) > 1 else "all"
    p = E.piv()
    items = VARIANTS.items() if only == "all" else [(only, VARIANTS[only])]
    rows = []
    for key, (label, fn) in items:
        for tp, sl in [(0.08, 0.08), (0.15, 0.15)]:
            sig = fn(p)
            eq, tr = S.backtest_signal(p, sig, tp=tp, sl=sl, use_gate=True)
            if len(eq) < 100:
                print(f"{label} TP{tp}: 无交易"); continue
            r = eq.pct_change(fill_method=None).dropna()
            yrs = len(eq) / 252
            ann = eq.iloc[-1] ** (1 / yrs) - 1
            vol = r.std() * np.sqrt(252)
            mdd = (eq / eq.cummax() - 1).min()
            row = {"策略": f"{label}[TP{int(tp*100)}%]", "年化": ann, "回撤": mdd,
                   "夏普": r.mean() * 252 / vol if vol > 0 else 0, "交易数": len(tr)}
            if len(tr):
                row["胜率"] = (tr["ret"] > 0).mean()
                w = tr.loc[tr["ret"] > 0, "ret"]; x = tr.loc[tr["ret"] <= 0, "ret"]
                row["盈亏比"] = abs(w.mean() / x.mean()) if len(x) and x.mean() != 0 else 0
            rows.append(row)
            print(f"{label} TP{int(tp*100)}%: {len(tr)}笔 年化{ann:+.1%} 回撤{mdd:.1%}", flush=True)
    df = pd.DataFrame(rows).sort_values("年化", ascending=False)
    print("\n=== 金叉正确用法测试 (2015-2026, 成本0.5%, 因子门控开) ===")
    d = df.copy()
    for kk in ["年化", "回撤", "胜率"]:
        d[kk] = d[kk].map(lambda x: f"{x:.1%}")
    d["夏普"] = d["夏普"].map(lambda x: f"{x:.2f}")
    d["盈亏比"] = d["盈亏比"].map(lambda x: f"{x:.2f}")
    print(d.to_string(index=False))
    df.to_csv(OUT / "pullback_test.csv", index=False, encoding="utf-8")
