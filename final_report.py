"""
最终策略报告: amihud 流动性因子
配置: N=100, R=60日调仓, 市值5%-30%分位, 单边成本0.5%
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

import engine as E

BASE = Path(__file__).resolve().parent
OUT = BASE / "results"

CFG = dict(factor="amihud", n_hold=100, rebal=60,
           size_range=(0.05, 0.30), cost=0.005)


def main():
    # 详细指标
    res = E.evaluate(CFG["factor"], "high", CFG["n_hold"], CFG["rebal"],
                     CFG["size_range"], cost=CFG["cost"])

    print("=" * 66)
    print("最终策略: Amihud 非流动性因子 + 小微盘池")
    print("=" * 66)
    print(f"选股: 全A(沪深) → 剔除ST/次新/日成交额<500万")
    print(f"      流通市值 5%~30% 分位内, 取 Amihud 非流动性最高的 100 只")
    print(f"调仓: 每 60 个交易日等权再平衡")
    print(f"区间: {res['period']}  ({res['days']} 交易日)")
    print()
    print(f"IC={res['IC']}  ICIR={res['ICIR']}  t={res['IC_t']}  正IC比={res['IC_pos_ratio']}")
    print(f"年化={res['ann']:.1%}  夏普={res['sharpe']}  最大回撤={res['mdd']:.1%}  Calmar={res['calmar']}")
    print(f"年化波动={res['vol']:.1%}  日胜率={res['win_rate']:.1%}  平均换手={res['turnover']:.1%}")
    print()
    print("分年度:")
    for k, v in res["yearly"].items():
        print(f"  {k}: {v:+7.1%}")

    # 成本敏感性
    print("\n成本敏感性:")
    for c in [0.0015, 0.005, 0.01, 0.02, 0.03]:
        r = E.evaluate(CFG["factor"], "high", CFG["n_hold"], CFG["rebal"],
                       CFG["size_range"], cost=c)
        print(f"  单边{c*100:4.2f}%: 年化 {r['ann']:6.1%}  夏普 {r['sharpe']:5.2f}  回撤 {r['mdd']:7.1%}")

    # 净值曲线
    p = E.piv()
    c = p["close"]
    amount = p["amount"]
    adv20 = amount.rolling(20, min_periods=10).mean()
    seasoned = c.shift(250).notna()
    fac = E.FACTORS[CFG["factor"]](p)
    dates = c.index
    rets, prev = [], set()
    for i in range(300, len(dates) - CFG["rebal"] - 2, CFG["rebal"]):
        t, t1 = dates[i], dates[i + 1]
        t2 = dates[min(i + 1 + CFG["rebal"], len(dates) - 1)]
        valid = seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna() & fac.loc[t].notna()
        cap = c.loc[t] * p["shares"]
        lo, hi = cap.quantile(0.05), cap.quantile(0.30)
        valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
        pool = valid[valid].index
        if len(pool) < 100:
            continue
        picks = list(fac.loc[t, pool].nlargest(CFG["n_hold"]).index)
        seg = c.loc[t1:t2, picks].ffill()
        if len(seg) < 2:
            continue
        pr = seg.div(seg.iloc[0]).mean(axis=1).pct_change().dropna()
        cur = set(picks)
        to = 1.0 if not prev else len(cur - prev) / max(len(cur), 1)
        if len(pr):
            pr.iloc[0] -= to * 2 * CFG["cost"]
        prev = cur
        rets.append(pr)

    r = pd.concat(rets).sort_index()
    r = r[~r.index.duplicated(keep="first")]
    eq = (1 + r).cumprod()

    pd.DataFrame({"ret": r, "equity": eq}).to_csv(
        OUT / "final_amihud_daily.csv", encoding="utf-8")

    # 基准
    import akshare as ak
    idx = ak.index_zh_a_hist(symbol="000985", period="daily",
                             start_date="20210101", end_date="20261231")
    idx["日期"] = pd.to_datetime(idx["日期"])
    bench = idx.set_index("日期").sort_index()["收盘"].astype(float)
    bench = bench.reindex(eq.index).ffill()
    beq = bench / bench.iloc[0]

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS",
                                           "Heiti SC", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8),
                                       gridspec_kw={"height_ratios": [3, 1]})
        ax1.plot(eq.index, eq.values, label="Amihud 流动性策略", lw=1.7, color="#c0392b")
        ax1.plot(beq.index, beq.values, label="中证全指", lw=1.2, color="#7f8c8d", alpha=0.85)
        ax1.set_yscale("log")
        ax1.set_ylabel("净值 (对数)")
        ax1.set_title(f"Amihud 非流动性策略  N=100, 60日调仓, 成本0.5%  "
                      f"年化{res['ann']:.1%} 夏普{res['sharpe']:.2f}")
        ax1.legend(); ax1.grid(alpha=0.3)

        dd = eq / eq.cummax() - 1
        ax2.fill_between(dd.index, dd.values * 100, 0, color="#c0392b", alpha=0.45)
        ax2.set_ylabel("回撤 (%)"); ax2.grid(alpha=0.3)

        fig.tight_layout()
        fig.savefig(OUT / "final_amihud_equity.png", dpi=130)
        print(f"\n图表: {OUT / 'final_amihud_equity.png'}")
    except Exception as e:
        print(f"绘图跳过: {e}")

    (OUT / "final_amihud_metrics.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"指标: {OUT / 'final_amihud_metrics.json'}")


if __name__ == "__main__":
    main()
