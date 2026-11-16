"""g_bf07 full-precision single-config rerun (K13). Caliber verbatim from research/sweep_beat_m07_k3.py.
Config: g_bf07 = M07 + by05 + cut both legs 0.78 + bx0.15 + bf0.7 (K3 CFGS line: by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.7; all other run_one defaults = M07).
No round(): full float precision for six windows + total + mdd. No lookahead: same RUN_START/EVAL_END/WINDOWS/MB/grid/shadow path as K3.
Repro: .venv/bin/python research/gbf07_fullprec_k13.py
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "team" / "audit")); sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB

# verbatim K3 config row
GBF07_KW = dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.7)

piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))


def run_one_fullprec(tag, cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, stop=0.25, a_take=1.2, b_take=0.80, a_n=5, b_n=4, b_exp=0.9, rs=60, bx=0.18, by_=0.08, bf=0.6, gate_a=-0.15, band_a_lo=0.02):
    # verbatim K3 run_one body, minus round()
    inp_a = MaxInputs(piv, band=(band_a_lo, 0.30), gate60=gate_a, max_cut=cut_a, max_win=win_a)
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=cut_b, max_win=win_b)
    CA = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=b_n, rebal=30, take=b_take, exposure=b_exp)
    ra = pc.run_strategy(inp_a, n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
    KW = dict(n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB, **{k: v for k, v in CA.items() if k != "exclude"})
    ns = build_ns(bx, by_, bf)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "total": float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, "mdd": float(_mdd(eq)) * 100, "trades": len(res.trades), "cost": float(res.meta["total_cost"]), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "brakes": len(res.meta.get("brake_log", [])) // 2,
           "switch_log": [list(x) for x in res.meta["switch_log"]], "brake_log": [list(x) for x in res.meta.get("brake_log", [])]}
    for w, d in WINDOWS.items():
        sub = eq.tail(d + 1)
        out[w] = float(sub.iloc[-1] / sub.iloc[0] - 1) * 100
        out[w + "_mdd"] = float(_mdd(sub)) * 100
    return out


if __name__ == "__main__":
    r = run_one_fullprec("g_bf07", **GBF07_KW)
    k3row = None
    for row in json.load(open(ROOT / "results" / "r30_bt" / "sweep_beat_m07_k3.json")):
        if row.get("tag") == "g_bf07":
            k3row = row
            break
    drift = {}
    if k3row is not None:
        for k in ("total", "mdd", "1m", "3m", "6m", "1y", "2y", "3y"):
            drift[k] = abs(r[k] - k3row[k])
    doc = {
        "tag": "g_bf07",
        "kind": "single-config full-precision rerun (no round)",
        "config": {"tag": "g_bf07", **GBF07_KW, "note": "all other run_one defaults = M07 final (same as K3 CFGS row verbatim)"},
        "caliber": "verbatim research/sweep_beat_m07_k3.py run_one (same MaxInputs/prior_check/build_ns/WINDOWS/RUN_START/EVAL_END/MB/grid/first_sig path); only round() removed",
        "repro": ".venv/bin/python research/gbf07_fullprec_k13.py",
        "result_fullprec": r,
        "k3_rounded_row": k3row,
        "abs_drift_vs_k3rounded": drift,
        "drift_flag_gt_0_005": {k: (v > 0.005) for k, v in drift.items()},
    }
    open(ROOT / "results" / "r30_bt" / "gbf07_fullprec_k13.json", "w").write(json.dumps(doc, ensure_ascii=False, indent=1))
    print(json.dumps({k: r[k] for k in ("tag", "total", "mdd", "1m", "3m", "6m", "1y", "2y", "3y", "trades", "cost", "mode", "switches", "brakes")}, ensure_ascii=False, indent=1))
    print("drift_vs_k3rounded=" + json.dumps(drift, ensure_ascii=False))
    print("saved results/r30_bt/gbf07_fullprec_k13.json")
