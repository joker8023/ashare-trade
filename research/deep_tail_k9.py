"""K9: 尾部深挖 (单点, 非sweep, 仅2配置).
复用 sweep_beat_m07_k8.py 的 run_one/get_shadows 结构 (口径逐字一致):
  ph0 / RUN_START=2023-01-03 / EVAL_END=2026-11-12 / 5万 /
  现实费率(cost_one_way=None) / slip=0.002 / 整手lot=100 /
  legacy_grid=False / full_liquidate=True / stop_exec=next /
  factor=amihud_60 / MB排除 / RS trailing (ra>=rb->A else B, rs_lookback).
只跑 2 个配置:
  base_M07          (M07逐字复现: cut双腿0.80/winA40/winB20/stop0.25/
                     a_take1.2/b_take0.80/a_n5/b_n4/b_exp0.9/rs60/
                     bx0.18/by0.08/bf0.6)
  g_bf07_winA30     (M07+by05+cut双腿0.78+bx0.15+bf0.7+winA30;
                     K8最强: total 2400.29/mdd -24.17)
目标: (a)尾部21/63根bar持仓代码集合交集/差集;
      (b)全精度尾窗起止净值与收益率 (证明1m持平是真持平还是舍入持平);
      (c)3m缺口-0.03pp归因到票/日期 (Top3贡献 / 刹车OFF时点).
无未来函数: 仅用回测引擎已产出的 trades/eq/meta + 同口径 picks 重建期末在持仓.
输出: results/r30_bt/deep_tail_k9.json. 不改动既有文件.
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

def run_deep(tag, combo, cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, stop=0.25, a_take=1.2, b_take=0.80, a_n=5, b_n=4, b_exp=0.9, rs=60, bx=0.18, by_=0.08, bf=0.6, gate_a=-0.15, band_a_lo=0.02):
    """与K8 run_one逐字同口径, 额外返回 (res, eq, inp_a, inp_b) 供尾部深挖."""
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
    return out, res, eq, inp_a, inp_b

CFGS = [
    dict(tag="base_M07", combo="M07逐字复现校准行"),
    dict(tag="g_bf07_winA30", combo="g_bf07+winA30", win_a=30, by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.7),
]

def full_windows(eq):
    fw = {}
    for w, d in WINDOWS.items():
        sub = eq.tail(d+1)
        s, e = float(sub.iloc[0]), float(sub.iloc[-1])
        fw[w] = {"start_date": str(sub.index[0].date()), "end_date": str(sub.index[-1].date()),
                 "start_eq": s, "end_eq": e,
                 "ret_full": (e/s-1)*100, "ret_r2": round((e/s-1)*100, 2)}
    return fw

def open_positions(res, eq, inp_a, inp_b, a_n, b_n):
    """重建期末在持仓: 最后一次调仓 picks − 其后止损/止盈已平仓部分.
    full_liquidate=True 下调仓后持仓恒等于本期 picks 减去段内 stop/take."""
    snaps = res.meta.get("rebalance_snapshots", [])
    if not snaps:
        return {"note": "no rebalance_snapshots", "open": []}
    last = snaps[-1]
    exec_day = pd.Timestamp(last["date"])
    epos = int(eq.index.searchsorted(exec_day))
    if epos >= len(eq) or eq.index[epos] != exec_day:
        return {"note": "exec day not in eq", "open": []}
    sig_day = eq.index[epos-1]  # exec=sig+1 (sig_lag=0, 逐字同引擎映射)
    mode = "A"
    for dstr, m in res.meta.get("switch_log", []):
        if pd.Timestamp(dstr) <= sig_day:
            mode = m
    # 最后一次调仓若本身就是切换日则 desired 已生效: 取不晚于 exec 的最后 switch
    for dstr, m in res.meta.get("switch_log", []):
        if pd.Timestamp(dstr) <= exec_day:
            mode = m
    inp_cur = inp_a if mode == "A" else inp_b
    n_eff = a_n if mode == "A" else b_n
    picks = list(inp_cur.picks(sig_day, n_eff, exclude=MB, factor="amihud_60"))
    tr = res.trades
    closed = set()
    if len(tr):
        m = (tr["entry_date"] == exec_day) & (tr["exit_date"] > exec_day)
        closed = set(tr.loc[m, "code"].tolist())
    openp = [c for c in picks if c not in closed]
    return {"exec_date": str(exec_day.date()), "sig_date": str(sig_day.date()), "mode_at_last_rebal": mode,
            "picks": sorted(picks), "take_stop_closed_after": sorted(closed), "open": sorted(openp)}

def held_in_window(res, eq, open_codes, d):
    sub = eq.tail(d+1)
    ws, we = sub.index[0], sub.index[-1]
    tr = res.trades
    overlap = set()
    od = []
    if len(tr):
        m = (tr["exit_date"] >= ws) & (tr["entry_date"] <= we)
        seg = tr.loc[m]
        overlap = set(seg["code"].tolist())
        for _, r in seg.iterrows():
            od.append({"code": r["code"], "entry": str(pd.Timestamp(r["entry_date"]).date()),
                       "exit": str(pd.Timestamp(r["exit_date"]).date()), "reason": str(r["reason"]),
                       "net_pnl": float(r["net_pnl"]), "shares": float(r["shares"])})
    held = set(overlap) | set(open_codes)
    return {"start": str(ws.date()), "end": str(we.date()), "held": sorted(held),
            "overlap_trades": od, "n_overlap": len(od), "n_open": len(open_codes)}

if __name__ == "__main__":
    store = {}
    for cfg in CFGS:
        c = dict(cfg); tag = c.pop("tag"); combo = c.pop("combo")
        out, res, eq, inp_a, inp_b = run_deep(tag, combo, **c)
        a_n = c.get("a_n", 5); b_n = c.get("b_n", 4)
        store[tag] = {"out": out, "eq": eq, "res": res, "inp_a": inp_a, "inp_b": inp_b, "a_n": a_n, "b_n": b_n}
        slim = {k: out[k] for k in ("tag","combo","total","mdd","trades","cost","switches","brakes","1m","3m","6m","1y","2y","3y")}
        print(json.dumps(slim, ensure_ascii=False), flush=True)
    # 校准断言 (与K8逐字同)
    b = store["base_M07"]["out"]
    assert abs(b["total"]-M07["total"]) < 0.01 and abs(b["mdd"]-M07["mdd"]) < 0.01 and all(b[w] == M07[w] for w in WINDOWS), "base_M07 calibration FAILED"
    print("BASE calibration OK", flush=True)

    data = {"meta": {"caliber": "ph0/RUN_START=2023-01-03/EVAL_END=2026-11-12/5万/现实费率/slip0.002/lot100/legacy_gridFalse/full_liquidateTrue/stop_next/amihud_60/MB排除/RS-trailing",
                      "k8_ref": {"g_bf07_winA30": {"total": 2400.29, "mdd": -24.17, "1m": -4.09, "3m": 17.25}},
                      "note": "全精度字段 ret_full/start_eq/end_eq 未舍入; 持仓集合=窗内有交集的已平仓往返代码 ∪ 期末在持仓(open重建)"},
            "configs": {}, "tails": {}, "attrib": {}}
    for tag, S in store.items():
        eq = S["eq"]; out = S["out"]
        op = open_positions(S["res"], eq, S["inp_a"], S["inp_b"], S["a_n"], S["b_n"])
        S["open"] = op["open"]
        data["configs"][tag] = {"combo": out["combo"], "params": {k: v for k, v in [("cut_a",None)]},
            "full_windows": full_windows(eq),
            "round2": {k: out[k] for k in ("total","mdd","trades","cost","mode","switches","brakes","1m","3m","6m","1y","2y","3y")},
            "switch_log": out["switch_log"], "brake_log": out["brake_log"],
            "open_rebuild": op}
    # 覆盖params
    data["configs"]["base_M07"]["params"] = {"cut_a":0.80,"win_a":40,"cut_b":0.80,"win_b":20,"stop":0.25,"a_take":1.2,"b_take":0.80,"a_n":5,"b_n":4,"b_exp":0.9,"rs":60,"bx":0.18,"by":0.08,"bf":0.6}
    data["configs"]["g_bf07_winA30"]["params"] = {"cut_a":0.78,"win_a":30,"cut_b":0.78,"win_b":20,"stop":0.25,"a_take":1.2,"b_take":0.80,"a_n":5,"b_n":4,"b_exp":0.9,"rs":60,"bx":0.15,"by":0.05,"bf":0.7}
    for d, w in ((21,"1m"),(63,"3m")):
        hb = held_in_window(store["base_M07"]["res"], store["base_M07"]["eq"], store["base_M07"]["open"], d)
        hg = held_in_window(store["g_bf07_winA30"]["res"], store["g_bf07_winA30"]["eq"], store["g_bf07_winA30"]["open"], d)
        sb, sg = set(hb["held"]), set(hg["held"])
        data["tails"][w] = {"bars": d, "start": hb["start"], "end": hg["end"],
            "base": hb, "g": hg,
            "inter": sorted(sb & sg), "only_base": sorted(sb - sg), "only_g": sorted(sg - sb),
            "identical": (sb == sg)}
    # 归因: 3m窗逐日spread + 按票net_pnl差 + 绝对涨幅(元) + 窗内刹车/切换
    for w, d in (("1m",21),("3m",63)):
        eb = store["base_M07"]["eq"].tail(d+1); eg = store["g_bf07_winA30"]["eq"].tail(d+1)
        assert (eb.index == eg.index).all()
        rb = eb.pct_change().iloc[1:]*100; rg = eg.pct_change().iloc[1:]*100
        sp = rg - rb
        days = [{"date": str(ix.date()), "r_base": float(rb.loc[ix]), "r_g": float(rg.loc[ix]), "spread_g_minus_b": float(sp.loc[ix])} for ix in sp.index]
        byneg = sorted(days, key=lambda x: x["spread_g_minus_b"])[:3]
        bypos = sorted(days, key=lambda x: x["spread_g_minus_b"], reverse=True)[:3]
        fb = data["configs"]["base_M07"]["full_windows"][w]; fg = data["configs"]["g_bf07_winA30"]["full_windows"][w]
        tb = store["base_M07"]["res"].trades; tg = store["g_bf07_winA30"]["res"].trades
        ws = pd.Timestamp(fb["start_date"]); we = pd.Timestamp(fb["end_date"])
        def pnl_by_code(tr):
            if len(tr) == 0: return {}
            m = (tr["exit_date"] >= ws) & (tr["entry_date"] <= we)
            g = tr.loc[m].groupby("code")["net_pnl"].sum()
            return {k: float(v) for k, v in g.items()}
        pb, pg = pnl_by_code(tb), pnl_by_code(tg)
        diff = {k: pg.get(k,0.0)-pb.get(k,0.0) for k in set(pb)|set(pg)}
        neg3 = sorted(diff.items(), key=lambda x: x[1])[:3]; pos3 = sorted(diff.items(), key=lambda x: x[1], reverse=True)[:3]
        data["attrib"][w] = {
            "abs_gain_yuan": {"base": fb["end_eq"]-fb["start_eq"], "g": fg["end_eq"]-fg["start_eq"]},
            "ret_full": {"base": fb["ret_full"], "g": fg["ret_full"], "gap_g_minus_b": fg["ret_full"]-fb["ret_full"]},
            "ret_r2": {"base": fb["ret_r2"], "g": fg["ret_r2"]},
            "top3_drag_days": byneg, "top3_lift_days": bypos,
            "pnl_by_code_base": pb, "pnl_by_code_g": pg,
            "code_diff_top3_neg": [{"code":k,"d_pnl":v,"base":pb.get(k,0.0),"g":pg.get(k,0.0)} for k,v in neg3],
            "code_diff_top3_pos": [{"code":k,"d_pnl":v,"base":pb.get(k,0.0),"g":pg.get(k,0.0)} for k,v in pos3],
            "brake_events_in_win": {"base": [x for x in data["configs"]["base_M07"]["brake_log"] if fb["start_date"] <= x[0] <= fb["end_date"]],
                                    "g": [x for x in data["configs"]["g_bf07_winA30"]["brake_log"] if fg["start_date"] <= x[0] <= fg["end_date"]]},
            "switch_events_in_win": {"base": [x for x in data["configs"]["base_M07"]["switch_log"] if fb["start_date"] <= x[0] <= fb["end_date"]],
                                     "g": [x for x in data["configs"]["g_bf07_winA30"]["switch_log"] if fg["start_date"] <= x[0] <= fg["end_date"]]},
            "last_brake_before_win": {"base": [x for x in data["configs"]["base_M07"]["brake_log"] if x[0] < fb["start_date"]][-1:],
                                       "g": [x for x in data["configs"]["g_bf07_winA30"]["brake_log"] if x[0] < fg["start_date"]][-1:]}}
    open(ROOT/"results"/"r30_bt"/"deep_tail_k9.json","w").write(json.dumps(data, ensure_ascii=False, indent=1, default=str))
    print("saved deep_tail_k9.json", flush=True)
    for w in ("1m","3m"):
        a = data["attrib"][w]
        print(w, "gap_full=", repr(a["ret_full"]["gap_g_minus_b"]), "base=", repr(a["ret_full"]["base"]), "g=", repr(a["ret_full"]["g"]), flush=True)
        print(w, "identical_holdings=", data["tails"][w]["identical"], "only_base=", data["tails"][w]["only_base"], "only_g=", data["tails"][w]["only_g"], flush=True)
