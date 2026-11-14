#!/usr/bin/env python3
# SWITCH-TB18 runner: dual-engine switch + E2 skip + trough-recovery brake.
# Base: A=R20_N5 take1.2/stop0.25 (n=5,rebal=20,exp1.0) / B=balanced N4 take0.45
# (n=4,rebal=30,exp0.9) / RS60 on A-grid only / skip-if-identical /
# stop=0.25 trailing. Brake X=0.18/Y=0.08/f=0.3. Keeps 2y, lifts 3y.
# Patches research/switch_engine.py source at runtime (repo file untouched).
# Expected ph0: total +1452.35% / -32.38%, 195 trades, cost 43001;
# 1m -4.98 / 3m +14.07 / 6m +32.01 / 1y +150.80 / 2y +1334.68 / 3y +1321.51;
# brake 2024-01-31 ON -> 2024-09-13 OFF; 5 switches, final B.
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import prior_check as pc
from design_r30_grid8 import X3Inputs
WINDOWS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}
RUN_START = "2023-01-03"
EVAL_END = pd.Timestamp("2026-11-12")
MB = ("688", "689", "300", "301", "8", "4")
EXP_TOTAL = 1483.37
EXP_MDD = -27.33
EXP_TRADES = 189
EXP_COST = 43376.0
EXP_W = {"1m": (-5.01, -9.03), "3m": (14.02, -10.65), "6m": (32.15, -11.80), "1y": (150.64, -12.94), "2y": (1337.64, -15.59), "3y": (1349.92, -27.33)}
EXP_BRAKE = [["2024-01-31", "ON", 19.87], ["2024-09-13", "OFF", 9.51]]
EXP_SWITCH = [["2023-06-21", "B"], ["2024-03-20", "A"], ["2024-04-19", "B"], ["2024-08-15", "A"], ["2026-09-08", "B"]]
AA = "    switch_log: List[Tuple[str, str]] = []"
BB = "        nonlocal cash, total_cost, mode, state_take, state_n, state_exposure"
CC = "        sig_day = dates[sig_i]"
DD = "        picks = inp_cur.picks(sig_day, n_eff, exclude=exclude, factor=factor)"
EE = "        for code in picks:"
FF = "        eq_rows.append((day, cash + mv, mv, cash, len(pos)))"
GG = "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode,"

def _mdd(s):
    return float((s / s.cummax() - 1).min())

def _patched_namespace():
    src = (ROOT / "research" / "switch_engine.py").read_text()
    def _once(old, new):
        assert src.count(old) == 1, (old[:60], src.count(old))
        return src.replace(old, new)
    add = "\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n    _brake_log: List = []\n    _BRAKE_X = 0.18\n    _BRAKE_Y = 0.08\n    _BRAKE_F = 0.3"
    src = _once(AA, AA + add)
    src = _once(BB, BB + ", _brake, _brake_trough, _brake_peak, _brake_log")
    brake_eval = "\n        tb_mv_pre = 0.0\n        for tb_cc, tb_p in pos.items():\n            tb_px = px_ffill_or_nan(mark, day, tb_cc)\n            if pd.isna(tb_px):\n                tb_px = tb_p.entry_px\n            tb_mv_pre += tb_p.shares * tb_px\n        tb_eq_pre = cash + tb_mv_pre\n        if tb_eq_pre > _brake_peak:\n            _brake_peak = tb_eq_pre\n        if not _brake and _brake_peak > 0 and (_brake_peak - tb_eq_pre) / _brake_peak >= _BRAKE_X:\n            _brake = True\n            _brake_trough = tb_eq_pre\n            _brake_log.append((str(day.date()), 'ON', round(float((_brake_peak - tb_eq_pre) / _brake_peak) * 100, 2)))\n        elif _brake:\n            if tb_eq_pre < _brake_trough:\n                _brake_trough = tb_eq_pre\n            if _brake_trough > 0 and tb_eq_pre >= _brake_trough * (1.0 + _BRAKE_Y):\n                _brake = False\n                _brake_log.append((str(day.date()), 'OFF', round(float(tb_eq_pre / _brake_trough - 1) * 100, 2)))"
    src = _once(CC, CC + brake_eval)
    skip_block = "\n        if not switching and set(picks) == set(pos):\n            return False"
    src = _once(DD, DD + skip_block)
    src = _once(EE, "        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n" + EE)
    src = _once(FF, FF + "\n        if (cash + mv) > _brake_peak:\n            _brake_peak = cash + mv")
    src = _once(GG, "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode, brake_log=_brake_log,")
    ns = {}
    exec(compile(src, "switch_engine_tb18", "exec"), ns)
    return ns

def main():
    piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean.pkl")
    dates = piv["close"].index
    grid_dates = [dates[i] for i in range(300, len(dates), 30)]
    first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
    inp_a = X3Inputs(piv, gate60=-0.15)
    inp_b = pc.Inputs(piv)
    COMMON = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50_000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=4, rebal=30, take=0.45, exposure=0.9)
    ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **COMMON)
    rb = pc.run_strategy(inp_b, phase=0, **{**COMMON, **CFG_B})
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, **COMMON)
    ns = _patched_namespace()
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    got_total = round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2)
    got_mdd = round(_mdd(eq) * 100, 2)
    print("TOTAL", got_total, got_mdd, len(res.trades), round(float(res.meta["total_cost"]), 0), res.meta["final_mode"], flush=True)
    for w, d in WINDOWS.items():
        sub = eq.tail(d + 1)
        r = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
        m = round(_mdd(sub) * 100, 2)
        print(w, r, m, flush=True)
        assert (r, m) == EXP_W[w], (w, r, m)
    print("BRAKE", res.meta["brake_log"], flush=True)
    assert got_total == EXP_TOTAL, got_total
    assert got_mdd == EXP_MDD, got_mdd
    assert len(res.trades) == EXP_TRADES
    assert round(float(res.meta["total_cost"]), 0) == EXP_COST
    assert [list(x) for x in res.meta["brake_log"]] == EXP_BRAKE
    assert [list(x) for x in res.meta["switch_log"]] == EXP_SWITCH
    assert res.meta["final_mode"] == "B"
    print("TB18-GAIN assertions passed", flush=True)

if __name__ == "__main__":
    main()