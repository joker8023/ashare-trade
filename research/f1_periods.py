"""
F1 流动性溢价（amihud_60）区间收益 / 最大回撤报告
================================================
口径（与 docs/strategy/README.md 完全一致）：
- 数据：data/pivots_2020_clean.pkl（新浪 qfq，ASHARE_PIVOTS 可覆盖）
- 选股：amihud_60 high，N=4，R=60，流通市值分位 0.02~0.15，min_adv=5e6，单边成本 0.5%
- 择时：中证1000（000852）收盘 < MA15 -> 20% 仓位，否则 100%
- 引擎：engine.returns_series（t+1 收盘建仓，等权，现金 0 收益）

输出：
- 滚动区间（截至序列最后交易日）：1m/3m/6m/1y/2y/3y 累计收益、年化、区间内最大回撤
- 自然年 2020~2026：收益率、年内最大回撤
- 补充：把网格之后“当前在建期”（截断到最后可用日）接上后的口径

用法：
  ASHARE_PIVOTS=pivots_2020_clean.pkl .venv/bin/python research/f1_periods.py [--json]
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

FACTOR, DIRECTION, N_HOLD, REBAL = "amihud_60", "high", 4, 60
SIZE, COST, MIN_ADV = (0.02, 0.15), 0.005, 5e6
MA, CUT, INDEX_CODE = 15, 0.2, "000852"

TRAIL = [("1m", 21), ("3m", 63), ("6m", 126), ("1y", 252), ("2y", 504), ("3y", 756)]
YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]


# ---------- 数据 / 缓存 ----------
def _piv_path() -> Path:
    return E.DATA / os.getenv("ASHARE_PIVOTS", "pivots_2020_clean.pkl")


def base_series() -> pd.Series:
    """基础策略逐日收益（带数据 mtime 的缓存，数据更新自动失效）"""
    p = _piv_path()
    cache_dir = E.OUT / "_cache"
    cache_dir.mkdir(exist_ok=True)
    key = f"F1periods_{FACTOR}_{N_HOLD}_{REBAL}_{SIZE[0]}_{SIZE[1]}_{COST}_m{int(p.stat().st_mtime)}"
    f = cache_dir / f"{key}.pkl"
    if f.exists():
        return pd.read_pickle(f)
    r = E.returns_series(FACTOR, direction=DIRECTION, n_hold=N_HOLD, rebal=REBAL,
                         size_range=SIZE, cost=COST, min_adv=MIN_ADV)
    r.to_pickle(f)
    return r


def _picks_at(fac, c, adv20, seasoned, t, prev):
    valid = seasoned.loc[t] & (adv20.loc[t] > MIN_ADV) & c.loc[t].notna() & fac.loc[t].notna()
    cap = c.loc[t] * E.piv()["shares"]
    lo, hi = cap.quantile(SIZE[0]), cap.quantile(SIZE[1])
    valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
    pool = valid[valid].index
    if len(pool) < N_HOLD:
        return None
    picks = list(fac.loc[t, pool].nsmallest(N_HOLD).index if DIRECTION == "low"
                 else fac.loc[t, pool].nlargest(N_HOLD).index)
    cur = set(picks)
    to = 1.0 if not prev else len(cur - prev) / max(len(cur), 1)
    return picks, cur, to


def pending_period() -> pd.Series:
    """网格之后尚未纳入的下一期（t+1 建仓，持有到最后一个可用交易日，即“当前在建期”）"""
    p = E.piv()
    c, adv20 = p["close"], p["amount"].rolling(20, min_periods=10).mean()
    seasoned = c.shift(250).notna()
    fac = E.FACTORS[FACTOR](p)
    dates = c.index
    last_i = 300 + ((len(dates) - REBAL - 3 - 300) // REBAL) * REBAL
    i = last_i + REBAL
    if i + 1 >= len(dates):
        return pd.Series(dtype=float)

    # 上一期持仓（算换手）
    prev = None
    pk = _picks_at(fac, c, adv20, seasoned, dates[last_i], None)
    if pk is not None:
        prev = pk[1]

    t, t1 = dates[i], dates[i + 1]
    t2 = dates[min(i + 1 + REBAL, len(dates) - 1)]
    pk = _picks_at(fac, c, adv20, seasoned, t, prev)
    if pk is None:
        return pd.Series(dtype=float)
    picks, cur, to = pk
    seg = c.loc[t1:t2, picks].ffill()
    if len(seg) < 2:
        return pd.Series(dtype=float)
    pr = seg.div(seg.iloc[0]).mean(axis=1).pct_change(fill_method=None).dropna()
    if len(pr):
        pr.iloc[0] -= to * 2 * COST
    return pr


# ---------- 统计 ----------
def window_stats(r: pd.Series, label: str) -> dict:
    if len(r) == 0:
        return {"window": label, "start": None, "end": None, "ret": None,
                "ann": None, "mdd": None, "sharpe": None, "n": 0}
    eq = (1 + r).cumprod()
    yrs = len(r) / 252.0
    ann = float(eq.iloc[-1] ** (1 / yrs) - 1) if yrs > 0 and eq.iloc[-1] > 0 else None
    mdd = float((eq / eq.cummax() - 1).min())
    vol = float(r.std() * np.sqrt(252))
    sharpe = float(r.mean() * 252 / vol) if vol > 0 else None
    return {"window": label, "start": str(r.index[0].date()), "end": str(r.index[-1].date()),
            "ret": float(eq.iloc[-1] - 1), "ann": ann, "mdd": mdd, "sharpe": sharpe, "n": int(len(r))}


def build(r: pd.Series) -> dict:
    out = {"asof": str(r.index[-1].date()), "first": str(r.index[0].date()), "n": int(len(r))}
    out["trailing"] = []
    for lab, nd in TRAIL:
        rr = r.iloc[-nd:] if len(r) >= nd else r
        s = window_stats(rr, lab)
        s["requested_days"] = nd
        s["actual_days"] = int(len(rr))
        out["trailing"].append(s)
    out["yearly"] = []
    for y in YEARS:
        rr = r[r.index.year == y]
        out["yearly"].append(window_stats(rr, str(y)))
    out["full"] = window_stats(r, "full")
    return out


def fmt(v, pct=True, nd=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v*100:+.{nd}f}%" if pct else f"{v:.{nd}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    base = base_series()
    r, scale = R.apply_index_filter(base, ma=MA, cut=CUT, index_code=INDEX_CODE)
    bare = base

    # 含当前在建期
    pend = pending_period()
    r_ext = pd.concat([r, pend]).sort_index()
    r_ext = r_ext[~r_ext.index.duplicated(keep="first")]
    bare_ext = pd.concat([bare, pend]).sort_index()
    bare_ext = bare_ext[~bare_ext.index.duplicated(keep="first")]

    res = {
        "config": {"factor": FACTOR, "direction": DIRECTION, "n_hold": N_HOLD, "rebal": REBAL,
                   "size_range": list(SIZE), "cost_one_way": COST, "min_adv": MIN_ADV,
                   "timing": f"{INDEX_CODE} MA{MA} cut {CUT}", "pivots": os.getenv("ASHARE_PIVOTS")},
        "data_range": [str(_piv_path())],
        "grid": build(r),
        "grid_bare": build(bare),
        "ext": build(r_ext),
        "ext_bare": build(bare_ext),
        "pending": {"start": str(pend.index[0].date()) if len(pend) else None,
                    "end": str(pend.index[-1].date()) if len(pend) else None,
                    "ret": float((1 + pend).prod() - 1) if len(pend) else None,
                    "n": int(len(pend))},
        "n_days_timing_off": int((scale < 1).sum()),
    }
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    p = E.piv()
    print("=" * 96)
    print("F1 流动性溢价 amihud_60 | N4 R60 size0.02-0.15 cost0.5%/边 + 000852 MA15 cut20%")
    print(f"数据 {p['close'].index.min().date()} ~ {p['close'].index.max().date()}  "
          f"({len(p['close'])} 交易日, {p['close'].shape[1]} 只)")
    print(f"网格回测序列 {res['grid']['first']} ~ {res['grid']['asof']}  ({res['grid']['n']} 天)")
    if res["pending"]["start"]:
        print(f"当前在建期 {res['pending']['start']} ~ {res['pending']['end']}  "
              f"({res['pending']['n']} 天, {fmt(res['pending']['ret'])})")
    print("=" * 96)

    for title, key in [("【滚动区间】网格口径（截至 %s）" % res["grid"]["asof"], "grid"),
                       ("【滚动区间】含当前在建期（截至 %s）" % res["ext"]["asof"], "ext")]:
        print("\n" + title)
        print(f"{'窗口':<6}{'区间':<26}{'累计收益':>12}{'年化':>11}{'最大回撤':>11}{'夏普':>8}{'天数':>7}")
        for s in res[key]["trailing"]:
            rng = f"{s['start']}~{s['end']}" if s["start"] else "—"
            print(f"{s['window']:<6}{rng:<26}{fmt(s['ret']):>12}{fmt(s['ann']):>11}"
                  f"{fmt(s['mdd']):>11}{fmt(s['sharpe'], False, 2):>8}{s['actual_days']:>7}")

    for title, key in [("【历年】网格口径", "grid"), ("【历年】含当前在建期", "ext")]:
        print("\n" + title)
        print(f"{'年份':<8}{'区间':<26}{'收益率':>12}{'最大回撤':>11}{'夏普':>8}{'天数':>7}")
        for s in res[key]["yearly"]:
            rng = f"{s['start']}~{s['end']}" if s["start"] else "—"
            print(f"{s['window']:<8}{rng:<26}{fmt(s['ret']):>12}{fmt(s['mdd']):>11}"
                  f"{fmt(s['sharpe'], False, 2):>8}{s['n']:>7}")

    print("\n【全区间】")
    for key, name in [("grid", "网格"), ("ext", "含在建期"), ("grid_bare", "裸(无择时)网格")]:
        f = res[key]["full"]
        print(f"  {name:<10}{f['start']}~{f['end']}  累计={fmt(f['ret'])}  "
              f"年化={fmt(f['ann'])}  回撤={fmt(f['mdd'])}  夏普={fmt(f['sharpe'], False)}")

    # 文档三关核对
    print("\n【三关核对（网格口径）】")
    for name, s, e in [("TRAIN", "2020-01-01", "2023-06-30"),
                       ("TEST", "2023-07-01", "2024-12-31"),
                       ("OOS", "2025-01-01", "2026-12-31")]:
        rr = r[(r.index >= pd.Timestamp(s)) & (r.index <= pd.Timestamp(e))]
        st = window_stats(rr, name)
        print(f"  {name:<6}{st['start']}~{st['end']}  年化={fmt(st['ann'])}  回撤={fmt(st['mdd'])}  "
              f"夏普={fmt(st['sharpe'], False)}  n={st['n']}")
    print(f"\n择时降仓天数: {res['n_days_timing_off']} / {res['grid']['n']}")


if __name__ == "__main__":
    main()
