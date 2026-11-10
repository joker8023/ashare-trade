"""N4 TP45 e0.9 月度选股 — 与 n4_tp45_e09_monthly.html 同口径
逻辑（已用 2026-11-02 反向验证通过）：
  amihud_60 最大4只；上市>=250日、日均成交额>500万、
  流通市值5%-30%分位、仅主板（剔除688/689/300/301/4/8开头）

用法：
  # 1) 先把行情补到信号日收盘后（信号日=12月首个交易日，2026-12-01周二）：
  .venv/bin/python daily_signal.py --update
  .venv/bin/python rebuild_pivots_long.py
  .venv/bin/python clean_data.py        # 生成 pivots_long_clean.pkl

  # 2) 出12月新股（信号日收盘后跑）：
  .venv/bin/python monthly_picks_n4.py --date 2026-12-01
  # 不加 --date 则用数据最后一天
  .venv/bin/python monthly_picks_n4.py
"""
import os
os.environ.setdefault("ASHARE_PIVOTS", "pivots_long_clean.pkl")
import argparse
import pandas as pd
import engine as E


def is_main(code: str) -> bool:
    s = str(code).strip()
    if s.startswith(("688", "689", "300", "301")):
        return False
    if s[:1] in ("4", "8"):
        return False
    return True


def picks_on(signal: pd.Timestamp):
    p = E.piv()
    c = p["close"]
    t = pd.Timestamp(signal)
    if t not in c.index:
        # 取 <= signal 的最近交易日
        cand = c.index[c.index <= t]
        if len(cand) == 0:
            raise SystemExit(f"信号日 {t.date()} 早于数据起点")
        t = cand[-1]
        print(f"注意：{signal} 非交易日，用最近交易日 {t.date()} 代替")
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    seasoned = c.shift(250).notna()
    amihud = E.FACTORS["amihud_60"](p)
    valid = seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna()
    cap = c.loc[t] * p["shares"]
    lo, hi = cap[valid].quantile(0.05), cap[valid].quantile(0.30)
    valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
    pool = valid[valid].index
    main = [x for x in pool if is_main(x)]
    top4 = list(amihud.loc[t, main].nlargest(4).index)
    return t, top4, len(main), lo, hi, c, amihud


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="信号日，默认数据最后一天，如 2026-12-01")
    a = ap.parse_args()
    p = E.piv()
    c = p["close"]
    sig = pd.Timestamp(a.date) if a.date else c.index[-1]
    t, top4, pool_n, lo, hi, closes, amihud = picks_on(sig)
    try:
        uni = pd.read_pickle("data/universe.pkl").set_index("code")
        getname = lambda code: str(uni["name"].get(code, ""))
    except Exception:
        getname = lambda code: ""
    print(f"信号日（首个交易日）: {t.date()}  池子 {pool_n} 只  市值 {lo/1e8:.1f}亿~{hi/1e8:.1f}亿")
    print("12月4只（代码 名称 推荐买入=信号日收盘 Amihud）：")
    for code in top4:
        px = float(closes.loc[t, code])
        print(f"  {code} {getname(code)}  {px:.2f}  amihud={float(amihud.loc[t, code]):.6f}")
    print("\n填表：打开 n4_tp45_e09_monthly.html → 月份选 2026-12（手动·无内置）→")
    print("每行填 代码/名称/推荐买入 → 点“实际买入＝推荐买入” → 按建议股数买入即可。")


if __name__ == "__main__":
    main()
