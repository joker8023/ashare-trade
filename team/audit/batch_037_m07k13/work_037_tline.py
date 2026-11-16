"""batch_037 K13 T-line suite (reviewer-executed, independent of research sweep).
Candidate: g_bf07 full-precision (research/gbf07_fullprec_k13.py, GBF07_KW),
nbeat=5 vs M07 -> triggers full T-line (>=4 per task rule; also >=5 legacy gate).
T-line: (B) independent rerun ph0, (C) cross-phase ph 5/7/10/14/15 vs phase-matched M07,
(D) ex-top3, (E) slip-double 0.004, (F) caliber + lookahead static gates.
Repro: .venv/bin/python team/audit/batch_037_m07k13/work_037_tline.py
"""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "team" / "audit")); sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB

WINS = list(WINDOWS.keys())
M07 = json.load(open(ROOT / "results" / "r30_bt" / "M07_final.json"))
M07W = {w: M07[w] for w in WINS}
GBF07 = dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.7)

piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
_ns_cache, _sh_cache = {}, {}

def get_ns(bx, by, bf):
    k = (bx, by, bf)
    if k not in _ns_cache:
        _ns_cache[k] = build_ns(bx, by, bf)
    return _ns_cache[k]

def run_cfg(ph=0, slip=0.002, **kw):
    cut_a = kw.get("cut_a", 0.80); win_a = kw.get("win_a", 40)
    cut_b = kw.get("cut_b", 0.80); win_b = kw.get("win_b", 20)
    stop = kw.get("stop", 0.25); a_take = kw.get("a_take", 1.2); b_take = kw.get("b_take", 0.80)
    a_n = kw.get("a_n", 5); b_n = kw.get("b_n", 4); b_exp = kw.get("b_exp", 0.9)
    bx = kw.get("bx", 0.18); by_ = kw.get("by_", 0.08); bf = kw.get("bf", 0.6)
    shk = (cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp, ph, slip)
    if shk not in _sh_cache:
        inp_a = MaxInputs(piv, band=(kw.get("band_a_lo", 0.02), 0.30), gate60=kw.get("gate_a", -0.15), max_cut=cut_a, max_win=win_a)
        inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=cut_b, max_win=win_b)
        CA = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=slip, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
        CFG_B = dict(n=b_n, rebal=30, take=b_take, exposure=b_exp)
        ra = pc.run_strategy(inp_a, n=a_n, rebal=20, take=a_take, exposure=1.0, phase=ph, **CA)
        rb = pc.run_strategy(inp_b, phase=ph, **{**CA, **CFG_B})
        _sh_cache[shk] = (inp_a, inp_b, ra, rb, CA, CFG_B)
    inp_a, inp_b, ra, rb, CA, CFG_B = _sh_cache[shk]
    KW = dict(n=a_n, rebal=20, take=a_take, exposure=1.0, phase=ph, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=kw.get("rs", 60), exclude_a=MB, exclude_b=MB, **{k: v for k, v in CA.items() if k != "exclude"})
    res = get_ns(bx, by_, bf)["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"total": float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, "mdd": float(_mdd(eq)) * 100, "trades": len(res.trades), "cost": float(res.meta["total_cost"]), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "switch_log": [list(x) for x in res.meta["switch_log"]]}
    for w, d in WINDOWS.items():
        sub = eq.tail(d + 1)
        out[w] = float(sub.iloc[-1] / sub.iloc[0] - 1) * 100
        out[w + "_mdd"] = float(_mdd(sub)) * 100
    pnl = res.trades["net_pnl"].fillna(0)
    top3 = pnl.nlargest(3).sum()
    out["top3_share"] = float(top3 / pnl.sum()) * 100
    out["extop3_total"] = float((eq.iloc[0] + pnl.sum() - top3) / eq.iloc[0] - 1) * 100
    out["pnl_sum"] = float(pnl.sum()); out["eq0"] = float(eq.iloc[0])
    return out

out = {"checks": {}}
# A. flags recompute over K1-K12 + K13 file row
import glob as _g
allrows = []
for f in sorted(_g.glob(str(ROOT / "results" / "r30_bt" / "sweep_beat_m07_k*.json"))):
    rows = json.load(open(f))
    for r in rows:
        r2 = dict(r); r2["_file"] = Path(f).name
        allrows.append(r2)
k13doc = json.load(open(ROOT / "results" / "r30_bt" / "gbf07_fullprec_k13.json"))
k13r = dict(k13doc["result_fullprec"]); k13r["_file"] = "gbf07_fullprec_k13.json"
mis = []
for r in allrows + [k13r]:
    nb = sum(1 for w in WINS if r[w] > M07W[w])
    ba = all(r[w] > M07W[w] for w in WINS)
    if "nbeat_m07" in r and (nb != r["nbeat_m07"] or ba != r["beat_all"]):
        mis.append((r["_file"], r["tag"]))
    r["_re_nb"] = nb; r["_re_ba"] = ba
new = [r for r in allrows if r["tag"] != "base_M07"]
out["checks"]["A_files_rows"] = len(allrows)
out["checks"]["A_new_cfgs"] = len(new)
out["checks"]["A_beat_all_true"] = [ (r["_file"], r["tag"]) for r in allrows + [k13r] if r["_re_ba"]]
out["checks"]["A_decl_mismatch"] = mis
out["checks"]["A_ge4"] = sorted((r["_file"], r["tag"], r["_re_nb"]) for r in new if r["_re_nb"] >= 4)
# B. independent rerun g_bf07 ph0
b = run_cfg(ph=0, slip=0.002, **GBF07)
f = k13doc["result_fullprec"]
keys = ["total", "mdd", "1m", "3m", "6m", "1y", "2y", "3y", "1m_mdd", "3m_mdd", "6m_mdd", "1y_mdd", "2y_mdd", "3y_mdd", "cost"]
out["checks"]["B_rerun_maxabsdev"] = max(abs(b[k] - f[k]) for k in keys)
out["checks"]["B_rerun_dev"] = {k: b[k] - f[k] for k in keys}
out["checks"]["B_meta"] = {k: (b[k], f[k]) for k in ["trades", "mode", "switches"]}
out["checks"]["B_switch_same"] = (b["switch_log"] == f["switch_log"])
out["checks"]["B_nbeat"] = sum(1 for w in WINS if b[w] > M07W[w])
out["checks"]["B_gaps_vs_M07"] = {w: b[w] - M07W[w] for w in WINS}
out["checks"]["B_mdd_edge"] = b["mdd"] - M07["mdd"]
# C. cross-phase vs phase-matched M07
out["checks"]["C_phases"] = {}
for ph in [0, 5, 7, 10, 14, 15]:
    g = run_cfg(ph=ph, slip=0.002, **GBF07)
    m = run_cfg(ph=ph, slip=0.002)
    mw = {w: m[w] for w in WINS}
    out["checks"]["C_phases"][str(ph)] = {
        "g_total": g["total"], "m_total": m["total"], "g_mdd": g["mdd"], "m_mdd": m["mdd"],
        "g_sw": g["switches"], "m_sw": m["switches"],
        "nbeat_vs_phasemached_M07": sum(1 for w in WINS if g[w] > mw[w]),
        "gaps": {w: g[w] - mw[w] for w in WINS}, "mdd_edge": g["mdd"] - m["mdd"]}
# D. ex-top3
out["checks"]["D_gbf07_top3_share"] = b["top3_share"]
out["checks"]["D_gbf07_extop3_total"] = b["extop3_total"]
out["checks"]["D_M07_top3_share"] = M07["top3_share"]
out["checks"]["D_M07_extop3_total"] = M07["extop3_total"]
# E. slip-double
out["checks"]["E"] = {}
for tag, kw in [("M07", {}), ("gbf07", GBF07)]:
    s = run_cfg(ph=0, slip=0.004, **kw)
    out["checks"]["E"][tag] = {"total": s["total"], "mdd": s["mdd"], "cost": s["cost"], "trades": s["trades"], "switches": s["switches"], **{w: s[w] for w in WINS}}
e = out["checks"]["E"]
out["checks"]["E_nbeat_gbf07_vs_slipdoubled_M07"] = sum(1 for w in WINS if e["gbf07"][w] > e["M07"][w])
out["checks"]["E_nbeat_gbf07slip2_vs_M07std"] = sum(1 for w in WINS if e["gbf07"][w] > M07W[w])
# F. caliber + lookahead static gates
out["checks"]["F_RUN_START"] = RUN_START; out["checks"]["F_EVAL_END"] = EVAL_END
out["checks"]["F_WINDOWS"] = {w: d for w, d in WINDOWS.items()}
out["checks"]["F_MB"] = MB
src = open(ROOT / "research" / "gbf07_fullprec_k13.py").read()
out["checks"]["F_tokens"] = {t: (t in src) for t in ["searchsorted", "shift(-", "dynamic", "confirm", "delay", "hold_days", "adaptive", "iloc", "round("]}
r = subprocess.run(["grep", "-rn", "shift(-", "research/"], capture_output=True, text=True, cwd=ROOT)
out["checks"]["F_shift_neg_hits"] = r.stdout.strip().splitlines() if r.stdout.strip() else []
open(ROOT / "team" / "audit" / "batch_037_m07k13" / "part_037_tline.json", "w").write(json.dumps(out, ensure_ascii=False, indent=1, default=str))
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
