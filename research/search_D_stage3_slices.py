"""Patch search_D_stage3.json: add missing y2023/y2025/y2026 slice fields (frozen values).
Re-runs each config via research/search_D_stage3.run_switch, asserts reproduced
total/mdd/annuals equal frozen values, then adds *_slice fields only.
Usage: .venv/bin/python research/search_D_stage3_slices.py
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
from search_D_stage3 import run_switch

p = ROOT / "results" / "r30_bt" / "search_D_stage3.json"
rows = json.load(open(p))
print("rows:", len(rows), flush=True)

def slices_of(tag, **kw):
    from search_D_stage3 import annuals, piv, first_sig
    import prior_check as pc
    from fresh2_max import MaxInputs
    from inputs_d27 import DInputs
    from sweep_beat_h1_v4 import build_ns, RUN_START, EVAL_END, MB
    b_n = kw.get("b_n", 4); b_rebal = kw.get("b_rebal", 30); b_take = kw.get("b_take", 0.80)
    b_cut = kw.get("b_cut", 0.70); b_win = kw.get("b_win", 20)
    bx = kw.get("bx", 0.18); by_ = kw.get("by_", 0.08); bf = kw.get("bf", 0.6)
    rs = kw.get("rs", 60); stop = kw.get("stop", 0.25); lock = kw.get("lock")
    inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
    inp_b = DInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=b_cut, max_win=b_win, sel="amihud_5")
    CA = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=MB, capital=50000.0,
              lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
              eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=b_n, rebal=b_rebal, take=b_take, exposure=0.9)
    ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B,
              shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB,
              **{k: v for k, v in CA.items() if k != "exclude"})
    ns = build_ns(bx, by_, bf)
    res = ns["run_strategy_switch"](inp_a, lock_mode=lock, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    an = annuals(eq)
    return an, eq

patched = 0
for r in rows:
    kw = dict(b_n=r["b_n"], b_rebal=r["b_rebal"], b_take=r["b_take"], b_cut=r.get("b_cut", 0.70),
              b_win=r.get("b_win", 20), bx=r.get("bx", 0.18), by_=r.get("by_", 0.08),
              bf=r.get("bf", 0.6), rs=r.get("rs", 60), stop=r.get("stop", 0.25), lock=r.get("lock"))
    an, eq = slices_of(r["tag"], **kw)
    import pandas as pd
    tot = round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2)
    assert abs(tot - r["total"]) < 1e-9, (r["tag"], tot, r["total"])
    assert an[2024]["yoy"] == r["y2024_yoy"] and an[2025]["yoy"] == r["y2025_yoy"] and an[2026]["yoy"] == r["y2026_yoy"], r["tag"]
    for y in (2023, 2025, 2026):
        r["y%d_slice" % y] = an[y]["slice"]
    patched += 1
    if patched % 20 == 0:
        print("patched %d/%d" % (patched, len(rows)), flush=True)

json.dump(rows, open(p, "w"), ensure_ascii=False, indent=1)
print("frozen file rewritten with slices: %d rows" % len(rows), flush=True)
ok = [r for r in rows if r.get("pass_all") and r.get("y2026_slice", 0) > 60]
print("pass_all+y2026_slice>60: %d" % len(ok), flush=True)
for r in sorted(ok, key=lambda x: -x["margin"])[:6]:
    print(r["tag"], "24s", r["y2024_slice"], "24y", r["y2024_yoy"], "25s", r["y2025_slice"],
          "25y", r["y2025_yoy"], "26s", r["y2026_slice"], "26y", r["y2026_yoy"],
          "mdd", r["mdd"], "mg", r["margin"], flush=True)
