"""
价位策略实验室 (Strategy Lab)
=============================
用户需求: 按策略选股 → 给出买入价/卖出价/止损价 → 达到价位就成交 → 算真实收益

引擎特性:
  - 买入价: 当日 low <= 买入价 即成交 (跳空低开以开盘价成交, 拿到更好价格)
  - 卖出价: 建仓时锁定, 当日 high >= 卖出价 即成交
  - 止损价: 建仓时锁定, 当日 low <= 止损价 即成交
  - 同一只股票当天卖出后不再买回
  - 最长持有 20 个交易日强制平仓
  - 每笔 5% 仓位, 最多 20 仓
  - 所有挂单价用 t-1 及以前数据计算, 无未来函数
  - 数据: pivots_long_clean.pkl (已清洗, 剔除前复权算崩的脏点)
"""
import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")

BASE = Path(__file__).resolve().parent
OUT = BASE / "results" / "lab"
OUT.mkdir(parents=True, exist_ok=True)

MIN_ADV = 20_000_000
COST = 0.0015
MAX_HOLD = 20
MAX_POS = 20
GATE = 0.70          # 因子门控: 只做 Amihud 排名前 30%
START = "2015-01-01"


# ============================================================
# 10 个策略
# 每个返回 (buy_px, sell_px, stop_px) 三个 date×code 矩阵
# ============================================================

def s01_grid(p, k=0.03):
    """1. 网格: 以 MA20 为中心, 下 k% 买, 上 k% 卖, 止损 -8%"""
    ma = p["close"].rolling(20).mean()
    buy = (ma * (1 - k)).shift(1)
    sell = (ma * (1 + k)).shift(1)
    return buy, sell, buy * 0.92


def s02_bollinger(p, k=2.0):
    """2. 布林带: 跌破下轨买, 回到中轨卖, 止损 -8%"""
    c = p["close"]
    ma, sd = c.rolling(20).mean(), c.rolling(20).std()
    buy = (ma - k * sd).shift(1)
    sell = ma.shift(1)
    return buy, sell, buy * 0.92


def s03_fixed(p, drop=0.03, take=0.05):
    """3. 固定幅度: 较昨收跌 drop% 买, 涨 take% 卖, 止损 -8%"""
    c = p["close"]
    buy = (c * (1 - drop)).shift(1)
    return buy, buy * (1 + take), buy * 0.92


def s04_support(p, n=20):
    """4. 支撑阻力: 近 N 日最低价买, 近 N 日最高价卖, 止损 -8%"""
    lo, hi = p["low"], p["high"]
    buy = lo.rolling(n).min().shift(1)
    sell = hi.rolling(n).max().shift(1)
    return buy, sell, buy * 0.92


def s05_ma_pullback(p, n=20, take=0.06):
    """5. 均线回踩: 回踩 MA20 买入, 涨 6% 卖出, 止损 -7%"""
    ma = p["close"].rolling(n).mean()
    buy = ma.shift(1)
    return buy, buy * (1 + take), buy * 0.93


def s06_atr_channel(p, k=2.0):
    """6. ATR通道: 昨收下方 k*ATR 买, 上方 k*ATR 卖, 止损 -8%"""
    c = p["close"]
    tr = pd.concat([
        p["high"] - p["low"],
        (p["high"] - c.shift(1)).abs(),
        (p["low"] - c.shift(1)).abs(),
    ]).groupby(level=0).max()
    atr = tr.rolling(14).mean()
    buy = (c - k * atr).shift(1)
    sell = (c + k * atr).shift(1)
    return buy, sell, buy * 0.92


def s07_low_rebound(p, n=60, take=0.08):
    """7. 低位反弹: 接近 N 日最低点买, 涨 8% 卖, 止损 -8%"""
    lo = p["low"].rolling(n).min()
    buy = (lo * 1.02).shift(1)
    return buy, buy * (1 + take), buy * 0.92


