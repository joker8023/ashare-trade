"""K10:复合秩和键试点 (amihud60秩+size/adv20/amihud5秩) x 单腿B/双腿 = 6配.

Baseline = M07 final (ph0).口径除选股器外与 run_m07_final.py / K1-K9 逐字一致:
  ph0 / RUN_START=2023-01-03 / EVAL_END=2026-11-12 / 5万 /
  现实费率(cost_one_way=None) / slip=0.002 / 整手lot=100 /
  legacy_grid=False / full_liquidate=True / stop_exec=next /
  MB排除 / RS trailing (ra>=rb->A else B, rs_lookback=60) / 刹车 bx0.18/by0.08/bf0.6.
M07:A band=(0.02,0.30) gate60=-0.15 cut=0.80 win=40 take=1.2 n=5 rebal=20 exp=1.0;
    B band=(0.05,0.30) gate60=-1.0 cut=0.80 win=20 take=0.8 n=4 rebal=30 exp=0.9;
    stop=0.25.
K10 dims (6新配,全部 lock_mode=None 单switch机制,无未来函数,不拼凑口径):
  selector in a60_size/a60_adv/a60_a5 (research/inputs_k10.py K10Inputs,实例绑定;
    秩和取小者优先;池与M07逐字一致;MAX过滤保持M07默认 双腿cut=0.80/winA40/winB20)
  x legs in B (仅B腿换K10,A腿保持M07 MaxInputs) / both (AB腿全换K10,各腿AB参数不变)
  + base_M07 校准行 (逐字复现 total 1863.27 / mdd -27.05,六窗对齐).
去重:K1-K9 从未引入复合秩和selector;K10 tags 均为 k10_ 前缀,与既往 json tags
无交集 -> 0 跳过,全跑.新配严格=6,不超配.
判定:严格>对比 M07 ph0 六窗, beat_all 且 mdd>-27.05 为 win_all.
输出:results/r30_bt/sweep_beat_m07_k10.json (K2 schema + selector/legs/max_filter/combo).
复现:
  .venv/bin/python research/sweep_beat_m07_k10.py --check-trailing   # 截断对照抽查
  .venv/bin/python research/sweep_beat_m07_k10.py --only base_M07    # base校准行
  .venv/bin/python research/sweep_beat_m07_k10.py                    # 全量6+1并落盘
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from inputs_k10 import K10Inputs, SELECTORS
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05, "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
M07_SWITCH = [["2023-06-21", "B"], ["2024-08-15", "A"], ["2026-09-08", "B"]]
assert RUN_START == "2023-01-03", RUN_START
assert str(EVAL_END)[:10] == "2026-11-12", EVAL_END
assert WINDOWS == {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}, WINDOWS
assert SELECTORS == ("a60_size", "a60_adv", "a60_a5"), SELECTORS
piv = pd.read_pickle(ROOT / "data" / "pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
A_P = dict(band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
B_P = dict(band=(0.05, 0.30), gate60=-1.0, max_cut=0.80, max_win=20)
NS = build_ns(0.18, 0.08, 0.6)
_inp_cache = {}
_shadow_cache = {}


def get_inp(kind, leg):
    key = (kind, leg)
    if key not in _inp_cache:
        P = A_P if leg == "A" else B_P
        if kind == "M07":
            _inp_cache[key] = MaxInputs(piv, **P)
        else:
            _inp_cache[key] = K10Inputs(piv, use_max=True, sel=kind, **P)
    return _inp_cache[key]


def get_shadow(kind, leg, n, rebal, take, exposure):
    key = (kind, leg, n, rebal, take, exposure)
    if key not in _shadow_cache:
        inp = get_inp(kind, leg)
        factor = "amihud_60" if kind == "M07" else kind
        CA = dict(factor=factor, stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
        _shadow_cache[key] = (inp, pc.run_strategy(inp, n=n, rebal=rebal, take=take, exposure=exposure, phase=0, **CA), CA)
    return _shadow_cache[key]


def run_one(tag, selector, combo, legs):
    a_kind = "M07" if legs == "B" else selector
    b_kind = "M07" if tag == "base_M07" else selector
    inp_a, ra, CA = get_shadow(a_kind, "A", 5, 20, 1.2, 1.0)
    inp_b, rb, _CB = get_shadow(b_kind, "B", 4, 30, 0.80, 0.9)
    CFG_B = dict(n=4, rebal=30, take=0.80, exposure=0.9)
    # switch 引擎双腿共用单一 factor:K10实例绑定sel(忽略传入值),M07腿用amihud_60.
    # 单腿B时传 amihud_60 (A腿生效,B腿K10忽略);双腿时传 selector (两腿K10均忽略).
    kw_factor = "amihud_60" if legs == "B" else selector
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=60, exclude_a=MB, exclude_b=MB, factor=kw_factor, **{k: v for k, v in CA.items() if k not in ("exclude", "factor")})
    res = NS["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "selector": selector, "legs": legs, "max_filter": "on", "combo": combo, "total": round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2), "mdd": round(_mdd(eq) * 100, 2), "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]), 0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "brakes": len(res.meta.get("brake_log", [])) // 2, "switch_log": [list(x) for x in res.meta["switch_log"]], "brake_log": [list(x) for x in res.meta.get("brake_log", [])]}
    for w, d in WINDOWS.items():
        sub = eq.tail(d + 1)
        out[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
        out[w + "_mdd"] = round(_mdd(sub) * 100, 2)
    out["nbeat_m07"] = sum(1 for w in WINDOWS if out[w] > M07[w])
    out["beat_all"] = all(out[w] > M07[w] for w in WINDOWS)
    out["mdd_better"] = out["mdd"] > M07["mdd"]
    out["win_all"] = bool(out["beat_all"] and out["mdd_better"])
    out["switch_same_m07"] = (out["switch_log"] == M07_SWITCH)
    return out


CN = {"a60_size": "amihud60秩+size秩", "a60_adv": "amihud60秩+adv20秩", "a60_a5": "amihud60秩+amihud5秩"}
CFGS = [dict(tag="base_M07", selector="amihud_60", combo="M07逐字复现校准行", legs="B")]
for _sel in ["a60_size", "a60_adv", "a60_a5"]:
    for _legs, _ln in [("B", "单腿B"), ("both", "双腿")]:
        CFGS.append(dict(tag="k10_" + _sel + "_" + _legs, selector=_sel,
                         combo=CN[_sel] + "+" + _ln + "+MAX开", legs=_legs))
assert len([c for c in CFGS if c["tag"] != "base_M07"]) == 6, CFGS


def dedup_check(cfgs):
    seen_tags = set()
    for fn in ["sweep_beat_m07_k1.json", "sweep_beat_m07_k2.json", "sweep_beat_m07_k3.json", "sweep_beat_m07_k4.json", "sweep_beat_m07_k5.json", "sweep_beat_m07_k6.json", "sweep_beat_m07_k7.json", "sweep_beat_m07_k8.json", "sweep_beat_m07_k9.json"]:
        p = ROOT / "results" / "r30_bt" / fn
        if p.exists():
            for r in json.loads(p.read_text()):
                seen_tags.add(r.get("tag"))
    skipped, kept = [], []
    for cfg in cfgs:
        if cfg["tag"] == "base_M07":
            kept.append(cfg)
            continue
        if cfg["tag"] in seen_tags:
            skipped.append((cfg["tag"], cfg["combo"], "tag已在K1-K9 json出现"))
            continue
        kept.append(cfg)
    return kept, skipped


def trailing_check():
    """截断对照抽查:全量piv实例 vs 截断至T的piv实例,同日picks必须逐字一致.

    若任一矩阵/排序漏用 t+1 及以后数据,截断实例结果必然偏离.覆盖 3 键 x 2 日期
    (任务要求至少 1 键 x 2 日期),另对手工重算 amihud5 做点查.
    """
    TS = [pd.Timestamp("2024-06-03"), pd.Timestamp("2025-09-01")]
    for T in TS:
        assert T in dates, T
    print("piv keys: %s" % sorted(piv.keys()), flush=True)
    ok_all = True
    for sel in SELECTORS:
        inp_full = K10Inputs(piv, sel=sel, **B_P)
        for T in TS:
            # 仅切行索引为时间的帧;shares 为代码索引静态快照,原样保留
            piv_tr = {k: (v[v.index <= T] if (hasattr(v, "index") and str(getattr(v.index, "dtype", "")) == "datetime64[ns]") else v)
                      for k, v in piv.items()}
            inp_tr = K10Inputs(piv_tr, sel=sel, **B_P)
            p_full = inp_full.picks(T, 4, exclude=MB)
            p_tr = inp_tr.picks(T, 4, exclude=MB)
            ok = (p_full == p_tr)
            ok_all &= ok
            print("TRUNC %s %s full=%s trunc=%s %s"
                  % (sel, T.date(), p_full, p_tr, "OK" if ok else "MISMATCH"),
                  flush=True)
    # 手工点查:amihud5 必须等于 t 及以前 5 日 mean(abs_ret/(amount/1e8))
    T = TS[0]
    inp = K10Inputs(piv, sel="a60_a5", **B_P)
    code = inp.amihud5.loc[T].dropna().index[0]
    loc = inp.close.index.get_loc(T)
    # 注意:pct_change 需在 6 行窗口上算再取后 5 个 (切 5 行直接 pct_change 首行变 NaN 只剩 4 个值)
    px = inp.close.iloc[loc-5:loc+1, inp.close.columns.get_loc(code)]
    am = inp.amount.iloc[loc-5:loc+1, inp.amount.columns.get_loc(code)]
    manual = float((px.pct_change(fill_method=None).abs().iloc[1:] / (am.iloc[1:] / 1e8)).mean())
    stored = float(inp.amihud5.loc[T, code])
    ok = abs(manual - stored) < 1e-9
    ok_all &= ok
    print("SPOT amihud5 %s %s manual=%.6f stored=%.6f %s"
          % (code, T.date(), manual, stored, "OK" if ok else "MISMATCH"), flush=True)
    print("trailing_check: %s" % ("ALL OK" if ok_all else "FAILED"), flush=True)
    if not ok_all:
        raise SystemExit(1)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--check-trailing", action="store_true")
    args = ap.parse_args()
    if args.check_trailing:
        trailing_check()
        raise SystemExit(0)
    kept, skipped = dedup_check(CFGS)
    for tag, combo, reason in skipped:
        print("SKIP %s (%s): %s" % (tag, combo, reason), flush=True)
    print("dedup: kept=%d skipped=%d" % (len(kept), len(skipped)), flush=True)
    cfgs = [c for c in kept if args.only is None or c["tag"] == args.only]
    rows = []
    for cfg in cfgs:
        c = dict(cfg)
        tag = c.pop("tag")
        try:
            r = run_one(tag, **c)
            slim = {k: r[k] for k in ("tag", "selector", "legs", "max_filter", "total", "mdd", "trades", "cost", "switches", "brakes", "1m", "3m", "6m", "1y", "2y", "3y", "nbeat_m07", "beat_all", "mdd_better", "win_all", "switch_same_m07")}
            print(json.dumps(slim, ensure_ascii=False), flush=True)
            if tag == "base_M07":
                assert abs(r["total"] - M07["total"]) < 0.01 and abs(r["mdd"] - M07["mdd"]) < 0.01 and r["1m"] == M07["1m"] and r["3m"] == M07["3m"] and r["6m"] == M07["6m"] and r["1y"] == M07["1y"] and r["2y"] == M07["2y"] and r["3y"] == M07["3y"], "base_M07 calibration FAILED: %s" % slim
                print("BASE calibration OK:逐字复现 M07_final", flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (tag, e), flush=True)
            import traceback
            traceback.print_exc()
    if args.only is None and not args.check_trailing:
        open(ROOT / "results" / "r30_bt" / "sweep_beat_m07_k10.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
        print("saved %d rows" % len(rows), flush=True)
