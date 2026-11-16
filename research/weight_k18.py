#!/usr/bin/env python3
"""K18 rank-weight module (new file only): sorting-based intra-leg position weighting.

Point of intervention (read-only finding, no edit to engine files):
  * team/audit/prior_check.py run_strategy  ~L314-316:
      alloc = equity_now * exposure / slots            # <-- equal-weight hard point
  * research/switch_engine.py do_rebalance ~L213-215:
      alloc = equity_now * state_exposure / slots      # <-- equal-weight hard point
  In both, the buy loop then does sh = alloc/px (lot-rounded). Everything else
  (signal t / exec t+1, full_liquidate, stop/take next-close, real fee +
  slip=0.002, lot=100, brake, RS switch) is untouched.

Weight schemes (t-and-before info ONLY):
  * rank_linear : picks are already sorted desc by signal-day factor value
                  (MaxInputs.picks -> amihud_60 desc). Rank r=1..N gets
                  w = (N-r+1)/sum. Rank-only, value-blind.
  * amihud_prop: w_i = fac_i / sum(fac) with fac = signal-day amihud_60
                  values of the picked codes (all >0 by construction;
                  guarded: non-positive / NaN fall back to equal weight).
  * rank_sqrt   : implemented for completeness but NOT piloted (K18 picks
                  2 of 3: rank_linear + amihud_prop, the two most distinct
                  corners; sqrt interpolates between them).
  Weights are normalized to the leg exposure (sum w = 1, then alloc_i =
  equity*exposure*w_i), lot-rounded with the verbatim cash-fallback chain.
  Shadow curves and live switch use the SAME weighting function, so the RS
  signal and the traded portfolio see identical sizing logic (no mismatch).

No lookahead: weights read fac.loc[sig_day] only (signal-day snapshot, the
same info set as picks). Execution stays on the native t+1 exec_map.
Long-only, no leverage (exposure<=1 preserved; weights only split the leg).
"""
from pathlib import Path
import math

ROOT = Path(__file__).resolve().parents[1]

WEIGHT_MODES = ("rank_linear", "rank_sqrt", "amihud_prop")
K18_PILOT_MODES = ("rank_linear", "amihud_prop")  # 3-pick-2: distinct corners


def compute_weights(fac_vals, mode):
    """fac_vals: list of signal-day factor values in picks (rank) order.
    Returns normalized weights summing to 1. Pure function (no data access)."""
    n = len(fac_vals)
    if n == 0:
        return []
    if n == 1:
        return [1.0]
    if mode == "rank_linear":
        raw = [float(n - i) for i in range(n)]
    elif mode == "rank_sqrt":
        raw = [math.sqrt(float(n - i)) for i in range(n)]
    elif mode == "amihud_prop":
        raw = []
        for v in fac_vals:
            try:
                f = float(v)
            except Exception:
                f = float("nan")
            raw.append(f if (f == f and f > 0) else 0.0)
        if sum(raw) <= 0:
            raw = [1.0] * n  # degenerate fallback: equal weight
    else:
        raise ValueError("unknown weight mode %r" % (mode,))
    s = sum(raw)
    return [x / s for x in raw]


# ---- source-rewrite anchors (verbatim from engine files) ----
_SW_ALLOC_OLD = """        if weight_cap is not None and weight_cap > 0 and not rank_fill:
            alloc = equity_now * state_exposure * min(1.0 / slots, weight_cap)
        else:
            alloc = equity_now * state_exposure / slots
        for code in picks:"""

_SW_LOOP_A = "                sh = int(alloc / px // lot) * lot"
_SW_LOOP_B = "                sh = alloc / px"
_SW_SNAP = "                               alloc_per_slot=float(alloc), picked=int(len(picks))))"

_PC_ALLOC_OLD = """        if weight_cap is not None and weight_cap > 0 and not rank_fill:
            alloc = equity_now * exposure * min(1.0 / slots, weight_cap)
        else:
            alloc = equity_now * exposure / slots
        for code in picks:"""

_PC_SNAP = "                               alloc_per_slot=float(alloc), picked=int(len(picks))))"


def _weight_block(prefix):
    # prefix: "state_exposure" (switch) or "exposure" (single-leg)
    return (
        "        # ---- K18 rank-weight (t-and-before only) ----\n"
        "        _w_expo = equity_now * " + prefix + "\n"
        "        _w_facsrc = inp_cur.amihud60 if factor == \"amihud_60\" else inp_cur.amihud\n"
        "        _w_vals = list(_w_facsrc.loc[sig_day, picks])\n"
        "        _w_mode = _WEIGHT_MODE\n"
        "        _w_n = len(picks)\n"
        "        _w_raw = None\n"
        "        import math as _w_math\n"
        "        if _w_mode == \"rank_linear\":\n"
        "            _w_raw = [float(_w_n - _w_i) for _w_i in range(_w_n)]\n"
        "        elif _w_mode == \"rank_sqrt\":\n"
        "            _w_raw = [_w_math.sqrt(float(_w_n - _w_i)) for _w_i in range(_w_n)]\n"
        "        elif _w_mode == \"amihud_prop\":\n"
        "            _w_raw = []\n"
        "            for _w_v in _w_vals:\n"
        "                try:\n"
        "                    _w_f = float(_w_v)\n"
        "                except Exception:\n"
        "                    _w_f = float(\"nan\")\n"
        "                _w_raw.append(_w_f if (_w_f == _w_f and _w_f > 0) else 0.0)\n"
        "            if sum(_w_raw) <= 0:\n"
        "                _w_raw = [1.0] * _w_n\n"
        "        else:\n"
        "            raise ValueError(\"bad K18 weight mode %r\" % (_w_mode,))\n"
        "        _w_s = sum(_w_raw)\n"
        "        _w_alloc = {cd: _w_expo * _w_x / _w_s for cd, _w_x in zip(picks, _w_raw)}\n"
        "        _w_mean = _w_expo / _w_n\n"
        "        for code in picks:"
    )


