"""Route-D scan2: refine around amihud/amihud_5 winners (single-leg, realshares_v2).
Same caliber + slice/yoy annual reporting as scan1.
Usage: .venv/bin/python research/search_D_scan2.py [--only TAG]
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from inputs_d27 import DInputs
from search_D_scan1 import annuals, RUN_START, EVAL_END, MB, _mdd

def run_one(tag, sel, band, gate, R, n=4, take=0.80, stop=0.25, max_win=20, max_cut=0.80, exposure=0.9):
    inp = DInputs(piv, band=band, gate60=gate, max_win=max_win, max_cut=max_cut, sel=sel)
    CA = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=MB, capital=50000.0,
              lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
              eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False,
              full_liquidate=True, exposure=exposure)
    res = pc.run_strategy(inp, n=n, rebal=R, take=take, phase=0, **CA)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    an = annuals(eq)
    return dict(tag=tag, sel=sel, band=list(band), gate=gate, R=R, n=n, take=take,
                stop=stop, max_win=max_win, max_cut=max_cut, exposure=exposure,
                total=round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
                mdd=round(_mdd(eq) * 100, 2), trades=len(res.trades),
                cost=round(float(res.meta["total_cost"]), 0),
                y2024_slice=an[2024]["slice"], y2024_yoy=an[2024]["yoy"], y2024_mdd=an[2024]["mdd"],
                y2025_yoy=an[2025]["yoy"], y2025_mdd=an[2025]["mdd"],
                y2026_yoy=an[2026]["yoy"], y2026_mdd=an[2026]["mdd"],
                y2023_yoy=an[2023]["yoy"])

piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))

CFGS = []
B = (0.05, 0.30)
# MAX grid for the two winner selectors x R
for sel in ("amihud_5", "amihud"):
    for R in (15, 20, 30):
        for cut in (0.70, 0.80, 0.90):
            for win in (10, 20, 40):
                if cut == 0.80 and win == 20:
                    continue
                CFGS.append(dict(tag="d2_%s_R%d_cut%s_win%d" % (sel, R, str(cut).replace(".", ""), win),
                                 sel=sel, band=B, gate=-1.0, R=R, max_cut=cut, max_win=win))
# stop/take/N/exposure refinements on amihud_5_R30 base
for stop in (0.20, 0.30, None):
    CFGS.append(dict(tag="d2_a5_R30_stop%s" % str(stop), sel="amihud_5", band=B, gate=-1.0, R=30, stop=stop))
for take in (0.60, 1.00, 1.20):
    CFGS.append(dict(tag="d2_a5_R30_take%s" % str(take).replace(".", ""), sel="amihud_5", band=B, gate=-1.0, R=30, take=take))
for n in (3, 5, 6):
    CFGS.append(dict(tag="d2_a5_R30_N%d" % n, sel="amihud_5", band=B, gate=-1.0, R=30, n=n))
CFGS.append(dict(tag="d2_a5_R30_exp100", sel="amihud_5", band=B, gate=-1.0, R=30, exposure=1.0))
# A-pool variants (band 2-30%, gate -0.15, take 1.2, exp 1.0) of winners
for sel in ("amihud_5", "amihud"):
    for R in (20, 30):
        CFGS.append(dict(tag="d2_%s_Apool_R%d" % (sel, R), sel="amihud_5" if False else sel,
                         band=(0.02, 0.30), gate=-0.15, R=R, take=1.20, exposure=1.0, n=5))

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--only", default=None); args = ap.parse_args()
    cfgs = [c for c in CFGS if args.only is None or c["tag"] == args.only]
    rows = []
    for c in cfgs:
        try:
            r = run_one(**c)
            print(json.dumps(r, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (c["tag"], e), flush=True)
    if args.only is None:
        open(ROOT / "results" / "r30_bt" / "search_D_scan2.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
        print("saved %d rows" % len(rows), flush=True)
