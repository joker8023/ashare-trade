"""F2 amihud_5族: 补算2026 slice + T08/T06刹车小邻域精修 (realshares_v2, 无前视).

族: B腿 DInputs sel=amihud_5 (band 0.05-0.30, gate60=-1.0), A腿 M07固定
    (MaxInputs band 0.02-0.30, gate60=-0.15, cut 0.8, win 40, N5/R20/take1.2).
口径: realshares_v2, RUN_START 2023-01-03, EVAL_END 2026-11-12, 5万本金,
    slip 0.002, 整手 lot=100, long-only exp<=1.
判定无前视: 复用 research/search_D_stage3.run_switch (trailing矩阵, .loc[t]只读t及以前,
    截面分位逐信号日现算, t+1收盘执行), 本脚本仅在其上追加 slice/年bar数统计.

Part 1: 对 search_D_stage3.json 全部 pass_all=17行重跑, 断言 total/mdd/各yoy与冻结值一致,
        补记 y2023/y2025/y2026 slice + 2026年内bar数.
Part 2: 在 s3_N4_R30_T08 / s3_N4_R30_T06 两锚 (b_n=4,b_rebal=30,b_cut=0.7,b_win=20)
        上做刹车小邻域 bx{0.10,0.12,0.14} x by{0.05,0.06,0.08} x bf{0.4,0.5,0.6}.
严格达标: 2024 slice>60且yoy>60, 2025_yoy>60, 2026 slice>60且yoy>60,
           全程及每年 mdd>-30.

Usage: .venv/bin/python research/fam_F2.py
"""
import os, sys, json, traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "team" / "audit")); sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from inputs_d27 import DInputs
from sweep_beat_h1_v4 import build_ns, _mdd, RUN_START, EVAL_END, MB
from search_D_stage3 import run_switch, annuals, piv, first_sig

CALIBER = dict(data="data/pivots_2020_clean_realshares_v2.pkl", run_start=RUN_START,
               eval_end=str(EVAL_END), capital=50000.0, slip=0.002, lot=100,
               long_only=True, exp_le=1.0, exec_note="t及以前判定, t+1收盘执行",
               slice_def="slice=eq[year].iloc[-1]/eq[year].iloc[0]-1 (年内区间收益, 非年化); yoy=eq[year].iloc[-1]/prev_year_end-1 (2023无prev_end故yoy==slice); mdd=年内(sub/sub.cummax()-1).min(), 非跨年回撤",
               a_leg="M07: MaxInputs band=(0.02,0.30) gate60=-0.15 cut=0.80 win=40 N5/R20/take1.2",
               b_leg="DInputs sel=amihud_5 band=(0.05,0.30) gate60=-1.0")

def run_full(tag, b_n=4, b_rebal=30, b_take=0.80, b_cut=0.70, b_win=20,
             bx=0.12, by_=0.06, bf=0.5, rs=60, stop=0.25, lock=None):
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
    nbars = {y: int((eq.index.year == y).sum()) for y in (2023, 2024, 2025, 2026)}
    if nbars[2026] == 0:
        raise ValueError("2026 has no bars (eq_end=%s)" % str(eq.index[-1].date()))
    r = dict(tag=tag, b_sel="amihud_5", b_n=b_n, b_rebal=b_rebal, b_take=b_take,
             b_cut=b_cut, b_win=b_win, bx=bx, by_=by_, bf=bf, rs=rs, stop=stop, lock=lock,
             total=round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
             mdd=round(_mdd(eq) * 100, 2), trades=len(res.trades),
             cost=round(float(res.meta["total_cost"]), 0), mode=res.meta["final_mode"],
             switches=len(res.meta["switch_log"]),
             switch_log=[list(x) for x in res.meta["switch_log"]],
             y2023_slice=an[2023]["slice"], y2023_yoy=an[2023]["yoy"], y2023_mdd=an[2023]["mdd"],
             y2024_slice=an[2024]["slice"], y2024_yoy=an[2024]["yoy"], y2024_mdd=an[2024]["mdd"],
             y2025_slice=an[2025]["slice"], y2025_yoy=an[2025]["yoy"], y2025_mdd=an[2025]["mdd"],
             y2026_slice=an[2026]["slice"], y2026_yoy=an[2026]["yoy"], y2026_mdd=an[2026]["mdd"],
             y2026_nbars=nbars[2026], nbars=nbars,
             eq_start=str(eq.index[0].date()), eq_end=str(eq.index[-1].date()))
    r["strict_pass"] = bool(r["y2024_slice"] > 60 and r["y2024_yoy"] > 60 and r["y2025_yoy"] > 60
                             and r["y2026_slice"] is not None and r["y2026_slice"] > 60
                             and r["y2026_yoy"] > 60 and r["mdd"] > -30
                             and r["y2024_mdd"] > -30 and r["y2025_mdd"] > -30 and r["y2026_mdd"] > -30)
    r["margin"] = round(min(r["y2024_yoy"] - 60, r["y2025_yoy"] - 60, r["y2026_yoy"] - 60,
                            r["y2024_slice"] - 60, (r["y2026_slice"] - 60) if r["y2026_slice"] is not None else -999,
                            r["mdd"] + 30, r["y2024_mdd"] + 30, r["y2025_mdd"] + 30,
                            r["y2026_mdd"] + 30), 2)
    return r

