#!/usr/bin/env python3
"""Beat-H1 sweep v1: TB18 base + single-factor variations (2020 caliber, ph0).
Goal: all six windows > TB18 AND 3y >> 2y. Long-only, no leverage, STAR allowed.
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import prior_check as pc
from design_r30_grid8 import X3Inputs
from typing import List, Tuple

WINDOWS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}
RUN_START = "2023-01-03"
EVAL_END = pd.Timestamp("2026-11-12")
MB = ("688", "689", "300", "301", "8", "4")
STAR = ("300", "301", "8", "4")  # allow 688/689
BASE_W = {"1m": -4.98, "3m": 14.07, "6m": 32.01, "1y": 150.80, "2y": 1334.68, "3y": 1321.51}

AA = "    switch_log: List[Tuple[str, str]] = []"
BB = "        nonlocal cash, total_cost, mode, state_take, state_n, state_exposure"
CC = "        sig_day = dates[sig_i]"
DD = "        picks = inp_cur.picks(sig_day, n_eff, exclude=exclude, factor=factor)"
EE = "        for code in picks:"
FF = "        eq_rows.append((day, cash + mv, mv, cash, len(pos)))"
GG = "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode,"

def _mdd(s):
    import pandas as pd
    return float((s / s.cummax() - 1).min())

def build_ns(bx=0.18, by_=0.08, bf=0.5):
    import prior_check as _pc
    src = (ROOT / "research" / "switch_engine.py").read_text()
    def _once(old, new):
        assert src.count(old) == 1, (old[:60], src.count(old))
        return src.replace(old, new)
    add = f"\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n    _brake_log: List = []\n    _BRAKE_X = {bx}\n    _BRAKE_Y = {by_}\n    _BRAKE_F = {bf}"
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

def run_one(piv, dates, first_sig, cfg):
    excl = STAR if cfg.get('star') else MB
    stop = cfg.get('stop')
    a_take = cfg.get('a_take', 1.2)
    b_exp = cfg.get('b_exp', 0.9)
    b_take = cfg.get('b_take', 0.45)
    inp_a = X3Inputs(piv, gate60=cfg.get('gate', -0.15))
    inp_b = pc.Inputs(piv)
    COMMON = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=excl, capital=50_000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=cfg.get('b_n', 4), rebal=30, take=b_take, exposure=b_exp)
    ra = pc.run_strategy(inp_a, n=cfg.get('a_n', 5), rebal=cfg.get('a_r', 20), take=a_take, exposure=cfg.get('a_exp', 1.0), phase=0, **COMMON)
    rb = pc.run_strategy(inp_b, phase=0, **{**COMMON, **CFG_B})
    KW = dict(n=cfg.get('a_n', 5), rebal=cfg.get('a_r', 20), take=a_take, exposure=cfg.get('a_exp', 1.0), phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, **COMMON)
    ns = build_ns(cfg.get('bx', 0.18), cfg.get('by', 0.08), cfg.get('bf', 0.5))
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, __import__('pandas').DataFrame) else res.eq
    eq = eq.dropna()
    out = {"total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), "mdd": round(_mdd(eq)*100,2), "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]),0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"])}
    for w, d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
        out[w+'_mdd'] = round(_mdd(sub)*100,2)
    out['gap_3y_2y'] = round(out['3y'] - out['2y'], 2)
    out['beat_all'] = all(out[w] > BASE_W[w] for w in WINDOWS)
    out['nbeat'] = sum(1 for w in WINDOWS if out[w] > BASE_W[w])
    return out

def main():
    piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean.pkl")
    dates = piv["close"].index
    grid_dates = [dates[i] for i in range(300, len(dates), 30)]
    first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
    configs = [
        {"tag": "v00_TB18_repro"},
        {"tag": "v01_Bexp100", "b_exp": 1.0},
        {"tag": "v02_STAR_both", "star": True},
        {"tag": "v03_STAR_Bexp100", "star": True, "b_exp": 1.0},
        {"tag": "v04_brakeF03", "bf": 0.3},
        {"tag": "v05_brakeX15", "bx": 0.15},
        {"tag": "v06_brakeX22", "bx": 0.22},
        {"tag": "v07_stop25", "stop": 0.25},
        {"tag": "v08_stop25_Bexp100", "stop": 0.25, "b_exp": 1.0},
        {"tag": "v09_Atake100", "a_take": 1.0},
        {"tag": "v10_An6", "a_n": 6},
        {"tag": "v11_Btake60_Bexp100", "b_take": 0.60, "b_exp": 1.0},
        {"tag": "v12_combo_STAR_B100_X22", "star": True, "b_exp": 1.0, "bx": 0.22},
    ]
    rows = []
    for cfg in configs:
        try:
            r = run_one(piv, dates, first_sig, cfg)
            r['tag'] = cfg['tag']
            print(json.dumps(r, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print(f"FAIL {cfg['tag']}: {e}", flush=True)
            import traceback; traceback.print_exc()
    with open(ROOT / "results" / "r30_bt" / "sweep_beat_h1_v1.json", "w") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"saved {len(rows)} rows", flush=True)

if __name__ == "__main__":
    main()
