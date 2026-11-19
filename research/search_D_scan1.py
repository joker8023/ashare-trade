"""Route-D scan1: single-leg annual landscape on realshares_v2.
Caliber: RUN_START=2023-01-03, EVAL_END=2026-11-12, 50k, slip=0.002, lot=100,
long-only, exposure<=1, stop_exec=next, legacy_grid=False, full_liquidate=True.
Reports slice (last/first in year) AND yoy (year_end/prev_year_end-1) + yearly mdd.
Usage: .venv/bin/python research/search_D_scan1.py [--only TAG]
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from inputs_d27 import SELECTORS
from inputs_d27 import DInputs

RUN_START = "2023-01-03"
EVAL_END = pd.Timestamp("2026-11-12")
MB = ("688", "689", "300", "301", "8", "4")

def _mdd(s):
    return float((s / s.cummax() - 1).min())

def annuals(eq):
    out = {}
    prev_end = None
    for y in [2023, 2024, 2025, 2026]:
        sub = eq[eq.index.year == y]
        if len(sub) == 0:
            out[y] = dict(slice=None, yoy=None, mdd=None, n=0); continue
        sret = float(sub.iloc[-1] / sub.iloc[0] - 1) * 100
        out[y] = dict(slice=round(sret, 2),
                      yoy=round((float(sub.iloc[-1] / prev_end - 1) * 100 if prev_end is not None else sret), 2),
                      mdd=round(_mdd(sub) * 100, 2), n=int(len(sub)))
        prev_end = float(sub.iloc[-1])
    return out

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
                stop=stop, max_win=max_win, max_cut=max_cut,
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
print("RUN", RUN_START, EVAL_END, "first_sig", first_sig.date(), flush=True)

CFGS = []
B = (0.05, 0.30)
for sel in SELECTORS:
    for R in (7, 15, 30):
        CFGS.append(dict(tag="d1_%s_R%d" % (sel, R), sel=sel, band=B, gate=-1.0, R=R))

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
        open(ROOT / "results" / "r30_bt" / "search_D_scan1.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
        print("saved %d rows" % len(rows), flush=True)
