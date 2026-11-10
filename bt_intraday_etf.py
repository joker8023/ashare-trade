"""三只ETF三类日内策略回测（单边成本0.02%，信号日内执行无未来函数）"""
import pandas as pd
import numpy as np
import os

COST = 0.0002  # 单边万2
SYMS = ["510300", "510500", "159915"]

def metrics(r, name):
    r = r.dropna()
    ann = r.mean() * 252
    vol = r.std() * np.sqrt(252)
    sharpe = ann / vol if vol > 0 else 0
    eq = (1 + r).cumprod()
    dd = eq / eq.cummax() - 1
    traded = r[r != 0]
    win = (traded > 0).mean() if len(traded) else 0
    return {"strategy": name, "n_days": len(r), "n_trades": int((r != 0).sum()),
            "ann_ret": round(float(ann), 4), "max_dd": round(float(dd.min()), 4),
            "sharpe": round(float(sharpe), 2), "win_rate": round(float(win), 3)}

all_rows = []
for SYM in SYMS:
    path = f"data/minute_etf/{SYM}_5m.csv"
    if not os.path.exists(path):
        continue
    df = pd.read_csv(path, parse_dates=["时间"])
    df = df.sort_values("时间").reset_index(drop=True)
    print(SYM, "rows:", len(df), df["时间"].min(), "~", df["时间"].max())
    df["date"] = df["时间"].dt.date
    df["hm"] = df["时间"].dt.strftime("%H:%M")
    g = df.groupby("date")
    daily = pd.DataFrame({
        "open": g.first()["开盘"],
        "close_1030": g["收盘"].apply(
            lambda s: s[df.loc[s.index, "hm"] <= "10:30"].iloc[-1]),
        "close": g.last()["收盘"],
    })
    daily["prev_close"] = daily["close"].shift(1)
    # 剔除数据断档接缝日（日历间隔>10天，如159915缺2025年）：缺口无意义
    dts = pd.Series(pd.to_datetime(daily.index), index=daily.index)
    seam = ((dts - dts.shift(1)).dt.days > 10).values
    daily = daily.loc[~seam]
    daily = daily.dropna()
    print("trading days:", len(daily), daily.index.min(), "~", daily.index.max())

    morn = daily["close_1030"] / daily["open"] - 1
    day_pm = daily["close"] / daily["close_1030"] - 1
    day_full = daily["close"] / daily["open"] - 1
    gap = daily["open"] / daily["prev_close"] - 1

    res = {}
    pos_a = np.sign(morn).replace(0, 1)          # a. 日内动量：上午方向持有到收盘
    res["a_am_momentum"] = pos_a * day_pm - 2 * COST
    sig_b = pd.Series(0.0, index=daily.index)   # b. 缺口>±1%反向持有到收盘
    sig_b[gap > 0.01] = -1
    sig_b[gap < -0.01] = 1
    res["b_gap_reversal_1pct"] = sig_b * day_full - (sig_b != 0) * 2 * COST
    sig_c = pd.Series(0.0, index=daily.index)   # c. 上午>±1.5%反向持有到收盘
    sig_c[morn > 0.015] = -1
    sig_c[morn < -0.015] = 1
    res["c_am_reversal_1.5pct"] = sig_c * day_pm - (sig_c != 0) * 2 * COST

    rows = [metrics(v, k) for k, v in res.items()]
    for r in rows:
        r["symbol"] = SYM
    all_rows += rows
    print(f"--- {SYM} ---")
    print(pd.DataFrame(rows).to_string(index=False))
    print("b触发占比:", round(float((res['b_gap_reversal_1pct'] != 0).mean()), 3),
          "c触发占比:", round(float((res['c_am_reversal_1.5pct'] != 0).mean()), 3),
          "上午均值/std:", round(float(morn.mean()), 5), round(float(morn.std()), 4),
          "缺口均值/std:", round(float(gap.mean()), 5), round(float(gap.std()), 4))

out = pd.DataFrame(all_rows)
os.makedirs("results", exist_ok=True)
out.to_csv("results/intraday_etf.csv", index=False)
print(out.to_string(index=False))
