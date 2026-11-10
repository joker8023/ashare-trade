"""team/lib/overnight014.py -- batch_014 G5 overnight engine.
R7 roster weekly refresh (t signal -> t+1 close buy), daily rolling close-buy / next-open-sell, zero intraday exposure.
Buy defers on limit-up/suspend; sell defers on limit-down/suspend (held overnight, recorded).
Caliber fresh/realistic/50000 capital/100 lots; row format aligned with harness.run_spec.
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import harness as H


def simulate_overnight(cfg):
    b = H.bundle()
    dates, nD = b.dates, b.n_dates
    c_ff = b.close_ff_np
    raw_c = b.close_np
    raw_o = b.df["open"].to_numpy(dtype=np.float32)
    lim = b.limit_down_ratio
    codes = [str(c) for c in b.codes]
    star = np.asarray(b.is_star)
    sig_pos = H._grid_positions(b, cfg)
    if not sig_pos:
        raise ValueError("window no signal")
    sim_start = sig_pos[0]
    ev_end = b.pos.get(pd.Timestamp(cfg["window"]["eval_end"]))
    if ev_end is None:
        ev_end = int(np.searchsorted(dates, pd.Timestamp(cfg["window"]["eval_end"]), "right") - 1)
    ev_end = min(ev_end, nD - 1)
    exec_map = {}
    for p in sig_pos:
        if p + 1 > ev_end:
            break
        exec_map[p + 1] = H.picks_at(b, cfg["selector"], p).tolist()
    exec_days = sorted(exec_map.keys())
    expo_frac = float(cfg.get("portfolio", {}).get("exposure", 1.0))
    real = cfg["cost"]["mode"] == "realistic"
    lot = cfg["cost"]["lot_size"] if real else 1
    if not real:
        budget_pad = 1.0 + cfg["cost"]["one_way"]
    else:
        budget_pad = 1.0 + H.LOT_FEE["comm"] + H.LOT_FEE["transfer"] + cfg["cost"].get("slip", H.LOT_FEE["slip"])
    mw = cfg["selector"].get("max_weight")
    cash0 = float(cfg["cost"]["capital"]) if real else 1.0
    cash = cash0
    holds = {}
    pending_buy = {}
    eq_path = np.full(nD, np.nan)
    cost_path = np.zeros(nD)
    expo_path = np.full(nD, np.nan)
    nhold_path = np.zeros(nD)
    starhold_path = np.zeros(nD)
    wmax_path = np.zeros(nD)
    trades = []
    rebal = []
    cost_total = 0.0
    n_trigger = 0
    n_deferred = 0
    n_ld = 0
    last_px = {}
    def up_ratio(j):
        return 2.0 - float(lim[j])

    def sell(j, pos, px, reason):
        nonlocal cash, cost_total
        h = holds.pop(j)
        notional = h["shares"] * px
        fee = H._sell_cost(notional, cfg)
        cash += notional - fee
        cost_total += fee
        pnl = notional - fee - h["notional"] - h["cost"]
        base = h["notional"] + h["cost"]
        trades.append(dict(code=codes[j], entry_pos=h["pos"], exit_pos=pos,
                           entry_date=dates[h["pos"]], exit_date=dates[pos],
                           shares=h["shares"], entry_px=h["px"], exit_px=px,
                           notional=h["notional"], cost=h["cost"] + fee, pnl=pnl,
                           ret=pnl / base if base > 0 else 0.0, reason=reason))
        return notional

    def roster_of(pos):
        r = None
        for e in exec_days:
            if e <= pos:
                r = exec_map[e]
            else:
                break
        return r

    def try_buy(j, pos, roster):
        nonlocal cash, cost_total
        cpx = float(c_ff[pos, j])
        if cpx <= 0:
            return 0.0
        budget = cash * expo_frac
        k = max(len(roster), 1)
        w = min(1.0 / k, mw) if mw else 1.0 / k
        per = budget / budget_pad * w
        sh = per / cpx
        if lot > 1:
            sh = math.floor(sh / lot) * lot
        if sh <= 0:
            return 0.0
        notional = sh * cpx
        fee = H._buy_cost(notional, cfg)
        if notional + fee > cash + 1e-12:
            return 0.0
        cash -= notional + fee
        cost_total += fee
        holds[j] = dict(shares=sh, orig=sh, px=cpx, notional=notional, cost=fee, pos=pos)
        return notional

    for pos in range(sim_start, ev_end + 1):
        sold_nb = 0.0
        for j in list(holds.keys()):
            opx = raw_o[pos, j]
            prevc = c_ff[pos - 1, j] if pos > 0 and np.isfinite(c_ff[pos - 1, j]) else None
            if not np.isfinite(opx) or float(opx) <= 0:
                n_deferred += 1
                continue
            if prevc and float(opx) <= float(prevc) * float(lim[j]) * 1.0005:
                n_deferred += 1
                n_ld += 1
                continue
            sold_nb += sell(j, pos, float(opx), "overnight")
            n_trigger += 1
        roster = roster_of(pos)
        bought_nb = 0.0
        if roster:
            for j in roster:
                if j in holds:
                    continue
                if not np.isfinite(raw_c[pos, j]):
                    pending_buy[j] = pos
                    n_deferred += 1
                    continue
                prevc = c_ff[pos - 1, j] if pos > 0 and np.isfinite(c_ff[pos - 1, j]) else None
                if prevc and float(raw_c[pos, j]) >= float(prevc) * up_ratio(j) * 0.9995:
                    pending_buy[j] = pos
                    n_deferred += 1
                    n_ld += 1
                    continue
                pending_buy.pop(j, None)
                bought_nb += try_buy(j, pos, roster)
        for j in list(pending_buy.keys()):
            if j in holds:
                pending_buy.pop(j, None)
                continue
            if not np.isfinite(raw_c[pos, j]):
                continue
            prevc = c_ff[pos - 1, j] if pos > 0 and np.isfinite(c_ff[pos - 1, j]) else None
            if prevc and float(raw_c[pos, j]) >= float(prevc) * up_ratio(j) * 0.9995:
                continue
            rn = roster_of(pos) or []
            if j not in rn:
                pending_buy.pop(j, None)
                continue
            pending_buy.pop(j, None)
            bought_nb += try_buy(j, pos, rn)
        mv = 0.0
        wmax = 0.0
        for j in holds:
            if np.isfinite(raw_c[pos, j]):
                last = float(raw_c[pos, j])
                last_px[j] = last
            elif j in last_px:
                last = last_px[j]
            else:
                px = c_ff[pos, j]
                last = float(px) if np.isfinite(px) else 0.0
                if last > 0:
                    last_px[j] = last
            v = holds[j]["shares"] * last
            mv += v
            wmax = max(wmax, v)
        eq = cash + mv
        eq_path[pos] = eq
        cost_path[pos] = cost_total
        expo_path[pos] = mv / eq if eq > 1e-12 else 0.0
        nhold_path[pos] = len(holds)
        starhold_path[pos] = sum(1 for j in holds if bool(star[j]))
        wmax_path[pos] = wmax / eq if eq > 1e-12 else 0.0
        eqa = eq if eq > 1e-12 else 1e-12
        rebal.append(dict(pos=pos, one_way=(sold_nb + bought_nb) / 2.0 / eqa, on=True,
                          n_picks=len(roster) if roster else 0, n_base=int(cfg["selector"]["n"]), mw=mw,
                          dd_state=True, vol_scale=1.0))
    if cash0 != 1.0:
        eq_path = eq_path / cash0
        cost_path = cost_path / cash0
    sl = slice(sim_start, ev_end + 1)
    eq_s = pd.Series(eq_path[sl], index=dates[sl])
    tr = pd.DataFrame(trades)
    if len(tr):
        tr = tr.sort_values(["exit_pos", "code"]).reset_index(drop=True)
    else:
        tr = pd.DataFrame(columns=["code", "entry_pos", "exit_pos", "entry_date", "exit_date",
                                   "shares", "entry_px", "exit_px", "notional", "cost", "pnl", "ret", "reason"])
    return dict(cfg=cfg, equity=eq_s, eq_full=eq_path, cost_full=cost_path,
                expo_full=expo_path, nhold_full=nhold_path, starhold_full=starhold_path,
                wmax_full=wmax_path, trades=tr, rebal=rebal, sim_start=sim_start, ev_end=ev_end,
                sig_pos=sig_pos, exec_map=exec_map, n_trigger=n_trigger,
                n_deferred=n_deferred, n_limit_down=n_ld, n_staged=0,
                staged_pnl_total=0.0,
                anchor_first_date=str(dates[sig_pos[0] + 1].date()) if sig_pos[0] + 1 < nD else "")


def run_overnight_spec(spec):
    t0 = time.time()
    cfg = H.normalize_spec(spec)
    sim = simulate_overnight(cfg)
    m26 = H._window_metrics(sim, cfg["window"]["eval_start"], cfg["window"]["eval_end"], "2025-12-31", cfg)
    row = {
        "id": cfg["id"], "selector": cfg["selector"]["type"], "n": cfg["selector"]["n"],
        "R": cfg["rebalance_days"],
        "size_range": ("%.0f-%.0f%%" % (cfg["selector"]["size_range"][0] * 100,
                                        cfg["selector"]["size_range"][1] * 100)) if cfg["selector"]["size_range"] else "all",
        "exit": "overnight", "stop_exec": cfg["exit"]["stop_exec"],
        "timing": cfg["timing"]["type"], "out_asset": cfg["timing"]["out_asset"],
        "phase": cfg["phase"], "anchor": cfg["rebalance_anchor"],
        "dd_action": "", "dd_trigger": None,
        "cost_mode": cfg["cost"]["mode"], "one_way": cfg["cost"]["one_way"],
        "exposure_target": cfg.get("portfolio", {}).get("exposure", 1.0),
        "max_weight": cfg["selector"].get("max_weight"),
        "staged_take": "", "vol_target": cfg.get("portfolio", {}).get("vol_target"),
        "n_sleeves": 1, "sleeve_offsets": "",
        "lot_size": cfg["cost"]["lot_size"], "capital": cfg["cost"]["capital"],
        "engine": "overnight_open",
        "hourly_entry": "t+1close",
        "hourly_exits": "overnight:t+2open",
        "hourly_exec_desc": "overnight: R7 weekly roster, daily close-buy/next-open-sell, zero intraday; buy defers limit-up/suspend, sell defers limit-down/suspend",
        "hourly_note": str((spec.get("execution") or {}).get("rule", ""))[:200],
        "n_gapskip": 0,
        "hb_missing_fallback": 0,
    }
    for k in H.CORE_KEYS:
        row[k] = H._r(m26.get(k))
    row["periods_2026"] = "|".join("%.4f" % x for x in m26.get("periods", []))
    row["monthly_2026"] = "|".join("%s:%.4f" % kv for kv in m26.get("months", {}).items())
    cfg_f = H.with_overrides(cfg, window={"warmup_start": cfg["window"]["eval_start"]})
    sim_f = simulate_overnight(cfg_f)
    mf = H._window_metrics(sim_f, cfg_f["window"]["eval_start"], cfg_f["window"]["eval_end"], "2025-12-31", cfg_f)
    for k, name in (("total", "fresh_total"), ("mdd", "fresh_mdd"),
                    ("win_period", "fresh_win_period"), ("win_month", "fresh_win_month"),
                    ("win_trade", "fresh_win_trade"), ("n_trades", "fresh_n_trades"),
                    ("calmar", "fresh_calmar_ann"), ("top3_pnl_share", "fresh_top3_pnl_share"),
                    ("max_single_name_pnl_share", "fresh_top1_pnl_share"),
                    ("exposure", "fresh_exposure"), ("ann", "fresh_ann"),
                    ("n_periods", "fresh_n_periods"), ("n_months", "fresh_n_months"),
                    ("win_period_loose", "fresh_win_period_loose"),
                    ("block30_win", "fresh_block30_win"), ("n_hold_avg", "fresh_n_hold_avg"),
                    ("n_picks_avg", "fresh_n_picks_avg"), ("n_distinct_names", "fresh_n_distinct"),
                    ("vol", "fresh_vol"), ("sharpe", "fresh_sharpe"),
                    ("cost_paid_pct", "fresh_cost_paid_pct"),
                    ("last_partial_ret", "fresh_last_partial_ret")):
        row[name] = H._r(mf.get(k))
    row["fresh_calmar"] = row["fresh_calmar_ann"]
    _t, _m = mf.get("total"), mf.get("mdd")
    row["fresh_calmar_total_over_mdd"] = H._r(float(_t) / abs(float(_m))) if _t is not None and _m not in (None, 0) else None
    row["fresh_calmar_raw"] = row["fresh_calmar_total_over_mdd"]
    row["fresh_monthly"] = "|".join("%s:%.4f" % kv for kv in mf.get("months", {}).items())
    row["fresh_periods"] = "|".join("%.4f" % x for x in mf.get("periods", []))
    row["fresh_2026"] = row["fresh_total"]
    row["fresh_2026_win_period"] = row["fresh_win_period"]
    row["fresh_2026_mdd"] = row["fresh_mdd"]
    for w in ("2025", "2025h2", "2024"):
        mw = H._window_metrics(sim, H.WINDOWS[w][0], H.WINDOWS[w][1], H.WINDOWS[w][2], cfg)
        for k in ("total", "ann", "mdd", "win_period", "n_periods", "win_trade", "n_trades", "win_month", "last_partial_ret"):
            row[k + "_" + w] = H._r(mw.get(k))
    row["anchor_first_date"] = sim.get("anchor_first_date", "")
    row["total_same_close"] = None
    row["equity_end"] = H._r(float(sim["equity"].iloc[-1]))
    row["sig_days"] = len(sim["sig_pos"])
    row["secs"] = round(time.time() - t0, 3)
    row["status"] = "ok"
    row["error"] = ""
    row["tier"] = ""
    return row, sim, sim_f