def _patch_switch_source(weight_mode):
    assert weight_mode in WEIGHT_MODES, weight_mode
    src = (ROOT / "research" / "switch_engine.py").read_text()
    assert src.count(_SW_ALLOC_OLD) == 1, ("switch alloc anchor", src.count(_SW_ALLOC_OLD))
    src = src.replace(_SW_ALLOC_OLD, _weight_block("state_exposure"))
    assert src.count(_SW_LOOP_A) == 1, ("loopA", src.count(_SW_LOOP_A))
    src = src.replace(_SW_LOOP_A, "                sh = int(_w_alloc[code] / px // lot) * lot")
    assert src.count(_SW_LOOP_B) == 1, ("loopB", src.count(_SW_LOOP_B))
    src = src.replace(_SW_LOOP_B, "                sh = _w_alloc[code] / px")
    assert src.count(_SW_SNAP) == 1, ("snap", src.count(_SW_SNAP))
    src = src.replace(
        _SW_SNAP,
        "                               alloc_per_slot=float(_w_mean), picked=int(len(picks)), "
        "weight_mode=_w_mode, weights={cd: round(float(_w_alloc[cd]), 4) for cd in picks}))",
    )
    # thread weight mode + factor handles into the namespace
    src = src.replace(
        "    switch_log: List[Tuple[str, str]] = []",
        "    switch_log: List[Tuple[str, str]] = []\n    _WEIGHT_MODE = " + repr(weight_mode),
        1,
    )
    # rebal_snap dicts gain new keys: extend the dict literal with defaults elsewhere?
    # (snapshot dict is built inline above; extra keys are fine.)
    ns = {}
    exec(compile(src, "switch_engine_k18_%s" % weight_mode, "exec"), ns)
    return ns


def _patch_single_source(weight_mode):
    assert weight_mode in WEIGHT_MODES, weight_mode
    src = (ROOT / "team" / "audit" / "prior_check.py").read_text()
    assert src.count(_PC_ALLOC_OLD) == 1, ("pc alloc anchor", src.count(_PC_ALLOC_OLD))
    blk = _weight_block("exposure").replace("inp_cur.amihud60", "inp.amihud60").replace(
        "inp_cur.amihud", "inp.amihud"
    )
    src = src.replace(_PC_ALLOC_OLD, blk)
    assert src.count(_SW_LOOP_A) == 1, ("pc loopA", src.count(_SW_LOOP_A))
    src = src.replace(_SW_LOOP_A, "                sh = int(_w_alloc[code] / px // lot) * lot")
    assert src.count(_SW_LOOP_B) == 1, ("pc loopB", src.count(_SW_LOOP_B))
    src = src.replace(_SW_LOOP_B, "                sh = _w_alloc[code] / px")
    assert src.count(_PC_SNAP) == 1, ("pc snap", src.count(_PC_SNAP))
    src = src.replace(
        _PC_SNAP,
        "                               alloc_per_slot=float(_w_mean), picked=int(len(picks)), "
        "weight_mode=_w_mode, weights={cd: round(float(_w_alloc[cd]), 4) for cd in picks}))",
    )
    # note: prior_check has no switch_log anchor; inject mode flag near stats init
    anchor = '    stats = {"stale_buys": 0'
    assert src.count(anchor) == 1, ("pc stats anchor", src.count(anchor))
    src = src.replace(anchor, "    _WEIGHT_MODE = " + repr(weight_mode) + "\n" + anchor, 1)
    import sys as _sys, types as _types
    _modname = "prior_check_k18_%s" % weight_mode
    _mod = _types.ModuleType(_modname)
    _mod.__file__ = str(ROOT / "team" / "audit" / "prior_check.py")
    _sys.modules[_modname] = _mod  # dataclass processing needs sys.modules[__name__]
    exec(compile(src, _modname, "exec"), _mod.__dict__)
    return dict(_mod.__dict__)


_NS_SWITCH_CACHE = {}
_NS_SINGLE_CACHE = {}


def get_switch_ns(weight_mode):
    if weight_mode not in _NS_SWITCH_CACHE:
        _NS_SWITCH_CACHE[weight_mode] = _patch_switch_source(weight_mode)
    return _NS_SWITCH_CACHE[weight_mode]


def get_single_ns(weight_mode):
    if weight_mode not in _NS_SINGLE_CACHE:
        _NS_SINGLE_CACHE[weight_mode] = _patch_single_source(weight_mode)
    return _NS_SINGLE_CACHE[weight_mode]
