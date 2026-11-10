"""
v3 滚动样本外验证 (Walk-Forward, 含风控参数)
==========================================
每年初只用手头历史数据, 从 24 个候选配置里挑一个最好的:
  factor ∈ {amihud, amihud60_neutral}
  N     ∈ {50, 100}
  rebal ∈ {20, 60}
  风控  ∈ {无, MA20→50%, MA40→50%}

然后原样跑下一年, 不允许任何未来信息。
"""
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

import os
os.environ.setdefault("ASHARE_PIVOTS", "pivots_long.pkl")
import engine as E
import risk_control as R

BASE = Path(__file__).resolve().parent
OUT = BASE / "results"
COST = 0.005
SIZE = (0.05, 0.30)

FACTORS = ["amihud", "amihud60_neutral"]
NS = [50, 100]
REBALS = [20, 60]
RISKS = [(None, 1.0), (20, 0.5), (40, 0.5)]


def build_series():
    """先建选股层的收益序列 (贵), 再叠加不同风控 (便宜)"""
    raw = {}
    for f, n, rb in itertools.product(FACTORS, NS, REBALS):
        key = (f, n, rb)
        try:
            raw[key] = R.cached_base(f, n, rb, SIZE, COST)
        except Exception as e:
            print(f"  {key} 失败: {e}")
    print(f"选股层序列: {len(raw)} 个")

    full = {}
    for key, r in raw.items():
        for ma, cut in RISKS:
            if ma is None:
                full[(key, None)] = r
            else:
                ov, _ = R.apply_index_filter(r, ma=ma, cut=cut, index_code="000852")
                full[(key, ma)] = ov
    print(f"含风控的完整配置: {len(full)} 个")
    return full


def sharpe(r):
    if len(r) < 60:
        return -9
    v = r.std() * np.sqrt(252)
    return r.mean() * 252 / v if v > 0 else -9


def ann(r):
    if len(r) == 0:
        return 0.0
    return (1 + r).prod() ** (252 / len(r)) - 1


def main():
    series = build_series()
    all_idx = sorted(set().union(*[set(s.index) for s in series.values()]))
    years = sorted({d.year for d in all_idx})
    print(f"覆盖年份: {years[0]} ~ {years[-1]}")

    print("\n" + "=" * 78)
    print("v3 滚动样本外 — 每年只用历史数据选 (选股+风控) 全部参数")
    print("=" * 78)

    oos_parts, rows = [], []
    for y in years:
        train_end = pd.Timestamp(f"{y}-01-01")
        test_end = pd.Timestamp(f"{y}-12-31")

        best, best_s = None, -9
        for k, s in series.items():
            tr = s[s.index < train_end]
            if len(tr) < 250:
                continue
            sc = sharpe(tr)
            if sc > best_s:
                best_s, best = sc, k
        if best is None:
            continue

        s = series[best]
        te = s[(s.index >= train_end) & (s.index <= test_end)]
        if len(te) < 40:
            continue

        (f, n, rb), ma = best
        oos_parts.append(te)
        rows.append({
            "年份": y,
            "选股": f"{f}|N={n}|R={rb}",
            "风控": f"MA{ma}→50%" if ma else "无",
            "训练夏普": round(best_s, 2),
            "当年收益": round(ann(te), 4),
            "当年夏普": round(sharpe(te), 2),
        })

    df = pd.DataFrame(rows)
    print(df.to_string(index=False))

    oos = pd.concat(oos_parts).sort_index()
    oos = oos[~oos.index.duplicated(keep="first")]
    eq = (1 + oos).cumprod()
    mdd = (eq / eq.cummax() - 1).min()

    print("\n" + "-" * 78)
    print(f"滚动样本外: 年化 {ann(oos):.1%}   夏普 {sharpe(oos):.2f}   "
          f"回撤 {mdd:.1%}   累计 {eq.iloc[-1]:.2f}x")
    print(f"盈利年份: {(df['当年收益']>0).sum()}/{len(df)}")
    print(f"选中风控的比例: {(df['风控']!='无').sum()}/{len(df)}")
    print("-" * 78)

    # 对照 1: 固定 v3 配置 (风控+选股都固定)
    fixed = series[(("amihud60_neutral", 100, 60), 20)]
    fx = fixed[fixed.index >= pd.Timestamp(f"{years[1]}-01-01")]
    print(f"\n对照A 固定v3配置(选择器只作参考): 年化 {ann(fx):.1%} 夏普 {sharpe(fx):.2f} "
          f"回撤 {((1+fx).cumprod()/(1+fx).cumprod().cummax()-1).min():.1%}")

    # 对照 2: 每年都选到"事后最优" (偷看未来) —— 上界
    print("对照B 事后最优 (不可实现的上界): 见下表")

    df.to_csv(OUT / "walkforward_v3.csv", index=False, encoding="utf-8")
    pd.DataFrame({"ret": oos, "equity": eq}).to_csv(
        OUT / "walkforward_v3_daily.csv", encoding="utf-8")

    # 图
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS",
                                           "Heiti SC", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(eq.index, eq.values, lw=1.6, color="#c0392b", label="滚动样本外(含风控选择)")
        ax.plot(fx.index, (1 + fx).cumprod().values, lw=1.2, color="#7f8c8d",
                alpha=0.85, label="固定 v3 配置")
        ax.set_yscale("log")
        ax.set_title(f"v3 滚动样本外  {oos.index[0].year}-{oos.index[-1].year}  "
                     f"年化{ann(oos):.1%}  夏普{sharpe(oos):.2f}  回撤{mdd:.1%}")
        ax.set_ylabel("净值 (对数)"); ax.legend(); ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(OUT / "walkforward_v3.png", dpi=130)
        print(f"\n图表: {OUT / 'walkforward_v3.png'}")
    except Exception as e:
        print(f"绘图跳过: {e}")


if __name__ == "__main__":
    main()
