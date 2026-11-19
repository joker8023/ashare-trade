#!/usr/bin/env python3
"""Independent audit: Route C2 five-candidate verify (audit-5).
No import of search_C_combo / search_C_stage2. Rebuilds the switch engine
from research/switch_engine.py source (build_ns idea, independently written).
Caliber per research/search_C_stage2.py comments:
 A=M07-A N5/R20/take1.2 ; B=B_R15_N5 N5/R15/take0.45 ;
 realshares_v2, RUN_START=2023-01-03, EVAL_END=2026-11-12, cap 5w,
 real fees + slip 0.002, lot 100, full_liquidate, exposure<=1,
 signal t-close / exec t+1-close, RS uses t and earlier only.
Output: results/r30_bt/verify_C5.json
Usage: .venv/bin/python research/verify_C5.py
"""
import hashlib
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))

import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, RUN_START, EVAL_END, MB

A_SWITCH_LOG = "    switch_log: List[Tuple[str, str]] = []"
A_NONLOCAL = "        nonlocal cash, total_cost, mode, state_take, state_n, state_exposure"
A_SIGDAY = "        sig_day = dates[sig_i]"
A_PICKS = "        picks = inp_cur.picks(sig_day, n_eff, exclude=exclude, factor=factor)"
A_FORCODE = "        for code in picks:"
A_EQROWS = "        eq_rows.append((day, cash + mv, mv, cash, len(pos)))"
A_META = "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode,"
A_SIG = "    exclude: Tuple[str, ...] = (),"
A_LOOPEND = "    loop_end = min(end_i, n_dates - 1)"
A_SWLOG = "            switch_log.append((str(sig_day.date()), mode))"

LOOKAHEAD = []


def _once(src, old, new, name):
    assert src.count(old) == 1, "anchor %s count=%d" % (name, src.count(old))
    return src.replace(old, new)


