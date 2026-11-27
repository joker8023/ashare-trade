"""
F1 区间收益报告 —— 指定 shares 锚点（不落盘，仅内存修正）
=========================================================
背景：pivots_2020_clean.pkl 的 shares = universe.float_cap / close(anchor)。
      文档口径 anchor = 数据最后一日收盘；2026-11-27 14:12 的重建误用了脚本默认
      anchor=2026-11-12，导致 97.5% 的股票 shares 变动 >1%，市值分位选股随之改变。
本脚本按指定 anchor 在内存里重算 shares，再跑 F1，用于对比。

用法:
  .venv/bin/python research/f1_periods_anchor.py --anchor last
  .venv/bin/python research/f1_periods_anchor.py --anchor 2026-11-24 --json
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("ASHARE_PIVOTS", "pivots_2020_clean.pkl")

import numpy as np
import pandas as pd

import engine as E
import risk_control as R
from research.f1_periods import (FACTOR, DIRECTION, N_HOLD, REBAL, SIZE, COST,
                                 MIN_ADV, MA, CUT, INDEX_CODE, TRAIL, YEARS,
                                 window_stats, build, pending_period)


def corrected_piv(anchor: str) -> dict:
    p = dict(E.piv())
    uni = pd.read_pickle(E.DATA / "universe_2020.pkl")
    fc = uni.set_index("code")["float_cap"].astype("float64")
    c = p["close"].astype("float64")
    a = c.index[-1] if anchor == "last" else pd.Timestamp(anchor)
    ac = c.loc[a]
    sh = (fc / ac).replace([np.inf, -np.inf], np.nan).dropna()
    p["shares"] = sh.astype("float32")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", default="last")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    base_piv = E.piv()
    E._PIV = corrected_piv(a.anchor)
    print(f"anchor={a.anchor}  (数据末日 {base_piv['close'].index[-1].date()})")

    base = E.returns_series(FACTOR, direction=DIRECTION, n_hold=N_HOLD, rebal=REBAL,
                            size_range=SIZE, cost=COST, min_adv=MIN_ADV)
    r, scale = R.apply_index_filter(base, ma=MA, cut=CUT, index_code=INDEX_CODE)
    pend_raw = pending_period()
    pend, _ = R.apply_index_filter(pend_raw, ma=MA, cut=CUT, index_code=INDEX_CODE) if len(pend_raw) else (pend_raw, None)
    r_ext = pd.concat([r, pend]).sort_index()
    r_ext = r_ext[~r_ext.index.duplicated(keep="first")]

    res = {"anchor": a.anchor, "grid": build(r), "ext": build(r_ext),
           "bare": build(base),
           "pending": {"start": str(pend.index[0].date()) if len(pend) else None,
                       "end": str(pend.index[-1].date()) if len(pend) else None,
                       "ret": float((1 + pend).prod() - 1) if len(pend) else None,
                       "n": int(len(pend))}}
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    def line(s):
        return (f"{s['window']:<8}{s['start']}~{s['end']:<12}  "
                f"ret={s['ret']*100:+8.2f}%  ann={s['ann']*100:+8.2f}%  "
                f"mdd={s['mdd']*100:+7.2f}%  sh={s['sharpe']:+.2f}  n={s['n']}")

    print("\n[滚动-网格]")
    for s in res["grid"]["trailing"]:
        print(" ", line(s))
    print("\n[滚动-含在建期]")
    for s in res["ext"]["trailing"]:
        print(" ", line(s))
    print("\n[历年-网格]")
    for s in res["grid"]["yearly"]:
        print(" ", line(s))
    print("\n[历年-含在建期]")
    for s in res["ext"]["yearly"]:
        print(" ", line(s))
    print("\n[全区间]")
    for k, nm in [("grid", "网格"), ("ext", "含在建期"), ("bare", "裸无择时")]:
        f = res[k]["full"]
        print(f"  {nm:<8}{f['start']}~{f['end']} ret={f['ret']*100:+.2f}% "
              f"ann={f['ann']*100:+.2f}% mdd={f['mdd']*100:+.2f}%")
    print("\n[三关]")
    for nm, s, e in [("TRAIN", "2020-01-01", "2023-06-30"),
                     ("TEST", "2023-07-01", "2024-12-31"),
                     ("OOS", "2025-01-01", "2026-12-31")]:
        rr = r[(r.index >= pd.Timestamp(s)) & (r.index <= pd.Timestamp(e))]
        st = window_stats(rr, nm)
        print(f"  {nm:<6}{st['start']}~{st['end']} ann={st['ann']*100:+.2f}% "
              f"mdd={st['mdd']*100:+.2f}% sh={st['sharpe']:+.2f}")


if __name__ == "__main__":
    main()
