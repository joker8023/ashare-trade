#!/usr/bin/env python3
"""batch_054 K22 independent recompute (reviewer agent-63).

Independent re-execution of the two 2y-window legs under review:
  leg M: base_M07  (grid eval, M07 seat; must reproduce M07_final + M07_equity.pkl)
  leg K: k21_daily_hyst003_gbf07 (daily+hyst0.03, gbf07 seat bx0.15/by0.05/bf0.7)
Built ONLY on research/sweep_beat_m07_k21.py primitives (already-audited
batch_052). Does NOT import research/attrib_k22.py (sibling R43 product).

Outputs (this dir only):
  eq_legM.pkl, eq_legK.pkl            full daily equity Series
  part_054_k22recompute.json          windows + monthly table + checks
"""
import sys, json, pickle
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import sweep_beat_m07_k21 as K21
from sweep_beat_h1_v4 import _mdd, WINDOWS

OUT = Path(__file__).resolve().parent
M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05,
       "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}

def run_leg(tag, **kw):
    print(f"START {tag}", flush=True)
    base_kw = dict(seat="M07", combo="", cut_a=0.80, win_a=40, cut_b=0.80,
                   win_b=20, stop=0.25, a_take=1.2, b_take=0.80, a_n=5, b_n=4,
                   b_exp=0.9, rs=60, bx=0.18, by_=0.08, bf=0.6,
                   evalfreq="grid", hyst=0.0)
    base_kw.update(kw)
    seat = base_kw.pop("seat"); combo = base_kw.pop("combo")
    tag_in = tag
    inp_a, inp_b, ra, rb, CA, CFG_B = K21.get_shadows(
        base_kw["cut_a"], base_kw["win_a"], base_kw["cut_b"], base_kw["win_b"],
        base_kw["stop"], base_kw["a_take"], base_kw["b_take"],
        base_kw["a_n"], base_kw["b_n"], base_kw["b_exp"])
    KW = dict(n=base_kw["a_n"], rebal=20, take=base_kw["a_take"],
              exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B,
              shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=base_kw["rs"],
              exclude_a=K21.MB if False else None, evalfreq=base_kw["evalfreq"],
              brake_daily=False,
              **{k: v for k, v in CA.items() if k != "exclude"})
    # NOTE: exclude_a/exclude_b mirror run_one: MB both legs
    from sweep_beat_h1_v4 import MB as _MB
    KW["exclude_a"] = _MB; KW["exclude_b"] = _MB
    ns = K21.get_ns(base_kw["bx"], base_kw["by_"], base_kw["bf"], base_kw["hyst"])
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    print(f"DONE {tag_in} n={len(eq)} total={eq.iloc[-1]/eq.iloc[0]-1:.4%}", flush=True)
    return eq, res

eqM, resM = run_leg("base_M07")
eqK, resK = run_leg("k21_daily_hyst003_gbf07", seat="gbf07",
    combo="phase2: k21_daily_hyst003_M07 x g_bf07 seat",
    cut_a=0.78, cut_b=0.78, bx=0.15, by_=0.05, bf=0.7,
    evalfreq="daily", hyst=0.03, rs=60)

def winstats(eq):
    o = {"total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100, 2),
         "mdd": round(float(_mdd(eq))*100, 2)}
    for w, d in WINDOWS.items():
        sub = eq.tail(d+1)
        o[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100, 2)
    return o

wM, wK = winstats(eqM), winstats(eqK)
# calibration vs M07_final
calib = {k: round(wM[k]-M07[k], 4) for k in M07}
# equity identity vs shipped pkl
refM = pd.read_pickle(ROOT/"results"/"r30_bt"/"M07_equity.pkl")
eqmaxdiff = float((eqM - refM).abs().max())

