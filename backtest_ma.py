"""
沪深300ETF (510300) 双均线择时回测 v2 —— 修正执行模型
- 数据: AKShare 前复权日线
- 信号: 收盘后计算 MA_fast > MA_slow
- 执行: 次日开盘成交 (T+1, 真实可执行)
- 收益分解: 隔夜段用昨日仓位, 日内段用今日仓位
- 成本: 佣金 0.025% + 滑点 0.1% (ETF 免印花税)
"""
import os
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
OUT = BASE / "results"
OUT.mkdir(exist_ok=True)

SYMBOL = os.getenv("SYMBOL", "510300")
START = os.getenv("START", "20200101")
END = datetime.now().strftime("%Y%m%d")
COMMISSION = 0.00025
SLIPPAGE = 0.001
COST = COMMISSION + SLIPPAGE


def fetch() -> pd.DataFrame:
    import akshare as ak
    df = ak.fund_etf_hist_em(symbol=SYMBOL, period="daily",
                             start_date=START, end_date=END, adjust="qfq")
    df = df.rename(columns={"日期": "date", "开盘": "open", "收盘": "close",
                            "最高": "high", "最低": "low", "成交额": "amount"})
    df["date"] = pd.to_datetime(df["date"])
    df = df[["date", "open", "high", "low", "close", "amount"]].sort_values("date")
    return df.set_index("date").astype(float)


def run_ma(df: pd.DataFrame, fast: int, slow: int) -> pd.DataFrame:
    d = df.copy()
    close = d["close"]
    d["ma_fast"] = close.rolling(fast).mean()
    d["ma_slow"] = close.rolling(slow).mean()

    # 收盘信号 -> 次日开盘执行
    signal = (d["ma_fast"] > d["ma_slow"]).astype(int)
    pos = signal.shift(1).fillna(0).astype(int)
    # 信号当日不可用(slow期未满)时强制空仓
    pos[d["ma_slow"].isna()] = 0
    d["pos"] = pos

    prev_pos = d["pos"].shift(1).fillna(0)
    overnight = d["open"] / close.shift(1) - 1
    intraday = close / d["open"] - 1

    d["ret_asset"] = close.pct_change().fillna(0)
    d["ret_strat"] = prev_pos * overnight.fillna(0) + d["pos"] * intraday.fillna(0)

    # 换仓成本
    d["turnover"] = (d["pos"] - prev_pos).abs()
    d["ret_strat"] -= d["turnover"] * COST

    d["equity"] = (1 + d["ret_strat"]).cumprod()
    d["equity_bh"] = (1 + d["ret_asset"]).cumprod()
    return d


def metrics(eq: pd.Series, ret: pd.Series, label: str) -> dict:
    n = len(eq)
    total = eq.iloc[-1] - 1
    years = n / 252
    ann = (1 + total) ** (1 / years) - 1 if years > 0 else 0
    vol = ret.std() * np.sqrt(252)
    sharpe = (ret.mean() * 252) / vol if vol > 0 else 0
    mdd = (eq / eq.cummax() - 1).min()
    return {
        "策略": label,
        "总收益": f"{total:.2%}",
        "年化": f"{ann:.2%}",
        "波动": f"{vol:.2%}",
        "夏普": f"{sharpe:.2f}",
        "最大回撤": f"{mdd:.2%}",
        "Calmar": f"{ann/abs(mdd):.2f}" if mdd < 0 else "N/A",
    }


def main():
    base = fetch()
    print(f"数据: {SYMBOL} {base.index[0].date()} ~ {base.index[-1].date()}  {len(base)} 行\n")

    # 参数扫描
    rows = []
    for fast in [5, 10, 20, 30, 40, 60]:
        for slow in [20, 40, 60, 120, 200]:
            if fast >= slow:
                continue
            d = run_ma(base, fast, slow)
            ret = d["ret_strat"]
            ann = (1 + d["equity"].iloc[-1] - 1) ** (252 / len(d)) - 1
            mdd = (d["equity"] / d["equity"].cummax() - 1).min()
            vol = ret.std() * np.sqrt(252)
            rows.append({
                "MA": f"{fast}/{slow}",
                "总收益": d["equity"].iloc[-1] - 1,
                "年化": ann,
                "夏普": (ret.mean() * 252) / vol if vol > 0 else 0,
                "最大回撤": mdd,
                "交易次数": int(d["turnover"].sum()),
            })

    sweep = pd.DataFrame(rows).sort_values("夏普", ascending=False)
    disp = sweep.copy()
    for c in ["总收益", "年化", "最大回撤"]:
        disp[c] = disp[c].map(lambda x: f"{x:.1%}")
    disp["夏普"] = disp["夏普"].map(lambda x: f"{x:.2f}")
    print("=== 参数扫描 (按夏普排序, Top 10) ===")
    print(disp.head(10).to_string(index=False))

    bh_ann = (base["close"].iloc[-1] / base["close"].iloc[0]) ** (252 / len(base)) - 1
    bh_mdd = (base["close"] / base["close"].cummax() - 1).min()
    print(f"\n基准 买入持有: 年化 {bh_ann:.2%}  最大回撤 {bh_mdd:.2%}")

    # 最优参数详细结果
    best = sweep.iloc[0]
    f, s = map(int, best["MA"].split("/"))
    d = run_ma(base, f, s)
    print(f"\n=== 最优参数 MA{f}/{s} vs 买入持有 ===")
    tbl = pd.DataFrame([
        metrics(d["equity"], d["ret_strat"], f"MA{f}/{s}"),
        metrics(d["equity_bh"], d["ret_asset"], "买入持有"),
    ])
    print(tbl.to_string(index=False))
    print(f"\n持仓天数: {int(d['pos'].sum())}/{len(d)} ({d['pos'].mean():.1%})  "
          f"换手次数: {int(d['turnover'].sum())}")

    tag = f"{SYMBOL}_MA{f}_{s}"
    d.to_csv(OUT / f"{tag}_daily.csv", encoding="utf-8")
    sweep.to_csv(OUT / f"{SYMBOL}_sweep.csv", index=False, encoding="utf-8")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(d.index, d["equity"], label=f"MA{f}/{s} timing", lw=1.6)
        ax.plot(d.index, d["equity_bh"], label="Buy & Hold", lw=1.2, alpha=0.75)
        ax.set_title(f"{SYMBOL} MA{f}/{s} Timing vs Buy&Hold")
        ax.set_ylabel("Equity (x)")
        ax.legend(); ax.grid(alpha=0.3)
        fig.tight_layout()
        p = OUT / f"{tag}_equity.png"
        fig.savefig(p, dpi=130)
        print(f"图表: {p}")
    except Exception as e:
        print(f"绘图跳过: {e}")


if __name__ == "__main__":
    main()
