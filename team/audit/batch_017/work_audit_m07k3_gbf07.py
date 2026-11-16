#!/usr/bin/env python3
"""batch_017: K3唯一nbeat>=5候选 g_bf07 的T1-T6复核.
g_bf07 = by0.05/cut0.78/cut0.78/bx0.15/bf0.7，其余与M07逐字一致（参数见research/sweep_beat_m07_k3.py CFGS）.
仿写 research/valid_m07_k3ph.py 与 team/audit/batch_017/work_audit_m07k3_gph.py 结构；只新增本文件.
M07同相位数据复用同口径审计自跑产物 team/audit/batch_017/part_gph.json（M07侧，命令见work_audit_m07k3_gph.py）.
用法：.venv/bin/python team/audit/batch_017/work_audit_m07k3_gbf07.py
产物：team/audit/batch_017/part_gbf07.json
"""
import sys, json
from pathlib import Path
ROOT = Path("/Users/joker/coding/ashare-trade")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB

M07W = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05, "2y": 1474.08, "3y": 1677.53, "mdd": -27.05, "total": 1863.27}
M07_SWITCH = [["2023-06-21", "B"], ["2024-08-15", "A"], ["2026-09-08", "B"]]
G3_K3 = {"tag": "g_bf07", "total": 2128.41, "mdd": -24.28,
         "1m": -4.10, "3m": 17.29, "6m": 39.30, "1y": 164.90, "2y": 1487.61, "3y": 1875.48}

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

def get_shadows(cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp, ph, slip):
    key = (cut_a, win_a, cut_b, win_b, stop, a_take, b_take, a_n, b_n, b_exp, ph, slip)
    if key in _shadow_cache:
        return _shadow_cache[key]
    inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=cut_a, max_win=win_a)
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=cut_b, max_win=win_b)
    CA = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=MB, capital=50000.0, lot=100,
              cost_one_way=None, slip=slip, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END,
              legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=b_n, rebal=30, take=b_take, exposure=b_exp)
    ra = pc.run_strategy(inp_a, n=a_n, rebal=20, take=a_take, exposure=1.0, phase=ph, **CA)
    rb = pc.run_strategy(inp_b, phase=ph, **{**CA, **CFG_B})
    _shadow_cache[key] = (inp_a, inp_b, ra, rb, CA, CFG_B)
    return _shadow_cache[key]

def run_one(tag, cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, stop=0.25, a_take=1.2, b_take=0.80,
            a_n=5, b_n=4, b_exp=0.9, rs=60, bx=0.18, by_=0.08, bf=0.6, ph=0, slip=0.002, with_trades=False):
    inp_a, inp_b, ra, rb, CA, CFG_B = get_shadows(cut_a, win_a, cut_b, win_b, stop, a_take, b_take,
                                                  a_n, b_n, b_exp, ph, slip)
    KW = dict(n=a_n, rebal=20, take=a_take, exposure=1.0, phase=ph, inp_b=inp_b, cfg_b=CFG_B,
              shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB,
              **{k: v for k, v in CA.items() if k != "exclude"})
    ns = get_ns(bx, by_, bf)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    eq0 = float(eq.iloc[0])
    out = {"tag": tag, "ph": ph, "slip": slip,
           "total": round(float(eq.iloc[-1]/eq0-1)*100, 2), "mdd": round(_mdd(eq)*100, 2),
           "trades": len(res.trades), "cost": round(float(res.meta["total_cost"]), 0),
           "mode": res.meta["final_mode"], "switches": len(res.meta["switch_log"]),
           "switch_log": [list(x) for x in res.meta["switch_log"]],
           "brake_log": [list(x) for x in res.meta.get("brake_log", [])]}
    for w, d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100, 2)
        out[w+"_mdd"] = round(_mdd(sub)*100, 2)
    out["nbeat_m07"] = sum(1 for w in WINDOWS if out[w] > M07W[w])
    out["mdd_better"] = out["mdd"] > M07W["mdd"]
    out["switch_same_m07"] = (out["switch_log"] == M07_SWITCH)
    if with_trades:
        tr = res.trades
        pnl = tr["net_pnl"].fillna(0)
        top3 = pnl.nlargest(3).sum()
        out["top3_share"] = round(float(top3/pnl.sum())*100, 1)
        out["extop3_total"] = round(float((eq0+pnl.sum()-top3)/eq0-1)*100, 2)
        out["pnl_sum"] = round(float(pnl.sum()), 1)
    return out

G3KW = dict(cut_a=0.78, cut_b=0.78, bx=0.15, by_=0.05, bf=0.7)  # g_bf07
PHASES = [5, 7, 10, 14, 15]

if __name__ == "__main__":
    rows = []
    r = run_one("gbf07_repro_ph0", slip=0.002, with_trades=True, **G3KW)
    print(json.dumps({k: r.get(k) for k in ("tag","total","mdd","trades","cost","mode","switches","1m","3m","6m","1y","2y","3y","nbeat_m07","mdd_better","switch_same_m07","top3_share","extop3_total")}, ensure_ascii=False), flush=True)
    rows.append(r)
    for ph in PHASES:
        rg = run_one("gbf07_ph%d" % ph, ph=ph, **G3KW)
        print(json.dumps({k: rg.get(k) for k in ("tag","total","mdd","switches","mode","1m","3m","6m","1y","2y","3y","nbeat_m07")}, ensure_ascii=False), flush=True)
        rows.append(rg)
    rs = run_one("gbf07_slip04_ph0", slip=0.004, with_trades=True, **G3KW)
    print(json.dumps({k: rs.get(k) for k in ("tag","total","mdd","trades","cost","mode","switches","1m","3m","6m","1y","2y","3y","nbeat_m07","mdd_better","top3_share","extop3_total")}, ensure_ascii=False), flush=True)
    rows.append(rs)
    open(ROOT/"team"/"audit"/"batch_017"/"part_gbf07.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
    print("saved %d rows -> team/audit/batch_017/part_gbf07.json" % len(rows), flush=True)