# --- 2y window monthly breakdown (calendar months, month-end marks) ---
D2Y = WINDOWS["2y"]
eM2, eK2 = eqM.tail(D2Y+1), eqK.tail(D2Y+1)
assert eM2.index[0] == eK2.index[0], "2y window start misaligned"
anchorM = eqM.loc[:eM2.index[0]].iloc[-2] if len(eqM.loc[:eM2.index[0]]) > 1 else eqM.iloc[0]
anchorK = eqK.loc[:eK2.index[0]].iloc[-2] if len(eqK.loc[:eK2.index[0]]) > 1 else eqK.iloc[0]
# anchor = last close BEFORE window start
preM = eqM[eqM.index < eM2.index[0]].iloc[-1]
preK = eqK[eqK.index < eK2.index[0]].iloc[-1]
mM = eM2.resample("ME").last(); mK = eK2.resample("ME").last()
months = sorted(set(mM.index.strftime("%Y-%m")) | set(mK.index.strftime("%Y-%m")))
rows = []
for m in months:
    ts = pd.Timestamp(m + "-01")
    eM = float(mM[mM.index.strftime("%Y-%m") == m].iloc[-1])
    eK = float(mK[mK.index.strftime("%Y-%m") == m].iloc[-1])
    pm = float(mM[mM.index.strftime("%Y-%m") < m].iloc[-1]) if (mM.index.strftime("%Y-%m") < m).any() else float(preM)
    pk = float(mK[mK.index.strftime("%Y-%m") < m].iloc[-1]) if (mK.index.strftime("%Y-%m") < m).any() else float(preK)
    rM = eM/pm-1; rK = eK/pk-1
    rows.append({"month": m, "m07_ret": round(rM*100, 4), "k_ret": round(rK*100, 4),
                 "diff_pp": round((rK-rM)*100, 4)})
# compounding self-check
import math
cm = math.prod(1+r["m07_ret"]/100 for r in rows)-1
ck = math.prod(1+r["k_ret"]/100 for r in rows)-1
winM = float(eM2.iloc[-1]/preM-1)*100; winK = float(eK2.iloc[-1]/preK-1)*100
neg = sorted(rows, key=lambda r: r["diff_pp"])[:3]
pos = sorted(rows, key=lambda r: -r["diff_pp"])[:3]

def slim_trades(res, cap=400):
    tr = res.trades
    out = []
    for _, t in tr.iterrows():
        out.append({"code": str(t["code"]), "entry": str(t["entry_date"])[:10],
                    "exit": str(t["exit_date"])[:10], "net_pnl": round(float(t["net_pnl"]), 2),
                    "reason": str(t["reason"])})
        if len(out) >= cap:
            break
    return out

part = {
    "legM_windows": wM, "legK_windows": wK,
    "gap_2y_pp": round(wK["2y"]-wM["2y"], 2),
    "gap_total_pp": round(wK["total"]-wM["total"], 2),
    "calib_vs_M07final": calib, "eqM_vs_pkl_maxabs": eqmaxdiff,
    "window_start": str(eM2.index[0].date()), "window_end": str(eM2.index[-1].date()),
    "anchor_prev_close": {"M": str(eqM[eqM.index < eM2.index[0]].index[-1].date()),
                            "K": str(eqK[eqK.index < eK2.index[0]].index[-1].date())},
    "monthly": rows,
    "top3_neg": [r["month"] for r in neg], "top3_neg_rows": neg,
    "top3_pos_rows": pos,
    "compound_check": {"M_prod": round(cm*100, 4), "M_win": round(winM, 4),
                         "K_prod": round(ck*100, 4), "K_win": round(winK, 4)},
    "meta": {
        "M": {"trades": len(resM.trades), "cost": round(float(resM.meta["total_cost"]), 1),
                "mode": resM.meta["final_mode"],
                "switch_log": [list(x) for x in resM.meta["switch_log"]],
                "brake_log": [list(x) for x in resM.meta.get("brake_log", [])]},
        "K": {"trades": len(resK.trades), "cost": round(float(resK.meta["total_cost"]), 1),
                "mode": resK.meta["final_mode"],
                "switch_log": [list(x) for x in resK.meta["switch_log"]],
                "brake_log": [list(x) for x in resK.meta.get("brake_log", [])]}},
}
# persist slim trades separately (large)
json.dump(slim_trades(resM), open(OUT/"trades_legM_slim.json", "w"))
json.dump(slim_trades(resK), open(OUT/"trades_legK_slim.json", "w"))
eqM.to_pickle(OUT/"eq_legM.pkl"); eqK.to_pickle(OUT/"eq_legK.pkl")
json.dump(part, open(OUT/"part_054_k22recompute.json", "w"), ensure_ascii=False, indent=1)
print("CALIB", json.dumps(calib, ensure_ascii=False))
print("EQMAXDIFF", eqmaxdiff)
print("GAP2Y", part["gap_2y_pp"], "TOP3NEG", part["top3_neg"])
print("SAVED part_054_k22recompute.json", flush=True)
