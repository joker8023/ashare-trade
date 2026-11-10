"""信号驱动策略 (金叉死叉 / MACD / KDJ / RSI)"""
import os
from pathlib import Path
import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import engine as E
import tech_signals as T

BASE = Path(__file__).resolve().parent
OUT = BASE / "results" / "signals"
OUT.mkdir(parents=True, exist_ok=True)

MIN_ADV = 20_000_000
COST = 0.005
MAX_HOLD = 20
START = "2015-01-01"


def universe(p):
    c = p["close"]
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    return (adv20 > MIN_ADV) & c.notna()


def gate_factor(p, pct=0.75):
    import combo_lab as C
    return C.combo_rank("amihud+amount_level") >= pct


def strat_ma_cross(p, fast=5, slow=20):
    c = p["close"]
    return T.ma_cross(c.rolling(fast).mean(), c.rolling(slow).mean())


def strat_macd(p, fast=12, slow=26, signal=9):
    return T.macd_cross(p["close"], fast, slow, signal)


def strat_kdj(p):
    k, d, j = T.kdj(p["close"], p["high"], p["low"])
    k1, d1 = k.shift(1), d.shift(1)
    golden = (k1 > d1) & (k1.shift(1) <= d1.shift(1)) & (d1 < 30)
    dead = (k1 < d1) & (k1.shift(1) >= d1.shift(1)) & (d1 > 70)
    sig = pd.DataFrame(0, index=k.index, columns=k.columns)
    sig[golden] = 1
    sig[dead] = -1
    return sig


def strat_rsi(p, n=14, oversold=30):
    r = T.rsi(p["close"], n)
    r1 = r.shift(1)
    buy = (r1 > oversold) & (r1.shift(1) <= oversold)
    sell = r1 > 70
    sig = buy.astype(int)
    sig = sig.where(buy, (-sell.astype(int)))
    return sig.fillna(0)


STRATEGIES = {
    "ma_cross": ("MA金叉死叉(5/20)", strat_ma_cross),
    "macd": ("MACD金叉死叉", strat_macd),
    "kdj": ("KDJ超卖金叉", strat_kdj),
    "rsi": ("RSI超卖回升", strat_rsi),
}


