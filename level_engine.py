"""
价位策略回测引擎 (限价单口径)
=============================
和之前的"因子组合"完全不同: 这里每个信号都给出明确的买入价和卖出价,
用日线 high/low 判断限价单能否成交, 再统计真实成交收益。

成交规则 (尽量贴近实盘):
  买入: 若当日 open <= 买入价 → 以 open 成交 (跳空低开, 拿到更好价格)
        否则若当日 low <= 买入价 → 以买入价成交
  卖出: 若当日 open >= 卖出价 → 以 open 成交 (跳空高开, 拿到更好价格)
        否则若当日 high >= 卖出价 → 以卖出价成交
  同一天不买卖同一只股票
  超过最大持有天数 → 按当日收盘强制平仓

资金模型:
  每笔仓位 = 初始资金 / 20 (即 5%), 最多约 20 个并发持仓
  现金不足则跳过该信号
  手续费: 单边 0.15% (佣金 + 印花税 + 滑点)

无未来函数: t 日的挂单价只用 t-1 及以前的数据计算
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long.pkl")
import engine as E

BASE = Path(__file__).resolve().parent
OUT = BASE / "results" / "levels"
OUT.mkdir(parents=True, exist_ok=True)

MIN_ADV = 20_000_000      # 日均成交额 > 2000万
COST = 0.0015             # 单边
MAX_POS = 20              # 同时最多 20 仓 (每仓 5%)
MAX_HOLD = 20             # 最长持有 20 个交易日


# ============================================================
# 策略: 输入 piv, 返回 (buy_price, sell_price) 两个 date×code 矩阵
# 约定: 这两个矩阵在 t 行的值, 是 t 日可挂的单 (用 t-1 及以前数据算)
# ============================================================

def strat_bollinger(p, k=2.0, exit_mid=True):
    """布林带均值回归: 跌到下轨买, 回到中轨卖"""
    c = p["close"]
    ma = c.rolling(20).mean()
    sd = c.rolling(20).std()
    buy = (ma - k * sd).shift(1)
    sell = (ma if exit_mid else ma + k * sd).shift(1)
    return buy, sell


def strat_grid(p, band=0.03):
    """网格: 以 20 日均线为中心, 下 grid% 买入, 上 grid% 卖出"""
    ma = p["close"].rolling(20).mean()
    buy = (ma * (1 - band)).shift(1)
    sell = (ma * (1 + band)).shift(1)
    return buy, sell


def strat_support(p, n=20):
    """支撑位买 / 阻力位卖: 近 N 日最低价买, 近 N 日最高价卖"""
    c, lo, hi = p["close"], p["low"], p["high"]
    buy = lo.rolling(n).min().shift(1)
    sell = hi.rolling(n).max().shift(1)
    return buy, sell


def strat_fixed_pct(p, drop=0.03, take=0.05):
    """固定幅度: 相对昨收跌 drop% 买入, 相对买入价涨 take% 卖出"""
    c = p["close"]
    buy = (c * (1 - drop)).shift(1)
    sell = (buy * (1 + take))
    return buy, sell


STRATEGIES = {
    "bollinger": ("布林带均值回归", strat_bollinger),
    "grid": ("网格交易", strat_grid),
    "support": ("支撑阻力位", strat_support),
    "fixed": ("固定幅度回调", strat_fixed_pct),
}


# ============================================================
# 回测引擎
# ============================================================

def backtest(p, buy_px, sell_px, max_hold=MAX_HOLD, max_pos=MAX_POS, cost=COST, priority=None):
    """
    核心修正: 卖出价在建仓时【锁定】, 之后不再变动。
    挂单只在信号次日有效, 未成交即作废。
    """
    o, h, l, c = p["open"], p["high"], p["low"], p["close"]
    dates = c.index
    codes = c.columns
    n = len(codes)

    buy_px = buy_px.reindex(index=dates, columns=codes)
    sell_px = sell_px.reindex(index=dates, columns=codes)

    o_arr, h_arr, l_arr, c_arr = o.values, h.values, l.values, c.values
    b_arr, s_arr = buy_px.values, sell_px.values
    pri_arr = (priority.reindex(index=dates, columns=codes).values
               if priority is not None else None)

    cash = 1.0
    qty = np.zeros(n)
    entry_cost = np.zeros(n)
    entry_px = np.zeros(n)
    target_sell = np.full(n, np.nan)   # ★ 建仓时锁定
    entry_i = np.full(n, -1, dtype=int)
    holding = np.zeros(n, dtype=bool)

    trades, equity = [], []

    for i in range(1, len(dates)):
        bp, sp = b_arr[i], s_arr[i]
        op, hi, lo, cl = o_arr[i], h_arr[i], l_arr[i], c_arr[i]
        sold_today = np.zeros(n, dtype=bool)

        def close_pos(j, fill, reason):
            nonlocal cash
            proceeds = qty[j] * fill * (1 - cost)
            pnl = proceeds - entry_cost[j]
            cash += proceeds
            trades.append({
                "code": codes[j], "entry_date": dates[entry_i[j]],
                "exit_date": dates[i], "entry_price": round(float(entry_px[j]), 3),
                "exit_price": round(float(fill), 3),
                "sell_target": round(float(target_sell[j]), 3),
                "ret": round(float(pnl / entry_cost[j]), 5),
                "days": int(i - entry_i[j]), "reason": reason,
            })
            holding[j] = False
            qty[j] = 0.0; entry_cost[j] = 0.0; entry_px[j] = 0.0
            target_sell[j] = np.nan; entry_i[j] = -1

        # ---- 1. 触及锁定的止盈价 → 卖出 ----
        m = holding & ~np.isnan(target_sell) & (hi >= target_sell)
        for j in np.where(m)[0]:
            ts = target_sell[j]
            fill = op[j] if (not np.isnan(op[j]) and op[j] >= ts) else ts
            if np.isnan(fill) or fill <= 0:
                continue
            close_pos(j, fill, "止盈")
            sold_today[j] = True

        # ---- 2. 超期强平 ----
        if max_hold:
            m = holding & (i - entry_i >= max_hold) & ~np.isnan(cl) & (cl > 0)
            for j in np.where(m)[0]:
                close_pos(j, cl[j], "超期")
                sold_today[j] = True

        # ---- 3. 买入 ----
        m = (~holding) & (~sold_today) & ~np.isnan(bp) & ~np.isnan(sp) & (sp > bp) \
            & (lo <= bp) & ~np.isnan(op) & (op > 0)
        if m.any():
            cand = np.where(m)[0]
            if pri_arr is not None and len(cand) > 1:
                # 候选太多时, 因子值高的优先
                pv = pri_arr[i, cand]
                order = np.argsort(-np.nan_to_num(pv, nan=-1e18))
                cand = cand[order]
            cur_val = cash + float(np.nansum(qty * np.where(np.isnan(c_arr[i]), entry_px, c_arr[i])))
            unit = cur_val / max_pos
            for j in cand:
                if cash < unit * 0.2:
                    break
                fill = op[j] if (op[j] <= bp[j]) else bp[j]
                if np.isnan(fill) or fill <= 0:
                    continue
                alloc = min(unit, cash)
                q = alloc / (fill * (1 + cost))
                cash -= q * fill * (1 + cost)
                holding[j] = True
                qty[j] = q
                entry_cost[j] = q * fill * (1 + cost)
                entry_px[j] = fill
                target_sell[j] = sp[j]          # ★ 锁定信号日的卖出价
                entry_i[j] = i

        px_now = np.where(np.isnan(c_arr[i]), entry_px, c_arr[i])
        equity.append(cash + float(np.nansum(qty * px_now)))

    eq = pd.Series(equity, index=dates[1:])
    return eq, pd.DataFrame(trades)


def stats(eq, tr, label):
    if len(eq) == 0:
        return None
    yrs = len(eq) / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else 0
    r = eq.pct_change(fill_method=None).dropna()
    vol = r.std() * np.sqrt(252)
    mdd = (eq / eq.cummax() - 1).min()
    out = {
        "策略": label,
        "总收益": f"{eq.iloc[-1]-1:+.1%}",
        "年化": f"{ann:+.1%}",
        "夏普": f"{r.mean()*252/vol:.2f}" if vol > 0 else "N/A",
        "最大回撤": f"{mdd:.1%}",
    }
    if len(tr):
        out["交易次数"] = len(tr)
        out["胜率"] = f"{(tr['ret']>0).mean():.1%}"
        out["平均单笔"] = f"{tr['ret'].mean():+.2%}"
        out["平均持有天数"] = f"{tr['days'].mean():.0f}"
        win = tr.loc[tr["ret"] > 0, "ret"].mean() if (tr["ret"] > 0).any() else 0
        loss = tr.loc[tr["ret"] <= 0, "ret"].mean() if (tr["ret"] <= 0).any() else 0
        out["盈亏比"] = f"{abs(win/loss):.2f}" if loss != 0 else "N/A"
    return out


def load_data():
    p = E.piv()
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    return p, adv20


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", default="all")
    ap.add_argument("--min-adv", type=float, default=MIN_ADV)
    ap.add_argument("--start", default="2015-01-01")
    a = ap.parse_args()

    p, adv20 = load_data()
    print(f"数据: {p['close'].shape[0]} 交易日 × {p['close'].shape[1]} 只")
    print(f"股票池: 日均成交额 > {a.min_adv/1e4:.0f}万")
    print(f"每笔仓位 5%, 最多 20 仓, 最长持有 {MAX_HOLD} 天, 成本 单边{COST:.2%}\n")

    names = STRATEGIES if a.strategy == "all" else {a.strategy: STRATEGIES[a.strategy]}
    rows, all_trades, eqs = [], {}, {}
    for key, (label, fn) in names.items():
        buy, sell = fn(p)
        # 股票池过滤: 把不合格的挂单价格置 NaN
        mask = (adv20 > a.min_adv) & p["close"].notna()
        buy = buy.where(mask)
        sell = sell.where(mask)
        # 只保留起始日之后
        if a.start:
            buy = buy.loc[a.start:]
            sell = sell.loc[a.start:]

        eq, tr = backtest(p, buy, sell)
        if len(eq) == 0:
            print(f"{label}: 无交易")
            continue
        s = stats(eq, tr, label)
        rows.append(s)
        all_trades[label] = tr
        eqs[key] = eq
        if len(tr):
            tr.to_csv(OUT / f"trades_{key}.csv", index=False, encoding="utf-8-sig")
        print(f"[{label}] 完成: {len(tr)} 笔交易")

    # 基准: 等权买入持有同一股票池
    mask = (adv20 > a.min_adv) & p["close"].notna()
    rr = p["close"].where(mask).pct_change(fill_method=None).mean(axis=1).dropna()
    rr = rr[rr.index >= (pd.Timestamp(a.start) if a.start else rr.index[0])]
    beq = (1 + rr).cumprod()
    byrs = len(rr) / 252
    rows.append({
        "策略": "【基准】等权买入持有",
        "总收益": f"{beq.iloc[-1]-1:+.1%}",
        "年化": f"{beq.iloc[-1]**(1/byrs)-1:+.1%}",
        "夏普": f"{rr.mean()*252/(rr.std()*np.sqrt(252)):.2f}",
        "最大回撤": f"{(beq/beq.cummax()-1).min():.1%}",
        "交易次数": "-", "胜率": "-", "平均单笔": "-",
        "平均持有天数": "-", "盈亏比": "-",
    })

    print("\n" + "=" * 118)
    print("价位策略对比 (限价单口径, 2015-2026) — 同池等权持有是必须跑赢的基准")
    print("=" * 118)
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))

    print(f"\n分年度收益 (基于净值曲线):")
    for key, (label, fn) in names.items():
        if key not in eqs:
            continue
        e = eqs[key]
        yr = e.groupby(e.index.year).apply(lambda x: x.iloc[-1] / x.iloc[0] - 1)
        ys = "  ".join(f"{y}:{v:+.0%}" for y, v in yr.items())
        print(f"  {label:<12} {ys}")

    print(f"\n交易明细已存: {OUT}/trades_*.csv")


if __name__ == "__main__":
    main()
