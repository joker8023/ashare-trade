import sys, json, gc
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import numpy as np
import prior_check as pc
from prior_check import Pos, px_ffill_or_nan, build_periods
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import _mdd, EVAL_END, MB
piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
RUN_START = str(dates[0].date())
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
print("RUN_START=" + RUN_START + " first=" + str(first_sig.date()) + " eval=" + str(EVAL_END.date()))
close = piv["close"]
shares = piv["shares"]
tot = (close * shares).sum(axis=1)
mret = tot.pct_change()
midx = (1 + mret.fillna(0)).cumprod()
ma20 = midx.rolling(20).mean()
ma60 = midx.rolling(60).mean()
THR = 0.01
REG = {}
for d in dates:
    a20 = ma20.loc[d]
    a60 = ma60.loc[d]
    if pd.isna(a20) or pd.isna(a60):
        REG[d] = "SIDE"
    else:
        g = float(a20 / a60 - 1)
        if g > THR:
            REG[d] = "BULL"
        elif g < -THR:
            REG[d] = "BEAR"
        else:
            REG[d] = "SIDE"
MAP = {"BULL": "C", "BEAR": "A", "SIDE": "B"}
from collections import Counter
print("grid dist:" + str(dict(Counter(REG[d] for d in grid30))))
print("2023+ dist:" + str(dict(Counter([REG[d] for d in grid30 if d >= pd.Timestamp("2023-01-03")]))))
CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
def make_inp(sel):
    return DInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=0.70, max_win=20, sel=sel)
CFG_A = dict(n=3, rebal=30, take=0.8, exposure=1.0)
CFG_B = dict(n=6, rebal=30, take=0.8, exposure=1.0)
CFG_C = dict(n=4, rebal=30, take=0.8, exposure=1.0)
SEL_A = "c_a60_vol"
SEL_B = "c_a60_turn"
SEL_C = "amihud_5"
inpA = make_inp(SEL_A)
inpB = make_inp(SEL_B)
inpC = make_inp(SEL_C)
INPS = {"A": inpA, "B": inpB, "C": inpC}
CFGS = {"A": CFG_A, "B": CFG_B, "C": CFG_C}
COMM, MINC, STAMP, TRANS = 0.00025, 5.0, 0.0005, 0.00001
def buy_cost(notional, slip):
    return max(notional * COMM, MINC) + notional * (TRANS + slip)
def sell_cost(notional, slip):
    return max(notional * COMM, MINC) + notional * (STAMP + TRANS + slip)
