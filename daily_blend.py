#!/usr/bin/env python
"""
组合策略每日信号 (v-final)
==========================
输出两档：

  A档【可执行】: 纯多头 + MA15择时清仓
     不需要融券, 普通股票账户可做
     预期: 年化 ~29% / 回撤 ~-19% / 夏普 ~1.5

  B档【理想版，需对冲工具】: 40%多头 + 60%多空对冲
     空头需要融券或股指期货, 普通账户做不了完整版
     预期: 年化 ~22% / 回撤 ~-9% / 夏普 ~2.4

用法:
  python daily_blend.py                # 用现有数据
  python daily_blend.py --update        # 先增量拉最新行情
  python daily_blend.py --commit        # 写状态文件
"""
import argparse
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import engine as E
import strategy_lab as S
import combo_lab as C
import risk_control as R

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
OUT = BASE / "results" / "signals"
STATE = BASE / "state"
OUT.mkdir(parents=True, exist_ok=True)
STATE.mkdir(parents=True, exist_ok=True)

GATE = 0.75          # 因子门控前25%
MIN_ADV = 20_000_000
ENTRY_ATR, TP_ATR = 0.3, 0.8
NHOLD_LONG = 50      # 多头持仓数(信号层面展示前50)
N_LS = 30            # 多空每边数量
MA, INDEX = 15, "000905"
STATE_FILE = STATE / "blend_holdings.json"


def load():
    p = E.piv()
    c = p["close"]
    return p, c


def long_candidates(p, c, top=50):
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    atr = C.get_atr(14)
    ratio = C.combo_rank("amihud+amount_level")
    t = c.index[-1]
    liquid = (adv20.loc[t] > MIN_ADV) & c.loc[t].notna()
    gate = liquid & (ratio.loc[t] >= GATE)
    pool = gate[gate].index
    buy = (c.loc[t] - ENTRY_ATR * atr.loc[t])
    sell = buy + TP_ATR * atr.loc[t].shift(0) if False else None
    # 卖出价按信号日 ATR 锁定
    sell_px = buy + TP_ATR * atr.loc[t]
    fac = ratio.loc[t, pool].dropna()
    picks = list(fac.nlargest(top).index)
    uni = pd.read_pickle(DATA / "universe.pkl").set_index("code")
    rows = []
    for code in picks:
        rows.append({
            "代码": code, "名称": uni["name"].get(code, ""),
            "现价": round(float(c.loc[t, code]), 2),
            "买入价": round(float(buy[code]), 2),
            "卖出价": round(float(sell_px[code]), 2),
            "距买入价": f"{(buy[code]/c.loc[t, code]-1):+.1%}",
            "日均成交额(万)": round(float(adv20.loc[t, code]) / 1e4, 0),
        })
    return pd.DataFrame(rows), t


def short_candidates(p, c, top=30):
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    seasoned = c.shift(250).notna()
    fac = E.FACTORS["amihud"](p)
    t = c.index[-1]
    valid = seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna() & fac.loc[t].notna()
    cap = c.loc[t] * p["shares"]
    lo, hi = cap.quantile(0.05), cap.quantile(0.30)
    valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
    pool = valid[valid].index
    if len(pool) < top:
        return pd.DataFrame(), t
    shorts = list(fac.loc[t, pool].nsmallest(top).index)
    uni = pd.read_pickle(DATA / "universe.pkl").set_index("code")
    rows = []
    for code in shorts:
        rows.append({
            "代码": code, "名称": uni["name"].get(code, ""),
            "现价": round(float(c.loc[t, code]), 2),
            "流通市值(亿)": round(float(cap[code]) / 1e8, 1),
        })
    return pd.DataFrame(rows), t


def timing_state():
    try:
        idx = R._index_series(INDEX)
        ma = idx.rolling(MA).mean()
        above = bool(idx.iloc[-1] > ma.iloc[-1])
        return above, float(idx.iloc[-1]), float(ma.iloc[-1])
    except Exception as e:
        return None, None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()

    if a.update:
        print("增量更新行情...")
        os.system(f"cd {BASE} && .venv/bin/python daily_signal.py --update > /dev/null 2>&1")
        os.system(f"cd {BASE} && .venv/bin/python rebuild_pivots_long.py > /dev/null 2>&1")
        print("完成")

    p, c = load()
    t = c.index[-1]

    print("=" * 78)
    print(f"组合策略每日信号 — {t.date()}")
    print("=" * 78)

    above, px, ma = timing_state()
    if above is None:
        print("择时状态获取失败, 默认满仓")
        pos = 1.0
    else:
        pos = 1.0 if above else 0.0
        print(f"【大盘择时】中证500 {px:.1f} vs MA15 {ma:.1f} → "
              f"{'在均线上方' if above else '在均线下方, 清仓观望'}")
        print(f"目标总仓位: {pos:.0%}")
        if not above:
            print("  ⚠️  当前应空仓, 下面清单仅供均线收复后建仓参考, 不要现在买入")

    print(f"\n--- A档【可执行】纯多头 (amihud+amount_level, 门控前25%) ---")
    longs, _ = long_candidates(p, c, NHOLD_LONG)
    print(f"候选 {len(longs)} 只, 每只买入价 = 昨收 - 0.3×ATR, 止盈 = 买入价 + 0.8×ATR")
    print(longs.head(a.top).to_string(index=False))
    if len(longs) > a.top:
        print(f"... 共 {len(longs)} 只")

    print(f"\n--- B档【需融券/期货】多空对冲腿 (N=30/边, 美元中性) ---")
    shorts, _ = short_candidates(p, c, N_LS)
    if len(shorts):
        print(f"空头候选 {len(shorts)} 只 (做多Amihud最低的 = 最流动小盘股):")
        print(shorts.head(min(a.top, 10)).to_string(index=False))
    else:
        print("  (无数据)")

    tag = t.strftime("%Y%m%d")
    longs.to_csv(OUT / f"blend_{tag}_long.csv", index=False, encoding="utf-8-sig")
    shorts.to_csv(OUT / f"blend_{tag}_short.csv", index=False, encoding="utf-8-sig")
    print(f"\n清单已存: {OUT / f'blend_{tag}_long.csv'} / {OUT / f'blend_{tag}_short.csv'}")

    if a.commit:
        STATE_FILE.write_text(__import__("json").dumps({
            "date": str(t.date()), "position": pos,
            "long": longs["代码"].tolist(),
            "short": shorts["代码"].tolist() if len(shorts) else [],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"状态已存: {STATE_FILE}")
        print("\n提醒: B档空头需要融券账户或股指期货对冲, 普通账户请只做A档。")


if __name__ == "__main__":
    main()
