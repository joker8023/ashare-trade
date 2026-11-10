"""
经典技术信号库 (金叉/死叉/MACD/KDJ/RSI)
=====================================
所有信号只用 t-1 及以前的数据, 输出 t 日可用的信号矩阵。
约定: 信号矩阵值为 1/-1/0 (买入/卖出/无信号)
"""
import numpy as np
import pandas as pd


def ma_cross(fast, slow):
    """均线金叉死叉: fast 上穿 slow = +1 (金叉), 下穿 = -1 (死叉)
    用 t-1 收盘算出的均线, t 日开盘前已知, 无未来函数"""
    g = (fast.shift(1) > slow.shift(1)).astype(int)
    return g.diff().fillna(0).clip(-1, 1)


def macd_line(c, fast=12, slow=26, signal=9):
    ema_f = c.ewm(span=fast, adjust=False).mean()
    ema_s = c.ewm(span=slow, adjust=False).mean()
    dif = ema_f - ema_s
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = 2 * (dif - dea)
    return dif, dea, hist


def macd_cross(c, fast=12, slow=26, signal=9):
    """MACD 金叉死叉"""
    dif, dea, _ = macd_line(c, fast, slow, signal)
    g = (dif.shift(1) > dea.shift(1)).astype(int)
    return g.diff().fillna(0).clip(-1, 1)


def kdj(c, h, l, n=9, m1=3, m2=3):
    """KDJ: RSV -> K, D, J"""
    lowest = l.rolling(n).min()
    highest = h.rolling(n).max()
    denom = (highest - lowest).replace(0, np.nan)
    rsv = ((c - lowest) / denom * 100).fillna(50)
    k = rsv.ewm(com=m1 - 1 if m1 > 1 else 1, adjust=False).mean()
    d = k.ewm(com=m2 - 1 if m2 > 1 else 1, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def bollinger(c, n=20, k=2.0):
    ma = c.rolling(n).mean()
    sd = c.rolling(n).std()
    return ma + k * sd, ma, ma - k * sd


def atr(h, l, c, n=14):
    tr = pd.concat([h - l,
                    (h - c.shift(1)).abs(),
                    (l - c.shift(1)).abs()]).groupby(level=0).max()
    return tr.rolling(n).mean()
