"""Route-D scan3: switch-family with new-selector B-leg (realshares_v2, annual slice+yoy).
A-leg keeps M07 MaxInputs amihud_60; B-leg uses DInputs new selector.
Switch = M07 grid brake (build_ns), RS trailing-60 shadows, MB both legs.
Usage: .venv/bin/python research/search_D_scan3.py [--only TAG]
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import build_ns, _mdd, RUN_START, EVAL_END, MB
from search_D_scan1 import annuals

def run_switch(tag, b_sel, b_band=(0.05, 0.30), b_gate=-1.0, b_cut=0.80, b_win=20,
               b_n=4, b_rebal=30, b_take=0.80, b_exp=0.9,
               a_cut=0.80, a_win=40, a_rebal=20,
               bx=0.18, by_=0.08, bf=0.6, rs=60, stop=0.25):
    inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=a_cut, max_win=a_win)
    inp_b = DInputs(piv, band=b_band, gate60=b_gate, max_cut=b_cut, max_win=b_win, sel=b_sel)
    CA = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=MB, capital=50000.0,
              lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
              eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=b_n, rebal=b_rebal, take=b_take, exposure=b_exp)
    ra = pc.run_strategy(inp_a, n=5, rebal=a_rebal, take=1.2, exposure=1.0, phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
    KW = dict(n=5, rebal=a_rebal, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B,
              shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB,
              **{k: v for k, v in CA.items() if k != "exclude"})
    ns = build_ns(bx, by_, bf)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    an = annuals(eq)
    return dict(tag=tag, b_sel=b_sel, b_band=list(b_band), b_gate=b_gate, b_cut=b_cut,
                b_win=b_win, b_n=b_n, b_rebal=b_rebal, b_take=b_take, b_exp=b_exp,
                a_cut=a_cut, a_win=a_win, a_rebal=a_rebal, bx=bx, by_=by_, bf=bf, rs=rs,
                total=round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
                mdd=round(_mdd(eq) * 100, 2), trades=len(res.trades),
                cost=round(float(res.meta["total_cost"]), 0), mode=res.meta["final_mode"],
                switches=len(res.meta["switch_log"]),
                switch_log=[list(x) for x in res.meta["switch_log"]],
                y2024_slice=an[2024]["slice"], y2024_yoy=an[2024]["yoy"], y2024_mdd=an[2024]["mdd"],
                y2025_yoy=an[2025]["yoy"], y2025_mdd=an[2025]["mdd"],
                y2026_yoy=an[2026]["yoy"], y2026_mdd=an[2026]["mdd"],
                y2023_yoy=an[2023]["yoy"])

piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))

CFGS = []
# B-leg winners from scan1/scan2 x B-holding R x brake
for b_sel, extra in (("amihud_5", {}), ("amihud", {}), ("c_a60_a5", {})):
    for b_rebal in (15, 30):
        CFGS.append(dict(tag="d3_%s_bR%d" % (b_sel, b_rebal), b_sel=b_sel, b_rebal=b_rebal, **extra))
CFGS.append(dict(tag="d3_a5_bR20_bf07", b_sel="amihud_5", b_rebal=20, bf=0.7))
CFGS.append(dict(tag="d3_a5_bR30_bf07", b_sel="amihud_5", b_rebal=30, bf=0.7))
CFGS.append(dict(tag="d3_a5_bR30_rs90", b_sel="amihud_5", b_rebal=30, rs=90))

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--only", default=None); args = ap.parse_args()
    cfgs = [c for c in CFGS if args.only is None or c["tag"] == args.only]
    rows = []
    for c in cfgs:
        try:
            r = run_switch(**c)
            print(json.dumps(r, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (c["tag"], e), flush=True)
            import traceback; traceback.print_exc()
    if args.only is None:
        open(ROOT / "results" / "r30_bt" / "search_D_scan3.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
        print("saved %d rows" % len(rows), flush=True)
