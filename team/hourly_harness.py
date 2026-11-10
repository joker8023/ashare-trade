"""
team/hourly_harness.py — 小时级回测引擎(batch_013)
复用 team/harness.py 日线口径: 选股roster / 现实成本 / fresh指标。
小时层只替换执行离场: 信号bar收盘 -> 下一bar收盘执行; 止损优先;
停牌(=无有效bar或全零bar)跳过信号/顺延执行, 估值ffill。
防未来函数: 信号只用<=信号bar收盘信息; 放量均值只用信号bar之前20日同slot。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import harness as H

BASE = HERE.parent
HOURLY_DIR = BASE / "data" / "hourly_60m"

RULES = {
    "b013_H01_firsthour_buy":   dict(entry="h1030",      exits=[("daily_tp", 0.45)]),
    "b013_H02_hourly_tp45":     dict(entry="close",      exits=[("hourly_tp", 0.45)]),
    "b013_H03_hourly_trail12":  dict(entry="close",      exits=[("hourly_trail", 0.12)]),
    "b013_H04_hourly_fixstop8": dict(entry="close",      exits=[("hourly_fixstop", 0.08)]),
    "b013_H05_1030buy_eodsell": dict(entry="h1030",      exits=[("hourly_tp", 0.45)], late_tail=True),
    "b013_H06_gap_filter":      dict(entry="h1030_gap3", exits=[("daily_tp", 0.45)]),
    "b013_H07_vol_tp":          dict(entry="close",      exits=[("vol_tp", 3.0, 0.20)]),
    "b013_H08_eodstoploss":     dict(entry="close",      exits=[("daily_tp", 0.45), ("eod_stop", 0.05)]),
    "b013_H09_hourly_tp45_exp90": dict(entry="close",    exits=[("hourly_tp", 0.45)]),
    "b013_H10_combo":           dict(entry="h1030_gap3", exits=[("hourly_trail", 0.12), ("hourly_tp", 0.45)], late_tail=True),
}


def engine_md5() -> str:
    return hashlib.md5(Path(__file__).read_bytes()).hexdigest()


_HBARS: dict = {}


def hourly_bars(code: str):
    if code in _HBARS:
        return _HBARS[code]
    fp = HOURLY_DIR / (str(code).zfill(6) + ".csv")
    if not fp.exists():
        _HBARS[code] = None
        return None
    df = pd.read_csv(fp, parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["date"] = df["datetime"].dt.normalize()
    df["slot"] = df["datetime"].dt.strftime("%H:%M")
    df["valid"] = df["close"] > 0
    _HBARS[code] = df
    return df


def day_bars(df, day):
    if df is None:
        return []
    g = df[(df["date"] == day) & (df["valid"])]
    return [tuple(r) for r in g[["datetime", "open", "high", "low", "close", "volume", "slot"]].itertuples(index=False, name=None)]


def same_slot_mean_vol(df, day, slot, n=20):
    if df is None:
        return None
    past = df[(df["date"] < day) & (df["slot"] == slot) & (df["valid"])]
    past = past.groupby("date").tail(1)
    if len(past) < 5:
        return None
    return float(past["volume"].tail(n).mean())


def simulate_hourly(cfg: dict, rules: dict) -> dict:
    b = H.bundle()
    dates, nD = b.dates, b.n_dates
    c_ff = b.close_ff_np
    raw = b.close_np
    lim = b.limit_down_ratio
    codes = [str(c) for c in b.codes]

    sig_pos = H._grid_positions(b, cfg)
    if not sig_pos:
        raise ValueError("window no signal")
    sim_start = sig_pos[0]
    ev_end = b.pos.get(pd.Timestamp(cfg["window"]["eval_end"]))
    if ev_end is None:
        ev_end = int(np.searchsorted(dates, pd.Timestamp(cfg["window"]["eval_end"]), "right") - 1)
    ev_end = min(ev_end, nD - 1)

    exec_map: dict = {}
    for p in sig_pos:
        if p + 1 > ev_end:
            break
        exec_map[p + 1] = H.picks_at(b, cfg["selector"], p).tolist()

    expo_frac = float(cfg.get("portfolio", {}).get("exposure", 1.0))
    real = cfg["cost"]["mode"] == "realistic"
    lot = cfg["cost"]["lot_size"] if real else 1
    if not real:
        budget_pad = 1.0 + cfg["cost"]["one_way"]
    else:
        budget_pad = 1.0 + H.LOT_FEE["comm"] + H.LOT_FEE["transfer"] + cfg["cost"].get("slip", H.LOT_FEE["slip"])
    mw = cfg["selector"].get("max_weight")
    cash0 = float(cfg["cost"]["capital"]) if real else 1.0
    entry_kind = rules["entry"]
    exits = rules["exits"]
    gap_skip = 0.03 if entry_kind == "h1030_gap3" else None
    star = np.asarray(b.is_star)

    ld_day: dict = {}
    for pos in range(max(sim_start - 1, 0), ev_end + 1):
        s = set()
        for j in range(len(codes)):
            px = raw[pos, j]
            if np.isfinite(px) and pos > 0:
                prev = c_ff[pos - 1, j]
                if np.isfinite(prev) and px <= prev * lim[j] * 1.0005:
                    s.add(j)
        ld_day[pos] = s

    universe = set()
    for picks in exec_map.values():
        universe.update(picks)
    hbars = {j: hourly_bars(codes[j]) for j in universe}
    missing_hourly = sorted(codes[j] for j in universe if hbars[j] is None)

    last_px: dict = {}
    cash = cash0
    holds: dict = {}
    pending: dict = {}
    eq_path = np.full(nD, np.nan)
    cost_path = np.zeros(nD)
    expo_path = np.full(nD, np.nan)
    nhold_path = np.zeros(nD)
    starhold_path = np.zeros(nD)
    wmax_path = np.zeros(nD)
    trades: list = []
    rebal: list = []
    cost_total = 0.0
    n_trigger = 0
    n_deferred = 0
    n_ld = 0
    n_gapskip = 0
    hb_missing_fallback = 0

    def bars_of(pos, j):
        return day_bars(hbars.get(j), dates[pos])

    def prev_valid_close(j, pos):
        if j in last_px:
            return last_px[j]
        if pos > 0 and np.isfinite(c_ff[pos - 1, j]):
            return float(c_ff[pos - 1, j])
        return None

    def sell(j, pos, px, reason):
        nonlocal cash, cost_total
        h = holds.pop(j)
        pending.pop(j, None)
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

    def exec_price(pos, j, slot):
        bl = bars_of(pos, j)
        if bl:
            if slot == "h1030":
                return float(bl[0][4]), False
            return float(bl[-1][4]), False
        px = c_ff[pos, j]
        if np.isfinite(px) and float(px) > 0:
            return float(px), True
        return None, True

    for pos in range(sim_start, ev_end + 1):
        daybars = {j: bars_of(pos, j) for j in list(holds.keys())}
        for j in list(exec_map.get(pos, [])):
            if j not in daybars:
                daybars[j] = bars_of(pos, j)

        for j, meta in list(pending.items()):
            if j not in holds:
                pending.pop(j, None)
                continue
            if meta["dpos"] != pos:
                continue
            slot = meta["slot"]
            if not daybars.get(j):
                slot = "close"
            px, fb = exec_price(pos, j, slot)
            if px is None:
                meta["dpos"] = pos + 1
                n_deferred += 1
                continue
            if (not fb) and j in ld_day.get(pos, set()):
                meta["dpos"] = pos + 1
                n_deferred += 1
                n_ld += 1
                continue
            sell(j, pos, px, meta["reason"])

        if holds:
            for j in list(holds.keys()):
                if j not in holds:
                    continue
                h = holds[j]
                bl = daybars.get(j) or []
                dpx = c_ff[pos, j]
                if np.isfinite(dpx) and float(dpx) > h["high_d"]:
                    h["high_d"] = float(dpx)
                for bi, bar in enumerate(bl):
                    if j not in holds:
                        break
                    bc = float(bar[4])
                    if bc > h["high_h"]:
                        h["high_h"] = bc
                    if j in pending:
                        continue
                    sigs = []
                    for ex in exits:
                        kind = ex[0]
                        if kind == "hourly_tp" and bc >= h["px"] * (1.0 + ex[1]):
                            sigs.append((False, "take_profit_h"))
                        elif kind == "hourly_trail" and bc <= h["high_h"] * (1.0 - ex[1]):
                            sigs.append((True, "trailing_stop_h"))
                        elif kind == "hourly_fixstop" and bc <= h["px"] * (1.0 - ex[1]):
                            sigs.append((True, "fixed_stop_h"))
                        elif kind == "vol_tp":
                            if bc >= h["px"] * (1.0 + ex[2]):
                                mv = same_slot_mean_vol(hbars.get(j), dates[pos], bar[6])
                                if mv and float(bar[5]) >= mv * ex[1]:
                                    sigs.append((False, "vol_take_h"))
                        elif kind == "eod_stop" and bi == len(bl) - 1:
                            prevc = prev_valid_close(j, pos)
                            if prevc and bc / prevc - 1.0 <= -ex[1]:
                                sigs.append((True, "eod_stop_h"))
                    if any(ex[0] == "daily_tp" for ex in exits):
                        tp = next(ex[1] for ex in exits if ex[0] == "daily_tp")
                        if np.isfinite(dpx) and float(dpx) >= h["px"] * (1.0 + tp):
                            sigs.append((False, "take_profit"))
                    if sigs:
                        sigs.sort(key=lambda s: (not s[0], s[1]))
                        stop, reason = sigs[0]
                        n_trigger += 1
                        if reason == "take_profit":
                            pending[j] = dict(reason=reason, stop=stop, dpos=pos + 1, slot="close")
                        else:
                            # lead裁决(11-07): 一律next-bar惯例; 最后一根bar信号顺延次日首bar, 禁同bar成交
                            is_last = (bi == len(bl) - 1)
                            if is_last:
                                pending[j] = dict(reason=reason, stop=stop, dpos=pos + 1, slot="h1030")
                            else:
                                if bi + 1 < len(bl):
                                    if j in ld_day.get(pos, set()):
                                        pending[j] = dict(reason=reason, stop=stop, dpos=pos + 1, slot="h1030")
                                        n_deferred += 1
                                        n_ld += 1
                                    else:
                                        sell(j, pos, float(bl[bi + 1][4]), reason)
                                else:
                                    pending[j] = dict(reason=reason, stop=stop, dpos=pos + 1, slot="h1030")

        is_exec = pos in exec_map
        if is_exec:
            picks = exec_map[pos]
            pxmap, skip = {}, set()
            for j in picks:
                bl = daybars.get(j) or bars_of(pos, j)
                if entry_kind == "close":
                    if bl:
                        px, fb = float(bl[-1][4]), False
                    else:
                        px, fb = exec_price(pos, j, "close")
                else:
                    if bl:
                        px, fb = float(bl[0][4]), False
                        if gap_skip is not None:
                            op = float(bl[0][1])
                            pc = prev_valid_close(j, pos)
                            if pc and op / pc - 1.0 > gap_skip:
                                skip.add(j)
                                n_gapskip += 1
                                continue
                    else:
                        px, fb = exec_price(pos, j, "close")
                if px is None or px <= 0:
                    skip.add(j)
                    continue
                if fb:
                    hb_missing_fallback += 1
                pxmap[j] = px
            want = [j for j in picks if j not in skip]
            if set(want) != set(holds.keys()):
                for j in list(holds.keys()):
                    bl = daybars.get(j) or []
                    if entry_kind == "close" or not bl:
                        px, _fb = exec_price(pos, j, "close")
                    else:
                        px, _fb = float(bl[0][4]), False
                    if px is None or px <= 0:
                        continue
                    if j in ld_day.get(pos, set()):
                        if j not in pending:
                            pending[j] = dict(reason="rebalance_defer", stop=False,
                                              dpos=pos + 1, slot="close" if entry_kind == "close" else "h1030")
                            n_deferred += 1
                            n_ld += 1
                        continue
                    sell(j, pos, px, "rebalance")
                budget = cash * expo_frac
                k = len(want)
                if k:
                    w = min(1.0 / k, mw) if mw else 1.0 / k
                    per = budget / budget_pad * w
                    for j in want:
                        if j in holds:
                            continue
                        px = pxmap[j]
                        sh = per / px
                        if lot > 1:
                            sh = math.floor(sh / lot) * lot
                        if sh <= 0:
                            continue
                        notional = sh * px
                        fee = H._buy_cost(notional, cfg)
                        if notional + fee > cash:
                            sh = min(per, cash / budget_pad) / px
                            if lot > 1:
                                sh = math.floor(sh / lot) * lot
                            if sh <= 0:
                                continue
                            notional = sh * px
                            fee = H._buy_cost(notional, cfg)
                            if notional + fee > cash + 1e-12:
                                continue
                        cash -= notional + fee
                        cost_total += fee
                        holds[j] = dict(shares=sh, orig=sh, px=px, notional=notional, cost=fee,
                                        high_h=px, high_d=px, pos=pos)
            rebal.append(dict(pos=pos, one_way=0.0, on=True, n_picks=len(want),
                              n_base=int(cfg["selector"]["n"]), mw=mw,
                              dd_state=True, vol_scale=1.0))

        mv = 0.0
        wmax = 0.0
        for j in holds:
            bl = daybars.get(j) or []
            if bl:
                last = float(bl[-1][4])
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
                anchor_first_date=str(dates[sig_pos[0] + 1].date()) if sig_pos[0] + 1 < nD else "",
                n_gapskip=n_gapskip, hb_missing_fallback=hb_missing_fallback,
                missing_hourly=missing_hourly)


def exec_desc(spec_id: str, rules: dict) -> str:
    e = rules["entry"]
    en = {"close": "建仓t+1日收盘(尾bar)", "h1030": "建仓t+1首小时bar(10:30)收盘",
          "h1030_gap3": "建仓t+1首小时bar收盘, 开盘高开>3%整单跳过"}[e]
    xn = []
    for ex in rules["exits"]:
        k = ex[0]
        if k == "daily_tp":
            xn.append("日线TP%.0f%%(收盘触发->次日收盘)" % (ex[1] * 100))
        elif k == "hourly_tp":
            xn.append("小时TP%.0f%%(bar收盘触发->下一bar收盘)" % (ex[1] * 100))
        elif k == "hourly_trail":
            xn.append("小时跟踪止损%.0f%%(止损优先)" % (ex[1] * 100))
        elif k == "hourly_fixstop":
            xn.append("小时固定止损-%.0f%%" % (ex[1] * 100))
        elif k == "vol_tp":
            xn.append("放量止盈(同slot20日均量x%.0f+浮盈%.0f%%)" % (ex[1], ex[2] * 100))
        elif k == "eod_stop":
            xn.append("尾盘日内止损(14:55bar当日<=-%.0f%%->次日10:30)" % (ex[1] * 100))
    late = "末bar信号顺延次日首bar(lead裁决, 禁同bar)" if spec_id in ("b013_H05_1030buy_eodsell", "b013_H10_combo") else "末bar信号顺延次日首bar"
    return en + "; 离场:" + "+".join(xn) + "; " + late


def run_hourly_spec(spec: dict) -> tuple:
    t0 = time.time()
    rules = RULES[spec["id"]]
    cfg = H.normalize_spec(spec)
    sim = simulate_hourly(cfg, rules)
    m26 = H._window_metrics(sim, cfg["window"]["eval_start"], cfg["window"]["eval_end"], "2025-12-31", cfg)
    row = {
        "id": cfg["id"], "selector": cfg["selector"]["type"], "n": cfg["selector"]["n"],
        "R": cfg["rebalance_days"],
        "size_range": ("%.0f-%.0f%%" % (cfg["selector"]["size_range"][0] * 100,
                                        cfg["selector"]["size_range"][1] * 100)) if cfg["selector"]["size_range"] else "all",
        "exit": H._exit_label(cfg["exit"]), "stop_exec": cfg["exit"]["stop_exec"],
        "timing": cfg["timing"]["type"], "out_asset": cfg["timing"]["out_asset"],
        "phase": cfg["phase"], "anchor": cfg["rebalance_anchor"],
        "dd_action": "", "dd_trigger": None,
        "cost_mode": cfg["cost"]["mode"], "one_way": cfg["cost"]["one_way"],
        "exposure_target": cfg.get("portfolio", {}).get("exposure", 1.0),
        "max_weight": cfg["selector"].get("max_weight"),
        "staged_take": "", "vol_target": cfg.get("portfolio", {}).get("vol_target"),
        "n_sleeves": 1, "sleeve_offsets": "",
        "lot_size": cfg["cost"]["lot_size"], "capital": cfg["cost"]["capital"],
        "engine": "hourly_60min",
        "hourly_entry": rules["entry"],
        "hourly_exits": ";".join("%s:%s" % (ex[0], ",".join(str(x) for x in ex[1:])) for ex in rules["exits"]),
        "hourly_exec_desc": exec_desc(spec["id"], rules),
        "hourly_note": str((spec.get("execution") or {}).get("rule", ""))[:200],
        "n_gapskip": sim.get("n_gapskip", 0),
        "hb_missing_fallback": sim.get("hb_missing_fallback", 0),
    }
    for k in H.CORE_KEYS:
        row[k] = H._r(m26.get(k))
    row["periods_2026"] = "|".join("%.4f" % x for x in m26.get("periods", []))
    row["monthly_2026"] = "|".join("%s:%.4f" % kv for kv in m26.get("months", {}).items())
    cfg_f = H.with_overrides(cfg, window={"warmup_start": cfg["window"]["eval_start"]})
    sim_f = simulate_hourly(cfg_f, rules)
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


def run_batch_013(tag: str = "013"):
    specs = json.loads((BASE / "team" / "specs" / ("batch_" + tag + ".json")).read_text(encoding="utf-8"))
    t_start = time.time()
    md5_d, md5_h = H.harness_md5(), engine_md5()
    rows, errs, sims = [], [], {}
    for sp in specs:
        sid = sp["id"]
        t0 = time.time()
        try:
            if sp.get("runnable"):
                r = H.run_spec(sp, variants=("next", "real", "fresh"))
                r["engine"] = "daily"
                r["hourly_entry"] = "t+1close"
                r["hourly_exits"] = "daily"
                r["hourly_exec_desc"] = "日线引擎t+1收盘执行(基线对照)"
                r["hourly_note"] = str(sp.get("notes", ""))[:200]
                r["n_gapskip"] = 0
                r["hb_missing_fallback"] = 0
                sims[sid] = None
            else:
                r, sim, _simf = run_hourly_spec(sp)
                sims[sid] = sim
            r["group"] = sp.get("group", "")
            r["notes"] = sp.get("notes", "")
            r["batch"] = tag
            rows.append(r)
            print("  [%s] %s: fresh=%s mdd=%s n=%s %.1fs" % (tag, sid, r.get("fresh_total"), r.get("fresh_mdd"), r.get("fresh_n_trades"), time.time() - t0), flush=True)
        except Exception as e:
            rows.append(dict(id=sid, batch=tag, group=sp.get("group", ""), R=sp.get("rebalance_days"),
                             engine="error", status="error", error="%s: %s" % (type(e).__name__, e),
                             secs=round(time.time() - t0, 3)))
            errs.append(dict(id=sid, error="%s: %s" % (type(e).__name__, e), trace=traceback.format_exc()[-800:]))
    df = pd.DataFrame(rows)
    if "status" in df.columns:
        ok = df[df["status"] != "error"].copy()
    else:
        ok = df.copy()
    if len(ok):
        ok["_ft"] = pd.to_numeric(ok["fresh_total"], errors="coerce")
        ok = ok.sort_values("_ft", ascending=False).drop(columns=["_ft"])
        bad = df[df["status"] == "error"] if "status" in df.columns else df.iloc[0:0]
        df = pd.concat([ok, bad], ignore_index=True)
    elapsed = time.time() - t_start
    outdir = BASE / "team" / "runs"
    df.to_csv(outdir / ("batch_" + tag + "_results.csv"), index=False)
    if errs:
        pd.DataFrame(errs).to_csv(outdir / ("batch_" + tag + "_errors.csv"), index=False)
    for sid, sim in sims.items():
        if sim is None:
            continue
        try:
            (outdir / ("batch_" + tag + "_equity")).mkdir(exist_ok=True)
            pd.DataFrame({"date": sim["equity"].index, "equity": sim["equity"].to_numpy()}).to_csv(
                outdir / ("batch_" + tag + "_equity") / (sid + ".csv"), index=False)
            (outdir / ("batch_" + tag + "_trades")).mkdir(exist_ok=True)
            sim["trades"].to_csv(outdir / ("batch_" + tag + "_trades") / (sid + ".csv"), index=False)
        except Exception:
            pass
    bft = float("nan")
    bsel = ok[ok["id"].str.contains("BASELINE", na=False)] if "id" in ok.columns else ok.iloc[0:0]
    if len(bsel):
        bft = float(bsel["fresh_total"].iloc[0])
    gate = "PASS" if abs(bft - 0.9123) * 100 <= 0.5 else "FAIL超差"
    L = ["# Batch " + tag + " — 小时级R7 vs 日线基线", "",
         "- 生成时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         "- spec数: **%d** (错误 %d)" % (len(specs), len(errs)),
         "- 耗时: **%.1fs**" % elapsed,
         "- harness md5: " + md5_d, "- hourly引擎 md5: " + md5_h,
         "- 口径: fresh现实费率/5万100股; 日线基线=日线引擎t+1收盘; H=小时引擎(信号bar收盘->下一bar收盘, 止损优先)",
         "- 小时数据: data/hourly_60m 57股4bar/日(10:30/11:30/14:00/15:00)Baostock前复权; 全零bar按停牌处理(顺延+ffill)",
         "- H05/H10尾盘裁决(lead 11-07): 末bar信号一律顺延次日首bar执行, 禁同bar成交; 执行说明见hourly_exec_desc列",
         "- 基线复现: fresh_total=%.4f%% (目标+91.23%%±0.5pp) %s" % (bft * 100, gate), ""]
    L.append("## 全表(fresh_total排序)")
    L.append("")
    L.append("| id | engine | entry | fresh_total | fresh_mdd | wp | wm | wt | n_tr | top3 | cost% | total | mdd |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for _i, r in ok.iterrows():
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["id"], r.get("engine"), r.get("hourly_entry"), r.get("fresh_total"), r.get("fresh_mdd"),
            r.get("fresh_win_period"), r.get("fresh_win_month"), r.get("fresh_win_trade"), r.get("fresh_n_trades"),
            r.get("fresh_top3_pnl_share"), r.get("fresh_cost_paid_pct"), r.get("total"), r.get("mdd")))
    L.append("")
    L.append("## 小时引擎限制(引用数字时一起引用)")
    L.append("")
    for x in H.LIMITATIONS:
        L.append("- " + x)
    for x in ["小时bar=Baostock 60min前复权, 与日线pkl存在~0.1%级日内差异, H策略信号与执行同源(内部一致)。",
              "停牌日小时文件为全零bar, 按无bar处理: 跳过信号、顺延执行、估值ffill。",
              "跌停判定沿用日线口径(raw<=prev*lim*1.0005), 当日小时卖出顺延; 买入沿日线口径不另卡。",
              "H05/H10末bar信号顺延次日首bar(lead裁决11-07, 禁同bar成交); results中hourly_exec_desc单列说明。",
              "缺失小时文件的券若被选中则回退日收盘执行并计数(hb_missing_fallback)。"]:
        L.append("- " + x)
    (outdir / ("batch_" + tag + "_summary.md")).write_text(chr(10).join(L), encoding="utf-8")
    log = outdir / "run_log.md"
    with log.open("a", encoding="utf-8") as f:
        f.write("| %s | %s | %d | %.1fs | — | %d | hourly | %s |\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tag, len(specs), elapsed, len(errs), md5_h[:8]))
    print("[run_batch_013] done: %d specs, %.1fs, errors=%d, baseline fresh=%.4f%% %s" % (len(specs), elapsed, len(errs), bft * 100, gate))
    return dict(df=df, errs=errs, baseline_fresh=bft, gate=gate)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="013")
    a = ap.parse_args(argv)
    return run_batch_013(a.tag)


if __name__ == "__main__":
    main()