def s08_bias(p, n=60, k=2.0):
    """8. 乖离率: 低于 MA60 下方 k 倍标准差买入, 回到 MA60 卖出, 止损 -10%"""
    c = p["close"]
    ma, sd = c.rolling(n).mean(), c.rolling(n).std()
    buy = (ma - k * sd).shift(1)
    return buy, ma.shift(1), buy * 0.90


def s09_double_low(p, n=20):
    """9. 双低点: min(N日最低, MA20*0.95) 买, MA20*1.05 卖, 止损 -8%"""
    c = p["close"]
    ma = c.rolling(n).mean()
    lo = p["low"].rolling(n).min()
    buy = np.minimum(lo, ma * 0.95).shift(1)
    sell = (ma * 1.05).shift(1)
    return buy, sell, buy * 0.92


def s10_lowvol(p, take=0.05):
    """10. 低波动回撤: 只做低波动股, 回撤 3% 买, 反弹 5% 卖, 止损 -6%"""
    c = p["close"]
    vol = c.pct_change(fill_method=None).rolling(20).std()
    buy = (c * 0.97).shift(1)
    sell = buy * (1 + take)
    stop = buy * 0.94
    # 低波动股票是唯一加分项 (在 gate 之外再收紧)
    lowvol = vol.rank(axis=1, pct=True) <= 0.5
    return buy.where(lowvol), sell.where(lowvol), stop.where(lowvol)


STRATEGIES = {
    "s01_grid":       ("1. 网格交易",      s01_grid),
    "s02_bollinger":  ("2. 布林带回归",    s02_bollinger),
    "s03_fixed":      ("3. 固定幅度回调",  s03_fixed),
    "s04_support":    ("4. 支撑阻力位",    s04_support),
    "s05_ma_pullback":("5. 均线回踩",      s05_ma_pullback),
    "s06_atr":        ("6. ATR通道",       s06_atr_channel),
    "s07_low_rebound":("7. 低位反弹",      s07_low_rebound),
    "s08_bias":       ("8. 乖离率",        s08_bias),
    "s09_double_low": ("9. 双低点",        s09_double_low),
    "s10_lowvol":     ("10. 低波动回撤",   s10_lowvol),
}


# ============================================================
# 回测引擎
# ============================================================

