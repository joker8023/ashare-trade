import sys, json, gc, pickle, itertools
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import prior_check as pc
from prior_check import Pos, px_ffill_or_nan
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, EVAL_END, MB
from collections import Counter

RUN_START = "2023-01-03"
piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean.pkl")
dates = piv["close"].index
grid30 = [d for d in [dates[i] for i in range(300, len(dates))] if False]
grid30 = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
close = piv["close"]
rets = close.pct_change(fill_method=None)

# ---- regime index variants (all trailing-only) ----
shares = piv["shares"]
s_aligned = shares.reindex(close.columns)
mktcap = close.mul(s_aligned, axis=1)
# prior-day cap rank -> bottom 30% mask (shifted, no lookahead)
valid = close.notna() & mktcap.notna()
rank = mktcap.rank(axis=1, pct=True)  # rank on same-day cap; we shift mask by 1 day for honesty
is_small_same = (rank <= 0.30) & valid
is_small_prior = is_small_same.shift(1)  # use prior-day membership for today's return
is_small_prior = is_small_prior.fillna(False)
small_rets = rets.where(is_small_prior)
small_mean = small_rets.mean(axis=1, skipna=True).fillna(0)
small_idx = (1 + small_mean).cumprod()
# cap-weighted (trailing weights = prior-day cap)
w_prior = mktcap.shift(1)
wsum = w_prior.sum(axis=1)
capw_mean = ((rets * w_prior).sum(axis=1, skipna=True) / wsum).fillna(0)
capw_idx = (1 + capw_mean).cumprod()
# equal-weight (current engine)
eq_idx = (1 + rets.mean(axis=1, skipna=True).fillna(0)).cumprod()
print("idx built", flush=True)
print("eq_idx tail", float(eq_idx.iloc[-1]), flush=True)

IDX = {"EQ": eq_idx, "SMALL30": small_idx, "CAPW": capw_idx}

def build_reg(idx_series, thr):
    ma20 = idx_series.rolling(20).mean()
    ma60 = idx_series.rolling(60).mean()
    reg = {}
    for d in dates:
        a20 = ma20.loc[d]; a60 = ma60.loc[d]
        if pd.isna(a20) or pd.isna(a60):
            reg[d] = "SIDE"
        else:
            g = float(a20 / a60 - 1)
            if g > thr: reg[d] = "BULL"
            elif g < -thr: reg[d] = "BEAR"
            else: reg[d] = "SIDE"
    return reg

# ---- shadows (run once) ----
CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
inpA = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
inpB = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=0.80, max_win=20)
CFG_A = dict(n=5, rebal=20, take=1.2)
CFG_B = dict(n=4, rebal=30, take=0.8)
shadow_path = ROOT / "results" / "r30_bt" / "_m07c_shadows.pkl"
import os
if os.path.exists(shadow_path):
    print("loading cached shadows", flush=True)
    d = pickle.load(open(shadow_path, "rb"))
    sha = d["sha"]; shb = d["shb"]
