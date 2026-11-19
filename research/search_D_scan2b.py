"""Route-D scan2b: fine grid for mdd headroom (single-leg, realshares_v2)."""
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
    r = dict(tag=tag, sel=sel, band=list(band), gate=gate, R=R, n=n, take=take,
             stop=stop, max_win=max_win, max_cut=max_cut, exposure=exposure,
             total=round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
             mdd=round(_mdd(eq) * 100, 2), trades=len(res.trades),
             cost=round(float(res.meta["total_cost"]), 0),
             y2024_slice=an[2024]["slice"], y2024_yoy=an[2024]["yoy"], y2024_mdd=an[2024]["mdd"],
             y2025_yoy=an[2025]["yoy"], y2025_mdd=an[2025]["mdd"],
             y2026_yoy=an[2026]["yoy"], y2026_mdd=an[2026]["mdd"],
             y2023_yoy=an[2023]["yoy"])
    r["pass_all"] = bool(r["y2024_slice"] > 60 and r["y2024_yoy"] > 60 and r["y2025_yoy"] > 60
                         and r["y2026_yoy"] > 60 and r["mdd"] > -30 and r["y2024_mdd"] > -30
                         and r["y2025_mdd"] > -30 and r["y2026_mdd"] > -30)
    return r

piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))

B = (0.05, 0.30)
CFGS = []
for R in (25, 28, 32, 35):
    for take in (0.9, 1.0):
        for exp in (0.85, 0.9):
            CFGS.append(dict(tag="e_a5_R%d_t%s_e%s" % (R, str(take).replace(".", ""), str(exp).replace(".", "")),
                             sel="amihud_5", band=B, gate=-1.0, R=R, take=take, exposure=exp))
for R in (25, 30):
    for exp in (0.85, 0.9):
        CFGS.append(dict(tag="e_a5_R%d_t10_s30_e%s" % (R, str(exp).replace(".", "")),
                         sel="amihud_5", band=B, gate=-1.0, R=R, take=1.0, stop=0.30, exposure=exp))
for R in (28, 30, 32):
    for take in (0.9, 1.0):
        for exp in (0.85, 0.9):
            CFGS.append(dict(tag="e_a20_R%d_t%s_e%s" % (R, str(take).replace(".", ""), str(exp).replace(".", "")),
                             sel="amihud", band=B, gate=-1.0, R=R, take=take, exposure=exp))
for R in (28, 30):
    for take in (0.9, 1.0, 1.1):
        CFGS.append(dict(tag="e_c5_R%d_t%s" % (R, str(take).replace(".", "")),
                         sel="c_a60_a5", band=B, gate=-1.0, R=R, take=take, exposure=0.9))
for gate in (-0.15, -0.25):
    CFGS.append(dict(tag="e_a5_R30_t10_g%s" % str(gate).replace(".", "").replace("-", "m"),
                     sel="amihud_5", band=B, gate=gate, R=30, take=1.0, exposure=0.9))

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
        open(ROOT / "results" / "r30_bt" / "search_D_scan2b.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
        print("saved %d rows" % len(rows), flush=True)
