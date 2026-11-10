"""1万元实盘模拟：2026-01-01起，整手交易，佣金max(0.025%,5元)，卖出印花0.05%+过户0.001%"""
import os; os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import pandas as pd, numpy as np
import engine as E
import risk_control as R

COMM, MINC, STAMP, TRANS = 0.00025, 5.0, 0.0005, 0.00001
START_CAP = 10000.0
STOP = None  # 个股跟踪止损比例，如 0.15

p = E.piv(); c = p["close"]
adv20 = p["amount"].rolling(20, min_periods=10).mean()
seasoned = c.shift(250).notna(); fac = E.FACTORS["amihud"](p)
dates = c.index
m500 = R._index_series("000905"); m1000 = R._index_series("000852")

def cost_buy(amount): return max(amount * COMM, MINC) + amount * TRANS
def cost_sell(amount): return max(amount * COMM, MINC) + amount * (STAMP + TRANS)
def px_at(day, code):
    px = c.loc[day, code]
    if pd.isna(px):
        h = c.loc[:day, code].ffill()
        px = h.iloc[-1] if len(h) else float("nan")
    return px

def run(N, REB, idx_code, ma):
    if idx_code == 'none':
        sig = None
    else:
        midx = m500 if idx_code == "000905" else m1000
        sig = (midx > midx.rolling(ma).mean()).shift(1)
    grid = [d for d in [dates[i] for i in range(300, len(dates) - REB - 2, REB)] if d >= pd.Timestamp(START)]
    cash, holds, trades, paid = START_CAP, {}, 0, 0.0
    highs, entrypx = {}, {}
    equity_curve = []

    def liquidate(day):
        nonlocal cash, trades, paid
        for code, sh in list(holds.items()):
            amt = sh * px_at(day, code)
            fee = cost_sell(amt)
            cash += amt - fee; paid += fee; trades += 1
        holds.clear(); highs.clear(); entrypx.clear()

    def buy(day, picks):
        nonlocal cash, trades, paid
        per = (cash / max(len(picks), 1))
        for code in picks:
            px = px_at(day, code)
            if pd.isna(px) or px <= 0: continue
            sh = int(per / px // 100 * 100)
            if sh <= 0: continue
            amt = sh * px
            fee = cost_buy(amt)
            if amt + fee > cash:  # 钱不够就少买
                sh = int((cash - MINC) / px // 100 * 100)
                if sh <= 0: continue
                amt = sh * px; fee = cost_buy(amt)
            cash -= amt + fee; paid += fee; trades += 1
            holds[code] = holds.get(code, 0) + sh
            entrypx[code] = px

    t1map = {}
    for g in grid:
        t1 = dates[dates.get_loc(g) + 1]
        t1map[t1] = g
    # 单循环：调仓 + 止损 + 净值（严格时间顺序）
    for day in dates[dates >= grid[0]]:
        if day in t1map:
            g = t1map[day]
            s = 1.0 if sig is None else (sig.loc[day] if day in sig.index else 1.0)
            if s != 1.0:
                if holds: liquidate(day)
            else:
                if PICKFILE:
                    newp = PICKMAP.get(str(g.date()), [])
                else:
                    valid = seasoned.loc[g] & (adv20.loc[g] > 5e6) & c.loc[g].notna() & fac.loc[g].notna()
                    cap = c.loc[g] * p["shares"]
                    lo, hi = cap.quantile(0.05), cap.quantile(0.30)
                    valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
                    pool = valid[valid].index
                    newp = list(fac.loc[g, pool].nlargest(N).index) if len(pool) >= N else []
                if newp:
                    if set(newp) != set(holds.keys()):
                        if holds: liquidate(day)
                        buy(day, newp)
                        highs = {code: px_at(day, code) for code in holds.keys()}
                        entrypx.update({code: px_at(day, code) for code in holds.keys()})
                else:
                    if holds: liquidate(day)
        if holds:
            for code in list(holds.keys()):
                px = px_at(day, code)
                if code in highs and px > highs[code]:
                    highs[code] = px
                hit_stop = STOP is not None and code in highs and px < highs[code] * (1 - STOP)
                hit_take = TAKE is not None and code in entrypx and px >= entrypx[code] * (1 + TAKE)
                if hit_stop or hit_take:
                    sh = holds.pop(code)
                    amt = sh * px; fee = cost_sell(amt)
                    cash += amt - fee; paid += fee; trades += 1
        mv = sum(sh * px_at(day, code) for code, sh in holds.items())
        equity_curve.append((day, cash + mv))
    eq = pd.DataFrame(equity_curve, columns=["date", "eq"]).set_index("date")["eq"]
    eq.to_csv(f"results/signals/ledger_N{N}_R{REB}_STOP{STOP}_TAKE{TAKE}.csv")
    # 最终全部卖出
    if holds:
        day = dates[-1]
        for code, sh in list(holds.items()):
            amt = sh * px_at(day, code); fee = cost_sell(amt)
            cash += amt - fee; paid += fee; trades += 1
        holds.clear()
    ret = cash / START_CAP - 1
    maxeq = eq.cummax(); mdd = ((eq - maxeq) / maxeq).min()
    print(f"N={N} R={REB} {idx_code}MA{ma} STOP={STOP} TAKE={TAKE}: 终值{cash:.0f} 收益{ret:.1%} 最大回撤{mdd:.1%} 交易{trades}笔 总费用{paid:.0f}元", flush=True)
    return cash, ret, mdd, trades, paid

import sys
STOP = float(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != "None" else None
NS = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [3]
REB = int(sys.argv[3]) if len(sys.argv) > 3 else 40
PICKFILE = os.environ.get("LEDGER_PICKS", "")
PICKMAP = {}
if PICKFILE:
    _pdf = pd.read_csv(PICKFILE, dtype=str).fillna("")
    PICKMAP = {r["date"]: [x for x in r["picks"].split(",") if x] for _, r in _pdf.iterrows()}
START = sys.argv[4] if len(sys.argv) > 4 else "2026-01-01"
START_CAP = float(sys.argv[5]) if len(sys.argv) > 5 else 10000.0
TAKE = float(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[6] != "None" else None
eq_save = {}
_orig_print = print
def run_save(N, REB, idx, ma):
    global eq_save
    import io
    cash, ret, mdd, trades, paid = run(N, REB, idx, ma)
    return cash, ret, mdd, trades, paid
for N in NS:
    run_save(N, REB, "none", 15)
