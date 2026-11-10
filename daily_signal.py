#!/usr/bin/env python
"""
A股 Amihud 流动性策略 — 每日信号脚本
=====================================
一条命令输出: 今天该持有哪 50 只、仓位多少、相比上次要买卖什么。

用法:
  python daily_signal.py                 # 用现有数据算信号
  python daily_signal.py --update        # 先增量拉最新行情再算
  python daily_signal.py --update --commit   # 确认调仓, 更新状态文件

策略规格 (v3-final):
  选股: 全A沪深, 剔除ST/次新/日均成交额<500万
        流通市值 5%~30% 分位, 取 Amihud(20日) 最高的 50 只, 等权
  调仓: 每 60 交易日
  风控: 中证1000 收盘 < MA20 → 仓位降至 50%
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
OUT = BASE / "results"
SIG = OUT / "signals"
STATE = BASE / "state"
SIG.mkdir(parents=True, exist_ok=True)
STATE.mkdir(parents=True, exist_ok=True)

NHOLD = 50
REBAL = 60
SIZE = (0.05, 0.30)
MIN_ADV = 5e6
FACTOR = "amihud"
INDEX = "000852"
MA = 20

STATE_FILE = STATE / "holdings.json"


# ---------------------------------------------------------------- 数据更新
def update_data():
    """增量拉取最新行情 (只补缺的日子)"""
    import akshare as ak
    from concurrent.futures import ThreadPoolExecutor, as_completed

    daily = pd.read_pickle(DATA / "ashare_daily_long.pkl")
    last = daily["date"].max()
    start = (last - pd.Timedelta(days=10)).strftime("%Y%m%d")
    end = datetime.now().strftime("%Y%m%d")
    codes = sorted(daily["code"].unique())
    print(f"更新行情: {len(codes)} 只, 区间 {start}~{end}")

    keep = daily[daily["date"] < last]
    fresh = []

    def one(code):
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                    start_date=start, end_date=end, adjust="qfq")
            if df is None or len(df) == 0:
                return None
            df = df.rename(columns={"日期": "date", "开盘": "open", "收盘": "close",
                                    "最高": "high", "最低": "low",
                                    "成交量": "volume", "成交额": "amount"})
            df = df[["date", "open", "high", "low", "close", "volume", "amount"]]
            df["date"] = pd.to_datetime(df["date"])
            df["code"] = code
            return df[df["date"] >= last]
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(one, c) for c in codes]
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            if r is not None and len(r):
                fresh.append(r)
            if i % 1000 == 0:
                print(f"  {i}/{len(codes)}", flush=True)

    if not fresh:
        print("没有新数据")
        return False
    add = pd.concat(fresh, ignore_index=True)
    merged = pd.concat([keep, add], ignore_index=True)
    merged = merged.drop_duplicates(subset=["date", "code"], keep="last")
    merged.to_pickle(DATA / "ashare_daily_long.pkl")
    print(f"新增 {len(add):,} 行, 最新日期 {merged['date'].max().date()}")
    return True


def rebuild_pivots():
    """行情更新后重建透视表"""
    print("重建透视表...")
    os.system(f'cd "{BASE}" && .venv/bin/python rebuild_pivots_long.py > /dev/null 2>&1')
    print("完成")


# ---------------------------------------------------------------- 信号计算
def compute(dates_to_check=None):
    os.environ.setdefault("ASHARE_PIVOTS", "pivots_long.pkl")
    import engine as E
    import risk_control as R

    p = E.piv()
    c = p["close"]
    dates = c.index
    t = dates[-1]

    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    seasoned = c.shift(250).notna()
    fac = E.FACTORS[FACTOR](p)
    cap = c.loc[t] * p["shares"]

    valid = seasoned.loc[t] & (adv20.loc[t] > MIN_ADV) & c.loc[t].notna() & fac.loc[t].notna()
    lo, hi = cap.quantile(SIZE[0]), cap.quantile(SIZE[1])
    valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
    pool = valid[valid].index

    picks = list(fac.loc[t, pool].nlargest(NHOLD).index)

    # 风控
    s = R._index_series(INDEX)
    ma = s.rolling(MA).mean()
    above = bool(s.iloc[-1] > ma.iloc[-1])
    pos = 1.0 if above else 0.5

    return dict(date=t, picks=picks, pool_size=len(pool),
                lo=lo, hi=hi, pos=pos, above=above,
                idx_last=float(s.iloc[-1]), idx_ma=float(ma.iloc[-1]),
                cap=cap, adv20=adv20, fac=fac, dates=dates, close=c.loc[t])


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return None


def save_state(res):
    STATE_FILE.write_text(json.dumps({
        "date": str(res["date"].date()),
        "picks": res["picks"],
        "position": res["pos"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="先增量拉最新行情")
    ap.add_argument("--commit", action="store_true", help="确认调仓, 写入状态文件")
    ap.add_argument("--top", type=int, default=15, help="控制台显示前N只")
    a = ap.parse_args()

    if a.update:
        if update_data():
            rebuild_pivots()

    res = compute()
    t = res["date"]
    picks = res["picks"]
    ind = None
    try:
        os.environ.setdefault("ASHARE_PIVOTS", "pivots_long.pkl")
        import engine as E
        ind = E.industry_map()
    except Exception:
        pass

    uni = pd.read_pickle(DATA / "universe.pkl").set_index("code")

    print("=" * 74)
    print(f"Amihud 流动性策略 — 信号 @ {t.date()}")
    print("=" * 74)
    print(f"股票池 {res['pool_size']} 只  "
          f"(流通市值 {res['lo']/1e8:.1f}亿 ~ {res['hi']/1e8:.1f}亿, 日成交额>{MIN_ADV/1e4:.0f}万)")

    print(f"\n【风控】中证1000 {res['idx_last']:.1f}  vs  MA20 {res['idx_ma']:.1f}")
    if res["above"]:
        print(f"  → 在均线上方, 目标仓位 100%")
    else:
        print(f"  → 在均线下方, 目标仓位 50%")

    # 调仓节奏
    st = load_state()
    if st:
        try:
            d0 = pd.Timestamp(st["date"])
            n = int((res["dates"] > d0).sum())
            nxt = max(REBAL - n, 0)
            print(f"\n【调仓节奏】上次调仓 {st['date']}, 已过 {n} 个交易日, "
                  f"{'距下次调仓还有 ' + str(nxt) + ' 天' if nxt > 0 else '★ 已到调仓日 ★'}")
        except Exception:
            pass
    else:
        print("\n【调仓节奏】无历史状态, 按首次建仓处理")

    # 变化
    if st:
        old, new = set(st["picks"]), set(picks)
        buy = [c for c in picks if c not in old]
        sell = [c for c in st["picks"] if c not in new]
        hold = len(set(picks) & set(st["picks"]))
        print(f"\n【相对上次的变化】买入 {len(buy)} 只 / 卖出 {len(sell)} 只 / 保留 {hold} 只")
        if buy:
            names = ", ".join(f"{c}({uni['name'].get(c,'')})" for c in buy[:10])
            print(f"  买入: {names}{' ...' if len(buy) > 10 else ''}")
        if sell:
            names = ", ".join(f"{c}({uni['name'].get(c,'')})" for c in sell[:10])
            print(f"  卖出: {names}{'...' if len(sell) > 10 else ''}")

    # 持仓
    print(f"\n【目标持仓】{len(picks)} 只, 每只 {res['pos']/NHOLD:.2%} (按 {res['pos']:.0%} 仓位)")
    rows = []
    for i, code in enumerate(picks, 1):
        rows.append({
            "序号": i, "代码": code,
            "名称": uni["name"].get(code, ""),
            "行业": ind.get(code, "") if ind is not None else "",
            "最新价": round(float(res["close"][code]), 2),
            "流通市值(亿)": round(float(res["cap"][code]) / 1e8, 2),
            "日均成交额(万)": round(float(res["adv20"].loc[t, code]) / 1e4, 0),
            "Amihud": round(float(res["fac"].loc[t, code]), 4),
            "权重": f"{res['pos']/NHOLD:.2%}",
        })
    df = pd.DataFrame(rows)
    print(df.head(a.top).to_string(index=False))
    if len(df) > a.top:
        print(f"... 其余 {len(df)-a.top} 只见 CSV")

    tag = t.strftime("%Y%m%d")
    df.to_csv(SIG / f"{tag}_target.csv", index=False, encoding="utf-8-sig")
    (SIG / f"{tag}_summary.json").write_text(json.dumps({
        "date": str(t.date()), "position": res["pos"], "above_ma": res["above"],
        "n_hold": len(picks), "pool_size": res["pool_size"], "picks": picks,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n清单: {SIG / f'{tag}_target.csv'}")

    if a.commit:
        save_state(res)
        print(f"状态已更新: {STATE_FILE}")
    elif st is None or st.get("picks") != picks:
        print("提示: 加 --commit 可把本次持仓写入状态, 作为下次对比基准")


if __name__ == "__main__":
    main()
