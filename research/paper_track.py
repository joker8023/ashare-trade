#!/usr/bin/env python3
"""X3 vs 均衡型基线 — 前向纸面跟踪 (样本外验证)。
inception = 2026-11-10 (本地数据末日)。此后每更新一次数据, 就用模拟器在
扩展数据上重跑两策略, 切 inception 之后的净值算前向收益 — 与回测同口径,
不另设账本, 避免两套账对不上。

用法:
  paper_track.py init    # 建立 inception 台账 (持仓快照/起始净值/下个调仓日)
  paper_track.py update  # 拉新数据 (新浪, END_DATE=今天) → 重建 pivots → 清洗 → report
  paper_track.py report  # 用现有数据重跑两策略并输出前向报告
"""
import json
import os
import subprocess
import sys

ROOT = os.path.expanduser("~/workspace/ashare-trade")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "team", "audit"))
sys.path.insert(0, os.path.expanduser("~/workspace/tools"))
os.chdir(ROOT)

import pandas as pd

import prior_check as pc
from design_r30_grid8 import X3Inputs

MB = ("688", "689", "300", "301", "8", "4")
PAPER_DIR = "results/paper"
STATE = os.path.join(PAPER_DIR, "state.json")
INCEPTION = pd.Timestamp("2026-11-10")

STRATS = {
    "baseline_tp45": dict(label="均衡型 N4 TP45 e0.9", take=0.45, exposure=0.9, inputs="base"),
    "x3_gate15": dict(label="X3 (带2-30/精炼门-15/TP100/e1.0)", take=1.0, exposure=1.0, inputs="x3"),
}


def get_inp(kind):
    base = pc.get_inputs()
    if kind == "base":
        return base
    return X3Inputs(base.piv, gate60=-0.15)


def run_sim(kind, take, exposure):
    return pc.run_strategy(
        get_inp(kind), factor="amihud_60", n=4, rebal=30, take=take, stop=None,
        stop_exec="next", exclude=MB, capital=50_000.0, lot=100,
        cost_one_way=None, slip=0.002, run_start="2023-11-10",
        eval_start=pd.Timestamp("2025-02-13"), eval_end=None,
        phase=0, legacy_grid=False, exposure=exposure, full_liquidate=True)