def backtest(p, buy_px, sell_px, stop_px,
             max_hold=MAX_HOLD, max_pos=MAX_POS, cost=COST,
             max_exposure=1.0, market_scale=None, liquidate_on_off=False):
    o, h, l, c = p["open"], p["high"], p["low"], p["close"]
    dates, codes = c.index, c.columns
    n = len(codes)

    def align(x):
        return x.reindex(index=dates, columns=codes)

    buy_px, sell_px, stop_px = align(buy_px), align(sell_px), align(stop_px)

    o_a, h_a, l_a, c_a = o.values, h.values, l.values, c.values
    b_a, s_a, st_a = buy_px.values, sell_px.values, stop_px.values

    cash = 1.0
    qty = np.zeros(n)
    e_cost = np.zeros(n)
    e_px = np.zeros(n)
    t_sell = np.full(n, np.nan)
    t_stop = np.full(n, np.nan)
    e_i = np.full(n, -1, dtype=int)
    hold = np.zeros(n, dtype=bool)

    trades, equity = [], []
    mkt = (market_scale.reindex(dates).ffill().fillna(1.0).values
           if market_scale is not None else np.ones(len(dates)))

    for i in range(1, len(dates)):
        bp, sp, stp = b_a[i], s_a[i], st_a[i]
        op, hi, lo, cl = o_a[i], h_a[i], l_a[i], c_a[i]
        sold = np.zeros(n, dtype=bool)

        def exit_pos(j, fill, reason):
            nonlocal cash
            proceeds = qty[j] * fill * (1 - cost)
            pnl = proceeds - e_cost[j]
            cash += proceeds
            trades.append({
                "code": codes[j], "entry_date": dates[e_i[j]], "exit_date": dates[i],
                "entry_price": round(float(e_px[j]), 3),
                "target_sell": round(float(t_sell[j]), 3),
                "target_stop": round(float(t_stop[j]), 3),
                "exit_price": round(float(fill), 3),
                "ret": round(float(pnl / e_cost[j]), 5),
                "days": int(i - e_i[j]), "reason": reason,
            })
            hold[j] = False
            qty[j] = e_cost[j] = e_px[j] = 0.0
            t_sell[j] = t_stop[j] = np.nan
            e_i[j] = -1

        # 1) 止盈
        m = hold & ~np.isnan(t_sell) & (hi >= t_sell)
        for j in np.where(m)[0]:
            ts = t_sell[j]
            fill = op[j] if (not np.isnan(op[j]) and op[j] >= ts) else ts
            if np.isnan(fill) or fill <= 0:
                continue
            exit_pos(j, fill, "止盈"); sold[j] = True

        # 2) 止损 (同一只当日先止盈后不重复)
        m = hold & ~sold & ~np.isnan(t_stop) & (lo <= t_stop)
        for j in np.where(m)[0]:
            ts = t_stop[j]
            fill = op[j] if (not np.isnan(op[j]) and op[j] <= ts) else ts
            if np.isnan(fill) or fill <= 0:
                continue
            exit_pos(j, fill, "止损"); sold[j] = True

        # 3) 超期
        if max_hold:
            m = hold & ~sold & (i - e_i >= max_hold) & ~np.isnan(cl) & (cl > 0)
            for j in np.where(m)[0]:
                exit_pos(j, cl[j], "超期"); sold[j] = True

        # 4) 买入
        m = ((~hold) & (~sold) & ~np.isnan(bp) & ~np.isnan(sp) & (sp > bp)
             & (lo <= bp) & ~np.isnan(op) & (op > 0))
        # 大盘择时: 关闭时强制清仓
        if liquidate_on_off and mkt[i] < 0.99:
            for j in np.where(hold)[0]:
                fill = cl[j] if (not np.isnan(cl[j]) and cl[j] > 0) else e_px[j]
                exit_pos(j, fill, "择时清仓"); sold[j] = True

        if m.any():
            px_now = np.where(np.isnan(c_a[i]), e_px, c_a[i])
            pos_val = float(np.nansum(qty * px_now))
            cur = cash + pos_val
            unit = cur / max_pos
            exp_limit = max_exposure * float(mkt[i]) * cur
            for j in np.where(m)[0]:
                if cash < unit * 0.2:
                    break
                if pos_val + unit > exp_limit:
                    break
                fill = op[j] if (op[j] <= bp[j]) else bp[j]
                if np.isnan(fill) or fill <= 0:
                    continue
                if not np.isnan(stp[j]) and stp[j] >= fill:
                    continue          # 止损价必须在买入价下方
                alloc = min(unit, cash)
                q = alloc / (fill * (1 + cost))
                cash -= q * fill * (1 + cost)
                hold[j] = True
                qty[j] = q
                e_cost[j] = q * fill * (1 + cost)
                e_px[j] = fill
                t_sell[j] = sp[j]
                t_stop[j] = stp[j]
                e_i[j] = i
                pos_val += q * fill

        px_now = np.where(np.isnan(c_a[i]), e_px, c_a[i])
        equity.append(cash + float(np.nansum(qty * px_now)))

    return pd.Series(equity, index=dates[1:]), pd.DataFrame(trades)


