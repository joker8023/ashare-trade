"""Route-D stage3: amihud_5 B-leg fine sweep in M07 switch family (realshares_v2).

A-leg fixed M07: MaxInputs band=(0.02,0.30) gate60=-0.15 cut=0.80 win=40,
  n=5 rebal=20 take=1.2 exp=1.0.
B-leg DInputs amihud_5: band=(0.05,0.30) gate60=-1.0 (gate off), MB both legs,
  stop=0.25 stop_exec=next, RS trailing-60 shadows, brake build_ns grid.
Caliber: RUN_START=2023-01-03, EVAL_END=2026-11-12, 50k, slip=0.002, lot=100,
  long-only, exp<=1, legacy_grid=False, full_liquidate=True.
Batch A: N{4,5,6} x R{15,20,30} x TP{0.45,0.6,0.8,1.0,1.2} @ cut=0.7/win=20,
  + MAX sensitivity cut{0.6,0.7,0.8} x win{10,20,40} on 2 anchors.
Batch B: brake variants on top-3 batch-A anchors.
Reports slice AND yoy per year + yearly mdd. No lookahead: all matrices
trailing, .loc[t] reads t-and-before, cross-sectional ranks computed per
signal day t only (see research/inputs_d27.py).
Usage: .venv/bin/python research/search_D_stage3.py [--only TAG]
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

def annuals(eq):
    out = {}
    prev_end = None
    for y in [2023, 2024, 2025, 2026]:
        sub = eq[eq.index.year == y]
        if len(sub) == 0:
            out[y] = dict(slice=None, yoy=None, mdd=None); continue
        sret = float(sub.iloc[-1] / sub.iloc[0] - 1) * 100
        out[y] = dict(slice=round(sret, 2),
                      yoy=round((float(sub.iloc[-1] / prev_end - 1) * 100 if prev_end is not None else sret), 2),
                      mdd=round(float((sub / sub.cummax() - 1).min()) * 100, 2))
        prev_end = float(sub.iloc[-1])
    return out

def run_switch(tag, b_n=4, b_rebal=30, b_take=0.80, b_cut=0.70, b_win=20,
               bx=0.18, by_=0.08, bf=0.6, rs=60, stop=0.25, lock=None):
    inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
    inp_b = DInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=b_cut, max_win=b_win, sel="amihud_5")
    CA = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=MB, capital=50000.0,
              lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
              eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=b_n, rebal=b_rebal, take=b_take, exposure=0.9)
    ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B,
              shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB,
              **{k: v for k, v in CA.items() if k != "exclude"})
    ns = build_ns(bx, by_, bf)
    res = ns["run_strategy_switch"](inp_a, lock_mode=lock, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    an = annuals(eq)
    r = dict(tag=tag, b_sel="amihud_5", b_n=b_n, b_rebal=b_rebal, b_take=b_take,
             b_cut=b_cut, b_win=b_win, bx=bx, by_=by_, bf=bf, rs=rs, stop=stop, lock=lock,
             total=round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
             mdd=round(_mdd(eq) * 100, 2), trades=len(res.trades),
             cost=round(float(res.meta["total_cost"]), 0), mode=res.meta["final_mode"],
             switches=len(res.meta["switch_log"]),
             switch_log=[list(x) for x in res.meta["switch_log"]],
             y2024_slice=an[2024]["slice"], y2024_yoy=an[2024]["yoy"], y2024_mdd=an[2024]["mdd"],
             y2025_yoy=an[2025]["yoy"], y2025_mdd=an[2025]["mdd"],
             y2026_yoy=an[2026]["yoy"], y2026_mdd=an[2026]["mdd"],
             y2023_yoy=an[2023]["yoy"])
    r["pass_all"] = bool(r["y2024_slice"] > 60 and r["y2024_yoy"] > 60 and r["y2025_yoy"] > 60
                         and r["y2026_yoy"] > 60 and r["mdd"] > -30 and r["y2024_mdd"] > -30
                         and r["y2025_mdd"] > -30 and r["y2026_mdd"] > -30)
    r["margin"] = round(min(r["y2024_yoy"] - 60, r["y2025_yoy"] - 60, r["y2026_yoy"] - 60,
                            r["mdd"] + 30, r["y2024_mdd"] + 30, r["y2025_mdd"] + 30,
                            r["y2026_mdd"] + 30), 2)
    return r

piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
print("RUN", RUN_START, EVAL_END, "first_sig", first_sig.date(), flush=True)

CFGS_A = []
for n in (4, 5, 6):
    for R in (15, 20, 30):
        for tp in (0.45, 0.6, 0.8, 1.0, 1.2):
            CFGS_A.append(dict(tag="s3_N%d_R%d_T%s" % (n, R, str(tp).replace(".", "")),
                               b_n=n, b_rebal=R, b_take=tp))
for (n, R, tp) in ((4, 15, 0.8), (4, 30, 1.0)):
    for cut in (0.6, 0.7, 0.8):
        for win in (10, 20, 40):
            if cut == 0.7 and win == 20:
                continue
            CFGS_A.append(dict(tag="s3_MAX_N%d_R%d_T%s_c%s_w%d" % (n, R, str(tp).replace(".", ""), str(cut).replace(".", ""), win),
                               b_n=n, b_rebal=R, b_take=tp, b_cut=cut, b_win=win))

BRAKES = [(0.15, 0.05, 0.7), (0.18, 0.08, 0.7), (0.12, 0.06, 0.5), (0.18, 0.08, 0.3)]

def top3(rows):
    ok = [r for r in rows if r.get("pass_all")]
    pool = ok if ok else rows
    return sorted(pool, key=lambda r: (r.get("margin", -999), r.get("total", 0)), reverse=True)[:3]

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--only", default=None); args = ap.parse_args()
    rows = []
    if args.only is None:
        for c in CFGS_A:
            try:
                r = run_switch(**c)
                print(json.dumps(r, ensure_ascii=False), flush=True)
                rows.append(r)
            except Exception as e:
                print("FAIL %s: %s" % (c["tag"], e), flush=True)
        anchors = top3(rows)
        print("ANCHORS: %s" % json.dumps([(a["tag"], a.get("margin")) for a in anchors], ensure_ascii=False), flush=True)
        for a in anchors:
            base = dict(b_n=a["b_n"], b_rebal=a["b_rebal"], b_take=a["b_take"],
                        b_cut=a["b_cut"], b_win=a["b_win"])
            for (bx, by_, bf) in BRAKES:
                tag = "%s_b%s%s%s" % (a["tag"], str(bx).replace(".", ""), str(by_).replace(".", ""), str(bf).replace(".", ""))
                try:
                    r = run_switch(tag, bx=bx, by_=by_, bf=bf, **base)
                    print(json.dumps(r, ensure_ascii=False), flush=True)
                    rows.append(r)
                except Exception as e:
                    print("FAIL %s: %s" % (tag, e), flush=True)
        # Batch C: lock_B (pure B-leg + brake) on single-leg winners from scan1/scan2
        for (lname, ln, lr, ltp) in (("a5R30T10", 4, 30, 1.0), ("a5R30T08", 4, 30, 0.8), ("a5R15T08", 4, 15, 0.8)):
            for (bx, by_, bf) in [(0.18, 0.08, 0.6)] + BRAKES:
                tag = "s3_lockB_%s_b%s%s%s" % (lname, str(bx).replace(".", ""), str(by_).replace(".", ""), str(bf).replace(".", ""))
                try:
                    r = run_switch(tag, b_n=ln, b_rebal=lr, b_take=ltp, b_cut=0.80, b_win=20,
                                   bx=bx, by_=by_, bf=bf, lock="B")
                    print(json.dumps(r, ensure_ascii=False), flush=True)
                    rows.append(r)
                except Exception as e:
                    print("FAIL %s: %s" % (tag, e), flush=True)
        open(ROOT / "results" / "r30_bt" / "search_D_stage3.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
        print("saved %d rows" % len(rows), flush=True)
    else:
        c = next(c for c in CFGS_A if c["tag"] == args.only)
        print(json.dumps(run_switch(**c), ensure_ascii=False), flush=True)