def main():
    frozen = json.load(open(ROOT / "results" / "r30_bt" / "search_D_stage3.json"))
    fr = {x["tag"]: x for x in frozen}
    passes = [x for x in frozen if x.get("pass_all")]
    print("frozen rows=%d pass_all=%d" % (len(frozen), len(passes)), flush=True)
    # ---- Part 1: slice补算 ----
    patch = []
    for x in sorted(passes, key=lambda r: (r.get("margin", -999), r.get("total", 0)), reverse=True):
        kw = dict(b_n=x["b_n"], b_rebal=x["b_rebal"], b_take=x["b_take"], b_cut=x["b_cut"],
                  b_win=x["b_win"], bx=x["bx"], by_=x["by_"], bf=x["bf"],
                  rs=x.get("rs", 60), stop=x.get("stop", 0.25), lock=x.get("lock"))
        try:
            r = run_full("patch_" + x["tag"], **kw)
            f = fr[x["tag"]]
            keys = ("total", "mdd", "y2023_yoy",
                    "y2024_slice", "y2024_yoy", "y2024_mdd",
                    "y2025_yoy", "y2025_mdd", "y2026_yoy", "y2026_mdd")
            ok = all(abs(r[k] - f[k]) < 1e-6 for k in keys)
            if not ok:
                bad = {k: (r[k], f[k]) for k in keys if abs(r[k] - f[k]) >= 1e-6}
                raise AssertionError("frozen mismatch on %s: %s" % (x["tag"], bad))
        except Exception as e:
            traceback.print_exc()
            patch.append(dict(tag=x["tag"], reproduced=False, error=str(e)))
            print(json.dumps(patch[-1], ensure_ascii=False), flush=True)
            continue
        patch.append(dict(tag=x["tag"], reproduced=ok, y2023_slice=r["y2023_slice"],
                          y2025_slice=r["y2025_slice"], y2026_slice=r["y2026_slice"],
                          y2026_yoy=r["y2026_yoy"], y2026_nbars=r["y2026_nbars"],
                          strict_pass=r["strict_pass"], margin_strict=r["margin"]))
        print(json.dumps(patch[-1], ensure_ascii=False), flush=True)
    # ---- Part 2: T08/T06刹车小邻域 ----
    grid = []
    for base_take, nm in ((0.8, "T08"), (0.6, "T06")):
        for bx in (0.10, 0.12, 0.14):
            for by_ in (0.05, 0.06, 0.08):
                for bf in (0.4, 0.5, 0.6):
                    tag = "famF2_%s_bx%s_by%s_bf%s" % (nm, str(bx).replace(".", ""),
                                                        str(by_).replace(".", ""), str(bf).replace(".", ""))
                    try:
                        r = run_full(tag, b_n=4, b_rebal=30, b_take=base_take,
                                   b_cut=0.70, b_win=20, bx=bx, by_=by_, bf=bf)
                    except Exception:
                        print("FAIL %s" % tag, flush=True)
                        traceback.print_exc()
                        continue
                    grid.append(r)
                    print(json.dumps({k: r[k] for k in
                          ("tag", "total", "mdd", "y2024_slice", "y2024_yoy", "y2024_mdd",
                           "y2025_slice", "y2025_yoy", "y2025_mdd", "y2026_slice",
                           "y2026_yoy", "y2026_mdd", "y2026_nbars", "strict_pass", "margin",
                           "mode", "switches", "trades")}, ensure_ascii=False), flush=True)
    strict_ok = [g for g in grid if g["strict_pass"]]
    strict_ok.sort(key=lambda r: (r["margin"], r["total"]), reverse=True)
    best = strict_ok[0] if strict_ok else None
    out = dict(caliber=CALIBER,
               note_2026="2026为年内slice(1-2至11-12, 非全年), yoy=相对2025年末; EVAL_END=2026-11-12",
               slices_patch=patch, grid=grid,
               best={k: best[k] for k in
                     ("tag", "total", "mdd", "y2024_slice", "y2024_yoy", "y2024_mdd",
                      "y2025_slice", "y2025_yoy", "y2025_mdd", "y2026_slice",
                      "y2026_yoy", "y2026_mdd", "y2026_nbars", "margin", "mode",
                      "switches", "trades", "cost", "eq_start", "eq_end",
                      "b_n", "b_rebal", "b_take", "b_cut", "b_win", "bx", "by_", "bf",
                      "rs", "stop", "lock")
                    } if best else None,
               strict_count=len(strict_ok))
    os.makedirs(ROOT / "results" / "r30_bt", exist_ok=True)
    with open(ROOT / "results" / "r30_bt" / "fam_F2_stage.json", "w") as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1))
    print("saved fam_F2_stage.json grid=%d strict=%d best=%s" %
          (len(grid), len(strict_ok), best["tag"] if best else None), flush=True)

if __name__ == "__main__":
    main()