def run_regime(tag, bx=0.12, by_=0.05, bf=0.4, slip=0.002):
    c = inpA.close
    mark = inpA.mark
    ret = inpA.ret
    n_dates = len(dates)
    run_ts = pd.Timestamp(RUN_START)
    gridA = [i for i in inpA.grid(30, 0) if dates[i] >= run_ts]
    gridB = [i for i in inpB.grid(30, 0) if dates[i] >= run_ts]
    gridC = [i for i in inpC.grid(30, 0) if dates[i] >= run_ts]
    sigA = set(gridA)
    sigB = set(gridB)
    sigC = set(gridC)
    allsig = sorted(sigA | sigB | sigC)
    exec_map = {}
    for i in allsig:
        ei = i + 1
        if ei < n_dates:
            exec_map.setdefault(ei, i)
    loop_start = gridA[0]
    end_i = int(dates.searchsorted(EVAL_END, side="right") - 1)
    loop_end = min(end_i, n_dates - 1)
    cash = 50000.0
    pos = {}
    trades = []
    pending = []
    total_cost = 0.0
    eq_rows = []
    mode = "A"
    switch_log = []
    brake_log = []
    brake = False
    brake_peak = 0.0
    brake_trough = 0.0
    state_take = CFG_A["take"]
    state_stop = 0.25
    state_n = CFG_A["n"]
    state_exp = CFG_A["exposure"]
    def close_pos(code, i, reason):
        nonlocal cash, total_cost
        day = dates[i]
        p = pos[code]
        sh = p.shares
        if sh <= 0:
            return
        px = px_ffill_or_nan(mark, day, code)
        if pd.isna(px):
            px = p.entry_px
        notional = sh * px
        fee = sell_cost(notional, slip)
        cash = cash + notional - fee
        total_cost = total_cost + fee
        frac = 1.0
        cost_basis = p.entry_px * sh + p.buy_cost * frac
        net_pnl = notional - fee - cost_basis
        trades.append(dict(code=code, entry_i=p.entry_i, exit_i=i, entry_date=dates[p.entry_i], exit_date=day, shares=sh, entry_px=p.entry_px, exit_px=px, net_pnl=net_pnl, reason=reason))
        del pos[code]
    def do_rebalance(i, sig_i):
        nonlocal cash, total_cost, mode, state_take, state_stop, state_n, state_exp, brake, brake_peak, brake_trough
        day = dates[i]
        sig_day = dates[sig_i]
        rg = REG.get(sig_day, "SIDE")
        want = MAP.get(rg, "B")
        desired = want
        switching = (desired != mode)
        on_grid_map = {"A": (sig_i in sigA), "B": (sig_i in sigB), "C": (sig_i in sigC)}
        on_grid = on_grid_map[desired]
        if (not switching) and (not on_grid):
            return False
        if switching:
            mode = desired
            cfgm = CFGS[mode]
            state_take = cfgm["take"]
            state_stop = 0.25
            state_n = cfgm["n"]
            state_exp = cfgm["exposure"]
            switch_log.append((str(sig_day.date()), mode, rg))
        else:
            cfgm = CFGS[mode]
            state_take = cfgm["take"]
            state_stop = 0.25
            state_n = cfgm["n"]
            state_exp = cfgm["exposure"]
        inp_cur = INPS[mode]
        n_eff = state_n
        picks = inp_cur.picks(sig_day, n_eff, exclude=MB, factor="amihud_60")
        for code in list(pos.keys()):
            close_pos(code, i, "rebalance")
        if not picks:
            return True
        slots = len(picks)
        alloc = cash * state_exp / slots if slots > 0 else 0
        if brake:
            alloc = alloc * bf
        for code in picks:
            if code in pos:
                continue
            px = px_ffill_or_nan(mark, day, code)
            if pd.isna(px) or px <= 0:
                continue
            sh = int(alloc / px // 100) * 100
            if sh <= 0:
                continue
            notional = sh * px
            fee = buy_cost(notional, slip)
            if notional + fee > cash:
                sh = int(max(cash - fee, 0.0) / px // 100) * 100
                if sh <= 0:
                    continue
                notional = sh * px
                fee = buy_cost(notional, slip)
                if notional + fee > cash:
                    continue
            cash = cash - notional - fee
            total_cost = total_cost + fee
            pos[code] = Pos(shares=sh, entry_px=px, entry_i=i, high=px, buy_cost=fee, entry_equity=cash)
        return True
    for i in range(loop_start, loop_end + 1):
        day = dates[i]
        if pending:
            todo = [x for x in pending]
            pending = []
            for code, _ii, reason in todo:
                if code in pos:
                    close_pos(code, i, reason)
        if i in exec_map:
            do_rebalance(i, exec_map[i])
        if pos:
            tb_mv = 0.0
            for cc, p in pos.items():
                px = px_ffill_or_nan(mark, day, cc)
                if pd.isna(px):
                    px = p.entry_px
                tb_mv = tb_mv + p.shares * px
            tb_eq = cash + tb_mv
            if tb_eq > brake_peak:
                brake_peak = tb_eq
            if (not brake) and brake_peak > 0:
                dd = (brake_peak - tb_eq) / brake_peak
                if dd >= bx:
                    brake = True
                    brake_trough = tb_eq
                    brake_log.append((str(day.date()), "ON", round(float(dd) * 100, 2)))
            elif brake:
                if tb_eq < brake_trough:
                    brake_trough = tb_eq
                if brake_trough > 0 and tb_eq >= brake_trough * (1.0 + by_):
                    brake = False
                    brake_log.append((str(day.date()), "OFF", round(float(tb_eq / brake_trough - 1) * 100, 2)))
        if pos:
            for code in list(pos.keys()):
                px = px_ffill_or_nan(mark, day, code)
                p = pos[code]
                if pd.isna(px):
                    continue
                if px > p.high:
                    p.high = px
                hit_stop = px < p.high * (1.0 - 0.25)
                hit_take = px >= p.entry_px * (1.0 + state_take)
                if hit_stop:
                    pending.append((code, i, "stop"))
                elif hit_take:
                    pending.append((code, i, "take"))
        mv = 0.0
        for cc, p in pos.items():
            px = px_ffill_or_nan(mark, day, cc)
            if pd.isna(px):
                px = p.entry_px
            mv = mv + p.shares * px
        eq_rows.append((day, cash + mv))
        if cash + mv > brake_peak:
            brake_peak = cash + mv
    eq = pd.Series([x[1] for x in eq_rows], index=[x[0] for x in eq_rows], name="eq")
    return eq, trades, switch_log, brake_log, total_cost, mode
eq, trades, slog, blog, cost, fmode = run_regime("REGIME3", bx=0.12, by_=0.05, bf=0.4)
eq = eq.dropna()
print("eq " + str(eq.index[0].date()) + " to " + str(eq.index[-1].date()) + " n=" + str(len(eq)))
eq.to_pickle(ROOT / "results" / "r30_bt" / "REGIME3_equity.pkl")
WINDOWS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}
out = {"tag": "REGIME3_gap1pct", "thr": THR, "total": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2), "mdd": round(float(_mdd(eq)) * 100, 2), "trades": int(len(trades)), "cost": round(float(cost), 0), "mode": fmode, "switches": len(slog), "switch_log": slog, "brakes": len(blog) // 2}
for w, d in WINDOWS.items():
    sub = eq.tail(d + 1)
    out[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
    out[w + "_mdd"] = round(float(_mdd(sub)) * 100, 2)
for y in [2021, 2022, 2023, 2024, 2025, 2026]:
    sub = eq[eq.index.year == y]
    if len(sub) > 1:
        out["ann_" + str(y)] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
        out["ann_" + str(y) + "_mdd"] = round(float(_mdd(sub)) * 100, 2)
import pickle as pk
combo = pk.load(open(ROOT / "results" / "r30_bt" / "combo_w70_equity.pkl", "rb"))
if isinstance(combo, pd.DataFrame):
    combo = combo.iloc[:, 0]
combo = combo.dropna()
start = combo.index[0]
eqs = eq[eq.index >= start]
combo_tot = float(combo.iloc[-1] / combo.iloc[0] - 1) * 100
sliced_tot = float(eqs.iloc[-1] / eqs.iloc[0] - 1) * 100
out["combo_window"] = {"combo_start": str(start.date()), "combo_total": round(combo_tot, 2), "combo_mdd": round(float(_mdd(combo)) * 100, 2), "regime_sliced_total": round(sliced_tot, 2), "regime_sliced_mdd": round(float(_mdd(eqs)) * 100, 2), "excess_pp": round(sliced_tot - combo_tot, 2)}
for w, d in WINDOWS.items():
    cs = combo.tail(d + 1)
    rs = eqs.tail(d + 1)
    out["cmp_" + w] = {"combo": round(float(cs.iloc[-1] / cs.iloc[0] - 1) * 100, 2), "regime": round(float(rs.iloc[-1] / rs.iloc[0] - 1) * 100, 2)}
print(json.dumps(out, ensure_ascii=False, indent=1))
open(ROOT / "results" / "r30_bt" / "REGIME3.json", "w").write(json.dumps(out, ensure_ascii=False, indent=1))
print("saved REGIME3")
