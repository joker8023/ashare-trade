#!/usr/bin/env python3
"""Route-B stage2c: gate-0.25/band(0.02,0.25) base + C-route brake bx0.15/by0.1/bf0.5 neighborhood.
Single-leg via switch lock-A. Output results/r30_bt/search_B_stage2b.json."""
import sys, json, time
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, MB
RUN_START = "2023-01-03"
EVAL_END = pd.Timestamp("2026-11-12")
FIRST_SIG = pd.Timestamp("2023-02-09")
BASE = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=FIRST_SIG, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
GATE = -0.25
BAND = (0.02, 0.25)
CUT, WIN = 0.80, 20
BRAKES = [None] + [(bx,by,bf) for bx in [0.12,0.15,0.18] for by in [0.08,0.10,0.15] for bf in [0.5,0.7]]
def _mdd(s):
    s = s.dropna()
    return float((s/s.cummax()-1).min()) if len(s) else float("nan")
def annual(eq):
    out = {}
    prev_end = None
    for y in [2023,2024,2025,2026]:
        sub = eq[eq.index.year==y]
        if len(sub)==0:
            out[str(y)] = None; out[str(y)+"_mdd"] = None; out[str(y)+"_yoy"] = None; out[str(y)+"_bars"] = 0
            continue
        sret = float(sub.iloc[-1]/sub.iloc[0]-1)*100
        out[str(y)] = round(sret,2)
        out[str(y)+"_mdd"] = round(_mdd(sub)*100,2)
        out[str(y)+"_bars"] = int(len(sub))
        out[str(y)+"_yoy"] = round(float(sub.iloc[-1]/prev_end-1)*100,2) if prev_end is not None else round(sret,2)
        prev_end = float(sub.iloc[-1])
    return out
def conc(trades, eq0):
    if trades is None or len(trades)==0:
        return dict(top3_share=None, ex_top3_ret=None, n_trades=0, n_win=0, top3_codes="")
    tp = trades.sort_values("net_pnl", ascending=False)
    tot = float(trades["net_pnl"].sum())
    t3 = float(tp.head(3)["net_pnl"].sum())
    return dict(top3_share=round(t3/tot*100,2) if tot else None, ex_top3_ret=round((tot-t3)/eq0*100,2) if eq0 else None, n_trades=int(len(trades)), n_win=int((trades["net_pnl"]>0).sum()), top3_codes=",".join(tp.head(3)["code"].astype(str).tolist()))
def check(row):
    try:
        return bool(row["2024_yoy"]>60 and row["2024"]>60 and row["2025_yoy"]>60 and row["2026_yoy"]>60 and row["mdd"]>-30 and row["2024_mdd"]>-30 and row["2025_mdd"]>-30 and row["2026_mdd"]>-30 and row["2023_mdd"]>-30)
    except Exception:
        return False
def main():
    piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean_realshares_v2.pkl")
    inp = MaxInputs(piv, band=BAND, gate60=GATE, max_cut=CUT, max_win=WIN)
    ns_cache = {}
    def get_ns(b):
        if b is None:
            return None
        if b not in ns_cache:
            ns_cache[b] = build_ns(b[0], b[1], b[2])
        return ns_cache[b]
    import switch_engine as se
    rows = []
    t0 = time.time()
    combos = [(n,r,tp,b) for n in [5,6] for r in [15,20] for tp in [0.45,0.6,0.8,1.2] for b in BRAKES]
    print("n_combos", len(combos), flush=True)
    for idx,(n,r,tp,b) in enumerate(combos):
        ns = get_ns(b)
        btag = "nobrk" if b is None else ("bx%.2f_by%.2f_bf%.1f" % b)
        tag = "B2c_N%d_R%d_TP%s_%s" % (n,r,tp,btag)
        try:
            KW = dict(n=n, rebal=r, take=tp, exposure=1.0, phase=0, inp_b=None, cfg_b=dict(n=4, rebal=30, take=0.6, exposure=1.0), shadow_a=None, shadow_b=None, rs_lookback=60, exclude_a=MB, exclude_b=MB, **{k:v for k,v in BASE.items() if k!="exclude"})
            if ns is None:
                KW2 = dict(KW); KW2.pop("exclude_a"); KW2.pop("exclude_b"); KW2["exclude"] = MB
                res = se.run_strategy_switch(inp, lock_mode="A", **KW2)
            else:
                res = ns["run_strategy_switch"](inp, lock_mode="A", **KW)
            eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
            eq = eq.dropna()
            row = dict(tag=tag, n=n, rebal=r, take=tp, brake=btag, total=round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), mdd=round(_mdd(eq)*100,2), trades_n=len(res.trades), cost=round(float(res.meta["total_cost"]),0), eq0=round(float(eq.iloc[0]),0))
            row.update(annual(eq))
            row.update(conc(res.trades, float(eq.iloc[0])))
            row["brake_n"] = len(res.meta.get("brake_log",[]))
            row["pass"] = check(row)
            rows.append(row)
            if row["pass"] or (row.get("2024_yoy") and row["2024_yoy"]>60):
                print(json.dumps(row, ensure_ascii=False), flush=True)
        except Exception as e:
            print("FAIL %s: %s" % (tag, e), flush=True)
        if (idx+1)%60==0:
            print("progress %d/%d elapsed %.0fs" % (idx+1, len(combos), time.time()-t0), flush=True)
    rows.sort(key=lambda d: (min(d.get("2024_yoy") or -1e9, d.get("2026_yoy") or -1e9, d.get("mdd") or -1e9)), reverse=True)
    open(ROOT/"results"/"r30_bt"/"search_B_stage2b.json","w").write(json.dumps(rows, ensure_ascii=False, indent=1))
    print("TOP20:", flush=True)
    for d in rows[:20]:
        print(json.dumps({k:d.get(k) for k in ["tag","2024","2024_yoy","2025_yoy","2026_yoy","mdd","2024_mdd","2026_mdd","trades_n","cost","top3_share","ex_top3_ret","brake_n","pass"]}, ensure_ascii=False), flush=True)
    print("saved %d rows" % len(rows), flush=True)
if __name__ == "__main__":
    main()
