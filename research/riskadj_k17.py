#!/usr/bin/env python3
"""K17 risk-adjusted shadow-RS comparison (new file only).

Caliber verbatim M07 (ph0 / RUN_START=2023-01-03 / EVAL_END=2026-11-12 / 50k /
real fee (cost_one_way=None) / slip=0.002 / lot=100 / legacy_grid=False /
full_liquidate=True / stop_exec=next / MB exclusion / native amihud_60 legs /
A band=(0.02,0.30) gate60=-0.15 cut=0.80 win=40 take=1.2 n=5 rebal=20 exp=1.0;
B band=(0.05,0.30) gate60=-1.0 cut=0.80 win=20 take=0.8 n=4 rebal=30 exp=0.9;
brake bx0.18/by0.08/bf0.6) EXCEPT the single comparison-scale dimension:
the switch rule still fires ONLY on A-grid signal days, still compares the
two shadow equities over the same trailing-60 window with t-and-before data
only, still executes flips at t+1 through the native chain -- but the raw
trailing return ra>=rb is replaced by a risk-adjusted score:

  sharpe   : mean(daily ret, trailing 60) / std(daily ret, trailing 60)
  calmar   : trailing-60 point return / trailing-60 max-drawdown depth
             (same point-to-point numerator as native RS)
  downside : trailing-60 point return / downside deviation
             (sqrt(mean(min(r,0)^2)) over trailing-60 daily rets)

Higher score wins (A if ma >= mb else B), mirroring native ra >= rb -> A.
Guards: zero-vol / zero-drawdown map to signed 1e9 (positive score wins,
negative loses, exact-zero ties to A like native equality). No lookahead:
every slice is eq.iloc[<=j] with j = searchsorted(sig_day, right)-1.

 audit helper metric_k17(eq_truncated_through_t, metric) exposes the same
 scoring on a truncated series for the truncation cross-check.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

AA = "    switch_log: List[Tuple[str, str]] = []"
BB = "        nonlocal cash, total_cost, mode, state_take, state_n, state_exposure"
CC = "        sig_day = dates[sig_i]"
DD = "        picks = inp_cur.picks(sig_day, n_eff, exclude=exclude, factor=factor)"
EE = "        for code in picks:"
FF = "        eq_rows.append((day, cash + mv, mv, cash, len(pos)))"
GG = "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode,"
SIG = "    exclude: Tuple[str, ...] = (),"
PICKLINE = "        picks = inp_cur.picks(sig_day, n_eff, exclude=exclude, factor=factor)"
DESIRED_ANCHOR = "                desired = "

OLD_RS = (
    "    def _rs(eq_s, s_idx: int):\n"
    "        if eq_s is None:\n"
    "            return None\n"
    "        j = int(eq_s.index.searchsorted(dates[s_idx], side=\"right\") - 1)\n"
    "        if j < rs_lookback:\n"
    "            return None\n"
    "        return float(eq_s.iloc[j] / eq_s.iloc[j - rs_lookback] - 1.0)"
)

RS_RISK_TMPL = (
    "    def _rs(eq_s, s_idx: int):\n"
    "        if eq_s is None:\n"
    "            return None\n"
    "        j = int(eq_s.index.searchsorted(dates[s_idx], side=\"right\") - 1)\n"
    "        if j < rs_lookback:\n"
    "            return None\n"
    "        _W = int(rs_lookback)\n"
    "        _w = eq_s.iloc[j - _W:j + 1].astype(float)\n"
    "        _r = (_w.iloc[1:].to_numpy() / _w.iloc[:-1].to_numpy() - 1.0)\n"
    "        _R = float(_w.iloc[-1] / _w.iloc[0] - 1.0)\n"
    "        _MET = \"%s\"\n"
    "        if _MET == \"sharpe\":\n"
    "            _m = float(np.mean(_r))\n"
    "            _s = float(np.std(_r, ddof=1)) if len(_r) > 1 else 0.0\n"
    "            if _s < 1e-12:\n"
    "                return 1e9 if _m > 0 else (-1e9 if _m < 0 else 0.0)\n"
    "            return float(_m / _s)\n"
    "        if _MET == \"calmar\":\n"
    "            _dd = float((_w / _w.cummax() - 1.0).min())\n"
    "            _a = -_dd\n"
    "            if _a < 1e-12:\n"
    "                return 1e9 if _R > 0 else (0.0 if _R == 0 else -1e9)\n"
    "            return float(_R / _a)\n"
    "        if _MET == \"downside\":\n"
    "            _d = float(np.sqrt(np.mean(np.minimum(_r, 0.0) ** 2)))\n"
    "            if _d < 1e-12:\n"
    "                return 1e9 if _R > 0 else (0.0 if _R == 0 else -1e9)\n"
    "            return float(_R / _d)\n"
    "        raise ValueError(\"unknown rs metric\" + str(_MET))"
)

BRAKE_EVAL = (
    "\n        tb_mv_pre = 0.0\n        for tb_cc, tb_p in pos.items():\n"
    "            tb_px = px_ffill_or_nan(mark, day, tb_cc)\n"
    "            if pd.isna(tb_px):\n"
    "                tb_px = tb_p.entry_px\n"
    "            tb_mv_pre += tb_p.shares * tb_px\n"
    "        tb_eq_pre = cash + tb_mv_pre\n"
    "        if tb_eq_pre > _brake_peak:\n"
    "            _brake_peak = tb_eq_pre\n"
    "        if not _brake and _brake_peak > 0 and (_brake_peak - tb_eq_pre) / _brake_peak >= _BRAKE_X:\n"
    "            _brake = True\n"
    "            _brake_trough = tb_eq_pre\n"
    "            _brake_log.append((str(day.date()), 'ON', round(float((_brake_peak - tb_eq_pre) / _brake_peak) * 100, 2)))\n"
    "        elif _brake:\n"
    "            if tb_eq_pre < _brake_trough:\n"
    "                _brake_trough = tb_eq_pre\n"
    "            if _brake_trough > 0 and tb_eq_pre >= _brake_trough * (1.0 + _BRAKE_Y):\n"
    "                _brake = False\n"
    "                _brake_log.append((str(day.date()), 'OFF', round(float(tb_eq_pre / _brake_trough - 1) * 100, 2)))"
)
SKIP_BLOCK = "\n        if not switching and set(picks) == set(pos):\n            return False"


def build_ns_k17(metric="sharpe", bx=0.18, by_=0.08, bf=0.6):
    """Switch engine identical to sweep_beat_h1_v4.build_ns except the _rs
    comparison scale. metric in {"sharpe","calmar","downside"}."""
    assert metric in ("sharpe", "calmar", "downside"), metric
    src = (ROOT / "research" / "switch_engine.py").read_text()

    def _once(old, new):
        nonlocal src
        assert src.count(old) == 1, (old[:60], src.count(old))
        src = src.replace(old, new)

    add = (
        "\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n"
        "    _brake_log: List = []\n    _BRAKE_X = %s\n    _BRAKE_Y = %s\n"
        "    _BRAKE_F = %s" % (bx, by_, bf)
    )
    _once(AA, AA + add)
    _once(BB, BB + ", _brake, _brake_trough, _brake_peak, _brake_log")
    _once(CC, CC + BRAKE_EVAL)
    assert src.count(OLD_RS) == 1, "OLD_RS anchor drift"
    src = src.replace(OLD_RS, RS_RISK_TMPL % metric)
    # desired comparison stays verbatim ("A" if ra >= rb else "B"); only the
    # scale of ra/rb changed from raw return to risk-adjusted score.
    assert src.count(DESIRED_ANCHOR) >= 1
    _once(DD, DD + SKIP_BLOCK)
    _once(
        PICKLINE,
        "        _ex = (exclude_a if mode == 'A' else exclude_b) if (exclude_a is not None or exclude_b is not None) else exclude\n"
        + PICKLINE.replace("exclude=exclude", "exclude=_ex"),
    )
    _once(SIG, SIG + "\n    exclude_a=None,\n    exclude_b=None,")
    _once(EE, "        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n" + EE)
    _once(FF, FF + "\n        if (cash + mv) > _brake_peak:\n            _brake_peak = cash + mv")
    _once(
        GG,
        "        rebalance_snapshots=rebal_snap, switch_log=switch_log, final_mode=mode, brake_log=_brake_log,",
    )
    ns = {}
    exec(compile(src, "switch_engine_k17_" + metric, "exec"), ns)
    return ns


def metric_k17(eq_truncated, metric="sharpe", lookback=60):
    """Audit helper: score the tail of a t-truncated shadow equity series."""
    import numpy as np

    assert metric in ("sharpe", "calmar", "downside"), metric
    w = eq_truncated.astype(float).iloc[-(lookback + 1):]
    assert len(w) == lookback + 1, len(w)
    r = w.iloc[1:].to_numpy() / w.iloc[:-1].to_numpy() - 1.0
    R = float(w.iloc[-1] / w.iloc[0] - 1.0)
    if metric == "sharpe":
        m, s = float(np.mean(r)), float(np.std(r, ddof=1))
        if s < 1e-12:
            return 1e9 if m > 0 else (-1e9 if m < 0 else 0.0)
        return float(m / s)
    if metric == "calmar":
        dd = float((w / w.cummax() - 1.0).min())
        a = -dd
        if a < 1e-12:
            return 1e9 if R > 0 else (0.0 if R == 0 else -1e9)
        return float(R / a)
    d = float(np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)))
    if d < 1e-12:
        return 1e9 if R > 0 else (0.0 if R == 0 else -1e9)
    return float(R / d)
