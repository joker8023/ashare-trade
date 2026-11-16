#!/usr/bin/env python3
"""K22: M07 vs k21_daily_hyst003_gbf07 2y-gap attribution (diagnostic only).

Reuses K21 engine verbatim (no caliber change, no lookahead):
  from sweep_beat_m07_k21 import get_shadows, get_ns  (same shadow RS, same
  switch/brake/cost/lot/slip semantics) + same KW construction as run_one.
Two configs only:
  BASE = M07 verbatim (grid, hyst=0, rs=60, cut .80/.80, bx.18/by.08/bf.6)
  CAND = k21_daily_hyst003_gbf07 (daily, hyst=.03, rs=60, cut .78/.78,
         bx.15/by.05/bf.7)
Output: results/r30_bt/attrib_k22.json:
  2y-window (504 trading days) month-by-month return diff (cand-base),
  top-3 gap months, per-month attribution (holdings identity, switch/brake
  events, top contributing tickets), verdict X.
Repro:
  .venv/bin/python research/attrib_k22.py
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))

import pandas as pd

from sweep_beat_h1_v4 import WINDOWS, RUN_START, EVAL_END, MB
from sweep_beat_m07_k21 import get_shadows, get_ns, M07

CALIB_M07 = json.load(open(ROOT / "results" / "r30_bt" / "M07_final.json"))
K21ROWS = json.load(open(ROOT / "results" / "r30_bt" / "sweep_beat_m07_k21.json"))
K21CAND = next(r for r in K21ROWS if r["tag"] == "k21_daily_hyst003_gbf07")

BASE_CFG = dict(cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, stop=0.25,
                a_take=1.2, b_take=0.80, a_n=5, b_n=4, b_exp=0.9,
                rs=60, bx=0.18, by_=0.08, bf=0.6,
                evalfreq="grid", hyst=0.0)
CAND_CFG = dict(cut_a=0.78, win_a=40, cut_b=0.78, win_b=20, stop=0.25,
                a_take=1.2, b_take=0.80, a_n=5, b_n=4, b_exp=0.9,
                rs=60, bx=0.15, by_=0.05, bf=0.7,
                evalfreq="daily", hyst=0.03)


def run_full(**cfg):
    c = dict(cfg)
    evalfreq, hyst = c["evalfreq"], c["hyst"]
    rs, bx, by_, bf = c["rs"], c["bx"], c["by_"], c["bf"]
    inp_a, inp_b, ra, rb, CA, CFG_B = get_shadows(
        c["cut_a"], c["win_a"], c["cut_b"], c["win_b"], c["stop"],
        c["a_take"], c["b_take"], c["a_n"], c["b_n"], c["b_exp"])
    KW = dict(n=c["a_n"], rebal=20, take=c["a_take"], exposure=1.0, phase=0,
              inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq,
              rs_lookback=rs, exclude_a=MB, exclude_b=MB,
              evalfreq=evalfreq, brake_daily=False,
              **{k: v for k, v in CA.items() if k != "exclude"})
    ns = get_ns(bx, by_, bf, hyst)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    return res, inp_a, ns


def wret(eq, w):
    sub = eq.tail(w + 1)
    return float(sub.iloc[-1] / sub.iloc[0] - 1) * 100


def monthly_table(eq):
    """Calendar-month simple returns inside the 2y window (tail 504 rets)."""
    W = WINDOWS["2y"]
    anchor = eq.iloc[-(W + 2)]  # day before window start (prev-month anchor)
    win = eq.iloc[-(W + 1):]   # W+1 points -> W returns
    # calendar-month grouping over window + anchor
    full = pd.concat([anchor.to_series() if hasattr(anchor, 'to_series') else pd.Series([anchor], index=[eq.iloc[-(W + 2):].index[0]]), win])
    out = []
    prev_end = full.iloc[0]
    for m, grp in full.iloc[1:].groupby([full.iloc[1:].index.year, full.iloc[1:].index.month]):
        end = grp.iloc[-1]
        r = float(end / prev_end - 1) * 100
        out.append({"month": "%04d-%02d" % (m[0], m[1]), "ret": round(r, 2), "raw": float(r),
                    "end_eq": round(float(end), 1), "ndays": len(grp)})
        prev_end = end
    return out


def month_index_range(dates, month):
    y, m = int(month[:4]), int(month[5:7])
    idx = [i for i, d in enumerate(dates) if d.year == y and d.month == m]
    return min(idx), max(idx)


def build_positions(trades, n_dates):
    """day-index -> {code: shares} intervals [entry_i, exit_i] (closed trades)."""
    pos = {}
    for _, t in trades.iterrows():
        e0, e1 = int(t["entry_i"]), int(t["exit_i"])
        for i in range(e0, e1 + 1):
            d = pos.get(i)
            if d is None:
                d = pos[i] = {}
            d[t["code"]] = d.get(t["code"], 0.0) + float(t["shares"])
    return pos


def main():
    import pickle
    cp = Path("/tmp/k22_cache.pkl")
    if cp.exists():
        print("K22: loading cached backtests ...", flush=True)
        D = pickle.load(open(cp, "rb"))
        res_b, res_c = D["res_b"], D["res_c"]
        inp_b, ns_b, ns_c = D["inp_b"], None, None
    else:
        print("K22: running BASE (M07 verbatim) ...", flush=True)
        res_b, inp_b, ns_b = run_full(**BASE_CFG)
        print("K22: running CAND (hyst003_gbf07) ...", flush=True)
        res_c, inp_c, ns_c = run_full(**CAND_CFG)
        pickle.dump({"res_b": res_b, "res_c": res_c, "inp_b": inp_b}, open(cp, "wb"))

    eq_b = res_b.eq.dropna()
    eq_c = res_c.eq.dropna()

    # ---- calibration: must reproduce published numbers exactly ----
    for w in WINDOWS:
        assert round(wret(eq_b, WINDOWS[w]), 2) == CALIB_M07[w], (w, wret(eq_b, WINDOWS[w]))
    assert round(wret(eq_c, WINDOWS["2y"]), 2) == K21CAND["2y"]
    assert [list(x) for x in res_b.meta["switch_log"]] == CALIB_M07["switch_log"]
    assert [list(x) for x in res_c.meta["switch_log"]] == K21CAND["switch_log"]
    print("K22 CALIB OK: base==M07_final all windows; cand 2y==%.2f; switch logs match" % K21CAND["2y"], flush=True)

    W = WINDOWS["2y"]
    wstart, wend = eq_b.iloc[-(W + 1):].index[0], eq_b.index[-1]
    gap = float(eq_c.iloc[-1] / eq_c.iloc[-(W + 1)] - 1) * 100 - float(eq_b.iloc[-1] / eq_b.iloc[-(W + 1)] - 1) * 100

    _tb = monthly_table(eq_b)
    _tc = monthly_table(eq_c)
    mb = {r["month"]: r["ret"] for r in _tb}
    mc = {r["month"]: r["ret"] for r in _tc}
    mb_raw = {r["month"]: r["raw"] for r in _tb}
    mc_raw = {r["month"]: r["raw"] for r in _tc}
    assert mb.keys() == mc.keys()
    months = []
    for m in mb:
        months.append({"month": m, "base": mb[m], "cand": mc[m],
                       "diff_pp": round(mc[m] - mb[m], 2)})
    Tb = float(eq_b.iloc[-1] / eq_b.iloc[-(W + 1)])
    Tc = float(eq_c.iloc[-1] / eq_c.iloc[-(W + 1)])
    # waterfall attribution (chronological, exact): flip months base->cand one by
    # one; contrib_k = L_k - L_{k-1}, telescopes exactly to Tc - Tb (pp of start eq)
    _P, _Q = 1.0, Tb
    for r in months:
        c, b = mc_raw[r["month"]] / 100.0, mb_raw[r["month"]] / 100.0
        _P *= (1 + c)
        _Q /= (1 + b)
        r["_L"] = _P * _Q
    _prev = Tb
    for r in months:
        r["term_pp"] = round((r.pop("_L") - _prev) * 100, 2)
        _prev += r["term_pp"] / 100.0
    _chk = sum(r["term_pp"] for r in months)
    assert abs(_chk - (Tc - Tb) * 100) < 0.6, (_chk, (Tc - Tb) * 100)
    top3 = sorted(months, key=lambda r: r["term_pp"])[:3]

    dates = inp_b.dates
    mark = inp_b.mark
    ffill = mark.ffill()
    tr_b, tr_c = res_b.trades, res_c.trades
    pos_b = build_positions(tr_b, len(dates))
    pos_c = build_positions(tr_c, len(dates))

    def contrib(trades, month):
        """per-code yuan contribution within calendar month (per-trade exact).
        shares * sum(px[i]-px[i-1]) over held days i in month (buy at close e0
        -> first earning day e0+1; sell at close e1 counts); fee drag
        (life price gain - net_pnl) allocated to exit month."""
        i0, i1 = month_index_range(dates, month)
        out = {}
        for _, t in trades.iterrows():
            e0, e1 = int(t["entry_i"]), int(t["exit_i"])
            code = t["code"]
            if code not in ffill.columns:
                continue
            px = ffill[code]
            lo, hi = max(e0 + 1, i0), min(e1, i1)
            if lo <= hi:
                s = 0.0
                for i in range(max(lo, 1), hi + 1):
                    p1, p0 = px.iloc[i], px.iloc[i - 1]
                    if pd.notna(p1) and pd.notna(p0):
                        s += float(t["shares"]) * (p1 - p0)
                out[code] = out.get(code, 0.0) + s
            ed = t["exit_date"]
            if "%04d-%02d" % (ed.year, ed.month) == month:
                fee = float(t["shares"]) * (float(t["exit_px"]) - float(t["entry_px"])) - float(t["net_pnl"])
                out[code] = out.get(code, 0.0) - fee
        return out

    sw_b = [(d, m) for d, m in res_b.meta["switch_log"]]
    sw_c = [(d, m) for d, m in res_c.meta["switch_log"]]
    br_b = [list(x) for x in res_b.meta.get("brake_log", [])]
    br_c = [list(x) for x in res_c.meta.get("brake_log", [])]

    top3_out = []
    for t in top3:
        m = t["month"]
        i0, i1 = month_index_range(dates, m)
        mdays = list(range(i0, i1 + 1))
        same = sum(1 for i in mdays if pos_b.get(i, {}) .keys() == pos_c.get(i, {}).keys()
                   and set(pos_b.get(i, {})) == set(pos_c.get(i, {})))
        hb = set().union(*[set(pos_b.get(i, {})) for i in mdays]) if mdays else set()
        hc = set().union(*[set(pos_c.get(i, {})) for i in mdays]) if mdays else set()
        cb = contrib(tr_b, m)
        cc = contrib(tr_c, m)
        dmap = {c: cc.get(c, 0.0) - cb.get(c, 0.0) for c in set(cb) | set(cc)}
        neg = sorted(((c, round(v, 1)) for c, v in dmap.items() if v < 0), key=lambda x: x[1])[:5]
        posd = sorted(((c, round(v, 1)) for c, v in dmap.items() if v > 0), key=lambda x: -x[1])[:5]
        # residual check
        tot_b = sum(cb.values())
        lb1 = eq_b.index.get_loc(dates[i1])
        lb0 = eq_b.index.get_loc(dates[i0])
        act_b = float(eq_b.iloc[lb1] - eq_b.iloc[lb0 - 1])
        tot_c = sum(cc.values())
        lc1 = eq_c.index.get_loc(dates[i1])
        lc0 = eq_c.index.get_loc(dates[i0])
        act_c = float(eq_c.iloc[lc1] - eq_c.iloc[lc0 - 1])
        # realized detail for top drivers
        def rlz(tr, code):
            rows = tr[(tr["code"] == code) & (tr["exit_date"].dt.strftime("%Y-%m") == m)]
            return [{"exit": str(r["exit_date"].date()), "shares": int(r["shares"]),
                     "entry_px": round(float(r["entry_px"]), 2), "exit_px": round(float(r["exit_px"]), 2),
                     "net_pnl": round(float(r["net_pnl"]), 1), "reason": r["reason"]} for _, r in rows.iterrows()]
        top3_out.append({
            "month": m, "base_ret": t["base"], "cand_ret": t["cand"], "diff_pp": t["diff_pp"],
            "term_pp": t["term_pp"],
            "holdings": {"same_days": same, "total_days": len(mdays),
                         "base_only": sorted(hb - hc), "cand_only": sorted(hc - hb),
                         "shared": sorted(hb & hc)},
            "switches": {"base": [x for x in sw_b if x[0][:7] == m],
                         "cand": [x for x in sw_c if x[0][:7] == m]},
            "brakes": {"base": [x for x in br_b if x[0][:7] == m],
                       "cand": [x for x in br_c if x[0][:7] == m]},
            "gap_drivers_neg": [{"code": c, "diff_yuan": v, "realized": {"base": rlz(tr_b, c), "cand": rlz(tr_c, c)}} for c, v in neg],
            "gap_drivers_pos": [{"code": c, "diff_yuan": v, "realized": {"base": rlz(tr_b, c), "cand": rlz(tr_c, c)}} for c, v in posd],
            "resid_check": {"base_recon": round(tot_b, 1), "base_actual": round(act_b, 1),
                            "cand_recon": round(tot_c, 1), "cand_actual": round(act_c, 1)},
        })

    # one-line summaries
    for a in top3_out:
        h, s, br = a["holdings"], a["switches"], a["brakes"]
        ident = "持股完全相同" if (h["same_days"] == h["total_days"] and not h["base_only"] and not h["cand_only"]) else (
            "持股%d/%d天相同" % (h["same_days"], h["total_days"]))
        ev = []
        if s["base"] or s["cand"]:
            ev.append("switch 基线%s/候选%s" % (s["base"] or "无", s["cand"] or "无"))
        if br["base"] or br["cand"]:
            ev.append("brake 基线%s/候选%s" % (br["base"] or "无", br["cand"] or "无"))
        neg1 = a["gap_drivers_neg"][0] if a["gap_drivers_neg"] else None
        a["summary_1line"] = "%s：%s；%s；头号拖累%s(%s元)" % (
            a["month"], ident, "；".join(ev) if ev else "当月无switch/brake事件",
            neg1["code"] if neg1 else "无", neg1["diff_yuan"] if neg1 else 0)

    # verdict: which mechanism must be fixed
    shr = sorted(top3_out, key=lambda a: a["term_pp"])
    dom = shr[0]
    sw_ev = dom["switches"]
    mech = ("switch时机" if (sw_ev["base"] or sw_ev["cand"]) else "同持股下暴露/费率/止盈差异")
    verdict_x = ("翻转2y必须修复X=【%s月%s】：该月终值缺口贡献%.2fpp，占2y总缺口%.2fpp的%.1f%%（当月简单收益差%.2fpp，经终值%.1f倍杠杆放大）；%s" % (
        dom["month"], mech, dom["term_pp"], gap,
        abs(dom["term_pp"] / gap * 100) if gap else 0, dom["diff_pp"], Tc, dom["summary_1line"]))
    out = {
        "meta": {
            "base": "M07 (grid,hyst=0,rs=60,cut.80,bx.18/by.08/bf.6)",
            "cand": "k21_daily_hyst003_gbf07 (daily,hyst=.03,rs=60,cut.78,bx.15/by.05/bf.7)",
            "engine": "reuse sweep_beat_m07_k21.get_shadows/get_ns (caliber verbatim, no lookahead)",
            "window_2y": {"start": str(wstart.date()), "end": str(wend.date()), "n": W},
            "gap_2y_pp": round(gap, 2),
            "repro": [".venv/bin/python research/sweep_beat_m07_k21.py  # K21 rows (calib base_M07==M07_final)",
                      ".venv/bin/python research/attrib_k22.py          # this file -> results/r30_bt/attrib_k22.json"],
            "calib": {"base_all_windows_eq_M07_final": True,
                      "cand_2y_eq_k21_file": K21CAND["2y"],
                      "switch_logs_match": True},
        },
        "monthly_diff_cand_minus_base_pp": months,
        "top3_gap_months": top3_out,
        "verdict": {"X": verdict_x},
    }
    p = ROOT / "results" / "r30_bt" / "attrib_k22.json"
    json.dump(out, open(p, "w"), ensure_ascii=False, indent=1)
    print("saved", p, flush=True)
    print(json.dumps({"gap_2y_pp": round(gap, 2),
                      "top3": [(a["month"], a["diff_pp"], a["term_pp"]) for a in top3_out],
                      "X": verdict_x}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