def build_ns_verify(bx, by_, bf, hyst, min_hold, confirm):
    assert bf > 0, "bf=0 deadlock"
    src = (ROOT / "research" / "switch_engine.py").read_text()
    for _name, _old in [("SWITCH_LOG", A_SWITCH_LOG), ("NONLOCAL", A_NONLOCAL),
                        ("SIGDAY", A_SIGDAY), ("PICKS", A_PICKS),
                        ("FORCODE", A_FORCODE), ("EQROWS", A_EQROWS),
                        ("META", A_META), ("SIG", A_SIG),
                        ("LOOPEND", A_LOOPEND), ("SWLOG", A_SWLOG)]:
        assert src.count(_old) == 1, _name
    eold = ("        desired = mode\n"
            "        if lock_mode is None and inp_b is not None and sig_i in sig_a:\n"
            "            ra = _rs(shadow_a, sig_i)\n"
            "            rb = _rs(shadow_b, sig_i)\n"
            "            if ra is not None and rb is not None:\n"
            '                desired = "A" if ra >= rb else "B"')
    assert src.count(eold) == 1, "EVAL_OLD"
    assert "searchsorted(dates[s_idx], side=" in src
    assert "if j < rs_lookback:" in src
    assert "ei = i + 1 + sig_lag" in src
    assert "picks = inp_cur.picks(sig_day, n_eff" in src
    assert "px = px_ffill_or_nan(mark, day, code)" in src
    assert "pending_stop" in src
    add = ("\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n"
           "    _brake_log: List = []\n    _BRAKE_X = %s\n    _BRAKE_Y = %s\n"
           "    _BRAKE_F = %s\n    _HYST = %s\n    _MIN_HOLD = %d\n    _CONFIRM = %d\n"
           "    _confirm_count = 0\n    _last_switch_i = -1000000000"
           % (bx, by_, bf, hyst, min_hold, confirm))
    src = _once(src, A_SWITCH_LOG, A_SWITCH_LOG + add, "SWITCH_LOG")
    src = _once(src, A_NONLOCAL, A_NONLOCAL + ", _brake, _brake_trough, _brake_peak, "
                "_brake_log, _confirm_count, _last_switch_i", "NONLOCAL")
    brake_eval = ("\n        tb_mv_pre = 0.0\n        for tb_cc, tb_p in pos.items():\n"
                  "            tb_px = px_ffill_or_nan(mark, day, tb_cc)\n"
                  "            if pd.isna(tb_px):\n"
                  "                tb_px = tb_p.entry_px\n"
                  "            tb_mv_pre += tb_p.shares * tb_px\n"
                  "        tb_eq_pre = cash + tb_mv_pre\n"
                  "        if tb_eq_pre > _brake_peak:\n"
                  "            _brake_peak = tb_eq_pre\n"
                  "        if not _brake and _brake_peak > 0 and "
                  "(_brake_peak - tb_eq_pre) / _brake_peak >= _BRAKE_X:\n"
                  "            _brake = True\n"
                  "            _brake_trough = tb_eq_pre\n"
                  "            _brake_log.append((str(day.date()), 'ON', "
                  "round(float((_brake_peak - tb_eq_pre) / _brake_peak) * 100, 2)))\n"
                  "        elif _brake:\n"
                  "            if tb_eq_pre < _brake_trough:\n"
                  "                _brake_trough = tb_eq_pre\n"
                  "            if _brake_trough > 0 and "
                  "tb_eq_pre >= _brake_trough * (1.0 + _BRAKE_Y):\n"
                  "                _brake = False\n"
                  "                _brake_log.append((str(day.date()), 'OFF', "
                  "round(float(tb_eq_pre / _brake_trough - 1) * 100, 2)))")
    brake_gated = ("\n        _brake_gate = brake_daily or (sig_i in sig_a) or (sig_i in sig_b)\n"
                   "        if _brake_gate:" + textwrap.indent(brake_eval, "    "))
    src = _once(src, A_SIGDAY, A_SIGDAY + brake_gated, "SIGDAY")
    skip_block = "\n        if not switching and set(picks) == set(pos):\n            return False"
    src = _once(src, A_PICKS, A_PICKS + skip_block, "PICKS-skip")
    src = _once(src, A_PICKS + skip_block,
                "        _ex = (exclude_a if mode == 'A' else exclude_b) if "
                "(exclude_a is not None or exclude_b is not None) else exclude\n"
                + A_PICKS.replace("exclude=exclude", "exclude=_ex") + skip_block,
                "PICKS-exclude")
    src = _once(src, A_SIG, A_SIG + "\n    exclude_a=None,\n    exclude_b=None,", "SIG-excl")
    src = _once(src, "    exclude_a=None,\n    exclude_b=None,",
                "    exclude_a=None,\n    exclude_b=None,\n    evalfreq='grid',\n    brake_daily=False,",
                "SIG-evalfreq")
    src = _once(src, A_FORCODE,
                "        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n" + A_FORCODE, "FORCODE")
    src = _once(src, A_EQROWS, A_EQROWS + "\n        if (cash + mv) > _brake_peak:\n"
                "            _brake_peak = cash + mv", "EQROWS")
    src = _once(src, A_META, A_META + " brake_log=_brake_log,", "META")
    execmap = ("\n    if evalfreq == 'daily':\n        for _t in range(loop_start, loop_end + 1):\n"
               "            _ei = _t + 1 + sig_lag\n            if _ei <= loop_end:\n"
               "                exec_map.setdefault(_ei, _t)")
    src = _once(src, A_LOOPEND, A_LOOPEND + execmap, "LOOPEND")
    enew = ("        desired = mode\n"
            "        _eval_daily = (evalfreq == 'daily')\n"
            "        if lock_mode is None and inp_b is not None and ((sig_i in sig_a) or _eval_daily):\n"
            "            ra = _rs(shadow_a, sig_i)\n"
            "            rb = _rs(shadow_b, sig_i)\n"
            "            if ra is not None and rb is not None:\n"
            "                if mode == 'A':\n"
            "                    _raw = 'B' if rb - ra >= _HYST else 'A'\n"
            "                else:\n"
            "                    _raw = 'A' if ra - rb >= _HYST else 'B'\n"
            "                if _raw == mode:\n"
            "                    _confirm_count = 0\n"
            "                else:\n"
            "                    _confirm_count += 1\n"
            "                    if _confirm_count >= _CONFIRM and (sig_i - _last_switch_i) >= _MIN_HOLD:\n"
            "                        desired = _raw")
    src = _once(src, eold, enew, "EVAL")
    src = _once(src, A_SWLOG, A_SWLOG + "\n            _last_switch_i = sig_i\n            _confirm_count = 0", "SWLOG")
    md5 = hashlib.md5(src.encode()).hexdigest()
    ns = {}
    exec(compile(src, "switch_engine_verify", "exec"), ns)
    return ns, md5
print("verify builder ready", flush=True)
print("RUN_START=%s EVAL_END=%s" % (RUN_START, EVAL_END), flush=True)

piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
print("first_sig=%s n_dates=%d" % (first_sig, len(dates)), flush=True)

inpA = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
inpB = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=20)
CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0,
          lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
          eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
CFG_B = dict(n=5, rebal=15, take=0.45, exposure=1.0)
print("building shadows A(N5/R20/take1.2) + B(N5/R15/take0.45)...", flush=True)
ra = pc.run_strategy(inpA, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
rb = pc.run_strategy(inpB, phase=0, **dict(CA, **CFG_B))
eqB0 = (rb.eq.iloc[:, 0] if isinstance(rb.eq, pd.DataFrame) else rb.eq).dropna()
print("shadows ready A trades=%d B trades=%d" % (len(ra.trades), len(rb.trades)), flush=True)


def annual_out(eq, res, tag, cfg):
    eq = eq.dropna()
    rets = eq.pct_change().dropna()
    shr = float(rets.mean() / rets.std() * (252 ** 0.5)) if float(rets.std()) > 0 else 0.0
    tot = float(eq.iloc[-1] / eq.iloc[0] - 1) * 100
    md = _mdd(eq) * 100
    out = {"tag": tag, "cfg": cfg, "eq_len": int(len(eq)),
           "eq_start": str(eq.index[0].date()), "eq_end": str(eq.index[-1].date()),
           "total": round(tot, 2), "mdd": round(md, 2),
           "calmar": round(tot / abs(md), 3) if md != 0 else None,
           "sharpe": round(shr, 3), "trades": int(len(res.trades)),
           "cost": round(float(res.meta["total_cost"]), 0),
           "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]),
           "switch_log": [list(x) for x in res.meta["switch_log"]],
           "brakes": len(res.meta.get("brake_log", [])) // 2,
           "brake_log": [list(x) for x in res.meta.get("brake_log", [])],
           "avg_exp": round(float(res.exposure.mean()), 4) if res.exposure is not None else None,
           "max_exp": round(float(res.exposure.max()), 4) if res.exposure is not None else None}
    prev_end = None
    for y in [2023, 2024, 2025, 2026]:
        sub = eq[eq.index.year == y]
        if len(sub) == 0:
            out[str(y)] = None
            continue
        sret = float(sub.iloc[-1] / sub.iloc[0] - 1) * 100
        out[str(y)] = round(sret, 2)
        out[str(y) + "_mdd"] = round(_mdd(sub) * 100, 2)
        out[str(y) + "_bars"] = int(len(sub))
        out[str(y) + "_yoy"] = round((float(sub.iloc[-1] / prev_end - 1) * 100) if prev_end is not None else sret, 2)
        prev_end = float(sub.iloc[-1])
    okpass = out["2024"] is not None and out["2024"] > 60 and out["2024_yoy"] > 60
    okpass = okpass and out["2025_yoy"] > 60 and out["2026_yoy"] > 60
    okpass = okpass and out["mdd"] > -30 and out["2024_mdd"] > -30
    okpass = okpass and out["2025_mdd"] > -30 and out["2026_mdd"] > -30
    out["pass"] = bool(okpass)
    out["margin"] = round(min(out["2024"] - 60, out["2024_yoy"] - 60, out["2025_yoy"] - 60,
                              out["2026_yoy"] - 60, out["mdd"] + 30, out["2024_mdd"] + 30,
                              out["2025_mdd"] + 30, out["2026_mdd"] + 30), 2)
    pe = float(eq.iloc[-1] - eq.iloc[0])
    out["cost_eff"] = round(pe / float(res.meta["total_cost"]), 2) if float(res.meta["total_cost"]) > 0 else None
    return out


_ns = {}


def get_ns(bx, by_, bf, hyst, mh, cf):
    k = (bx, by_, bf, hyst, mh, cf)
    if k not in _ns:
        _ns[k] = build_ns_verify(bx, by_, bf, hyst, mh, cf)
    return _ns[k]


def run_one(tag, rs=60, bx=0.18, by_=0.08, bf=0.6, hyst=0.0, mh=0, cf=1,
            evalfreq="grid", brake_daily=False, lock=None):
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inpB, cfg_b=CFG_B,
              shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB,
              evalfreq=evalfreq, brake_daily=brake_daily)
    for k, v in CA.items():
        if k != "exclude":
            KW[k] = v
    ns, md5 = get_ns(bx, by_, bf, hyst, mh, cf)
    res = ns["run_strategy_switch"](inpA, lock_mode=lock, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    cfg = dict(rs=rs, bx=bx, by_=by_, bf=bf, hyst=hyst, min_hold=mh, confirm=cf,
               evalfreq=evalfreq, brake_daily=brake_daily, lock=lock, engine_md5=md5)
    return annual_out(eq, res, tag, cfg), eq


CFGS = [
    dict(tag="C2_grid_mh0_bx0.15_by0.1_bf0.5", rs=60, bx=0.15, by_=0.1, bf=0.5,
         hyst=0.0, mh=0, cf=1, evalfreq="grid", brake_daily=False),
    dict(tag="C2_daily_h0.03_mh0_bx0.15_by0.05_bf0.5_bd", rs=60, bx=0.15, by_=0.05, bf=0.5,
         hyst=0.03, mh=0, cf=1, evalfreq="daily", brake_daily=True),
    dict(tag="C2_daily_h0.03_mh10_bx0.15_by0.05_bf0.5_bd", rs=60, bx=0.15, by_=0.05, bf=0.5,
         hyst=0.03, mh=10, cf=1, evalfreq="daily", brake_daily=True),
    dict(tag="C2_daily_h0.02_mh10_bx0.15_by0.1_bf0.5_bg", rs=60, bx=0.15, by_=0.1, bf=0.5,
         hyst=0.02, mh=10, cf=1, evalfreq="daily", brake_daily=False),
    dict(tag="C2_grid_mh0_bx0.15_by0.1_bf0.7", rs=60, bx=0.15, by_=0.1, bf=0.7,
         hyst=0.0, mh=0, cf=1, evalfreq="grid", brake_daily=False),
]

CMP_FIELDS = ["total", "mdd", "2024", "2024_yoy", "2024_mdd", "2025_yoy", "2025_mdd",
              "2026", "2026_yoy", "2026_mdd", "switches", "trades", "cost"]
def strict_verdict(o):
    checks = {
        "2024_slice>60": o["2024"] is not None and o["2024"] > 60,
        "2024_yoy>60": o["2024_yoy"] is not None and o["2024_yoy"] > 60,
        "2025_yoy>60": o["2025_yoy"] is not None and o["2025_yoy"] > 60,
        "2026_slice>60": o["2026"] is not None and o["2026"] > 60,
        "2026_yoy>60": o["2026_yoy"] is not None and o["2026_yoy"] > 60,
        "mdd>-30": o["mdd"] is not None and o["mdd"] > -30,
        "2024_mdd>-30": o["2024_mdd"] is not None and o["2024_mdd"] > -30,
        "2025_mdd>-30": o["2025_mdd"] is not None and o["2025_mdd"] > -30,
        "2026_mdd>-30": o["2026_mdd"] is not None and o["2026_mdd"] > -30,
    }
    dists = [o["2024"] - 60, o["2024_yoy"] - 60, o["2025_yoy"] - 60,
             o["2026"] - 60, o["2026_yoy"] - 60, o["mdd"] + 30,
             o["2024_mdd"] + 30, o["2025_mdd"] + 30, o["2026_mdd"] + 30]
    return all(checks.values()), checks, round(min(dists), 2)


def main():
    refB, _eB = run_one("REF_lockB_R15_nobrake_verify", bx=0.90, by_=0.50, bf=1.0,
                        evalfreq="grid", lock="B")
    direct_tot = float(eqB0.iloc[-1] / eqB0.iloc[0] - 1) * 100
    direct_mdd = float(_mdd(eqB0) * 100)
    parity = {
        "lockB_total": refB["total"], "directB_total": round(direct_tot, 2),
        "lockB_mdd": refB["mdd"], "directB_mdd": round(direct_mdd, 2),
        "lockB_trades": refB["trades"], "directB_trades": int(len(rb.trades)),
        "match": bool(abs(refB["total"] - direct_tot) < 1e-6 and refB["trades"] == len(rb.trades)),
    }
    print("PARITY lockB total %.2f vs direct %.2f | mdd %.2f vs %.2f | trades %d vs %d | match=%s"
          % (refB["total"], direct_tot, refB["mdd"], direct_mdd,
             refB["trades"], len(rb.trades), parity["match"]), flush=True)
    ref_by = {r["tag"]: r for r in json.load(open(ROOT / "results" / "r30_bt" / "search_C_stage2.json"))}
    rows = []
    for c in CFGS:
        tag = c.pop("tag")
        o, eq = run_one(tag, **c)
        r = ref_by.get(tag)
        assert r is not None, "stage2 missing tag: " + tag
        diff = {}
        for f in CMP_FIELDS:
            a, b = o.get(f), r.get(f)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                diff[f] = round(a - b, 6)
            else:
                diff[f] = 0 if a == b else "MISMATCH"
        sw_match = (o["switch_log"] == [list(x) for x in r["switch_log"]])
        br_match = (o["brake_log"] == [list(x) for x in r["brake_log"]])
        numdiffs = [abs(v) for v in diff.values() if isinstance(v, (int, float))]
        max_abs = round(max(numdiffs), 6) if numdiffs else 0
        ok, checks, mstrict = strict_verdict(o)
        sub26 = eq[eq.index.year == 2026]
        ddays = int((sub26.index[-1] - sub26.index[0]).days) + 1
        ann26 = round(((1 + o["2026"] / 100.0) ** (365.0 / ddays) - 1) * 100, 2)
        fragile = bool(ok and mstrict < 5.0)
        keep = ["tag", "total", "mdd", "2024", "2024_yoy", "2024_mdd", "2025_yoy",
                "2025_mdd", "2026", "2026_yoy", "2026_mdd", "switches", "trades",
                "cost", "switch_log", "brake_log", "pass", "margin", "eq_start",
                "eq_end", "eq_len", "mode", "brakes", "calmar", "sharpe"]
        refkeep = ["tag", "total", "mdd", "2024", "2024_yoy", "2024_mdd", "2025_yoy",
                   "2025_mdd", "2026", "2026_yoy", "2026_mdd", "switches", "trades",
                   "cost", "pass", "margin"]
        row = {
            "tag": tag,
            "verify": {k: o.get(k) for k in keep},
            "ref": {k: r.get(k) for k in refkeep},
            "diff": diff, "max_abs_diff": max_abs,
            "switch_log_match": bool(sw_match), "brake_log_match": bool(br_match),
            "strict_checks": checks, "verdict": "PASS" if ok else "FAIL",
            "fragile": fragile, "margin_strict": mstrict,
            "y2026_days": ddays, "y2026_annualized": ann26,
            "note2026": "2026 covers 01-01~11-12 only; slice must still exceed 60; annualized is reference",
        }
        print(json.dumps({"tag": tag, "max_abs_diff": max_abs, "sw": sw_match, "br": br_match,
                          "verdict": row["verdict"], "fragile": fragile,
                          "margin_strict": mstrict, "total": o["total"]}, ensure_ascii=False), flush=True)
        rows.append(row)
    out = {
        "meta": {
            "data": "data/pivots_2020_clean_realshares_v2.pkl",
            "RUN_START": str(RUN_START), "EVAL_END": str(EVAL_END),
            "capital": 50000.0, "slip": 0.002, "lot": 100, "cost_one_way": None,
            "stop": 0.25, "stop_exec": "next", "full_liquidate": True, "legacy_grid": False,
            "shadow_A": "MaxInputs(band=(0.02,0.30),gate60=-0.15,cut0.80,win40) N5/R20/take1.2/exp1.0",
            "shadow_B": "MaxInputs(band=(0.02,0.30),gate60=-0.15,cut0.80,win20) N5/R15/take0.45/exp1.0",
            "no_import_search": True,
            "first_sig": str(first_sig.date()),
        },
        "lookahead": [
            "RS uses shadow equity up to and including sig_i (searchsorted right-1, j>=rs_lookback=60).",
            "Default exec map: exec = signal+1+sig_lag (sig_lag=0 means t+1 close).",
            "picks(sig_day) uses signal-day factors; fills use exec-day mark prices.",
            "stop/take stop_exec=next: triggered at t close, executed t+1 close via pending_stop.",
            "hyst=0 degenerates to ra>=rb->A, identical to original EVAL_OLD.",
            "daily mode: evaluates daily but exec_map.setdefault keeps grid mapping; signal sig_i=i-1, more conservative.",
            "min_hold counts signal-index distance: 10 trading days in daily mode; always satisfied in grid mode.",
            "confirm=1: single trigger switches (subject to min_hold); counter resets when raw==mode.",
            "brake: evaluated on rebalance days (or daily if brake_daily) using same-day holdings mark-to-market;",
            "brake scales only new-buy alloc; bf>0 avoids deadlock.",
            "lot=100, real fees, slip 0.002 match stage2.",
        ],
        "parity": parity,
        "rows": rows,
    }
    p = ROOT / "results" / "r30_bt" / "verify_C5.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("saved " + str(p) + " rows=" + str(len(rows)), flush=True)


if __name__ == "__main__":
    main()
