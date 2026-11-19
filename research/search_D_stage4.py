"""Route-D stage4: amihud_5_R15 base + C-road brake + switching (realshares_v2).

Base B-leg (from scan1/scan2 winner d1_amihud_5_R15 family):
  DInputs amihud_5, band=(0.05,0.30), gate60=-1.0, cut=0.80, win=20,
  b_n=4, b_rebal=15, exp=0.9, stop=0.25.
A-leg (switch mode): M07 MaxInputs band=(0.02,0.30) gate60=-0.15 cut=0.80 win=40,
  n=5 rebal=20 take=1.2 exp=1.0. RS trailing-60 shadows, MB both legs.
Caliber: RUN_START=2023-01-03, EVAL_END=2026-11-12, 50k, slip=0.002, lot=100,
  long-only, exp<=1, legacy_grid=False, full_liquidate=True.
Grid: brake C-road best (0.15,0.10,0.5) + neighbors, x lock {B, None(switch)},
  x TP {0.6,0.8,1.0,1.2}, x rs {60,90}, + N5 probe.
Goal: 2024_yoy>60% & slice>60%, 2025/2026_yoy>60% (2026 to 11-12), mdd>-30%.
No lookahead: trailing matrices only, per-signal-day cross-sectional ranks.
Usage: .venv/bin/python research/search_D_stage4.py [--only TAG]
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
from search_D_stage3 import run_switch

BRAKE_C = (0.15, 0.10, 0.5)
BRAKES = [(0.15, 0.10, 0.5), (0.12, 0.08, 0.5), (0.15, 0.10, 0.7),
          (0.12, 0.06, 0.5), (0.18, 0.08, 0.6)]

CFGS = []
for (bx, by_, bf) in BRAKES:
    CFGS.append(dict(tag="s4_lockB_T08_b%s%s%s" % (str(bx).replace(".", ""), str(by_).replace(".", ""), str(bf).replace(".", "")),
                     lock="B", b_take=0.8, bx=bx, by_=by_, bf=bf))
for tp in (0.6, 1.0, 1.2):
    CFGS.append(dict(tag="s4_lockB_T%s_bC" % str(tp).replace(".", ""),
                     lock="B", b_take=tp, bx=BRAKE_C[0], by_=BRAKE_C[1], bf=BRAKE_C[2]))
for (bx, by_, bf) in BRAKES:
    CFGS.append(dict(tag="s4_sw_T08_b%s%s%s" % (str(bx).replace(".", ""), str(by_).replace(".", ""), str(bf).replace(".", "")),
                     lock=None, b_take=0.8, bx=bx, by_=by_, bf=bf))
for tp in (0.6, 1.0):
    CFGS.append(dict(tag="s4_sw_T%s_bC" % str(tp).replace(".", ""),
                     lock=None, b_take=tp, bx=BRAKE_C[0], by_=BRAKE_C[1], bf=BRAKE_C[2]))
for lock in ("B", None):
    CFGS.append(dict(tag="s4_%s_T08_bC_rs90" % ("lockB" if lock else "sw"),
                     lock=lock, b_take=0.8, bx=BRAKE_C[0], by_=BRAKE_C[1], bf=BRAKE_C[2], rs=90))
for lock in ("B", None):
    CFGS.append(dict(tag="s4_%s_N5_T08_bC" % ("lockB" if lock else "sw"),
                     lock=lock, b_n=5, b_take=0.8, bx=BRAKE_C[0], by_=BRAKE_C[1], bf=BRAKE_C[2]))

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--only", default=None); args = ap.parse_args()
    base = dict(b_n=4, b_rebal=15, b_cut=0.80, b_win=20)
    rows = []
    cfgs = [c for c in CFGS if args.only is None or c["tag"] == args.only]
    for c in cfgs:
        try:
            kw = dict(base); kw.update(c)
            tag = kw.pop("tag")
            r = run_switch(tag, **kw)
            print(json.dumps(r, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (c["tag"], e), flush=True)
    if args.only is None:
        open(ROOT / "results" / "r30_bt" / "search_D_stage4.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
        print("saved %d rows" % len(rows), flush=True)
