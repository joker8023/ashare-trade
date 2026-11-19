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
def run_variant(tag, cfgC, ns_args, ns_kw, rs, ef, bx_note=""):
    inpA = mk_max((0.02, 0.30), -0.15, 0.80, 40)
    inpB = mk_max((0.05, 0.30), -1.0, 0.80, 20)
    inpC = mk_max((0.05, 0.30), -1.0, 0.80, 20)
    sha = shadow(inpA, CFG_A, 0.25, tag + "_A")[0]
    shb = shadow(inpB, CFG_B, 0.25, tag + "_B")[0]
    shc = shadow(inpC, cfgC, 0.25, tag + "_C")[0]
    nsp = build_ns3(*ns_args, **ns_kw)
    KW = dict(n=CFG_A["n"], rebal=CFG_A["rebal"], take=CFG_A["take"], exposure=CFG_A["exposure"], phase=0, inp_b=inpB, cfg_b=CFG_B, inp_c=inpC, cfg_c=cfgC, shadow_a=sha, shadow_b=shb, shadow_c=shc, rs_lookback=rs, exclude_a=MB, exclude_b=MB, exclude_c=MB, evalfreq=ef, brake_daily=False, **{k: v for k, v in CA0.items() if k != "exclude"})
    res = nsp["run_strategy_switch"](inpA, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "total": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2), "mdd": round(float(_mdd(eq)) * 100, 2), "trades": int(len(res.trades)), "cost": round(float(res.meta["total_cost"]), 0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "switch_log": [list(x) for x in res.meta["switch_log"]], "brakes": len(res.meta.get("brake_log", [])), "rs": rs, "ef": ef, "cfgC": cfgC, "ns": str(ns_args) + str(ns_kw) + bx_note}
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
C03 = dict(n=4, rebal=30, take=0.8, exposure=0.3)
C02 = dict(n=4, rebal=30, take=0.8, exposure=0.2)
C025 = dict(n=4, rebal=30, take=0.8, exposure=0.25)
C035 = dict(n=4, rebal=30, take=0.8, exposure=0.35)
PLAN = [
    ("G0_base", C03, (0.18, 0.08, 0.5, 0.0, 0, 1), {}, 60, "grid"),
    ("D1_daily", C03, (0.18, 0.08, 0.5, 0.0, 0, 1), {}, 60, "daily"),
    ("D2_d_h002", C03, (0.18, 0.08, 0.5, 0.02, 0, 1), {}, 60, "daily"),
    ("D3_d_asymA", C03, (0.18, 0.08, 0.5, 0.02, 0, 1), {"hyst_a": 0.005, "hyst_b": 0.005, "hyst_c": 0.08}, 60, "daily"),
    ("D4_d_asymB", C03, (0.18, 0.08, 0.5, 0.02, 0, 1), {"hyst_a": 0.01, "hyst_b": 0.01, "hyst_c": 0.05}, 60, "daily"),
    ("D5_d_asymC", C03, (0.18, 0.08, 0.5, 0.02, 0, 1), {"hyst_a": 0.03, "hyst_b": 0.01, "hyst_c": 0.08}, 60, "daily"),
    ("D6_d_h002_cf2", C03, (0.18, 0.08, 0.5, 0.02, 0, 2), {}, 60, "daily"),
    ("D7_d_h002_mh1", C03, (0.18, 0.08, 0.5, 0.02, 1, 1), {}, 60, "daily"),
    ("D8_d_asym_cf2", C03, (0.18, 0.08, 0.5, 0.02, 0, 2), {"hyst_a": 0.005, "hyst_b": 0.005, "hyst_c": 0.08}, 60, "daily"),
    ("D9_d_h002_rs30", C03, (0.18, 0.08, 0.5, 0.02, 0, 1), {}, 30, "daily"),
    ("D10_d_h002_rs90", C03, (0.18, 0.08, 0.5, 0.02, 0, 1), {}, 90, "daily"),
    ("D11_d_asym_rs30", C03, (0.18, 0.08, 0.5, 0.02, 0, 1), {"hyst_a": 0.005, "hyst_b": 0.005, "hyst_c": 0.08}, 30, "daily"),
    ("D12_d_asym_rs90", C03, (0.18, 0.08, 0.5, 0.02, 0, 1), {"hyst_a": 0.005, "hyst_b": 0.005, "hyst_c": 0.08}, 90, "daily"),
    ("G1_g_asymA", C03, (0.18, 0.08, 0.5, 0.02, 0, 1), {"hyst_a": 0.005, "hyst_b": 0.005, "hyst_c": 0.08}, 60, "grid"),
    ("G2_g_h002", C03, (0.18, 0.08, 0.5, 0.02, 0, 1), {}, 60, "grid"),
    ("G3_g_asym_cf2", C03, (0.18, 0.08, 0.5, 0.02, 0, 2), {"hyst_a": 0.005, "hyst_b": 0.005, "hyst_c": 0.08}, 60, "grid"),
    ("E1_d_e02", C02, (0.18, 0.08, 0.5, 0.02, 0, 1), {}, 60, "daily"),
    ("E2_d_e025", C025, (0.18, 0.08, 0.5, 0.02, 0, 1), {}, 60, "daily"),
    ("E3_d_e035", C035, (0.18, 0.08, 0.5, 0.02, 0, 1), {}, 60, "daily"),
    ("E4_d_bf04", C03, (0.18, 0.08, 0.4, 0.02, 0, 1), {}, 60, "daily"),
    ("E5_d_bf06_bx010", C03, (0.10, 0.08, 0.6, 0.02, 0, 1), {}, 60, "daily"),
    ("E6_d_bx015", C03, (0.15, 0.08, 0.5, 0.02, 0, 1), {}, 60, "daily"),
]
OUTP = ROOT / "results" / "r30_bt" / "REG3_d1_sweep.json"
rows = []
if OUTP.exists():
    try:
        rows = json.loads(OUTP.read_text()).get("rows", [])
    except Exception as e:
        print("resume failed: " + str(e), flush=True)
have = set(r["tag"] for r in rows)
for tag, cfgC, ns_args, ns_kw, rs, ef in PLAN:
    if tag in have:
        print("SKIP " + tag, flush=True)
        continue
    print("RUN " + tag + " ef=" + ef + " rs=" + str(rs) + " ns=" + str(ns_args) + str(ns_kw), flush=True)
    out = run_variant(tag, cfgC, ns_args, ns_kw, rs, ef)
    rows.append(out)
    OUTP.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=1))
    print(tag + " total=" + str(out["total"]) + " mdd=" + str(out["mdd"]) + " nbeat=" + str(out["nbeat"]) + " mdd_win=" + str(out["mdd_win"]) + " win_all=" + str(out["win_all"]) + " sw=" + str(out["switches"]) + " 1m=" + str(out["1m"]) + " 3m=" + str(out["3m"]) + " 6m=" + str(out["6m"]) + " 1y=" + str(out["1y"]) + " 2y=" + str(out["2y"]) + " 3y=" + str(out["3y"]), flush=True)
print("DONE rows=" + str(len(rows)), flush=True)
