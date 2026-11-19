#!/usr/bin/env python3
"""Route-B stage2: neighborhood + cut/win/gate/band around stage1 families (single-leg, rs2)."""
import sys, json, time
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
RUN_START = "2023-01-03"
EVAL_END = pd.Timestamp("2026-11-12")
MB = ("688","689","300","301","8","4")
FIRST_SIG = pd.Timestamp("2023-02-09")
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
def check(row):
    return bool(row["2024_yoy"] is not None and row["2024_yoy"]>60 and row["2024"]>60 and row["2025_yoy"]>60 and row["2026_yoy"]>60 and row["mdd"]>-30 and row["2024_mdd"]>-30 and row["2025_mdd"]>-30 and row["2026_mdd"]>-30 and row["2023_mdd"]>-30)
def main():
    piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean_realshares_v2.pkl")
    combos = []
    for n,r in [(5,15),(4,15),(6,15),(4,30),(6,30),(5,20),(4,20),(6,20),(5,10),(4,10),(5,12),(6,12)]:
        for take in [0.45,0.6,0.8,1.2]:
            for stop in [0.22,0.25,0.28,0.32,None]:
                combos.append(dict(n=n, rebal=r, take=take, stop=stop, cut=0.80, win=20, gate=-0.15, band=(0.02,0.30)))
    for n,r,take,stop in [(5,15,0.6,0.25),(4,15,0.8,0.25),(4,30,0.6,0.25),(6,15,0.8,0.25)]:
        for cut in [0.70,0.75,0.85]:
            for win in [15,30,40]:
                combos.append(dict(n=n, rebal=r, take=take, stop=stop, cut=cut, win=win, gate=-0.15, band=(0.02,0.30)))
    for n,r,take,stop in [(5,15,0.6,0.25),(4,30,0.6,0.25)]:
        for gate in [-0.10,-0.20,-0.25]:
            for band in [(0.05,0.30),(0.02,0.25)]:
                combos.append(dict(n=n, rebal=r, take=take, stop=stop, cut=0.80, win=20, gate=gate, band=band))
    print("n_combos", len(combos), flush=True)
    cache = {}
    def get_inp(cut, win, gate, band):
        k = (cut,win,gate,band)
        if k not in cache:
            cache[k] = MaxInputs(piv, band=band, gate60=gate, max_cut=cut, max_win=win)
        return cache[k]
    rows = []
    t0 = time.time()
    for idx,c in enumerate(combos):
        tag = "B2_N%d_R%d_TP%s_S%s_c%s_w%s_g%s_b%s-%s" % (c["n"],c["rebal"],c["take"],c["stop"],c["cut"],c["win"],c["gate"],c["band"][0],c["band"][1])
        try:
            inp = get_inp(c["cut"],c["win"],c["gate"],c["band"])
            res = pc.run_strategy(inp, factor="amihud_60", n=c["n"], rebal=c["rebal"], take=c["take"], stop=c["stop"], stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=FIRST_SIG, eval_end=EVAL_END, phase=0, legacy_grid=False, full_liquidate=True, exposure=1.0)
            eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
            eq = eq.dropna()
            row = dict(tag=tag, **{k:c[k] for k in ("n","rebal","take","stop","cut","win","gate")}, band=list(c["band"]), total=round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), mdd=round(_mdd(eq)*100,2), trades_n=len(res.trades), cost=round(float(res.meta["total_cost"]),0), eq0=round(float(eq.iloc[0]),0))
            row.update(annual(eq))
            row.update(conc(res.trades, float(eq.iloc[0])))
            row["pass"] = check(row)
            rows.append(row)
            if row["pass"] or (row["2024_yoy"] is not None and row["2024_yoy"]>60 and row["2025_yoy"]>60 and row["2026_yoy"]>60):
                print(json.dumps(row, ensure_ascii=False), flush=True)
        except Exception as e:
            print("FAIL %s: %s" % (tag, e), flush=True)
        if (idx+1)%60==0:
            print("progress %d/%d elapsed %.0fs" % (idx+1, len(combos), time.time()-t0), flush=True)
    rows.sort(key=lambda d: (d.get("2024_yoy") or -1e9), reverse=True)
    open(ROOT/"results"/"r30_bt"/"search_B_stage2.json","w").write(json.dumps(rows, ensure_ascii=False, indent=1))
    print("TOP20 by 2024_yoy:", flush=True)
    for d in rows[:20]:
        print(json.dumps({k:d.get(k) for k in ["tag","2024","2024_yoy","2025_yoy","2026_yoy","mdd","2024_mdd","2026_mdd","trades_n","cost","top3_share","ex_top3_ret"]}, ensure_ascii=False), flush=True)
    print("saved %d rows" % len(rows), flush=True)
if __name__ == "__main__":
    main()
