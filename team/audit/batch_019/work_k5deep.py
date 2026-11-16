import sys, json
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
import sweep_beat_m07_k5 as K

M07_SWITCH = [["2023-06-21", "B"], ["2024-08-15", "A"], ["2026-09-08", "B"]]
M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05, "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
WINS = ["1m", "3m", "6m", "1y", "2y", "3y"]

piv = K.piv
dates = K.dates
first_sig = K.first_sig
_extra_cache = {}

def get_custom(p, phase, slip):
    key = (tuple(sorted((k, v) for k, v in p.items() if k != "lock_mode")), phase, slip)
    if key in _extra_cache:
        return _extra_cache[key]
    inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=p["cut_a"], max_win=p["win_a"])
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=p["cut_b"], max_win=p["win_b"])
    CA = dict(factor="amihud_60", stop=p["stop"], stop_exec="next", exclude=MB, capital=50000.0,
              lot=100, cost_one_way=None, slip=slip, run_start=RUN_START,
              eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=p["b_n"], rebal=p["b_rebal"], take=p["b_take"], exposure=p["b_exp"])
    ra = pc.run_strategy(inp_a, n=p["a_n"], rebal=p["a_rebal"], take=p["a_take"],
                         exposure=p["a_exp"], phase=phase, **CA)
    rb = pc.run_strategy(inp_b, phase=phase, **{**CA, **CFG_B})
    _extra_cache[key] = (inp_a, inp_b, ra, rb, CA, CFG_B)
    return _extra_cache[key]

def my_run(tag, p, phase=0, slip=0.002, lock_mode=None):
    if phase == 0 and abs(slip - 0.002) < 1e-12:
        inp_a, inp_b, ra, rb, CA, CFG_B = K.get_shadows(p)
    else:
        inp_a, inp_b, ra, rb, CA, CFG_B = get_custom(p, phase, slip)
    KW = dict(n=p["a_n"], rebal=p["a_rebal"], take=p["a_take"], exposure=p["a_exp"], phase=phase,
              inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=p["rs"],
              exclude_a=MB, exclude_b=MB, **{k: v for k, v in CA.items() if k != "exclude"})
    ns = K.get_ns(p["bx"], p["by_"], p["bf"])
    res = ns["run_strategy_switch"](inp_a, lock_mode=lock_mode, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag}
    out["total"] = round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2)
    out["mdd"] = round(_mdd(eq) * 100, 2)
    for w, d in WINDOWS.items():
        sub = eq.tail(d + 1)
        out[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
    out["trades"] = len(res.trades)
    out["cost"] = round(float(res.meta["total_cost"]), 0)
    out["mode"] = res.meta["final_mode"]
    out["switches"] = len(res.meta["switch_log"])
    out["brakes"] = len(res.meta.get("brake_log", [])) // 2
    out["switch_log"] = [list(x) for x in res.meta["switch_log"]]
    out["brake_log"] = [list(x) for x in res.meta.get("brake_log", [])]
    return out, res

def top3_stats(res):
    tr = res.trades
    try:
        if isinstance(tr, pd.DataFrame) and "net_pnl" in tr.columns:
            pnl = tr["net_pnl"].astype(float)
            top3 = float(pnl.nlargest(3).sum())
            tot = float(pnl.sum())
        elif isinstance(tr, list) and tr and isinstance(tr[0], dict):
            pnls = sorted([float(t.get("net_pnl", t.get("pnl", 0))) for t in tr], reverse=True)
            top3 = float(sum(pnls[:3]))
            tot = float(sum(pnls))
        else:
            return {"note": "unknown trades schema: " + str(type(tr))}
        share = round(top3 / tot * 100, 1) if tot else None
        return {"top3_pnl": round(top3, 1), "pnl_sum": round(tot, 1), "top3_share": share}
    except Exception as e:
        return {"note": "ex-top3 failed: " + str(e)}

file_rows = {r["tag"]: r for r in json.load(open("results/r30_bt/sweep_beat_m07_k5.json"))}
FIELDS = ["total", "mdd", "trades", "cost", "mode", "switches", "brakes"] + WINS
result = {}

for tag, p in [("nobrake_M07", K.M07P and dict(K.M07P, bx=10.0)), ("nobrake_gbf07", dict(K.G_BF07, bx=10.0))]:
    out, res = my_run(tag, p)
    f = file_rows[tag]
    dev = {k: (round(out[k] - f[k], 2) if isinstance(out[k], (int, float)) else (out[k] == f[k])) for k in FIELDS}
    maxdev = max([abs(v) for v in dev.values() if isinstance(v, (int, float))] + [0])
    result[tag + "_repro"] = {"out": {k: out[k] for k in FIELDS}, "maxdev": maxdev, "dev": dev}
    result[tag + "_brake_empty"] = (out["brake_log"] == [])
    result[tag + "_switch_same"] = (out["switch_log"] == M07_SWITCH)
    result[tag + "_exTop3"] = top3_stats(res)
    nd = sum(1 for w in WINS if out[w] > M07[w])
    result[tag + "_nbeat"] = {"nbeat": nd, "diff": {w: round(out[w] - M07[w], 2) for w in WINS},
                              "total_gap": round(out["total"] - M07["total"], 2),
                              "mdd_gap": round(out["mdd"] - M07["mdd"], 2)}
    print(tag, "maxdev=", maxdev, "brake_empty=", result[tag + "_brake_empty"], "switch_same=", result[tag + "_switch_same"], flush=True)
    print("  nbeat=", nd, result[tag + "_nbeat"]["diff"], "total_gap=", result[tag + "_nbeat"]["total_gap"], "mdd_gap=", result[tag + "_nbeat"]["mdd_gap"], flush=True)
    print("  exTop3=", result[tag + "_exTop3"], flush=True)

for ph in [5, 15]:
    out, res = my_run("nobrake_gbf07_ph%d" % ph, dict(K.G_BF07, bx=10.0), phase=ph)
    result["nobrake_gbf07_ph%d" % ph] = {k: out[k] for k in ["total", "mdd", "trades", "cost", "mode", "switches"] + WINS}
    print("nobrake_gbf07_ph%d" % ph, "total=", out["total"], "mdd=", out["mdd"], "six=", {w: out[w] for w in WINS}, flush=True)

out, res = my_run("nobrake_gbf07_slip04", dict(K.G_BF07, bx=10.0), slip=0.004)
result["nobrake_gbf07_slip04"] = {k: out[k] for k in ["total", "mdd", "trades", "cost", "mode", "switches"] + WINS}
print("nobrake_gbf07_slip04 total=", out["total"], "mdd=", out["mdd"], "cost=", out["cost"], "six=", {w: out[w] for w in WINS}, flush=True)

json.dump(result, open("team/audit/batch_019/part_k5deep.json", "w"), ensure_ascii=False, indent=1)
print("saved team/audit/batch_019/part_k5deep.json", flush=True)