def backtest_signal(p, sig, tp=0.08, sl=0.08, use_gate=True, gate_pct=0.75):
    o, h, l, c = p["open"], p["high"], p["low"], p["close"]
    dates, codes = c.index, c.columns
    n = len(codes)
    d0 = pd.Timestamp(START)
    idx = dates[dates >= d0]

    liq = universe(p)
    if use_gate:
        ok = liq & (gate_factor(p, gate_pct) >= gate_pct if False else True)
        import combo_lab as C
        ratio = C.combo_rank("amihud+amount_level")
        ok = liq & (ratio >= gate_pct)
    else:
        ok = liq
    ok = ok.reindex(index=idx, columns=codes).fillna(False)
    sig = sig.reindex(index=idx, columns=codes).fillna(0)

    o_a, h_a, l_a, c_a = o.values, h.values, l.values, c.values
    s_a = sig.values
    ok_a = ok.values

    cash = 1.0
    qty = np.zeros(n); e_cost = np.zeros(n); e_px = np.zeros(n)
    tgt = np.full(n, np.nan); stp = np.full(n, np.nan)
    e_i = np.full(n, -1, dtype=int); hold = np.zeros(n, dtype=bool)
    max_pos = 20
    trades, equity = [], []

    for ii in range(1, len(idx)):
        i = dates.get_loc(idx[ii])
        op, hi, lo, cl = o_a[i], h_a[i], l_a[i], c_a[i]
        sg = s_a[ii]
        valid = ok_a[ii]
        sold = np.zeros(n, dtype=bool)

        def close_pos(j, fill, reason):
            nonlocal cash
            proceeds = qty[j] * fill * (1 - COST)
            pnl = proceeds - e_cost[j]
            cash += proceeds
            trades.append({"code": codes[j], "entry_date": dates[e_i[j]],
                           "exit_date": dates[i], "entry_price": round(float(e_px[j]), 3),
                           "exit_price": round(float(fill), 3),
                           "ret": round(float(pnl / e_cost[j]), 5),
                           "days": int(i - e_i[j]), "reason": reason})
            hold[j] = False
            qty[j] = e_cost[j] = e_px[j] = 0.0
            tgt[j] = stp[j] = np.nan; e_i[j] = -1

        m = hold & ~np.isnan(tgt) & (hi >= tgt)
        for j in np.where(m)[0]:
            fill = op[j] if (not np.isnan(op[j]) and op[j] >= tgt[j]) else tgt[j]
            if not (np.isnan(fill) or fill <= 0):
                close_pos(j, fill, "止盈"); sold[j] = True
        m = hold & ~sold & ~np.isnan(stp) & (lo <= stp)
        for j in np.where(m)[0]:
            fill = op[j] if (not np.isnan(op[j]) and op[j] <= stp[j]) else stp[j]
            if not (np.isnan(fill) or fill <= 0):
                close_pos(j, fill, "止损"); sold[j] = True
        m = hold & ~sold & (sg == -1)
        for j in np.where(m)[0]:
            if not (np.isnan(op[j]) or op[j] <= 0):
                close_pos(j, op[j], "反向信号"); sold[j] = True
        m = hold & ~sold & (i - e_i >= MAX_HOLD) & ~np.isnan(cl) & (cl > 0)
        for j in np.where(m)[0]:
            close_pos(j, cl[j], "超期"); sold[j] = True

        m = (~hold) & (~sold) & (sg == 1) & valid & ~np.isnan(op) & (op > 0)
        if m.any():
            px_now = np.where(np.isnan(c_a[i]), e_px, c_a[i])
            cur = cash + float(np.nansum(qty * px_now))
            unit = cur / max_pos
            for j in np.where(m)[0]:
                if cash < unit * 0.2:
                    break
                fill = op[j]
                alloc = min(unit, cash)
                q = alloc / (fill * (1 + COST))
                cash -= q * fill * (1 + COST)
                hold[j] = True
                qty[j] = q; e_cost[j] = q * fill * (1 + COST); e_px[j] = fill
                e_i[j] = i
                tgt[j] = fill * (1 + tp)
                stp[j] = fill * (1 - sl)

        px_now = np.where(np.isnan(c_a[i]), e_px, c_a[i])
        equity.append(cash + float(np.nansum(qty * px_now)))

    eq = pd.Series(equity, index=idx[1:])
    return eq, pd.DataFrame(trades)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", default="all")
    ap.add_argument("--no-gate", action="store_true")
    ap.add_argument("--tp", type=float, default=0.08)
    ap.add_argument("--sl", type=float, default=0.08)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    p = E.piv()
    names = STRATEGIES if a.strategy == "all" else {a.strategy: STRATEGIES[a.strategy]}
    rows = []
    for key, (label, fn) in names.items():
        sig = fn(p)
        eq, tr = backtest_signal(p, sig, tp=a.tp, sl=a.sl, use_gate=not a.no_gate)
        if len(eq) < 100:
            print(f"{label}: 无交易"); continue
        r = eq.pct_change(fill_method=None).dropna()
        yrs = len(eq) / 252
        ann = eq.iloc[-1] ** (1 / yrs) - 1
        vol = r.std() * np.sqrt(252)
        mdd = (eq / eq.cummax() - 1).min()
        row = {"策略": label, "年化": ann, "回撤": mdd,
               "夏普": r.mean() * 252 / vol if vol > 0 else 0,
               "交易数": len(tr)}
        if len(tr):
            row["胜率"] = (tr["ret"] > 0).mean()
            row["平均单笔"] = tr["ret"].mean()
            row["平均持有天"] = tr["days"].mean()
            w = tr.loc[tr["ret"] > 0, "ret"]; x = tr.loc[tr["ret"] <= 0, "ret"]
            row["盈亏比"] = abs(w.mean() / x.mean()) if len(x) and x.mean() != 0 else 0
        rows.append(row)
        print(f"{label} 完成: {len(tr)}笔 年化{ann:+.1%} 回撤{mdd:.1%}", flush=True)

    df = pd.DataFrame(rows).sort_values("年化", ascending=False)
    print("\n=== 经典技术信号策略 (2015-2026, 成本0.5%, 门控=" + ("关" if a.no_gate else "开") + ") ===")
    d = df.copy()
    for kk in ["年化", "回撤", "胜率", "平均单笔"]:
        if kk in d.columns:
            d[kk] = d[kk].map(lambda x: f"{x:.1%}" if pd.notna(x) else "-")
    for kk in ["夏普", "盈亏比"]:
        if kk in d.columns:
            d[kk] = d[kk].map(lambda x: f"{x:.2f}" if pd.notna(x) else "-")
    if "平均持有天" in d.columns:
        d["平均持有天"] = d["平均持有天"].map(lambda x: f"{x:.1f}" if pd.notna(x) else "-")
    print(d.to_string(index=False))
    df.to_csv(OUT / "signal_strategies.csv", index=False, encoding="utf-8")
    print(f"\n明细: {OUT / 'signal_strategies.csv'}")
    return df


if __name__ == "__main__":
    main()
