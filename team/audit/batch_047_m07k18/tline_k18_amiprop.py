#!/usr/bin/env python3
"""batch_047 T-line for k18_amiprop_gbf07 (best K18 row: nbeat=1, total 1581.87, only mdd_better).
leg1 rerun-vs-JSON | leg2 cross-phase ph0/5/7/10/14/15 weighted-vs-equal seat | leg3 ex-top3 | leg4 slipx2 | leg5 weight-equivalence (live+shadow snapshot weights vs independent t-only recompute) + RS-drift mechanism.
Only writes team/audit/batch_047_m07k18/tline_k18_amiprop_out.json"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
import weight_k18 as W
from weight_k18 import compute_weights
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
from sweep_beat_h1_v4 import AA, BB, CC, DD, EE, FF, GG, SIG, PICKLINE
import sweep_beat_m07_k18 as K18

M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05, "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
A_GBF07 = dict(band=(0.02, 0.30), gate60=-0.15, max_cut=0.78, max_win=40)
B_GBF07 = dict(band=(0.05, 0.30), gate60=-1.0, max_cut=0.78, max_win=20)
GBX, GBY, GBF = 0.15, 0.05, 0.7
TAG = "k18_amiprop_gbf07"
WEIGHT = "amihud_prop"
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
JS = {r["tag"]: r for r in json.loads((ROOT/"results"/"r30_bt"/"sweep_beat_m07_k18.json").read_text())}

def _s(x):
    return x.iloc[:, 0] if isinstance(x, pd.DataFrame) else x

def CA(slip=0.002):
    return dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0,
                lot=100, cost_one_way=None, slip=slip, run_start=RUN_START, eval_start=first_sig,
                eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)

def shadows_equal(ph, slip=0.002):
    ia = MaxInputs(piv, **A_GBF07); ib = MaxInputs(piv, **B_GBF07)
    ca = CA(slip)
    ra = pc.run_strategy(ia, n=5, rebal=20, take=1.2, exposure=1.0, phase=ph, **ca)
    rb = pc.run_strategy(ib, n=4, rebal=30, take=0.80, exposure=0.9, phase=ph, **ca)
    return ia, ib, ra, rb, ca

def shadows_weighted(ph, slip=0.002, weight=WEIGHT):
    ia = MaxInputs(piv, **A_GBF07); ib = MaxInputs(piv, **B_GBF07)
    ca = CA(slip)
    ns = W.get_single_ns(weight)
    ra = ns["run_strategy"](ia, n=5, rebal=20, take=1.2, exposure=1.0, phase=ph, **ca)
    rb = ns["run_strategy"](ib, n=4, rebal=30, take=0.80, exposure=0.9, phase=ph, **ca)
    return ia, ib, ra, rb, ca

def run_equal_switch(ia, ib, ra, rb, ca, ph):
    CFG_B = dict(n=4, rebal=30, take=0.80, exposure=0.9)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=ph, inp_b=ib, cfg_b=CFG_B,
              shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=60, exclude_a=MB, exclude_b=MB,
              factor="amihud_60", **{k: v for k, v in ca.items() if k not in ("exclude", "factor")})
    res = build_ns(GBX, GBY, GBF)["run_strategy_switch"](ia, lock_mode=None, **KW)
    return res

def run_weighted_switch(ia, ib, ra, rb, ca, ph, weight=WEIGHT):
    import weight_k18 as _W
    src = (ROOT/"research"/"switch_engine.py").read_text()
    def _once(old, new):
        nonlocal src
        assert src.count(old) == 1, (old[:60], src.count(old))
        src = src.replace(old, new)
    add = "\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n    _brake_log: List = []\n    _BRAKE_X = %s\n    _BRAKE_Y = %s\n    _BRAKE_F = %s" % (GBX, GBY, GBF)
    _once(AA, AA + add)
    _once(BB, BB + ", _brake, _brake_trough, _brake_peak, _brake_log")
    brake_eval = "\n        tb_mv_pre = 0.0\n        for tb_cc, tb_p in pos.items():\n            tb_px = px_ffill_or_nan(mark, day, tb_cc)\n            if pd.isna(tb_px):\n                tb_px = tb_p.entry_px\n            tb_mv_pre += tb_p.shares * tb_px\n        tb_eq_pre = cash + tb_mv_pre\n        if tb_eq_pre > _brake_peak:\n            _brake_peak = tb_eq_pre\n        if not _brake and _brake_peak > 0 and (_brake_peak - tb_eq_pre) / _brake_peak >= _BRAKE_X:\n            _brake = True\n            _brake_trough = tb_eq_pre\n            _brake_log.append((str(day.date()), 'ON', round(float((_brake_peak - tb_eq_pre) / _brake_peak) * 100, 2)))\n        elif _brake:\n            if tb_eq_pre < _brake_trough:\n                _brake_trough = tb_eq_pre\n            if _brake_trough > 0 and tb_eq_pre >= _brake_trough * (1.0 + _BRAKE_Y):\n                _brake = False\n                _brake_log.append((str(day.date()), 'OFF', round(float(tb_eq_pre / _brake_trough - 1) * 100, 2)))"
    _once(CC, CC + brake_eval)
    skip_block = "\n        if not switching and set(picks) == set(pos):\n            return False"
    _once(DD, DD + skip_block)
    _once(PICKLINE, "        _ex = (exclude_a if mode == 'A' else exclude_b) if (exclude_a is not None or exclude_b is not None) else exclude\n" + PICKLINE.replace("exclude=exclude", "exclude=_ex"))
    _once(SIG, SIG + "\n    exclude_a=None,\n    exclude_b=None,")
    _once(EE, "        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n" + EE)
    _once(FF, FF + "\n        if (cash + mv) > _brake_peak:\n            _brake_peak = cash + mv")
    _once(GG, "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode, brake_log=_brake_log,")
    eq_split = "            alloc = equity_now * state_exposure / slots\n        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n        for code in picks:"
    assert src.count(eq_split) == 1, ("braked alloc anchor", src.count(eq_split))
    wblk = _W._weight_block("state_exposure").replace(
        "_w_expo = equity_now * state_exposure",
        "_w_expo = equity_now * state_exposure * (_BRAKE_F if _brake else 1.0)")
    _wlines = wblk.split("\n")
    assert _wlines[-1] == "        for code in picks:", _wlines[-1]
    wblk12 = "\n".join(("    " + ln) if ln.strip() else ln for ln in _wlines[:-1]) + "\n" + _wlines[-1]
    src = src.replace(eq_split, wblk12)
    assert src.count(_W._SW_LOOP_A) == 1
    src = src.replace(_W._SW_LOOP_A, "                sh = int(_w_alloc[code] / px // lot) * lot")
    assert src.count(_W._SW_LOOP_B) == 1
    src = src.replace(_W._SW_LOOP_B, "                sh = _w_alloc[code] / px")
    assert src.count(_W._SW_SNAP) == 1
    src = src.replace(_W._SW_SNAP,
        "                               alloc_per_slot=float(_w_mean), picked=int(len(picks)), "
        "weight_mode=_w_mode, weights={cd: round(float(_w_alloc[cd]), 4) for cd in picks}))")
    src = src.replace("    switch_log: List[Tuple[str, str]] = []",
        "    switch_log: List[Tuple[str, str]] = []\n    _WEIGHT_MODE = " + repr(weight), 1)
    ns = {}
    exec(compile(src, "switch_engine_k18_tline_%s" % weight, "exec"), ns)
    CFG_B = dict(n=4, rebal=30, take=0.80, exposure=0.9)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=ph, inp_b=ib, cfg_b=CFG_B,
              shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=60, exclude_a=MB, exclude_b=MB,
              factor="amihud_60", **{k: v for k, v in ca.items() if k not in ("exclude", "factor")})
    return ns["run_strategy_switch"](ia, lock_mode=None, **KW)

def summarize(res):
    eq = _s(res.eq).dropna()
    out = {"total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100, 2), "mdd": round(_mdd(eq)*100, 2),
           "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]), 0),
           "mode": res.meta.get("final_mode", "B"), "switches": len(res.meta.get("switch_log", [])),
           "switch_log": [list(x) for x in res.meta.get("switch_log", [])]}
    for w, d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100, 2)
    out["nbeat_m07"] = sum(1 for w in WINDOWS if out[w] > M07[w])
    return out

def snaps_of(res):
    m = res.meta.get("rebalance_snapshots") or getattr(res, "rebalance_snapshots", None) or []
    return m

out = {}
# leg1: module rerun vs JSON
cfg = next(c for c in K18.CFGS if c["tag"] == TAG)
r1 = K18.run_one(cfg)
js = JS[TAG]
out["leg1_rerun"] = {"mine": {k: r1[k] for k in ("total","mdd","trades","cost","switches","nbeat_m07","beat_all","mdd_better")},
    "match_total": abs(r1["total"]-js["total"]) < 1e-9, "match_mdd": abs(r1["mdd"]-js["mdd"]) < 1e-9,
    "match_trades": r1["trades"] == js["trades"], "match_cost": r1["cost"] == js["cost"],
    "match_switch": r1["switch_log"] == js["switch_log"], "json": {k: js[k] for k in ("total","mdd","trades","cost","switches","nbeat_m07")}}
# local composition rerun (returns res) for leg3/leg5
ia0, ib0, ra0w, rb0w, ca0 = shadows_weighted(0)
res_w0 = run_weighted_switch(ia0, ib0, ra0w, rb0w, ca0, 0)
s0 = summarize(res_w0)
out["leg1_local"] = {"total": s0["total"], "mdd": s0["mdd"], "trades": s0["trades"], "cost": s0["cost"],
    "switches": s0["switches"], "match_json": [s0["total"] == js["total"], s0["mdd"] == js["mdd"], s0["trades"] == js["trades"], s0["switch_log"] == js["switch_log"]]}
# leg3 ex-top3
tr = res_w0.trades; pnl = tr["net_pnl"].fillna(0); top3 = pnl.nlargest(3).sum()
eq0 = float(_s(res_w0.eq).dropna().iloc[0])
out["leg3_extop3"] = {"w_extop3_total": round(float((eq0+pnl.sum()-top3)/eq0-1)*100, 2), "m07_extop3_total": 1351.75,
    "n_trades": len(tr), "top3_share_of_pnl": round(float(top3/pnl.sum())*100, 2) if float(pnl.sum()) else None}
# leg2 cross-phase
out["leg2_xphase"] = []
for ph in [0, 5, 7, 10, 14, 15]:
    iae, ibe, rae, rbe, cae = shadows_equal(ph)
    res_e = run_equal_switch(iae, ibe, rae, rbe, cae, ph)
    se = summarize(res_e)
    if ph == 0:
        iaw, ibw, raw_, rbw, caw = ia0, ib0, ra0w, rb0w, ca0
        res_w = res_w0; sw = s0
    else:
        iaw, ibw, raw_, rbw, caw = shadows_weighted(ph)
        res_w = run_weighted_switch(iaw, ibw, raw_, rbw, caw, ph)
        sw = summarize(res_w)
    out["leg2_xphase"].append({"ph": ph, "w_total": sw["total"], "w_mdd": sw["mdd"], "w_switches": sw["switches"],
        "w_nbeat": sw["nbeat_m07"], "eq_total": se["total"], "eq_mdd": se["mdd"], "eq_switches": se["switches"], "eq_nbeat": se["nbeat_m07"]})
# leg4 slipx2
ia4, ib4, ra4, rb4, ca4 = shadows_weighted(0, slip=0.004)
res4 = run_weighted_switch(ia4, ib4, ra4, rb4, ca4, 0)
s4 = summarize(res4)
out["leg4_slipx2"] = {"total": s4["total"], "mdd": s4["mdd"], "nbeat_vs_stdM07": s4["nbeat_m07"],
    "delta_total_vs_ph0": round(s4["total"]-s0["total"], 2), "switches": s4["switches"]}
# leg5 weight-equivalence: every live+shadow snapshot with weights vs independent t-only recompute
inpA = MaxInputs(piv, **A_GBF07); inpB = MaxInputs(piv, **B_GBF07)
facA = inpA.amihud60; facB = inpB.amihud60
def check_snaps(snaps, fac, leg):
    n = 0; mx = 0.0; bad = []
    for sn in snaps:
        w = sn.get("weights"); wm = sn.get("weight_mode")
        if not w or wm != WEIGHT: continue
        codes = list(w.keys())
        try:
            j = int(dates.searchsorted(pd.Timestamp(sn["date"]), side="right") - 1)
        except Exception:
            bad.append((leg, sn.get("date"), "date-parse")); continue
        if j < 1: continue
        sig_day = dates[j-1]
        try:
            vals = list(fac.loc[sig_day, codes])
        except Exception:
            bad.append((leg, sn.get("date"), "fac-missing")); continue
        exp = compute_weights(vals, WEIGHT)
        tot = sum(float(v) for v in w.values())
        if tot <= 0: bad.append((leg, sn.get("date"), "zero-sum")); continue
        got = [float(w[c])/tot for c in codes]
        d = max(abs(a-b) for a, b in zip(got, exp))
        mx = max(mx, d); n += 1
        if d > 1e-6: bad.append((leg, sn.get("date"), round(d, 9)))
    return {"snaps": n, "max_abs_diff": mx, "mismatches": bad[:10]}
l5 = {"live": check_snaps(snaps_of(res_w0), None if False else facA, "live")}
# live leg can be A or B: check against both panels, take the matching one
def check_live_both(snaps):
    outB = {}
    for leg, fac in (("A", facA), ("B", facB)):
        outB[leg] = check_snaps(snaps, fac, "live-"+leg)
    return outB
l5["live_by_leg"] = check_live_both(snaps_of(res_w0))
l5["shadowA"] = check_snaps(list((ra0w.meta.get("rebalance_snapshots") or [])), facA, "shadowA")
l5["shadowB"] = check_snaps(list((rb0w.meta.get("rebalance_snapshots") or [])), facB, "shadowB")
out["leg5_weights"] = l5
# mechanism: RS drift equal-vs-weighted shadows on A-grid signal days
sig_days = [d for d in grid_dates if d >= pd.Timestamp(RUN_START)]
iae_, ibe_, rae0, rbe0, _cae = shadows_equal(0)
def trail60_ret(eq, t):
    w = _s(eq).loc[:t]
    if len(w) < 61: return None
    w = w.iloc[-61:]
    return float(w.iloc[-1]/w.iloc[0]-1)
n_sig = 0; n_flip = 0; flips = []
for t in sig_days:
    rea = trail60_ret(rae0.eq, t); reb = trail60_ret(rbe0.eq, t)
    rwa = trail60_ret(ra0w.eq, t); rwb = trail60_ret(rb0w.eq, t)
    if None in (rea, reb, rwa, rwb): continue
    n_sig += 1
    de = "A" if rea >= reb else "B"; dw = "A" if rwa >= rwb else "B"
    if de != dw:
        n_flip += 1
        if len(flips) < 12: flips.append(str(t.date()) + " eq=" + de + " w=" + dw)
ea = _s(rae0.eq).dropna(); wa = _s(ra0w.eq).dropna()
eb = _s(rbe0.eq).dropna(); wb = _s(rb0w.eq).dropna()
out["mechanism"] = {"n_sig_days": n_sig, "n_desired_flips": n_flip, "flip_sample": flips,
    "eq_shadowA_final": round(float(ea.iloc[-1]/ea.iloc[0]-1)*100, 2),
    "w_shadowA_final": round(float(wa.iloc[-1]/wa.iloc[0]-1)*100, 2),
    "eq_shadowB_final": round(float(eb.iloc[-1]/eb.iloc[0]-1)*100, 2),
    "w_shadowB_final": round(float(wb.iloc[-1]/wb.iloc[0]-1)*100, 2),
    "eq_switches": 3, "w_switches": js["switches"]}
(ROOT/"team"/"audit"/"batch_047_m07k18"/"tline_k18_amiprop_out.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps({k: (v if k in ("leg1_rerun","leg1_local","leg3_extop3","leg4_slipx2") else ("n=%d" % len(v) if isinstance(v, list) else v)) for k, v in out.items()}, ensure_ascii=False, indent=1))
