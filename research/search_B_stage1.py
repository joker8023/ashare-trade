#!/usr/bin/env python3
"""Route-B stage1: high-concentration short-horizon single-leg sweep (MaxInputs, rs2)."""
import sys, json, time, itertools
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
RUN_START = "2023-01-03"
EVAL_END = pd.Timestamp("2026-11-12")
MB = ("688","689","300","301","8","4")
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
    sh = round(t3/tot*100,2) if tot else None
    ex = round((tot-t3)/eq0*100,2) if eq0 else None
    return dict(top3_share=sh, ex_top3_ret=ex, n_trades=int(len(trades)), n_win=int((trades["net_pnl"]>0).sum()), top3_codes=",".join(tp.head(3)["code"].astype(str).tolist()))
def main():
    piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean_realshares_v2.pkl")
    dates = piv["close"].index
    grid30 = [dates[i] for i in range(300, len(dates), 30)]
    first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
    print("first_sig", first_sig, flush=True)
    combos = list(itertools.product([2,3,4,5,6],[7,15,20,30,60],[0.45,0.6,0.8,1.2,2.0,None],[0.15,0.25,0.35]))
    print("n_combos", len(combos), flush=True)
    inp = MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=20)
    rows = []
    t0 = time.time()
    for idx,(n,r,take,stop) in enumerate(combos):
        tag = "B_N%d_R%d_TP%s_S%s" % (n,r,take,stop)
        try:
            res = pc.run_strategy(inp, factor="amihud_60", n=n, rebal=r, take=take, stop=stop, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, phase=0, legacy_grid=False, full_liquidate=True, exposure=1.0)
            eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
            eq = eq.dropna()
            row = dict(tag=tag, n=n, rebal=r, take=take, stop=stop, total=round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), mdd=round(_mdd(eq)*100,2), trades_n=len(res.trades), cost=round(float(res.meta["total_cost"]),0), eq0=round(float(eq.iloc[0]),0))
            row.update(annual(eq))
            row.update(conc(res.trades, float(eq.iloc[0])))
            ok = (row["2024_yoy"] is not None and row["2024_yoy"]>60 and row["2024"]>60 and row["2025_yoy"]>60 and row["2026_yoy"]>60 and row["mdd"]>-30 and row["2024_mdd"]>-30 and row["2025_mdd"]>-30 and row["2026_mdd"]>-30 and row["2023_mdd"]>-30)
            row["pass"] = bool(ok)
            rows.append(row)
            if ok or (row["2024_yoy"] is not None and row["2024_yoy"]>50):
                print(json.dumps(row, ensure_ascii=False), flush=True)
        except Exception as e:
            print("FAIL %s: %s" % (tag, e), flush=True)
        if (idx+1)%60==0:
            print("progress %d/%d elapsed %.0fs" % (idx+1, len(combos), time.time()-t0), flush=True)
    rows.sort(key=lambda d: (d.get("2024_yoy") or -1e9), reverse=True)
    open(ROOT/"results"/"r30_bt"/"search_B_stage1.json","w").write(json.dumps(rows, ensure_ascii=False, indent=1))
    print("TOP15 by 2024_yoy:", flush=True)
    for d in rows[:15]:
        print(json.dumps({k:d.get(k) for k in ["tag","2024","2024_yoy","2025_yoy","2026_yoy","mdd","2024_mdd","trades_n","cost","top3_share","ex_top3_ret"]}, ensure_ascii=False), flush=True)
    print("saved %d rows" % len(rows), flush=True)
if __name__ == "__main__":
    main()
