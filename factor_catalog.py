"""
因子目录 + 单因子筛选
====================
54 个因子按经济含义分类, 每个因子给出:
  - 经济逻辑
  - 信息系数 IC / ICIR / t值 (预测能力)
  - 单因子组合回测 (年化/夏普/回撤/胜率)

用于后续挑出可作为选股条件的因子
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import engine as E

BASE = Path(__file__).resolve().parent
OUT = BASE / "results"
OUT.mkdir(exist_ok=True)

# 因子分类与含义
CATALOG = {
    "流动性/规模": {
        "amihud": "Amihud非流动性(20日): |收益|/成交额, 越大越不流动",
        "amihud_5": "Amihud 5日窗口",
        "amihud_60": "Amihud 60日窗口",
        "amihud_neutral": "Amihud 行业内中性化",
        "amihud60_neutral": "Amihud60 行业内中性化",
        "amihud_orth": "Amihud 剔除市值影响后的残差",
        "amihud_smooth": "Amihud 与低换手加权组合",
        "amihud_icw": "Amihud 与反转按IC加权",
        "amihud_turnstd": "Amihud + 换手率波动",
        "amihud60_turnstd": "Amihud60 + 换手率波动",
        "amount_level": "成交额水平: 越小越冷门",
        "size": "流通市值: 越小越好",
        "turn20": "换手率(20日): 越低越好",
        "turn_orth": "换手率 剔除市值影响",
        "turn_std": "换手率波动: 越不稳定越差",
        "turn_chg": "换手率变化: 近期相对长期",
    },
    "反转/动量": {
        "rev5": "5日反转", "rev20": "20日反转", "rev60": "60日反转",
        "rev20_orth": "20日反转 剔除市值影响",
        "lag_rev": "滞后反转(剔除最近5日)",
        "mom60": "60日动量", "mom120": "120日动量", "mom12_1": "12-1动量",
        "bias20": "乖离率: 价格偏离20日均线",
        "rsi14": "RSI超卖反转",
    },
    "波动/风险": {
        "vol20": "20日波动率(低波溢价)", "vol60": "60日波动率",
        "downvol20": "下行波动率", "idio_vol": "特质波动率",
        "max20": "MAX效应: 最大单日收益", "skew20": "收益率偏度",
        "kurt20": "收益率峰度", "volvol": "波动率的波动率",
        "beta60": "Beta(低beta溢价)", "amplitude": "振幅(低振幅溢价)",
        "maxdd20": "近20日内部最大回撤", "dd48w": "距48周最大回撤",
    },
    "量价关系": {
        "volratio": "量比: 近期量/长期量",
        "pv_corr": "量价相关性",
        "pv_div": "价量背离: 涨但量缩",
        "gap": "隔夜跳空均值",
        "overnight": "累计隔夜收益",
        "intraday": "累计日内收益",
        "streak": "连续涨跌天数",
    },
    "位置/形态": {
        "high52": "距52周高点距离",
        "low52": "距52周低点距离",
    },
    "复合": {
        "liq_rev": "流动性+反转", "liq_lowvol": "流动性+低波",
        "liq_size": "流动性+小市值", "triple": "流动性+反转+低波",
        "quad": "流动性+反转+低波+低换手",
        "size_rev": "小市值+反转", "rev_lowvol": "反转+低波",
    },
}


def all_catalog_entries():
    rows = []
    for cat, d in CATALOG.items():
        for k, v in d.items():
            rows.append({"类别": cat, "因子": k, "含义": v})
    return pd.DataFrame(rows)


def screen(factor, n=100, rebal=20, cost=0.005, size=(0.05, 0.30)):
    """单因子 IC + 组合回测"""
    try:
        r = E.evaluate(factor, "high", n_hold=n, rebal=rebal,
                       size_range=size, cost=cost)
        return r
    except Exception as e:
        return {"factor": factor, "error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="只打印因子目录")
    ap.add_argument("--factor", default=None, help="只筛一个因子")
    ap.add_argument("--all", action="store_true", help="筛全部")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.list:
        df = all_catalog_entries()
        have = set(E.FACTORS.keys())
        df["已实现"] = df["因子"].isin(have)
        print(df.to_string(index=False))
        print(f"\n合计 {len(df)} 个因子, 已实现 {df['已实现'].sum()} 个")
        return

    if a.factor:
        r = screen(a.factor)
        print(json.dumps({k: (round(float(v), 4) if isinstance(v, (int, float, np.floating)) else v)
                          for k, v in r.items() if k != "yearly"}, ensure_ascii=False))
        return

    if a.all:
        rows = []
        for i, f in enumerate(sorted(E.FACTORS.keys()), 1):
            r = screen(f)
            if "error" in r:
                print(f"[{i}] {f}: 失败 {r['error'][:60]}")
                continue
            rows.append({
                "因子": f, "IC": r["IC"], "ICIR": r["ICIR"], "t值": r["IC_t"],
                "正IC比": r["IC_pos_ratio"], "年化": r["ann"], "夏普": r["sharpe"],
                "回撤": r["mdd"], "胜率": r["win_rate"],
            })
            print(f"[{i}] {f:<20} IC={r['IC']:+.4f} 年化={r['ann']:+.1%} 夏普={r['sharpe']:.2f}")
        df = pd.DataFrame(rows).sort_values("IC", ascending=False)
        df.to_csv(OUT / "factor_screen_clean.csv", index=False, encoding="utf-8")
        print(f"\n已存: {OUT / 'factor_screen_clean.csv'}")


if __name__ == "__main__":
    main()
