import sys, json, gc
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "team" / "audit")); sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, WINDOWS, RUN_START, EVAL_END, MB
from switch_ns3 import build_ns3
print("RUN_START", RUN_START, "EVAL_END", EVAL_END, flush=True)
piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
CA0 = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
CFG_A = dict(n=5, rebal=20, take=1.2, exposure=1.0)
CFG_B = dict(n=4, rebal=30, take=0.8, exposure=0.9)
CFG_C = dict(n=4, rebal=30, take=0.8, exposure=0.3)
def mk_max(band, gate, cut, win):
    return MaxInputs(piv, band=band, gate60=gate, max_cut=cut, max_win=win)
_sh = {}
def shadow(inp, cfg, stop, tag):
    key = (tag, tuple(sorted(cfg.items())), stop)
    if key not in _sh:
        CA = dict(CA0); CA["stop"] = stop
        r = pc.run_strategy(inp, phase=0, **{**CA, **cfg})
        eq = r.eq.iloc[:, 0] if isinstance(r.eq, pd.DataFrame) else r.eq
        _sh[key] = (eq, len(r.trades))
        print("  shadow " + tag + " trades=" + str(len(r.trades)), flush=True)
        del r; gc.collect()
    return _sh[key]
COMBO = {"1m": -2.38, "3m": 17.84, "6m": 39.86, "1y": 165.34, "2y": 1335.20, "3y": 1528.63, "mdd": -22.61}
def run_variant(tag, cfgC, ns_args, ns_kw, rs, ef, cfgB=None):
    cfgB = cfgB or CFG_B
    inpA = mk_max((0.02, 0.30), -0.15, 0.80, 40)
    inpB = mk_max((0.05, 0.30), -1.0, 0.80, 20)
    inpC = mk_max((0.05, 0.30), -1.0, 0.80, 20)
    sha = shadow(inpA, CFG_A, 0.25, tag + "_A")[0]
    shb = shadow(inpB, cfgB, 0.25, tag + "_B")[0]
    shc = shadow(inpC, cfgC, 0.25, tag + "_C")[0]
    nsp = build_ns3(*ns_args, **ns_kw)
    KW = dict(n=CFG_A["n"], rebal=CFG_A["rebal"], take=CFG_A["take"], exposure=CFG_A["exposure"], phase=0, inp_b=inpB, cfg_b=cfgB, inp_c=inpC, cfg_c=cfgC, shadow_a=sha, shadow_b=shb, shadow_c=shc, rs_lookback=rs, exclude_a=MB, exclude_b=MB, exclude_c=MB, evalfreq=ef, brake_daily=False, **{k: v for k, v in CA0.items() if k != "exclude"})
    res = nsp["run_strategy_switch"](inpA, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "total": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2), "mdd": round(float(_mdd(eq)) * 100, 2), "trades": int(len(res.trades)), "cost": round(float(res.meta["total_cost"]), 0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "switch_log": [list(x) for x in res.meta["switch_log"]], "brakes": len(res.meta.get("brake_log", [])), "rs": rs, "ef": ef, "cfgC": cfgC, "cfgB": cfgB, "ns": str(ns_args) + str(ns_kw)}
    for w, d in WINDOWS.items():
        sub = eq.tail(d + 1)
        out[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
        out[w + "_mdd"] = round(float(_mdd(sub)) * 100, 2)
    out["nbeat"] = sum(1 for w in WINDOWS if out[w] > COMBO[w])
    out["mdd_win"] = bool(out["mdd"] > COMBO["mdd"])
    out["win_all"] = bool(all(out[w] > COMBO[w] for w in WINDOWS) and out["mdd"] > COMBO["mdd"])
    eq.to_pickle(ROOT / "results" / "r30_bt" / ("REG3_" + tag + "_equity.pkl"))
    del res; gc.collect()
    return out
PLAN = [
    ("R1_g_bx015", CFG_C, (0.15, 0.08, 0.5, 0.0, 0, 1), {}, 60, "grid", None),
    ("R2_g_bf04", CFG_C, (0.18, 0.08, 0.4, 0.0, 0, 1), {}, 60, "grid", None),
    ("R3_d_mh10", CFG_C, (0.18, 0.08, 0.5, 0.0, 10, 1), {}, 60, "daily", None),
]
OUTP = ROOT / "results" / "r30_bt" / "REG3_d2_sweep.json"
rows = []
if OUTP.exists():
    try:
        rows = json.loads(OUTP.read_text()).get("rows", [])
    except Exception as e:
        print("resume failed: " + str(e), flush=True)
have = set(r["tag"] for r in rows)
for tag, cfgC, ns_args, ns_kw, rs, ef, cfgB in PLAN:
    if tag in have:
        print("SKIP " + tag, flush=True)
        continue
    print("RUN " + tag, flush=True)
    out = run_variant(tag, cfgC, ns_args, ns_kw, rs, ef, cfgB)
    rows.append(out)
    OUTP.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=1))
    print(tag + " total=" + str(out["total"]) + " mdd=" + str(out["mdd"]) + " nbeat=" + str(out["nbeat"]) + " mdd_win=" + str(out["mdd_win"]) + " win_all=" + str(out["win_all"]) + " sw=" + str(out["switches"]) + " 1m=" + str(out["1m"]) + " 3m=" + str(out["3m"]) + " 6m=" + str(out["6m"]) + " 1y=" + str(out["1y"]) + " 2y=" + str(out["2y"]) + " 3y=" + str(out["3y"]), flush=True)
print("DONE rows=" + str(len(rows)), flush=True)
