"""
组合层面风控 overlay
====================
把基础策略 (amihud 选股) 的逐日收益, 叠加风控层, 看能否压住 -60% 回撤。

三种 overlay (都可组合):
  1. vol_target   : 按实现波动率动态调仓, 目标年化波动 X%
  2. dd_breaker   : 组合回撤超过阈值 → 降仓; 回撤修复 → 恢复
  3. index_filter : 基准指数(中证1000)跌破均线 → 降仓

所有信号都用「昨日及以前」的数据, 不含未来函数。
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import engine as E

BASE = Path(__file__).resolve().parent
OUT = BASE / "results"


def cached_base(factor, n, rebal, size, cost):
    """缓存基础策略收益序列, 避免每次重复计算"""
    cache_dir = BASE / "results" / "_cache"
    cache_dir.mkdir(exist_ok=True)
    piv_name = os.getenv("ASHARE_PIVOTS", "pivots_full.pkl").replace(".pkl", "")
    key = f"{factor}_{n}_{rebal}_{size[0]}_{size[1]}_{cost}_{piv_name}"
    f = cache_dir / f"{key}.pkl"
    if f.exists():
        return pd.read_pickle(f)
    r = E.returns_series(factor, n_hold=n, rebal=rebal, size_range=size, cost=cost)
    r.to_pickle(f)
    return r


def apply_vol_target(r: pd.Series, target=0.20, window=20, max_lev=1.0):
    """按滚动实现波动率缩放到目标波动"""
    rv = r.rolling(window).std() * np.sqrt(252)
    scale = (target / rv).clip(upper=max_lev)
    scale = scale.shift(1).fillna(1.0)
    return r * scale, scale


def apply_dd_breaker(r: pd.Series, trigger=-0.20, recover=-0.10, cut=0.5):
    """
    回撤熔断: 组合自身回撤触发降仓。
    用逐日模拟, 因为降仓会改变后续净值路径 (路径依赖)。
    """
    scale = pd.Series(1.0, index=r.index)
    eq = 1.0
    peak = 1.0
    state = 1.0
    for i, (dt, x) in enumerate(r.items()):
        dd = eq / peak - 1           # 用昨日为止的回撤决策今日仓位
        if state >= 1.0 and dd <= trigger:
            state = cut
        elif state < 1.0 and dd >= recover:
            state = 1.0
        scale.iloc[i] = state
        eq *= (1 + x * state)
        peak = max(peak, eq)
    return r * scale, scale


def _index_series(index_code):
    """缓存指数日线, 避免重复请求"""
    cache_dir = BASE / "results" / "_cache"
    cache_dir.mkdir(exist_ok=True)
    f = cache_dir / f"index_{index_code}.pkl"
    if f.exists():
        return pd.read_pickle(f)
    import akshare as ak
    idx = ak.index_zh_a_hist(symbol=index_code, period="daily",
                             start_date="20090101", end_date="20261231")
    idx["日期"] = pd.to_datetime(idx["日期"])
    s = idx.set_index("日期").sort_index()["收盘"].astype(float)
    s.to_pickle(f)
    return s


def apply_index_filter(r, ma=60, cut=0.5, index_code="000852"):
    """基准指数择时: 指数在均线下方时降仓 (非空仓)"""
    try:
        s = _index_series(index_code)
        sig = (s > s.rolling(ma).mean()).shift(1)
        on = sig.reindex(r.index.union(s.index)).ffill().reindex(r.index)
        scale = on.map({True: 1.0, False: cut}).astype(float).fillna(1.0)
    except Exception as e:
        print(f"[warn] 指数 {index_code} 获取失败({e}), 跳过该层", file=sys.stderr)
        return r, pd.Series(1.0, index=r.index)
    return r * scale, scale


def stats(r, base=None):
    eq = (1 + r).cumprod()
    yrs = len(r) / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else 0
    vol = r.std() * np.sqrt(252)
    mdd = (eq / eq.cummax() - 1).min()
    out = {
        "ann": round(float(ann), 4),
        "vol": round(float(vol), 4),
        "sharpe": round(float(r.mean() * 252 / vol), 3) if vol > 0 else None,
        "mdd": round(float(mdd), 4),
        "calmar": round(float(ann / abs(mdd)), 3) if mdd < 0 else None,
        "total": round(float(eq.iloc[-1] - 1), 4),
    }
    if base is not None:
        out["ann_vs_base"] = round(float(ann - stats(base)["ann"]), 4)
    return out


def build(factor="amihud", n=100, rebal=60, size=(0.05, 0.30), cost=0.005,
          vol_target=None, dd_trigger=None, dd_cut=0.5, dd_recover=-0.10,
          index_ma=None, index_cut=0.5):
    r = cached_base(factor, n, rebal, size, cost)
    layers = []

    if vol_target:
        r, s = apply_vol_target(r, target=vol_target)
        layers.append(f"vol_target({vol_target:.0%})")
    if dd_trigger is not None:
        r, s = apply_dd_breaker(r, trigger=dd_trigger, recover=dd_recover, cut=dd_cut)
        layers.append(f"dd_breaker({dd_trigger:.0%}→{dd_cut:.0%})")
    if index_ma:
        r, s = apply_index_filter(r, ma=index_ma, cut=index_cut)
        layers.append(f"index_ma({index_ma}d→{index_cut:.0%})")

    return r, layers


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--factor", default="amihud")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--rebal", type=int, default=60)
    ap.add_argument("--size", nargs=2, type=float, default=[0.05, 0.30])
    ap.add_argument("--cost", type=float, default=0.005)
    ap.add_argument("--vol-target", type=float, default=None)
    ap.add_argument("--dd-trigger", type=float, default=None)
    ap.add_argument("--dd-cut", type=float, default=0.5)
    ap.add_argument("--dd-recover", type=float, default=-0.10)
    ap.add_argument("--index-ma", type=int, default=None)
    ap.add_argument("--index-cut", type=float, default=0.5)
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    base_r = cached_base(a.factor, a.n, a.rebal, tuple(a.size), a.cost)
    r, layers = build(a.factor, a.n, a.rebal, tuple(a.size), a.cost,
                      a.vol_target, a.dd_trigger, a.dd_cut, a.dd_recover,
                      a.index_ma, a.index_cut)

    if a.start:
        base_r = base_r[base_r.index >= pd.Timestamp(a.start)]
        r = r[r.index >= pd.Timestamp(a.start)]
    if a.end:
        base_r = base_r[base_r.index <= pd.Timestamp(a.end)]
        r = r[r.index <= pd.Timestamp(a.end)]

    res = {
        "base": stats(base_r),
        "overlay": stats(r),
        "layers": layers,
        "period": f"{r.index[0].date()}~{r.index[-1].date()}",
    }
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(f"区间 {res['period']}  层: {layers or ['无']}")
        for k, v in [("基础", res["base"]), ("叠加风控", res["overlay"])]:
            print(f"  {k:8s} 年化={v['ann']:7.1%} 波动={v['vol']:6.1%} "
                  f"夏普={v['sharpe']:5.2f} 回撤={v['mdd']:7.1%} Calmar={v['calmar']:5.2f}")


if __name__ == "__main__":
    main()
