"""
A股多因子策略: 小市值 + 反转 (横截面 alpha)

思路
----
A股散户主导, 存在两个长期稳定的横截面效应:
  1. 小市值溢价: 流通市值越小, 长期收益越高 (剔除最小10%规避退市/流动性陷阱)
  2. 短期反转: 过去20日涨幅越高的, 未来越容易回吐; 越低的反转越强

构建
----
- 股票池: 全A, 剔除 ST/退市、上市不足250日、当日无成交
- 市值: 流通市值 = 收盘价 × 流通股本 (股本用当前值近似, 无未来价格信息)
- 反转: ret20 = close/close[-20] - 1
- 选股: 市值分位 10%~50% 内, 取 ret20 最低的 N 只, 等权
- 调仓: 每 20 个交易日
- 成本: 单边 0.15% (印花税0.05%卖出 + 佣金0.025% + 滑点)
- 可选: 中证全指 MA60 择时, 跌破空仓
"""
import os
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
OUT = BASE / "results"
OUT.mkdir(exist_ok=True)

N_HOLD = int(os.getenv("N_HOLD", "50"))
REBAL = int(os.getenv("REBAL", "20"))
SIZE_LO = float(os.getenv("SIZE_LO", "0.10"))
SIZE_HI = float(os.getenv("SIZE_HI", "0.50"))
COST_ONE_WAY = 0.0015
USE_TIMING = os.getenv("USE_TIMING", "0") == "1"


def load_data():
    daily = pd.read_pickle(DATA / "ashare_daily.pkl")
    uni = pd.read_pickle(DATA / "universe.pkl")
    print(f"数据: {len(daily):,} 行, {daily['code'].nunique()} 只股票")

    close = daily.pivot_table(index="date", columns="code", values="close")
    amount = daily.pivot_table(index="date", columns="code", values="amount")
    close = close.sort_index()
    amount = amount.sort_index()
    # 清洗: 0 或负价格视为缺失, 避免除零产生 -inf
    close = close.where(close > 0)

    # 流通股本 = 当前流通市值 / 最新收盘价
    last_close = close.iloc[-1]
    fcap = uni.set_index("code")["float_cap"]
    shares = (fcap / last_close).replace([np.inf, -np.inf], np.nan)
    shares = shares.dropna()

    return close, amount, shares


def backtest(close, amount, shares):
    dates = close.index
    codes = [c for c in close.columns if c in shares.index]
    close = close[codes]
    amount = amount[codes]
    shares = shares[codes]

    ret20 = close / close.shift(20) - 1
    adv20 = amount.rolling(20, min_periods=10).mean()
    # 上市满 250 交易日: 250日前有价格
    seasoned = close.shift(250).notna()

    rebal_idx = list(range(300, len(dates), REBAL))
    print(f"调仓次数: {len(rebal_idx)}, 每次持仓 {N_HOLD} 只")

    periods = []
    prev_set = set()
    for k, i in enumerate(rebal_idx):
        t = dates[i]
        t_end = dates[min(i + REBAL, len(dates) - 1)]

        r = ret20.loc[t]
        s = shares
        cap = close.loc[t] * s
        liquid = adv20.loc[t] > 5e6  # 日均成交额 > 500万
        valid = r.notna() & cap.notna() & liquid & seasoned[codes].loc[t]

        # 市值分位 10%~50%
        cap_valid = cap[valid]
        if len(cap_valid) < 200:
            continue
        lo = cap_valid.quantile(SIZE_LO)
        hi = cap_valid.quantile(SIZE_HI)
        pool = cap_valid[(cap_valid >= lo) & (cap_valid <= hi)].index

        rv = r.loc[pool]
        picks = list(rv.nsmallest(N_HOLD).index)
        if not picks:
            continue

        # 持仓期等权买入持有
        seg = close.loc[t:t_end, picks].ffill()
        if len(seg) < 2:
            continue
        rel = seg.div(seg.iloc[0])
        port_val = rel.mean(axis=1)
        port_ret = port_val.pct_change().dropna()

        # 换手成本
        cur = set(picks)
        turnover = 1.0 if not prev_set else len(cur - prev_set) / max(len(cur), 1)
        cost = turnover * 2 * COST_ONE_WAY
        if len(port_ret) > 0:
            port_ret.iloc[0] -= cost
        prev_set = cur
        periods.append(port_ret)

    ret = pd.concat(periods).sort_index()
    ret = ret[~ret.index.duplicated(keep="first")]
    eq = (1 + ret).cumprod()
    return ret, eq