def evaluate(p, key, gate=GATE, start=START, use_gate=True, use_stop=True,
             max_exposure=1.0, market_filter=None, liquidate=False):
    """运行一个策略, 返回指标字典"""
    import engine as E
    name, fn = STRATEGIES[key]
    buy, sell, stop = fn(p)
    if not use_stop:
        stop = stop * np.nan

    c = p["close"]
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    liquid = (adv20 > MIN_ADV) & c.notna()

    if use_gate:
        fac = E.FACTORS["amihud"](p)
        rank = fac.rank(axis=1, pct=True)
        ok = liquid & (rank >= gate)
    else:
        ok = liquid

    d0 = pd.Timestamp(start)
    idx = c.index[c.index >= d0]
    cols = c.columns
    buy = buy.reindex(index=idx, columns=cols).where(ok.reindex(index=idx, columns=cols))
    sell = sell.reindex(index=idx, columns=cols).where(ok.reindex(index=idx, columns=cols))
    stop = stop.reindex(index=idx, columns=cols).where(ok.reindex(index=idx, columns=cols))

    # 大盘择时信号
    mkt = None
    if market_filter is not None:
        import risk_control as R
        idx = R._index_series("000852")
        ma = idx.rolling(market_filter).mean()
        sig = (idx > ma).shift(1).astype(float)
        mkt = sig.reindex(p["close"].index).ffill().fillna(0.0)

    eq, tr = backtest(p, buy, sell, stop, max_exposure=max_exposure,
                      market_scale=mkt, liquidate_on_off=liquidate)
    if len(eq) < 100:
        return None

    yrs = len(eq) / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1
    r = eq.pct_change(fill_method=None).dropna()
    vol = r.std() * np.sqrt(252)
    mdd = (eq / eq.cummax() - 1).min()
    active = r[r != 0]

    res = {
        "key": key, "name": name,
        "年化": ann, "夏普": r.mean() * 252 / vol if vol > 0 else 0,
        "最大回撤": mdd, "总收益": eq.iloc[-1] - 1,
        "Calmar": ann / abs(mdd) if mdd < 0 else 0,
        "交易数": len(tr),
    }
    if len(tr):
        res["胜率"] = (tr["ret"] > 0).mean()
        res["平均单笔"] = tr["ret"].mean()
        res["平均持有天"] = tr["days"].mean()
        win = tr.loc[tr["ret"] > 0, "ret"]
        loss = tr.loc[tr["ret"] <= 0, "ret"]
        res["盈亏比"] = abs(win.mean() / loss.mean()) if len(loss) and loss.mean() != 0 else np.nan
        vc = tr["reason"].value_counts()
        res["止盈率"] = vc.get("止盈", 0) / len(tr)
        res["止损率"] = vc.get("止损", 0) / len(tr)
        res["超期率"] = vc.get("超期", 0) / len(tr)
    return res, eq, tr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--gate", type=float, default=GATE)
    ap.add_argument("--no-gate", action="store_true")
    ap.add_argument("--start", default=START)
    ap.add_argument("--no-stop", action="store_true")
    ap.add_argument("--max-exposure", type=float, default=1.0)
    ap.add_argument("--market-filter", type=int, default=None)
    ap.add_argument("--liquidate", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    import engine as E
    p = E.piv()
    out = evaluate(p, a.strategy, gate=a.gate, start=a.start,
                   use_gate=not a.no_gate, use_stop=not a.no_stop,
                   max_exposure=a.max_exposure, market_filter=a.market_filter,
                   liquidate=a.liquidate)
    if out is None:
        print('{"error":"数据不足"}')
        return
    res, eq, tr = out

    if a.json:
        import json
        d = {k: (round(float(v), 5) if isinstance(v, (int, float, np.floating)) else v)
             for k, v in res.items()}
        print(json.dumps(d, ensure_ascii=False))
        return

    print(f"{res['name']}  (门控={'无' if a.no_gate else f'前{(1-a.gate)*100:.0f}%'})")
    print(f"  年化 {res['年化']:+.1%}  夏普 {res['夏普']:.2f}  回撤 {res['最大回撤']:.1%}  "
          f"Calmar {res['Calmar']:.2f}")
    if len(tr):
        print(f"  交易 {res['交易数']} 笔  胜率 {res['胜率']:.1%}  平均单笔 {res['平均单笔']:+.2%}  "
              f"平均持有 {res['平均持有天']:.0f}天  盈亏比 {res['盈亏比']:.2f}")
        print(f"  平仓: 止盈 {res['止盈率']:.0%} / 止损 {res['止损率']:.0%} / 超期 {res['超期率']:.0%}")


if __name__ == "__main__":
    main()
