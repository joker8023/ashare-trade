"""唐奇安通道突破 (海龟交易简化版)"""
import os
from pathlib import Path
import numpy as np
import pandas as pd
os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import engine as E
import signal_strategies as S

def sig_donchian(p, entry_n=20, exit_n=10):
    """突破N日高点买入, 跌破M日低点卖出"""
    hi = p["high"].rolling(entry_n).max().shift(1)
    lo = p["low"].rolling(exit_n).min().shift(1)
    c1 = p["close"].shift(1)
    buy = (c1 >= hi).astype(int)
    sell = (c1 <= lo).astype(int) * -1
    return buy.where(buy > 0, sell).fillna(0)

def sig_donchian_filter(p, entry_n=20, exit_n=10):
    """唐奇安 + 价格在MA60上方才做多"""
    c = p["close"]
    hi = p["high"].rolling(entry_n).max().shift(1)
    lo = p["low"].rolling(exit_n).min().shift(1)
    c1 = c.shift(1)
    above = (c1 > c.rolling(60).mean().shift(1)).astype(int)
    buy = ((c1 >= hi) & (above == 1)).astype(int)
    sell = (c1 <= lo).astype(int) * -1
    return buy.where(buy > 0, sell).fillna(0)

if __name__ == "__main__":
    p = E.piv()
    for name, fn in [("唐奇安(20/10)", lambda x: sig_donchian(x, 20, 10)),
                     ("唐奇安(55/20)", lambda x: sig_donchian(x, 55, 20)),
                     ("唐奇安+MA60过滤", sig_donchian_filter)]:
        for tp, sl in [(0.15, 0.10), (0.30, 0.15)]:
            sig = fn(p)
            eq, tr = S.backtest_signal(p, sig, tp=tp, sl=sl, use_gate=True)
            if len(eq) < 100:
                print(f"{name} TP{int(tp*100)}: 无交易"); continue
            r = eq.pct_change(fill_method=None).dropna()
            yrs = len(eq) / 252
            ann = eq.iloc[-1] ** (1 / yrs) - 1
            vol = r.std() * np.sqrt(252)
            mdd = (eq / eq.cummax() - 1).min()
            wr = (tr["ret"] > 0).mean() if len(tr) else 0
            print(f"{name} TP{int(tp*100)}: {len(tr)}笔 年化{ann:+.1%} 回撤{mdd:.1%} 夏普{r.mean()*252/vol if vol>0 else 0:.2f} 胜率{wr:.1%}", flush=True)
