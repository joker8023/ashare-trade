"""金叉确认条件测试: 多周期共振 / 成交量确认"""
import os
from pathlib import Path
import numpy as np
import pandas as pd
os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import engine as E, tech_signals as T, signal_strategies as S

def sig_multi_tf(p):
    """多周期共振: MA5>MA20 且 MA20>MA60 才买"""
    c = p["close"]
    m5, m20, m60 = c.rolling(5).mean(), c.rolling(20).mean(), c.rolling(60).mean()
    cross = T.ma_cross(m5, m20)
    aligned = (m20.shift(1) > m60.shift(1)).astype(int)
    buy = ((cross == 1) & (aligned == 1)).astype(int)
    sell = (cross == -1).astype(int) * -1
    return buy.where(buy > 0, sell).fillna(0)

def sig_vol_confirm(p, mult=1.5):
    """成交量确认: 金叉当天成交量 > 20日均量*mult"""
    c = p["close"]; v = p["volume"]
    cross = T.ma_cross(c.rolling(5).mean(), c.rolling(20).mean())
    vol_ok = (v.shift(1) > v.rolling(20).mean().shift(1) * mult).astype(int)
    buy = ((cross == 1) & (vol_ok == 1)).astype(int)
    sell = (cross == -1).astype(int) * -1
    return buy.where(buy > 0, sell).fillna(0)

def sig_trend_pullback_vol(p):
    """组合: 金叉+回踩+放量确认"""
    c = p["close"]
    ma_f, ma_s = c.rolling(5).mean(), c.rolling(20).mean()
    cross = T.ma_cross(ma_f, ma_s)
    armed = (cross == 1).rolling(10, min_periods=1).max() > 0
    near = (c.shift(1) / ma_f.shift(1) - 1).abs() <= 0.02
    v = p["volume"]
    vol_ok = (v.shift(1) > v.rolling(20).mean().shift(1)).astype(int)
    buy = (armed & near & (vol_ok == 1)).astype(int)
    sell = (cross == -1).astype(int) * -1
    return buy.where(buy > 0, sell).fillna(0)

VARIANTS = {
    "multi_tf": ("多周期共振(5>20>60)", sig_multi_tf),
    "vol_confirm": ("金叉+放量确认(1.5x)", sig_vol_confirm),
    "combo_all": ("金叉+回踩+放量三合一", sig_trend_pullback_vol),
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
                print(f"{label} TP{int(tp*100)}: 无交易"); continue
            r = eq.pct_change(fill_method=None).dropna()
            yrs = len(eq) / 252
            ann = eq.iloc[-1] ** (1 / yrs) - 1
            vol = r.std() * np.sqrt(252)
            mdd = (eq / eq.cummax() - 1).min()
            row = {"策略": f"{label}[TP{int(tp*100)}]", "年化": ann, "回撤": mdd,
                   "夏普": r.mean() * 252 / vol if vol > 0 else 0, "交易数": len(tr)}
            if len(tr):
                row["胜率"] = (tr["ret"] > 0).mean()
                w = tr.loc[tr["ret"] > 0, "ret"]; x = tr.loc[tr["ret"] <= 0, "ret"]
                row["盈亏比"] = abs(w.mean() / x.mean()) if len(x) and x.mean() != 0 else 0
            rows.append(row)
            print(f"{label} TP{int(tp*100)}%: {len(tr)}笔 年化{ann:+.1%} 回撤{mdd:.1%} 夏普{row['夏普']:.2f}", flush=True)
    df = pd.DataFrame(rows).sort_values("年化", ascending=False)
    print("\n=== 确认条件测试结果 ===")
    d = df.copy()
    for kk in ["年化", "回撤", "胜率"]:
        d[kk] = d[kk].map(lambda x: f"{x:.1%}")
    for kk in ["夏普", "盈亏比"]:
        d[kk] = d[kk].map(lambda x: f"{x:.2f}")
    print(d.to_string(index=False))
    df.to_csv("results/signals/confirm_test.csv", index=False, encoding="utf-8")
