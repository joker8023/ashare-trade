#!/usr/bin/env python3
"""Route-B stage2b: R15-leg (2024-strong) + R30-leg (2026-strong) RS-switch + brake grid.
Base: B_N5_R15. No lookahead: picks t-only, exec t+1 close. rs2 realshares."""
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
LEGS = {
 "A1_N5R15_TP045": dict(n=5, rebal=15, take=0.45, exposure=1.0),
 "A2_N5R15_TP06": dict(n=5, rebal=15, take=0.6, exposure=1.0),
 "A3_N4R15_TP08": dict(n=4, rebal=15, take=0.8, exposure=1.0),
 "A4_N6R15_TP08": dict(n=6, rebal=15, take=0.8, exposure=1.0),
 "B1_N4R30_TP06": dict(n=4, rebal=30, take=0.6, exposure=1.0),
 "B2_N4R30_TP12": dict(n=4, rebal=30, take=1.2, exposure=1.0),
 "B3_N6R30_TP08": dict(n=6, rebal=30, take=0.8, exposure=1.0),
}
PAIRS = [("A1_N5R15_TP045","B1_N4R30_TP06"),("A2_N5R15_TP06","B1_N4R30_TP06"),("A3_N4R15_TP08","B1_N4R30_TP06"),("A1_N5R15_TP045","B2_N4R30_TP12"),("A2_N5R15_TP06","B3_N6R30_TP08"),("A4_N6R15_TP08","B1_N4R30_TP06"),("A1_N5R15_TP045","B3_N6R30_TP08")]
BRAKES = [None,(0.18,0.08,0.7),(0.15,0.05,0.7),(0.18,0.05,0.7),(0.20,0.05,0.7),(0.15,0.08,0.7),(0.18,0.08,0.5)]
RSS = [30,60,90]
BEXPS = [1.0,0.9]
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
    inp = MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=20)
    t0 = time.time()
    shadows = {}
    for tag, cfg in LEGS.items():
        res = pc.run_strategy(inp, phase=0, **{**BASE, **cfg})
        eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
        shadows[tag] = (eq.dropna(), res)
        print("shadow %s total=%.1f" % (tag, float(eq.iloc[-1]/eq.iloc[0]-1)*100), flush=True)
    ns_cache = {}
    def get_ns(b):
        if b is None:
            return None
        if b not in ns_cache:
            ns_cache[b] = build_ns(b[0], b[1], b[2])
        return ns_cache[b]
    rows = []
    def emit(tag, res, extra):
        eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
        eq = eq.dropna()
        row = dict(tag=tag, total=round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), mdd=round(_mdd(eq)*100,2), trades_n=len(res.trades), cost=round(float(res.meta["total_cost"]),0), eq0=round(float(eq.iloc[0]),0))
        row.update(annual(eq))
        row.update(conc(res.trades, float(eq.iloc[0])))
        row.update(extra)
        try:
            row["mode"] = res.meta.get("final_mode"); row["switches"] = len(res.meta.get("switch_log",[])); row["brake_n"] = len(res.meta.get("brake_log",[]))
        except Exception:
            pass
        row["pass"] = check(row)
        rows.append(row)
        if row["pass"] or (row.get("2024_yoy") and row["2024_yoy"]>60 and row.get("2026_yoy") and row["2026_yoy"]>60):
            print(json.dumps(row, ensure_ascii=False), flush=True)
        return row
    n_est = len(PAIRS)*len(RSS)*len(BRAKES)*len(BEXPS) + len(LEGS)*len(BRAKES)*2
    print("n_est", n_est, flush=True)
    cnt = 0
    for la, lb in PAIRS:
        ca, cb = LEGS[la], LEGS[lb]
        for rs in RSS:
            for b in BRAKES:
                for bexp in BEXPS:
                    cb2 = dict(cb); cb2["exposure"] = bexp
                    KW = dict(n=ca["n"], rebal=ca["rebal"], take=ca["take"], exposure=ca["exposure"], phase=0, inp_b=inp, cfg_b=dict(n=cb2["n"], rebal=cb2["rebal"], take=cb2["take"], exposure=cb2["exposure"]), shadow_a=shadows[la][0], shadow_b=shadows[lb][0], rs_lookback=rs, exclude_a=MB, exclude_b=MB, **{k:v for k,v in BASE.items() if k!="exclude"})
                    KW_nb = dict(KW); KW_nb.pop('exclude_a'); KW_nb.pop('exclude_b'); KW_nb['exclude'] = MB
                    ns = get_ns(b)
                    btag = "nobrk" if b is None else ("bx%.2f_by%.2f_bf%.1f" % b)
                    tag = "B2b_%s_x_%s_rs%d_%s_Bexp%s" % (la, lb, rs, btag, bexp)
                    try:
                        if ns is None:
                            import switch_engine as se
                            res = se.run_strategy_switch(inp, lock_mode=None, **KW_nb)
                        else:
                            res = ns["run_strategy_switch"](inp, lock_mode=None, **KW)
                        emit(tag, res, dict(stage="2b-switch", leg_a=la, leg_b=lb, rs=rs, brake=btag, b_exp=bexp))
                    except Exception as e:
                        print("FAIL %s: %s" % (tag, e), flush=True)
                    cnt += 1
                    if cnt%40==0:
                        print("progress switch %d elapsed %.0fs" % (cnt, time.time()-t0), flush=True)
    for leg, cfg in LEGS.items():
        for b in BRAKES:
            ns = get_ns(b)
            btag = "nobrk" if b is None else ("bx%.2f_by%.2f_bf%.1f" % b)
            for lock in ["A"]:
                tag = "B2b_lock%s_%s_%s" % (lock, leg, btag)
                try:
                    KW = dict(n=cfg["n"], rebal=cfg["rebal"], take=cfg["take"], exposure=cfg["exposure"], phase=0, inp_b=None, cfg_b=dict(n=4, rebal=30, take=0.6, exposure=1.0), shadow_a=None, shadow_b=None, rs_lookback=60, exclude_a=MB, exclude_b=MB, **{k:v for k,v in BASE.items() if k!="exclude"})
                    KW_nb = dict(KW); KW_nb.pop('exclude_a'); KW_nb.pop('exclude_b'); KW_nb['exclude'] = MB
                    if ns is None:
                        import switch_engine as se
                        res = se.run_strategy_switch(inp, lock_mode=lock, **KW_nb)
                    else:
                        res = ns["run_strategy_switch"](inp, lock_mode=lock, **KW)
                    emit(tag, res, dict(stage="2b-lock", leg_a=leg, leg_b=None, rs=None, brake=btag, b_exp=None))
                except Exception as e:
                    print("FAIL %s: %s" % (tag, e), flush=True)
    rows.sort(key=lambda d: (min(d.get("2024_yoy") or -1e9, d.get("2026_yoy") or -1e9)), reverse=True)
    open(ROOT/"results"/"r30_bt"/"search_B_stage2.json","w").write(json.dumps(rows, ensure_ascii=False, indent=1))
    print("TOP20 by min(2024,2026):", flush=True)
    for d in rows[:20]:
        print(json.dumps({k:d.get(k) for k in ["tag","2024","2024_yoy","2025_yoy","2026_yoy","mdd","2024_mdd","2026_mdd","trades_n","cost","top3_share","ex_top3_ret","switches","brake_n","pass"]}, ensure_ascii=False), flush=True)
    print("saved %d rows elapsed %.0fs" % (len(rows), time.time()-t0), flush=True)
if __name__ == "__main__":
    main()
