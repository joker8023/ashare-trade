"""K6 deep: independent rerun (self-written stats) of top-3 new rows + xphase + slip04 + extop3."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/"research")); sys.path.insert(0, str(ROOT/"team"/"audit"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import RUN_START, EVAL_END, MB
import sweep_beat_m07_k6 as K6

W = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}
M07 = json.load(open(ROOT/"results"/"r30_bt"/"M07_final.json"))
GPH = {r["tag"]: r for r in json.load(open(ROOT/"team"/"audit"/"batch_017"/"part_gph.json"))}

def _mdd(s):
    s = pd.Series(s).dropna()
    return float((s / s.cummax() - 1).min())

def stats(eq):
    eq = eq.dropna()
    o = {"total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), "mdd": round(_mdd(eq)*100,2)}
    for w, d in W.items():
        sub = eq.tail(d+1)
        o[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
    return o

piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
_ns = K6.build_ns_ab(0.18, 0.08, 0.6)
_cache = {}
def run_cfg(fa="amihud_60", fb="amihud_60", ca=0.80, wa=40, cb=0.80, wb=20, phase=0, slip=0.002):
    key = (fa, fb, ca, wa, cb, wb, phase, slip)
    if key in _cache:
        return _cache[key]
    ia = MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=ca, max_win=wa)
    ib = MaxInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=cb, max_win=wb)
    base = dict(stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100,
                 cost_one_way=None, slip=slip, run_start=RUN_START, eval_start=first_sig,
                 eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    ra = pc.run_strategy(ia, n=5, rebal=20, take=1.2, exposure=1.0, phase=phase, **dict(base, factor=fa))
    rb = pc.run_strategy(ib, phase=phase, **dict(base, factor=fb, n=4, rebal=30, take=0.80, exposure=0.9))
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=phase, inp_b=ib,
               cfg_b=dict(n=4, rebal=30, take=0.80, exposure=0.9),
               shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=60, exclude_a=MB, exclude_b=MB,
               factor="amihud_60", factor_a=fa, factor_b=fb, **base)
    res = _ns["run_strategy_switch"](ia, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq, pd.DataFrame) else res.eq
    _cache[key] = (res, eq.dropna())
    return _cache[key]

CFGS = {"cut75_both": dict(fa="amihud_60", fb="amihud_60", ca=0.75, cb=0.75),
        "Aleg_amihud": dict(fa="amihud", fb="amihud_60"),
        "asym_A82B78": dict(ca=0.82, cb=0.78)}
FILE = {r["tag"]: r for r in json.load(open(ROOT/"results"/"r30_bt"/"sweep_beat_m07_k6.json"))}
out = {"repro": {}, "xphase": {}, "slip04": {}, "extop3": {}}
for tag, kw in CFGS.items():
    res, eq = run_cfg(**kw)
    s = stats(eq)
    f = FILE[tag]
    dev = {k: round(s[k]-f[k],2) for k in ["total","mdd"]+list(W)}
    out["repro"][tag] = {"self": s, "file": {k: f[k] for k in ["total","mdd"]+list(W)},
        "dev": dev, "maxdev": max(abs(v) for v in dev.values()),
        "trades": (len(res.trades), f["trades"]), "cost": (round(float(res.meta["total_cost"]),0), f["cost"]),
        "mode": (res.meta["final_mode"], f["mode"]),
        "switch_same": (list(map(list,res.meta["switch_log"])) == K6.M07_SWITCH, f["switch_same_m07"]),
        "brake_empty": (len(res.meta.get("brake_log",[]))==0, f["brakes"]==0)}
    # ex-top3 (self-written from trades)
    try:
        tr = res.trades
        pnl = tr["net_pnl"] if hasattr(tr,"__getitem__") and "net_pnl" in getattr(tr,"columns",[]) else pd.Series([t["net_pnl"] for t in tr])
        pnl = pd.Series(pnl).dropna()
        top3 = float(pnl.nlargest(3).sum()); tot_pnl = float(pnl.sum())
        eq0 = float(eq.iloc[0])
        out["extop3"][tag] = {"top3_share": round(top3/tot_pnl*100,1) if tot_pnl else None,
            "extop3_total": round((tot_pnl-top3)/eq0*100,2)}
    except Exception as e:
        out["extop3"][tag] = {"err": str(e)[:120]}
    # cross-phase
    for ph in (5, 15):
        _, eqp = run_cfg(phase=ph, **kw)
        sp = stats(eqp)
        m = GPH["m07_ph%d" % ph]
        out["xphase"]["%s_ph%d" % (tag, ph)] = {
            "self_total": sp["total"], "m07_total": m["total"], "gap": round(sp["total"]-m["total"],2),
            "self_mdd": sp["mdd"], "m07_mdd": m["mdd"],
            "nbeat": sum(1 for w in W if sp[w] > m[w]),
            "d": [round(sp[w]-m[w],2) for w in W]}
# slip doubling on strongest row
res4, eq4 = run_cfg(slip=0.004, **CFGS["cut75_both"])
s4 = stats(eq4)
m4 = GPH["m07_slip04_ph0"]
out["slip04"]["cut75_both"] = {"self": s4, "cost": round(float(res4.meta["total_cost"]),0),
    "m07_total": m4["total"], "m07_mdd": m4["mdd"],
    "m07_w": [m4[w] for w in W],
    "nbeat_sameslip": sum(1 for w in W if s4[w] > m4[w]),
    "d_sameslip": [round(s4[w]-m4[w],2) for w in W]}
open(Path(__file__).parent/"part_k6deep.json","w").write(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps({"repro_maxdev": {k: v["maxdev"] for k,v in out["repro"].items()},
  "xphase": {k: (v["gap"], v["nbeat"]) for k,v in out["xphase"].items()},
  "slip04": {k: (v["self"]["total"], v["nbeat_sameslip"], v["d_sameslip"]) for k,v in out["slip04"].items()},
  "extop3": out["extop3"]}, ensure_ascii=False, indent=1))