def holdings_snapshot(kind, res):
    """重建当前持仓: 最后信号日 picks − 段内已被止盈平仓的。股数按 alloc/手取整 (近似)。"""
    inp = get_inp(kind)
    dates = inp.dates
    sig_idxs = [i for i in range(300, len(dates) - 1, 30)]
    si = sig_idxs[-1]
    sig_day, exec_day = dates[si], dates[si + 1]
    if kind == "x3":
        picks = get_inp("x3").picks(sig_day, 4, exclude=MB, factor="amihud_60")
    else:
        picks = inp.picks(sig_day, 4, exclude=MB, factor="amihud_60")
    tr = res.trades
    closed = set()
    if len(tr):
        m = (tr.entry_date == exec_day) & (tr.reason == "take")
        closed = set(tr.loc[m, "code"])
    snap = res.meta["rebalance_snapshots"][-1]
    alloc = float(snap["alloc_per_slot"])
    openp = pd.read_pickle("data/pivots_long_clean.pkl")["open"]
    pos = []
    for c in picks:
        if c in closed:
            continue
        px = float(openp.at[exec_day, c])
        shares = int(alloc // (px * 100) * 100)
        pos.append({"code": c, "entry_date": str(exec_day.date()),
                    "entry_px_open": round(px, 3), "shares_approx": shares})
    return {"signal_date": str(sig_day.date()), "exec_date": str(exec_day.date()),
            "positions": pos, "take_closed": sorted(closed),
            "cash_at_rebalance": round(float(snap["cash"]), 0)}


def next_rebalance(dates):
    sig_idxs = [i for i in range(300, len(dates) - 1, 30)]
    nxt = sig_idxs[-1] + 30
    # 用工作日推算未来交易日 (忽略节假日, 仅作提示)
    last = dates[-1]
    future = pd.bdate_range(last + pd.Timedelta(days=1), periods=nxt - (len(dates) - 1) + 1)
    return str(future[-2].date()), str(future[-1].date())


def cmd_init():
    os.makedirs(PAPER_DIR, exist_ok=True)
    state = {"inception": str(INCEPTION.date()), "strategies": {}}
    dates = pc.get_inputs().dates
    ns, ne = next_rebalance(dates)
    state["next_signal_est"], state["next_exec_est"] = ns, ne
    for key, cfg in STRATS.items():
        res = run_sim(cfg["inputs"], cfg["take"], cfg["exposure"])
        eq = res.eq.dropna()
        state["strategies"][key] = {
            "label": cfg["label"],
            "inception_equity": round(float(eq.loc[INCEPTION]), 2),
            "holdings": holdings_snapshot(cfg["inputs"], res),
        }
        print(key, state["strategies"][key]["inception_equity"],
              [p["code"] for p in state["strategies"][key]["holdings"]["positions"]])
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    print("下个调仓 (推算): 信号", ns, "执行", ne)
    print("state →", STATE)


def cmd_report():
    with open(STATE, encoding="utf-8") as f:
        state = json.load(f)
    out = {"as_of": None, "forward": {}}
    for key, cfg in STRATS.items():
        res = run_sim(cfg["inputs"], cfg["take"], cfg["exposure"])
        eq = res.eq.dropna()
        fwd = eq.loc[INCEPTION:]
        inc_eq = state["strategies"][key]["inception_equity"]
        fwd_ret = float(eq.iloc[-1] / inc_eq - 1) * 100
        fwd_mdd = float((fwd / fwd.cummax() - 1).min()) * 100 if len(fwd) > 1 else 0.0
        out["forward"][key] = {
            "label": cfg["label"], "equity": round(float(eq.iloc[-1]), 0),
            "fwd_ret_pct": round(fwd_ret, 2), "fwd_mdd_pct": round(fwd_mdd, 2),
            "holdings_now": [p["code"] for p in holdings_snapshot(cfg["inputs"], res)["positions"]],
        }
        out["as_of"] = str(eq.index[-1].date())
    path = os.path.join(PAPER_DIR, f"report_{out['as_of']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


def cmd_update():
    today = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y%m%d")
    # 下载器的缓存只看文件存不存在 — 先删掉 max date 落后于最近工作日的缓存, 否则拉不到新数据
    cache_dir = "data/_sina3y_cache"
    last_bdate = pd.bdate_range(end=pd.Timestamp.now(tz="Asia/Shanghai").normalize(),
                                 periods=1)[0]
    stale = 0
    for fn in os.listdir(cache_dir):
        p = os.path.join(cache_dir, fn)
        try:
            d = pd.read_pickle(p)
            if len(d) == 0 or pd.to_datetime(d["date"]).max() < last_bdate:
                os.unlink(p)
                stale += 1
        except Exception:
            os.unlink(p)
            stale += 1
    print(f"失效缓存 {stale} 只, 将重新拉取 (目标 END_DATE={today})", flush=True)
    env = dict(os.environ, END_DATE=today)
    subprocess.run([sys.executable, os.path.expanduser("~/workspace/tools/download_ashare_3y.py")],
                   env=env, check=True)
    # 重建 pivots_long.pkl: 长表透视; shares 沿用旧静态快照
    long = pd.read_pickle("data/ashare_daily_long.pkl")
    old = pd.read_pickle("data/pivots_long.pkl")
    piv = {}
    for fld in ("open", "high", "low", "close", "volume", "amount"):
        piv[fld] = long.pivot(index="date", columns="code", values=fld)
    piv["shares"] = old["shares"]
    for fld in ("open", "high", "low", "close", "volume", "amount"):
        piv[fld] = piv[fld].reindex(columns=old["close"].columns)
    pd.to_pickle(piv, "data/pivots_long.pkl")
    subprocess.run([sys.executable, "clean_data.py"], check=True)
    cmd_report()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    {"init": cmd_init, "report": cmd_report, "update": cmd_update}[cmd]()