else:
    print("running shadows", flush=True)
    ra = pc.run_strategy(inpA, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
    rb = pc.run_strategy(inpB, n=4, rebal=30, take=0.8, exposure=0.9, phase=0, **CA)
    sha = ra.eq.iloc[:, 0] if isinstance(ra.eq, pd.DataFrame) else ra.eq
    shb = rb.eq.iloc[:, 0] if isinstance(rb.eq, pd.DataFrame) else rb.eq
    print("shadows done A trades=" + str(len(ra.trades)) + " B trades=" + str(len(rb.trades)), flush=True)
    pickle.dump({"sha": sha, "shb": shb}, open(shadow_path, "wb"))

RS = 60
def rs_of(eq_s, s_idx):
    j = int(eq_s.index.searchsorted(dates[s_idx], side="right") - 1)
    if j < RS:
        return None
    return float(eq_s.iloc[j] / eq_s.iloc[j - RS] - 1.0)

COMM, MINC, STAMP, TRANS = 0.00025, 5.0, 0.0005, 0.00001
def buy_cost(notional, slip):
    return max(notional * COMM, MINC) + notional * (TRANS + slip)
def sell_cost(notional, slip):
    return max(notional * COMM, MINC) + notional * (STAMP + TRANS + slip)
BX, BY, BF = 0.18, 0.08, 0.6
c = inpA.close
mark = inpA.mark
n_dates = len(dates)
run_ts = pd.Timestamp(RUN_START)
gridA = [i for i in inpA.grid(20, 0) if dates[i] >= run_ts]
gridB = [i for i in inpB.grid(30, 0) if dates[i] >= run_ts]
sigA = set(gridA); sigB = set(gridB)
allsig = sorted(sigA | sigB)
exec_map = {}
for i in allsig:
    ei = i + 1
    if ei < n_dates:
        exec_map.setdefault(ei, i)
loop_start = min(gridA[0], gridB[0])
end_i = int(dates.searchsorted(EVAL_END, side="right") - 1)
loop_end = min(end_i, n_dates - 1)

combo = pickle.load(open(ROOT / "results" / "r30_bt" / "combo_w70_equity.pkl", "rb"))
if isinstance(combo, pd.DataFrame):
    combo = combo.iloc[:, 0]
combo = combo.dropna()

def run_one(REG, EXP):
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
    state_n = CFG_A["n"]
    state_exp = 1.0
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
        fee = sell_cost(notional, 0.002)
        cash = cash + notional - fee
        total_cost = total_cost + fee
        cost_basis = p.entry_px * sh + p.buy_cost
        net_pnl = notional - fee - cost_basis
        trades.append(dict(code=code, entry_i=p.entry_i, exit_i=i, entry_date=dates[p.entry_i], exit_date=day, shares=sh, entry_px=p.entry_px, exit_px=px, net_pnl=net_pnl, reason=reason))
        del pos[code]
    def do_rebalance(i, sig_i):
        nonlocal cash, total_cost, mode, state_take, state_n, state_exp, brake, brake_peak, brake_trough
        day = dates[i]
        sig_day = dates[sig_i]
        ra_v = rs_of(sha, sig_i)
        rb_v = rs_of(shb, sig_i)
        want_leg = mode
        if sig_i in sigA and ra_v is not None and rb_v is not None:
            want_leg = "A" if ra_v >= rb_v else "B"
        rg = REG.get(sig_day, "SIDE")
        want_exp = EXP.get(rg, 0.9)
        switching = (want_leg != mode)
        on_grid = (sig_i in sigA) if want_leg == "A" else (sig_i in sigB)
        if (not switching) and (not on_grid):
            if abs(want_exp - state_exp) < 0.001:
                return False
        if switching:
            mode = want_leg
            switch_log.append((str(sig_day.date()), mode, rg, round(ra_v,4) if ra_v is not None else None, round(rb_v,4) if rb_v is not None else None))
        cfgm = CFG_A if mode == "A" else CFG_B
        state_take = cfgm["take"]
        state_n = cfgm["n"]
        state_exp = cfgm.get("exposure", 1.0)
        inp_cur = inpA if mode == "A" else inpB
        picks = inp_cur.picks(sig_day, state_n, exclude=MB, factor="amihud_60")
        if (not switching) and set(picks) == set(pos) and abs(want_exp - state_exp) < 0.001:
            return False
        for code2 in list(pos.keys()):
            close_pos(code2, i, "rebalance")
        if not picks:
            return True
        slots = len(picks)
        alloc = cash * state_exp / slots if slots > 0 else 0
        if brake:
            alloc = alloc * BF
        for code2 in picks:
            if code2 in pos:
                continue
            px = px_ffill_or_nan(mark, day, code2)
            if pd.isna(px) or px <= 0:
                continue
            sh = int(alloc / px // 100) * 100
            if sh <= 0:
                continue
            notional = sh * px
            fee = buy_cost(notional, 0.002)
            if notional + fee > cash:
                sh = int(max(cash - fee, 0.0) / px // 100) * 100
                if sh <= 0:
                    continue
                notional = sh * px
                fee = buy_cost(notional, 0.002)
                if notional + fee > cash:
                    continue
            cash = cash - notional - fee
            total_cost = total_cost + fee
            pos[code2] = Pos(shares=sh, entry_px=px, entry_i=i, high=px, buy_cost=fee, entry_equity=cash)
        return True
    for i in range(loop_start, loop_end + 1):
        day = dates[i]
        if pending:
            todo = [x for x in pending]
            pending = []
            for code2, _ii, reason in todo:
                if code2 in pos:
                    close_pos(code2, i, reason)
        if i in exec_map:
            do_rebalance(i, exec_map[i])
        if pos and (i in exec_map):
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
                if dd >= BX:
                    brake = True
                    brake_trough = tb_eq
                    brake_log.append((str(day.date()), "ON", round(float(dd) * 100, 2)))
            elif brake:
                if tb_eq < brake_trough:
                    brake_trough = tb_eq
                if brake_trough > 0 and tb_eq >= brake_trough * (1.0 + BY):
                    brake = False
                    brake_log.append((str(day.date()), "OFF", round(float(tb_eq / brake_trough - 1) * 100, 2)))
        if pos:
            for code2 in list(pos.keys()):
                px = px_ffill_or_nan(mark, day, code2)
                p = pos[code2]
                if pd.isna(px):
                    continue
                if px > p.high:
                    p.high = px
                hit_stop = px < p.high * (1.0 - 0.25)
                hit_take = px >= p.entry_px * (1.0 + state_take)
                if hit_stop:
                    pending.append((code2, i, "stop"))
                elif hit_take:
                    pending.append((code2, i, "take"))
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
    eq = eq.dropna()
    return eq, trades, total_cost, mode, switch_log, brake_log

import time
THRS = [0.01, 0.015, 0.02, 0.03]
BEARS = [0.5, 0.6, 0.7, 0.85, 1.0]
SIDES = [0.7, 0.9]
IDXNAMES = ["EQ", "SMALL30", "CAPW"]
results = []
eq_store = {}
t0 = time.time()
for idxn in IDXNAMES:
    for thr in THRS:
        REG = build_reg(IDX[idxn], thr)
        dist = dict(Counter(REG[d] for d in grid30 if d >= pd.Timestamp(RUN_START)))
        for bear in BEARS:
            for side in SIDES:
                EXP = {"BULL": 1.0, "SIDE": side, "BEAR": bear}
                t1 = time.time()
                eq, trades, cost, mode, slog, blog = run_one(REG, EXP)
                tot = float(eq.iloc[-1] / eq.iloc[0] - 1) * 100
                mdd = float(_mdd(eq)) * 100
                # combo-window aligned
                eqa = eq.loc[combo.index]
                mtot = float(eqa.iloc[-1] / eqa.iloc[0] - 1) * 100
                mmdd = float(_mdd(eqa)) * 100
                ctot = float(combo.iloc[-1] / combo.iloc[0] - 1) * 100
                cmdd = float(_mdd(combo)) * 100
                key = f"{idxn}_T{thr}_B{bear}_S{side}"
                results.append(dict(key=key, idx=idxn, thr=thr, bear=bear, side=side, total=round(tot,2), mdd=round(mdd,2), mine_total=round(mtot,2), mine_mdd=round(mmdd,2), combo_total=round(ctot,2), combo_mdd=round(cmdd,2), excess=round(mtot-ctot,2), trades=len(trades), cost=int(cost), mode=mode, switches=len(slog), brakes=len(blog), dist=dist, dt=round(time.time()-t1,1)))
                eq_store[key] = eq
                print(f"{key} total={tot:.2f} mdd={mdd:.2f} mine_cw={mtot:.2f}/{mmdd:.2f} excess={mtot-ctot:.1f} sw={len(slog)} br={len(blog)} dist={dist} ({time.time()-t1:.1f}s)", flush=True)
print(f"ALL DONE {time.time()-t0:.0f}s", flush=True)
# save summary sorted by mine_total desc
results_sorted = sorted(results, key=lambda r: r['mine_total'], reverse=True)
pickle.dump(results_sorted, open(ROOT / "results" / "r30_bt" / "_m07c_sweep.pkl", "wb"))
open(ROOT / "results" / "r30_bt" / "_m07c_sweep.json", "w").write(json.dumps(results_sorted, ensure_ascii=False, indent=1))
# save top-3 full detail incl switch logs by re-running? store logs now
detail = {}
for r in results_sorted[:5]:
    key = r['key']
    # re-derive logs: need to re-run to capture logs (cheap: re-run top5 only) OR store during loop. We stored only counts; re-run for logs:
    thr=r['thr']; EXP={"BULL":1.0,"SIDE":r['side'],"BEAR":r['bear']}; REG=build_reg(IDX[r['idx']], thr)
    eq, trades, cost, mode, slog, blog = run_one(REG, EXP)
    detail[key] = dict(switch_log=slog, brake_log=blog, total=r['total'], mdd=r['mdd'])
    eq_store[key].to_pickle(ROOT / "results" / "r30_bt" / f"_m07c_{key}_equity.pkl")
pickle.dump(eq_store, open(ROOT / "results" / "r30_bt" / "_m07c_eqstore.pkl", "wb"))
open(ROOT / "results" / "r30_bt" / "_m07c_top5_detail.json", "w").write(json.dumps(detail, ensure_ascii=False, indent=1))
print("saved sweep", flush=True)
