"""K6: M07 signal-source sweep (factor-only + MAX-cut asym). Baseline = M07 final (ph0).
Caliber identical to run_m07_final.py / sweep_beat_m07_k2.py:
  ph0 / RUN_START=2023-01-03 / EVAL_END=2026-11-12 / 5万 / 现实费率(cost_one_way=None) + slip=0.002 / 整手lot=100.
Engine-native factors only: 'amihud_60' vs 'amihud' (engine maps any other string to amihud20;
size/amount_level/liq_size/amihud_5 are NOT supported by pc.Inputs/X3Inputs/MaxInputs -> skipped, noted below).
Single-leg factor variants route factor_a/factor_b per active mode inside the switch engine
(same string-patch mechanism as build_ns brake patch; no hand-written backtester).
MAX-cut variants keep win_a=40/win_b=20; gate/band/RS/brake untouched.
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
from typing import List, Tuple
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, WINDOWS, RUN_START, EVAL_END, MB
M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05, "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
M07_SWITCH = [["2023-06-21", "B"], ["2024-08-15", "A"], ["2026-09-08", "B"]]
AA = "    switch_log: List[Tuple[str, str]] = []"
BB = "        nonlocal cash, total_cost, mode, state_take, state_n, state_exposure"
CC = "        sig_day = dates[sig_i]"
DD = "        picks = inp_cur.picks(sig_day, n_eff, exclude=exclude, factor=factor)"
EE = "        for code in picks:"
FF = "        eq_rows.append((day, cash + mv, mv, cash, len(pos)))"
GG = "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode,"
SIG = "    exclude: Tuple[str, ...] = (),"
SIGF = '    factor: str = "amihud",'
PICKLINE = "        picks = inp_cur.picks(sig_day, n_eff, exclude=exclude, factor=factor)"
def build_ns_ab(bx=0.18, by_=0.08, bf=0.6):
    src = (ROOT / "research" / "switch_engine.py").read_text()
    def _once(old, new):
        assert src.count(old) == 1, (old[:60], src.count(old))
        return src.replace(old, new)
    # NOTE: replicate build_ns exactly, plus factor_a/factor_b routing
    add = "\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n    _brake_log: List = []\n    _BRAKE_X = %s\n    _BRAKE_Y = %s\n    _BRAKE_F = %s" % (bx, by_, bf)
    src = _once(AA, AA + add)
    src = _once(BB, BB + ", _brake, _brake_trough, _brake_peak, _brake_log")
    brake_eval = "\n        tb_mv_pre = 0.0\n        for tb_cc, tb_p in pos.items():\n            tb_px = px_ffill_or_nan(mark, day, tb_cc)\n            if pd.isna(tb_px):\n                tb_px = tb_p.entry_px\n            tb_mv_pre += tb_p.shares * tb_px\n        tb_eq_pre = cash + tb_mv_pre\n        if tb_eq_pre > _brake_peak:\n            _brake_peak = tb_eq_pre\n        if not _brake and _brake_peak > 0 and (_brake_peak - tb_eq_pre) / _brake_peak >= _BRAKE_X:\n            _brake = True\n            _brake_trough = tb_eq_pre\n            _brake_log.append((str(day.date()), 'ON', round(float((_brake_peak - tb_eq_pre) / _brake_peak) * 100, 2)))\n        elif _brake:\n            if tb_eq_pre < _brake_trough:\n                _brake_trough = tb_eq_pre\n            if _brake_trough > 0 and tb_eq_pre >= _brake_trough * (1.0 + _BRAKE_Y):\n                _brake = False\n                _brake_log.append((str(day.date()), 'OFF', round(float(tb_eq_pre / _brake_trough - 1) * 100, 2)))"
    src = _once(CC, CC + brake_eval)
    skip_block = "\n        if not switching and set(picks) == set(pos):\n            return False"
    src = _once(DD, DD + skip_block)
    src = _once(PICKLINE, "        _ex = (exclude_a if mode == 'A' else exclude_b) if (exclude_a is not None or exclude_b is not None) else exclude\n        _f = (factor_a if mode == 'A' else factor_b) if (factor_a is not None or factor_b is not None) else factor\n" + PICKLINE.replace("exclude=exclude", "exclude=_ex").replace("factor=factor", "factor=_f"))
    src = _once(SIG, SIG + "\n    exclude_a=None,\n    exclude_b=None,")
    src = _once(SIGF, SIGF + "\n    factor_a=None,\n    factor_b=None,")
    src = _once(EE, "        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n" + EE)
    src = _once(FF, FF + "\n        if (cash + mv) > _brake_peak:\n            _brake_peak = cash + mv")
    src = _once(GG, "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode, brake_log=_brake_log,")
    ns = {}
    exec(compile(src, "switch_engine_k6", "exec"), ns)
    return ns
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
_ns = build_ns_ab(0.18, 0.08, 0.6)
_shadow_cache = {}
def get_shadows(cut_a, win_a, cut_b, win_b, fa, fb):
    key = (cut_a, win_a, cut_b, win_b, fa, fb)
    if key in _shadow_cache:
        return _shadow_cache[key]
    inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=cut_a, max_win=win_a)
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=cut_b, max_win=win_b)
    base = dict(stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CA = dict(base, factor=fa)
    CB = dict(base, factor=fb)
    CFG_B = dict(n=4, rebal=30, take=0.80, exposure=0.9)
    ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CB, **CFG_B})
    _shadow_cache[key] = (inp_a, inp_b, ra, rb, base, CFG_B)
    return _shadow_cache[key]
def run_one(tag, factor_a="amihud_60", factor_b="amihud_60", cut_a=0.80, win_a=40, cut_b=0.80, win_b=20):
    inp_a, inp_b, ra, rb, base, CFG_B = get_shadows(cut_a, win_a, cut_b, win_b, factor_a, factor_b)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=60, exclude_a=MB, exclude_b=MB, factor="amihud_60", factor_a=factor_a, factor_b=factor_b, **base)
    res = _ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "factor_a": factor_a, "factor_b": factor_b, "cut_a": cut_a, "win_a": win_a, "cut_b": cut_b, "win_b": win_b,
           "total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), "mdd": round(_mdd(eq)*100,2), "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]),0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "brakes": len(res.meta.get("brake_log",[]))//2,
           "switch_log": [list(x) for x in res.meta["switch_log"]], "brake_log": [list(x) for x in res.meta.get("brake_log", [])]}
    for w, d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
        out[w+"_mdd"] = round(_mdd(sub)*100,2)
    out["nbeat_m07"] = sum(1 for w in WINDOWS if out[w] > M07[w])
    out["beat_all"] = all(out[w] > M07[w] for w in WINDOWS)
    out["mdd_better"] = out["mdd"] > M07["mdd"]
    out["win_all"] = bool(out["beat_all"] and out["mdd_better"])
    out["switch_same_m07"] = (out["switch_log"] == M07_SWITCH)
    return out
CFGS = [
    dict(tag="base_M07"),
    dict(tag="both_amihud", factor_a="amihud", factor_b="amihud"),
    dict(tag="Aleg_amihud", factor_a="amihud", factor_b="amihud_60"),
    dict(tag="Bleg_amihud", factor_a="amihud_60", factor_b="amihud"),
    dict(tag="cut75_both", cut_a=0.75, cut_b=0.75),
    dict(tag="cut85_both", cut_a=0.85, cut_b=0.85),
    dict(tag="asym_A78B82", cut_a=0.78, cut_b=0.82),
    dict(tag="asym_A82B78", cut_a=0.82, cut_b=0.78),
]
SKIPPED = ["amihud_5", "size", "amount_level", "liq_size"]
if __name__ == "__main__":
    rows = []
    for cfg in CFGS:
        c = dict(cfg); tag = c.pop("tag")
        try:
            r = run_one(tag, **c)
            slim = {k: r[k] for k in ("tag","factor_a","factor_b","total","mdd","trades","cost","switches","brakes","1m","3m","6m","1y","2y","3y","nbeat_m07","beat_all","mdd_better","win_all","switch_same_m07")}
            print(json.dumps(slim, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (tag, e), flush=True)
            import traceback; traceback.print_exc()
    open(ROOT/"results"/"r30_bt"/"sweep_beat_m07_k6.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
    print("saved %d rows; skipped non-native factors: %s" % (len(rows), ",".join(SKIPPED)), flush=True)
