"""
因子组合 × 动态止盈止损 策略实验室
==================================
用户目标: 胜率高 + 回撤少 + 收益高

核心设计:
  1. 选股: 多个因子秩和组合 (f1+f2+...) → 因子门控
  2. 买入价: 昨收 - k1 × ATR        (ATR 自适应波动, 高波动股挂更远)
  3. 止盈价: 买入价 + k2 × ATR      ← 动态, 随 ATR 缩放
  4. 止损价: 买入价 - k3 × ATR      ← 动态, 随 ATR 缩放
  5. 大盘择时: 中证1000 破 MA20 → 清仓

用法:
  python combo_lab.py --combo "amihud" --entry-atr 1.0 --tp-atr 2.0 --sl-atr 3.0
  python combo_lab.py --combo "amihud+turn20" --json
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import engine as E
import strategy_lab as S

BASE = Path(__file__).resolve().parent
OUT = BASE / "results" / "combo"
OUT.mkdir(parents=True, exist_ok=True)

START = "2015-01-01"
MIN_ADV = 20_000_000
COST = 0.0015
MAX_HOLD = 20
MAX_POS = 20

_FAC_CACHE = {}
_ATR_CACHE = {}


def get_factor(name):
    if name not in _FAC_CACHE:
        _FAC_CACHE[name] = E.FACTORS[name](E.piv())
    return _FAC_CACHE[name]


def get_atr(n=14):
    if n not in _ATR_CACHE:
        p = E.piv()
        h, l, c = p["high"], p["low"], p["close"]
        tr = pd.concat([
            h - l,
            (h - c.shift(1)).abs(),
            (l - c.shift(1)).abs(),
        ]).groupby(level=0).max()
        _ATR_CACHE[n] = tr.rolling(n).mean()
    return _ATR_CACHE[n]


def combo_rank(combo: str):
    """把多个因子等权秩和后归一化到 0~1, 越大越优先"""
    names = [x.strip() for x in combo.replace("|", "+").split("+") if x.strip()]
    acc = None
    for nm in names:
        f = get_factor(nm)
        r = f.rank(axis=1, pct=True)
        acc = r if acc is None else acc + r
    return acc / len(names)


def run(combo="amihud", gate=0.80, entry_atr=1.0, tp_atr=2.0, sl_atr=3.0,
        atr_n=14, max_hold=MAX_HOLD, start=START, use_market=True,
        max_exposure=1.0, min_adv=MIN_ADV, market_ma=20, market_index="000852",
        max_pos=MAX_POS):
    p = E.piv()
    c = p["close"]
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    atr = get_atr(atr_n)
    ratio = combo_rank(combo)

    d0 = pd.Timestamp(start)
    idx = c.index[c.index >= d0]
    cols = c.columns

    # 挂单价 (全部用 t-1 数据)
    buy = (c - entry_atr * atr).shift(1)
    sell = buy + tp_atr * atr.shift(1)
    stop = buy - sl_atr * atr.shift(1)

    liquid = (adv20 > min_adv) & c.notna()
    ok = liquid & (ratio >= gate)

    def cut(x):
        return x.reindex(index=idx, columns=cols).where(ok.reindex(index=idx, columns=cols))

    eq, tr = S.backtest(p, cut(buy), cut(sell), cut(stop),
                        max_hold=max_hold, max_pos=max_pos, cost=COST,
                        max_exposure=max_exposure,
                        market_scale=(_market_scale(p, market_ma, market_index) if use_market else None),
                        liquidate_on_off=use_market)
    if len(eq) < 200:
        return None

    yrs = len(eq) / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1
    r = eq.pct_change(fill_method=None).dropna()
    vol = r.std() * np.sqrt(252)
    mdd = (eq / eq.cummax() - 1).min()

    res = {
        "combo": combo, "gate": gate,
        "entry_atr": entry_atr, "tp_atr": tp_atr, "sl_atr": sl_atr,
        "market": use_market, "exposure": max_exposure,
        "年化": float(ann), "夏普": float(r.mean() * 252 / vol) if vol > 0 else 0.0,
        "回撤": float(mdd), "Calmar": float(ann / abs(mdd)) if mdd < 0 else 0.0,
        "总收益": float(eq.iloc[-1] - 1), "交易数": int(len(tr)),
    }
    if len(tr):
        res["胜率"] = float((tr["ret"] > 0).mean())
        res["平均单笔"] = float(tr["ret"].mean())
        res["平均持有天"] = float(tr["days"].mean())
        w = tr.loc[tr["ret"] > 0, "ret"]
        l = tr.loc[tr["ret"] <= 0, "ret"]
        res["盈亏比"] = float(abs(w.mean() / l.mean())) if len(l) and l.mean() != 0 else 0.0
        vc = tr["reason"].value_counts()
        res["止盈率"] = float(vc.get("止盈", 0) / len(tr))
        res["止损率"] = float(vc.get("止损", 0) / len(tr))
        res["清仓率"] = float(vc.get("择时清仓", 0) / len(tr))
        res["超期率"] = float(vc.get("超期", 0) / len(tr))
    return res


_MKT = {}


def _market_scale(p, ma=20, code="000852"):
    k = (ma, code)
    if k not in _MKT:
        import risk_control as R
        idx = R._index_series(code)
        sig = (idx > idx.rolling(ma).mean()).shift(1).astype(float)
        _MKT[k] = sig.reindex(p["close"].index).ffill().fillna(0.0)
    return _MKT[k]


def score(res):
    """综合分: 目标为 胜率高 + 回撤少 + 收益高"""
    if not res:
        return -9e9
    ann = res["年化"]
    mdd = abs(res["回撤"])
    win = res.get("胜率", 0)
    # 硬约束: 回撤 > 35% 或 胜率 < 50% 降权
    s = 0.40 * ann + 0.30 * (1 - min(mdd / 0.5, 1.0)) + 0.30 * win
    if mdd > 0.35:
        s -= 0.5
    if win < 0.55:
        s -= 0.3
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", default="amihud")
    ap.add_argument("--gate", type=float, default=0.80)
    ap.add_argument("--entry-atr", type=float, default=1.0)
    ap.add_argument("--tp-atr", type=float, default=2.0)
    ap.add_argument("--sl-atr", type=float, default=3.0)
    ap.add_argument("--atr-n", type=int, default=14)
    ap.add_argument("--max-hold", type=int, default=MAX_HOLD)
    ap.add_argument("--no-market", action="store_true")
    ap.add_argument("--max-exposure", type=float, default=1.0)
    ap.add_argument("--market-ma", type=int, default=20)
    ap.add_argument("--market-index", default="000852")
    ap.add_argument("--max-pos", type=int, default=MAX_POS)
    ap.add_argument("--start", default=START)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    res = run(a.combo, a.gate, a.entry_atr, a.tp_atr, a.sl_atr, a.atr_n,
              a.max_hold, a.start, not a.no_market, a.max_exposure,
              market_ma=a.market_ma, market_index=a.market_index,
              max_pos=a.max_pos)
    if res is None:
        print('{"error":"数据不足"}')
        return
    res["score"] = round(score(res), 4)

    if a.json:
        print(json.dumps({k: (round(v, 5) if isinstance(v, float) else v)
                          for k, v in res.items()}, ensure_ascii=False))
        return

    print(f"组合 {res['combo']}  门控前{(1-res['gate'])*100:.0f}%  "
          f"买入-{res['entry_atr']}ATR 止盈+{res['tp_atr']}ATR 止损-{res['sl_atr']}ATR")
    print(f"  年化 {res['年化']:+.1%}  回撤 {res['回撤']:.1%}  夏普 {res['夏普']:.2f}  "
          f"Calmar {res['Calmar']:.2f}")
    if "胜率" in res:
        print(f"  胜率 {res['胜率']:.1%}  盈亏比 {res['盈亏比']:.2f}  平均单笔 {res['平均单笔']:+.2%}  "
              f"交易 {res['交易数']}  均持 {res['平均持有天']:.1f}天")
        print(f"  平仓: 止盈{res['止盈率']:.0%} 止损{res['止损率']:.0%} "
              f"择时清仓{res['清仓率']:.0%} 超期{res['超期率']:.0%}")


if __name__ == "__main__":
    main()
