"""
生成今日挂单价清单
==================
对每个策略, 输出今天应该挂什么单: 哪只股票、买入价多少、卖出价多少、止损价多少。

只列出「买入价距离当前价 5% 以内」的股票 —— 这些是近期可能触发的
清单按买入价距当前价的远近排序
"""
import os
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import engine as E
import strategy_lab as S

BASE = Path(__file__).resolve().parent
OUT = BASE / "results" / "levels"
OUT.mkdir(parents=True, exist_ok=True)

GATE = 0.70
MIN_ADV = 20_000_000
NEAR = 0.05          # 只看买入价在现价 5% 以内的
TOP_SHOW = 15


def main():
    p = E.piv()
    c = p["close"]
    t = c.index[-1]

    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    liquid = (adv20 > MIN_ADV) & c.notna()
    fac = E.FACTORS["amihud"](p)
    rank = fac.rank(axis=1, pct=True)
    gate = liquid & (rank >= GATE)

    uni = pd.read_pickle(BASE / "data" / "universe.pkl").set_index("code")
    ind = E.industry_map()

    sel = ["s05_ma_pullback", "s10_lowvol", "s01_grid", "s03_fixed"]
    print("=" * 96)
    print(f"今日挂单价清单 — 基准日 {t.date()}   候选池 {int(gate.loc[t].sum())} 只")
    print("=" * 96)

    all_rows = []
    for key in sel:
        name, fn = S.STRATEGIES[key]
        buy, sell, stop = fn(p)
        b = buy.loc[t]
        s = sell.loc[t]
        st = stop.loc[t]
        px = c.loc[t]

        ok = gate.loc[t] & b.notna() & s.notna() & px.notna()
        cand = pd.DataFrame({
            "code": px.index, "现价": px.values, "买入价": b.reindex(px.index).values,
            "卖出价": s.reindex(px.index).values, "止损价": st.reindex(px.index).values,
        }).set_index("code")
        cand = cand[ok.reindex(cand.index).fillna(False)]
        if cand.empty:
            continue
        cand["距离"] = cand["买入价"] / cand["现价"] - 1
        cand = cand[(cand["距离"] > -NEAR) & (cand["距离"] < 0.005)]
        if cand.empty:
            continue
        cand = cand.sort_values("距离", ascending=False).head(TOP_SHOW)

        print(f"\n【{name}】 可挂单 {len(cand)} 只 (买入价在现价5%以内)")
        print(f"{'代码':<8}{'名称':<10}{'现价':>8}{'买入价':>8}{'卖出价':>8}"
              f"{'止损价':>8}{'距现价':>8}{'预期收益':>9}")
        print("-" * 76)
        for code, r in cand.iterrows():
            nm = str(uni["name"].get(code, ""))[:8]
            exp = r["卖出价"] / r["买入价"] - 1
            print(f"{code:<8}{nm:<10}{r['现价']:>8.2f}{r['买入价']:>8.2f}"
                  f"{r['卖出价']:>8.2f}{r['止损价']:>8.2f}"
                  f"{r['距离']:>7.1%}{exp:>9.1%}")
            all_rows.append({
                "策略": name, "代码": code, "名称": nm,
                "行业": ind.get(code, ""), "现价": round(r["现价"], 2),
                "买入价": round(r["买入价"], 2), "卖出价": round(r["卖出价"], 2),
                "止损价": round(r["止损价"], 2),
                "距现价": f"{r['距离']:.2%}",
                "预期收益": f"{r['卖出价']/r['买入价']-1:.1%}",
                "日均成交额(万)": round(float(adv20.loc[t, code]) / 1e4, 0),
            })

    df = pd.DataFrame(all_rows)
    tag = t.strftime("%Y%m%d")
    df.to_csv(OUT / f"orders_{tag}.csv", index=False, encoding="utf-8-sig")
    print(f"\n完整清单: {OUT / f'orders_{tag}.csv'}  ({len(df)} 条)")
    print("\n说明:")
    print("  · 买入价 = 挂限价买单的价格, 当日最低价触及即成交")
    print("  · 卖出价 = 建仓时锁定, 之后不再变动")
    print("  · 止损价 = 建议设 -8%, 但回测显示会降低夏普, 可自行决定")
    print("  · 数据基于清洗后行情, 最新交易日为 " + str(t.date()))


if __name__ == "__main__":
    main()
