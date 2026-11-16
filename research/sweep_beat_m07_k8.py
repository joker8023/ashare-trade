"""K8: 峰顶二阶组合 (g_bf07 基座上的二阶/三阶叠加, 仅从未试过的新配).
Baseline = M07 final (ph0). 口径与 run_m07_final.py / sweep_beat_m07_k1-k7 逐字一致:
  ph0 / RUN_START=2023-01-03 / EVAL_END=2026-11-12 / 5万 /
  现实费率(cost_one_way=None) / slip=0.002 / 整手lot=100 /
  legacy_grid=False / full_liquidate=True / stop_exec=next /
  factor=amihud_60 / MB排除 / RS trailing (ra>=rb->A else B, rs_lookback).
M07: A band=(0.02,0.30) gate60=-0.15 cut=0.80 win=40 take=1.2 n=5 rebal=20 exp=1.0;
     B band=(0.05,0.30) gate60=-1.0 cut=0.80 win=20 take=0.8 n=4 rebal=30 exp=0.9;
     stop=0.25; brake bx=0.18/by=0.08/bf=0.6; rs=60.
g_bf07 = M07 + by=0.05 + cut双腿0.78 + bx=0.15 + bf=0.7 (K3 g_bf07, 全场峰值
  total 2128.41/mdd -24.28, nbeat 5/6 仅1m差-0.01pp).
K8 dims (<=8行, 全部 lock_mode=None 单switch机制, 无未来函数, 不拼凑口径):
  1. g_bf07+rs70            (rs_lookback=70)
  2. g_bf07+winA30          (win_a=30)
  3. g_bf07+rs70+winA30     (rs=70, win_a=30)
  4. g_bf07+cut75双腿       (cut_a=cut_b=0.75, 替代0.78)
  5. g_bf07+cut75+rs70      (cut双腿0.75, rs=70)
  6. g_bf07+stop22          (stop=0.22; K3 g_stop22 为 bf=0.6 版, 不重复)
  7. g_bf07+takeB90         (b_take=0.90; K3 g_takeB90 为 bf=0.6 版, 不重复)
  8. base_M07 校准行 (逐字复现: total 1863.27 / mdd -27.05, 六窗对齐).
去重总账 (开跑前自查, 来自 K1-K7 脚本 CFGS 与 json tags):
  K1: 全部单改 (bf0.7/bf0.5/bx0.15/bx0.20/by0.05/by0.10/stop22/stop28/
      btake70/90/100/atake100/140/bn3/bn5/bexp100/an4/rs45/75/90/
      winB30/10/winBoth40/cut82/cut78双腿/非对称cut/btake90+bf07/bx15+bf05).
  K2: by05+cut78双腿(a/b/c/d/e/f), g=by05+cut78+bx15(bf0.6), h=by05+cut78+bf07(bx0.18).
  K3: a_winA30/50, cutA非对称, takeA, gateA, bandA, takeB70/90/100, stop20/30,
      expB95, rs50/70/80, g_bf05, g_bf07(峰顶本体), g_bx20(bf0.6),
      g_takeB90/g_takeA100/g_stop22/g_takeB100/g_expB95/g_rs70/g_winA30 (均为bf0.6版).
  K4: sleeves(phase +/-5/8/15, 三袖) + R(rebal)网格; K8 全为 ph0 单switch, 无交集.
  K5: legA/B_only, lockA/B(+gbf07), nobrake(bx=10), rs30/rs120(+gbf07),
      pair_hi/lo(+gbf07), swap_NR/swap_full(+gbf07); 无 stop22/takeB90 单改, 无rs70.
  K6: factor(amihud)切换, cut75/85双腿(M07裸基座), 非对称cut; K8 cut75 均带 by05/bx15/bf07.
  K7: g_bf065/075/080/085(bf!=0.7), m07_bf07(裸), g_bf080_takeB90/bx20(bf0.8).
结论: K8 的 7 个组合签名均不在 K1-K7 中 (关键区分位 bf=0.7; #6/#7 相对 K3 同名行
多了 bf0.7; #4/#5 相对 K6 cut75_both 多了 by05/bx15/bf07) -> 0 跳过, 全跑.
判定: 严格>对比 M07 ph0 六窗, beat_all 且 mdd>-27.05 为 win_all.
输出: results/r30_bt/sweep_beat_m07_k8.json (同 K2 schema + combo 字段).
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05, "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
M07_SWITCH = [["2023-06-21", "B"], ["2024-08-15", "A"], ["2026-09-08", "B"]]
assert RUN_START == "2023-01-03", RUN_START
assert str(EVAL_END)[:10] == "2026-11-12", EVAL_END
assert WINDOWS == {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "3y": 756}, WINDOWS
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
_shadow_cache = {}
_ns_cache = {}
def get_ns(bx, by, bf):
    k = (bx, by, bf)
    if k not in _ns_cache:
        _ns_cache[k] = build_ns(bx, by, bf)
    return _ns_cache[k]
def get_shadows(cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp, gate_a=-0.15, band_a_lo=0.02):
    key = (cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp, gate_a, band_a_lo)
    if key in _shadow_cache:
        return _shadow_cache[key]
    inp_a = MaxInputs(piv, band=(band_a_lo, 0.30), gate60=gate_a, max_cut=cut_a, max_win=win_a)
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=cut_b, max_win=win_b)
    CA = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=b_n, rebal=30, take=b_take, exposure=b_exp)
    ra = pc.run_strategy(inp_a, n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
    _shadow_cache[key] = (inp_a, inp_b, ra, rb, CA, CFG_B)
    return _shadow_cache[key]
def run_one(tag, combo, cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, stop=0.25, a_take=1.2, b_take=0.80, a_n=5, b_n=4, b_exp=0.9, rs=60, bx=0.18, by_=0.08, bf=0.6, gate_a=-0.15, band_a_lo=0.02):
    inp_a, inp_b, ra, rb, CA, CFG_B = get_shadows(cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp, gate_a, band_a_lo)
    KW = dict(n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB, **{k: v for k, v in CA.items() if k != "exclude"})
    ns = get_ns(bx, by_, bf)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {"tag": tag, "combo": combo, "total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), "mdd": round(_mdd(eq)*100,2), "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]),0), "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]), "brakes": len(res.meta.get("brake_log",[]))//2,
           "switch_log": [list(x) for x in res.meta["switch_log"]], "brake_log": [list(x) for x in res.meta.get("brake_log", [])]}
    for w, d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
        out[w+"_mdd"] = round(_mdd(sub)*100,2)
    out["nbeat_m07"] = sum(1 for w in WINDOWS if out[w] > M07[w])
    out["beat_all"] = all(out[w] > M07[w] for w in WINDOWS)
    out["mdd_better"] = out["mdd"] > M07["mdd"]
    out["win_all"] = bool(out["beat_all"] and out["mdd_better"])
    out["switch_same_m07"] = (out["switch_log"] == M07_SWITCH)
    return out
GBF07 = dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.7)
CFGS = [
    dict(tag="base_M07", combo="M07逐字复现校准行"),
    dict(tag="g_bf07_rs70", combo="g_bf07+rs70", rs=70, **GBF07),
    dict(tag="g_bf07_winA30", combo="g_bf07+winA30", win_a=30, **GBF07),
    dict(tag="g_bf07_rs70_winA30", combo="g_bf07+rs70+winA30", rs=70, win_a=30, **GBF07),
    dict(tag="g_bf07_cut75", combo="g_bf07+cut75双腿", cut_a=0.75, cut_b=0.75, **{k: v for k, v in GBF07.items() if not k.startswith("cut_")}),
    dict(tag="g_bf07_cut75_rs70", combo="g_bf07+cut75+rs70", cut_a=0.75, cut_b=0.75, rs=70, **{k: v for k, v in GBF07.items() if not k.startswith("cut_")}),
    dict(tag="g_bf07_stop22", combo="g_bf07+stop22", stop=0.22, **GBF07),
    dict(tag="g_bf07_takeB90", combo="g_bf07+takeB90", b_take=0.90, **GBF07),
]
SIG_KEYS = ("cut_a", "win_a", "cut_b", "win_b", "stop", "a_take", "b_take", "a_n", "b_n", "b_exp", "rs", "bx", "by_", "bf")
def _sig(d):
    base = dict(cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, stop=0.25, a_take=1.2, b_take=0.80, a_n=5, b_n=4, b_exp=0.9, rs=60, bx=0.18, by_=0.08, bf=0.6)
    base.update({k: d[k] for k in SIG_KEYS if k in d})
    return tuple(base[k] for k in SIG_KEYS)
KNOWN_SIGS = {
    _sig(dict(b_take=0.90, bf=0.7)): "K1 k28_btake90_bf07 (by0.08/cut0.80/bx0.18, 无by05/cut78/bx15)",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78)): "K2 a_by05_cut78",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15)): "K2 g_by05_cut78_bx15 (bf0.6)",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bf=0.7)): "K2 h_by05_cut78_bf07 (bx0.18)",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.5)): "K3 g_bf05",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.7)): "K3 g_bf07 (峰顶本体, K8基座非测试行)",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.20, bf=0.6)): "K3 g_bx20",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, b_take=0.90)): "K3 g_takeB90 (bf0.6)",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, a_take=1.0)): "K3 g_takeA100 (bf0.6)",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, stop=0.22)): "K3 g_stop22 (bf0.6)",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, b_take=1.00)): "K3 g_takeB100 (bf0.6)",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, b_exp=0.95)): "K3 g_expB95 (bf0.6)",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, rs=70)): "K3 g_rs70 (bf0.6)",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, win_a=30)): "K3 g_winA30 (bf0.6)",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.7, rs=30)): "K5 g_rs30",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.7, rs=120)): "K5 g_rs120",
    _sig(dict(cut_a=0.75, cut_b=0.75)): "K6 cut75_both (M07裸基座)",
    _sig(dict(cut_a=0.85, cut_b=0.85)): "K6 cut85_both",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.65)): "K7 g_bf065",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.75)): "K7 g_bf075",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.80)): "K7 g_bf080",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.85)): "K7 g_bf085",
    _sig(dict(bf=0.7, )): "K1 k01_bf07 / K7 m07_bf07 (裸bf0.7)",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.80, b_take=0.90)): "K7 g_bf080_takeB90",
    _sig(dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.20, bf=0.80)): "K7 g_bf080_bx20",
}
def dedup_check(cfgs):
    seen_tags = set()
    for fn in ["sweep_beat_m07_k1.json", "sweep_beat_m07_k2.json", "sweep_beat_m07_k3.json", "sweep_beat_m07_k4.json", "sweep_beat_m07_k5.json", "sweep_beat_m07_k6.json", "sweep_beat_m07_k7.json"]:
        p = ROOT/"results"/"r30_bt"/fn
        if p.exists():
            for r in json.loads(p.read_text()):
                seen_tags.add(r.get("tag"))
    skipped, kept = [], []
    for cfg in cfgs:
        c = dict(cfg); tag = c.pop("tag"); combo = c.pop("combo")
        if tag == "base_M07":
            kept.append(cfg)  # 校准行豁免: 必须重跑逐字复现, 不判重
            continue
        if tag in seen_tags:
            skipped.append((tag, combo, "tag已在K1-K7 json出现"))
            continue
        if tag != "base_M07":
            s = _sig(c)
            if s in KNOWN_SIGS:
                skipped.append((tag, combo, "参数签名已存在: " + KNOWN_SIGS[s]))
                continue
        kept.append(cfg)
    return kept, skipped
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--only", default=None)
    args = ap.parse_args()
    kept, skipped = dedup_check(CFGS)
    for tag, combo, reason in skipped:
        print("SKIP %s (%s): %s" % (tag, combo, reason), flush=True)
    print("dedup: kept=%d skipped=%d" % (len(kept), len(skipped)), flush=True)
    cfgs = [c for c in kept if args.only is None or c["tag"] == args.only]
    rows = []
    for cfg in cfgs:
        c = dict(cfg); tag = c.pop("tag"); combo = c.pop("combo")
        try:
            r = run_one(tag, combo, **c)
            slim = {k: r[k] for k in ("tag","combo","total","mdd","trades","cost","switches","brakes","1m","3m","6m","1y","2y","3y","nbeat_m07","beat_all","mdd_better","win_all","switch_same_m07")}
            print(json.dumps(slim, ensure_ascii=False), flush=True)
            if tag == "base_M07":
                assert abs(r["total"]-M07["total"]) < 0.01 and abs(r["mdd"]-M07["mdd"]) < 0.01 and r["1m"] == M07["1m"] and r["3m"] == M07["3m"] and r["6m"] == M07["6m"] and r["1y"] == M07["1y"] and r["2y"] == M07["2y"] and r["3y"] == M07["3y"], "base_M07 calibration FAILED: %s" % slim
                print("BASE calibration OK: 逐字复现 M07_final", flush=True)
            rows.append(r)
        except Exception as e:
            print("FAIL %s: %s" % (tag, e), flush=True)
            import traceback; traceback.print_exc()
    if args.only is None:
        open(ROOT/"results"/"r30_bt"/"sweep_beat_m07_k8.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
        print("saved %d rows" % len(rows), flush=True)