def benchmark(close):
    """基准: 优先用中证全指(000985), 失败则退回清洗后的等权全市场"""
    try:
        import akshare as ak
        idx = ak.index_zh_a_hist(symbol="000985", period="daily",
                                 start_date="20200101",
                                 end_date=pd.Timestamp.now().strftime("%Y%m%d"))
        idx["日期"] = pd.to_datetime(idx["日期"])
        s = idx.set_index("日期").sort_index()["收盘"].astype(float)
        if len(s) > 500:
            r = s.pct_change().dropna()
            return r, (1 + r).cumprod(), "中证全指"
    except Exception as e:
        print(f"指数基准获取失败({e}), 退回等权全市场")

    r = close.pct_change(fill_method=None).mean(axis=1).dropna()
    return r, (1 + r).cumprod(), "等权全市场"


def stats(ret, eq, label):
    n = len(eq)
    years = n / 252
    total = eq.iloc[-1] - 1
    ann = (1 + total) ** (1 / years) - 1
    vol = ret.std() * np.sqrt(252)
    sharpe = ret.mean() * 252 / vol if vol > 0 else 0
    mdd = (eq / eq.cummax() - 1).min()
    calmar = ann / abs(mdd) if mdd < 0 else np.nan
    active = ret[ret != 0]
    win = (active > 0).mean() if len(active) else float("nan")
    return {
        "策略": label,
        "总收益": f"{total:.1%}",
        "年化": f"{ann:.1%}",
        "波动": f"{vol:.1%}",
        "夏普": f"{sharpe:.2f}",
        "最大回撤": f"{mdd:.1%}",
        "Calmar": f"{calmar:.2f}" if not np.isnan(calmar) else "N/A",
        "日胜率": f"{win:.1%}",
    }


def main():
    close, amount, shares = load_data()
    ret, eq = backtest(close, amount, shares)

    if USE_TIMING:
        import akshare as ak
        idx = ak.index_zh_a_hist(symbol="000985", period="daily",
                                 start_date="20200101",
                                 end_date=pd.Timestamp.now().strftime("%Y%m%d"))
        idx["日期"] = pd.to_datetime(idx["日期"])
        idx = idx.set_index("日期").sort_index()["收盘"]
        ma = idx.rolling(60).mean()
        # 关键: 用前一日收盘确定的信号, 次日才生效, 避免未来函数
        sig = (idx > ma).shift(1)
        on = sig.reindex(ret.index).ffill().fillna(False)
        ret = ret * on.astype(float)
        eq = (1 + ret).cumprod()
        label = f"小市值+反转(MA60择时)"
    else:
        label = "小市值+反转"

    bret, beq, bname = benchmark(close)
    common = ret.index.intersection(bret.index)
    bret = bret.loc[common]
    beq = (1 + bret).cumprod()

    tbl = pd.DataFrame([
        stats(ret, eq, label),
        stats(bret, beq, bname),
    ])
    print("\n" + "=" * 78)
    print(tbl.to_string(index=False))
    print("=" * 78)
    print(f"回测区间: {ret.index[0].date()} ~ {ret.index[-1].date()}  ({len(ret)} 交易日)")

    tag = f"smallcap_reversal_N{N_HOLD}_R{REBAL}" + ("_timing" if USE_TIMING else "")
    pd.DataFrame({"ret": ret, "equity": eq}).to_csv(OUT / f"{tag}_daily.csv", encoding="utf-8")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS",
                                           "Heiti SC", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(eq.index, eq.values, label=label, lw=1.6)
        ax.plot(beq.index, beq.values, label=bname, lw=1.2, alpha=0.75)
        ax.set_yscale("log")
        ax.set_title(f"A-share Small-cap + Reversal  (N={N_HOLD}, rebal={REBAL}d, log scale), " + "timing" if USE_TIMING else "A-share Small-cap + Reversal  (N={}, rebal={}d, log scale)".format(N_HOLD, REBAL))
        ax.set_ylabel("Equity (x, log)")
        ax.legend(); ax.grid(alpha=0.3)
        fig.tight_layout()
        p = OUT / f"{tag}_equity.png"
        fig.savefig(p, dpi=130)
        print(f"图表: {p}")
    except Exception as e:
        print(f"绘图跳过: {e}")


if __name__ == "__main__":
    main()
