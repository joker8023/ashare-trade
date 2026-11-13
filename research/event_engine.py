#!/usr/bin/env python3
"""事件驱动引擎 (脱离 R30 网格): 每日收盘决策、次日收盘按盯市价成交,
费率/滑点/整手口径与 team 模拟器一致 (_cost_buy_real/_cost_sell_real, 滑点 0.2%)。
E1 非流动性事件版: X3 选股逻辑逐日扫描, 进 top 名单且有空位就买; 跌出 top25 / 门触发 /
   持满 60 个交易日 / 涨幅 +100% 就卖。最多 3 仓 (1 万本金整手可行性), 可空仓。
E2 洗盘触发: 成交额缩至 120日均 70% 以下 + 距 120日低点 <10% + ret10>0 且当日收涨 → 买;
   +25% 止盈 / -10% 止损 / 持满 30 日卖。最多 3 仓。
E3 突破触发: 收盘创 120日新高 + 成交额 >60日均 1.5 倍 → 买; 跌破 20日均线 / +50% 止盈 /
   持满 60 日卖。最多 3 仓。
窗口: 2025-02-11 → 2026-11-10 (与 X3 同窗)。本金 1 万 (E1 另跑 5 万对照)。
"""
import json
import os
import sys

ROOT = os.path.expanduser("~/workspace/ashare-trade")
sys.path.insert(0, os.path.join(ROOT, "team", "audit"))
sys.path.insert(0, os.path.expanduser("~/workspace/tools"))
os.chdir(ROOT)

import numpy as np
import pandas as pd

import prior_check as pc
from design_r30_grid8 import X3Inputs

MB = ("688", "689", "300", "301", "8", "4")
SLIP = 0.002


class EInputs(X3Inputs):
    def __init__(self, piv):
        super().__init__(piv, gate60=-0.15)
        c = self.close
        self.amt_r = self.adv20 / self.amount.rolling(120, min_periods=120).mean()
        self.lowpos = c / c.rolling(120, min_periods=120).min() - 1.0
        self.hi120 = c / c.rolling(120, min_periods=120).max()
        self.ma20 = c.rolling(20, min_periods=20).mean()
        self.amt60 = self.amount.rolling(60, min_periods=60).mean()
        self.ret1 = c.pct_change(fill_method=None)
        self.amihud60_s = self.amihud60.rolling(20, min_periods=10).mean()

    def x3_ranking(self, t, fac=None):
        """X3 规则下当日的完整排名 (Series, 值=因子, 降序即名次)。"""
        fac = self.amihud60 if fac is None else fac
        valid = (self.seasoned.loc[t] & (self.adv20.loc[t] > 5e6)
                 & self.close.loc[t].notna() & fac.loc[t].notna())
        valid &= ~((self.ret60.loc[t] < self.gate60) & (self.ret10.loc[t] < 0)).fillna(False)
        cap_t = self.cap.loc[t]
        lo, hi = cap_t.quantile(0.02), cap_t.quantile(0.30)
        valid &= ((cap_t >= lo) & (cap_t <= hi)).fillna(False)
        valid &= ~pd.Series(list(valid.index), index=valid.index).str.startswith(MB)
        return fac.loc[t][valid].sort_values(ascending=False)


def simulate(inp, mode, capital=10_000.0, max_pos=3,
             start="2025-02-11", end="2026-11-10", exit_rank=25, max_hold=60):
    dates = inp.dates
    mark = inp.mark
    i0 = int(dates.searchsorted(pd.Timestamp(start)))
    i1 = int(dates.searchsorted(pd.Timestamp(end), side="right") - 1)
    cash = float(capital)
    pos = {}          # code -> dict(shares, entry_px, entry_i, high)
    streak_in, streak_out = {}, {}   # R1 阈值再平衡: 名单持续性计数
    pending_sell, pending_buy = [], []   # [(code, alloc_hint)]
    trades, total_cost = [], 0.0
    eq_rows, expo_rows = [], []

    def px_of(i, code):
        v = mark.iat[i, mark.columns.get_loc(code)] if code in mark.columns else np.nan
        return v

    for i in range(i0, i1 + 1):
        day = dates[i]
        # ---- 执行昨日决策 (今日收盘价) ----
        for code in pending_sell:
            if code not in pos:
                continue
            px = px_of(i, code)
            if pd.isna(px) or px <= 0:
                continue
            p = pos.pop(code)
            notional = p["shares"] * px
            fee = pc._cost_sell_real(notional, SLIP)
            cash += notional - fee
            total_cost += fee
            trades.append(dict(code=code, entry_i=p["entry_i"], exit_i=i,
                               ret=px / p["entry_px"] - 1.0, hold=i - p["entry_i"]))
        pending_sell = []
        for code in pending_buy:
            if code in pos or len(pos) >= max_pos:
                continue
            px = px_of(i, code)
            if pd.isna(px) or px <= 0:
                continue
            mv = sum(p["shares"] * (px_of(i, cc) if pd.notna(px_of(i, cc)) else p["entry_px"])
                     for cc, p in pos.items())
            alloc = (cash + mv) / max_pos
            sh = int(alloc / px // 100) * 100
            if sh <= 0:
                continue
            notional = sh * px
            fee = pc._cost_buy_real(notional, SLIP)
            if notional + fee > cash:
                sh = int(max(cash - fee, 0.0) / px // 100) * 100
                if sh <= 0:
                    continue
                notional = sh * px
                fee = pc._cost_buy_real(notional, SLIP)
                if notional + fee > cash:
                    continue
            cash -= notional + fee
            total_cost += fee
            pos[code] = dict(shares=sh, entry_px=px, entry_i=i, high=px)
        pending_buy = []
        # ---- 盯市 ----
        mv = 0.0
        for cc, p in pos.items():
            v = px_of(i, cc)
            mv += p["shares"] * (v if pd.notna(v) else p["entry_px"])
            if pd.notna(v) and v > p["high"]:
                p["high"] = v
        eq_rows.append((day, cash + mv))
        expo_rows.append(mv / (cash + mv) if cash + mv > 0 else 0.0)
        if i == i1:
            break
        # ---- 当日收盘决策 ----
        t = day
        sells, buys = [], []
        if mode == "E1":
            ranking = inp.x3_ranking(t)
            ranks = {c: k + 1 for k, c in enumerate(ranking.index)}
            for code, p in pos.items():
                px = inp.close.at[t, code] if code in inp.close.columns else np.nan
                reason = (ranks.get(code, 10 ** 9) > exit_rank
                          or (pd.notna(px) and px >= p["entry_px"] * 2.0)
                          or (i - p["entry_i"] >= max_hold))
                if reason:
                    sells.append(code)
            free = max_pos - (len(pos) - len(sells))
            if free > 0:
                for code in ranking.index[:12]:
                    if free <= 0:
                        break
                    if code not in pos and code not in buys:
                        buys.append(code)
                        free -= 1
        elif mode == "E2":
            for code, p in pos.items():
                px = inp.close.at[t, code] if code in inp.close.columns else np.nan
                if pd.notna(px) and (px >= p["entry_px"] * 1.25 or px <= p["entry_px"] * 0.90
                                     or (i - p["entry_i"] >= 30)):
                    sells.append(code)
            free = max_pos - (len(pos) - len(sells))
            if free > 0:
                v = (inp.seasoned.loc[t] & (inp.adv20.loc[t] > 5e6)
                     & (inp.amt_r.loc[t] < 0.7).fillna(False)
                     & (inp.lowpos.loc[t] < 0.10).fillna(False)
                     & (inp.ret10.loc[t] > 0).fillna(False)
                     & (inp.ret1.loc[t] > 0).fillna(False))
                cand = inp.lowpos.loc[t][v].sort_values()
                for code in cand.index:
                    if free <= 0:
                        break
                    if code not in pos and code not in buys:
                        buys.append(code)
                        free -= 1
        elif mode == "E4":
            # 平滑信号: 按 20日平滑 Amihud60 排名, 进 top8 买 / 跌出 top40 卖 (迟滞抗噪)
            ranking = inp.x3_ranking(t, fac=inp.amihud60_s)
            ranks = {c: k + 1 for k, c in enumerate(ranking.index)}
            for code, p in pos.items():
                px = inp.close.at[t, code] if code in inp.close.columns else np.nan
                if (ranks.get(code, 10 ** 9) > 40
                        or (pd.notna(px) and px >= p["entry_px"] * 2.0)
                        or (i - p["entry_i"] >= 90)):
                    sells.append(code)
            free = max_pos - (len(pos) - len(sells))
            if free > 0:
                for code in ranking.index[:8]:
                    if free <= 0:
                        break
                    if code not in pos and code not in buys:
                        buys.append(code)
                        free -= 1
        elif mode == "E5":
            # 冷门 + 转强: X3 池内 top15 且站上 20日线、ret10>0 才买; 跌破 20日线*0.98 / +80% / 45日卖
            ranking = inp.x3_ranking(t)
            ranks = {c: k + 1 for k, c in enumerate(ranking.index)}
            for code, p in pos.items():
                px = inp.close.at[t, code] if code in inp.close.columns else np.nan
                ma = inp.ma20.at[t, code] if code in inp.ma20.columns else np.nan
                if pd.notna(px) and ((pd.notna(ma) and px < ma * 0.98)
                                     or px >= p["entry_px"] * 1.8
                                     or (i - p["entry_i"] >= 45)):
                    sells.append(code)
            free = max_pos - (len(pos) - len(sells))
            if free > 0:
                for code in ranking.index[:15]:
                    if free <= 0:
                        break
                    if code in pos or code in buys:
                        continue
                    px = inp.close.at[t, code]
                    ma = inp.ma20.at[t, code]
                    if pd.notna(px) and pd.notna(ma) and px > ma and inp.ret10.at[t, code] > 0:
                        buys.append(code)
                        free -= 1
        elif mode == "E6":
            # 量能拐点: 成交额比 amt_r 从 <1 升破 1 (前 5 日均未破) 且仍在 120日低位区 (<25%)
            for code, p in pos.items():
                px = inp.close.at[t, code] if code in inp.close.columns else np.nan
                if pd.notna(px) and (px >= p["entry_px"] * 1.30 or px <= p["entry_px"] * 0.88
                                     or (i - p["entry_i"] >= 45)):
                    sells.append(code)
            free = max_pos - (len(pos) - len(sells))
            if free > 0:
                ar = inp.amt_r.loc[t]
                prev_max = inp.amt_r.iloc[max(0, i - 5):i].max()
                v = (inp.seasoned.loc[t] & (inp.adv20.loc[t] > 5e6)
                     & (ar >= 1.0).fillna(False)
                     & (inp.lowpos.loc[t] < 0.25).fillna(False))
                cand = ar[v].sort_values(ascending=False)
                for code in cand.index:
                    if free <= 0:
                        break
                    if code in pos or code in buys:
                        continue
                    pm = prev_max[code] if code in prev_max.index else np.nan
                    if pd.notna(pm) and pm < 1.0:
                        buys.append(code)
                        free -= 1
        elif mode == "R1":
            # 阈值再平衡: 目标 = 当日 X3 top4; 连续 3 日在榜才买入 (有空位),
            # 连续 5 日不在榜才卖出; +100% 止盈随时触发。权重带内不调仓。
            ranking = inp.x3_ranking(t)
            top4 = set(ranking.index[:4])
            for c_ in top4:
                streak_in[c_] = streak_in.get(c_, 0) + 1
                streak_out[c_] = 0
            for c_ in list(streak_in):
                if c_ not in top4:
                    streak_in[c_] = 0
            for code, p in pos.items():
                px = inp.close.at[t, code] if code in inp.close.columns else np.nan
                if code not in top4:
                    streak_out[code] = streak_out.get(code, 0) + 1
                if (pd.notna(px) and px >= p["entry_px"] * 2.0) or streak_out.get(code, 0) >= 5:
                    sells.append(code)
            free = max_pos - (len(pos) - len(sells))
            if free > 0:
                for code in ranking.index[:4]:
                    if free <= 0:
                        break
                    if code not in pos and code not in buys and streak_in.get(code, 0) >= 3:
                        buys.append(code)
                        free -= 1
        else:  # E3
            for code, p in pos.items():
                px = inp.close.at[t, code] if code in inp.close.columns else np.nan
                ma = inp.ma20.at[t, code] if code in inp.ma20.columns else np.nan
                if pd.notna(px) and ((pd.notna(ma) and px < ma)
                                     or px >= p["entry_px"] * 1.5
                                     or (i - p["entry_i"] >= 60)):
                    sells.append(code)
            free = max_pos - (len(pos) - len(sells))
            if free > 0:
                v = (inp.seasoned.loc[t] & (inp.adv20.loc[t] > 5e6)
                     & (inp.hi120.loc[t] >= 0.995).fillna(False)
                     & (inp.amount.loc[t] > 1.5 * inp.amt60.loc[t]).fillna(False))
                cand = (inp.amount.loc[t] / inp.amt60.loc[t])[v].sort_values(ascending=False)
                for code in cand.index:
                    if free <= 0:
                        break
                    if code not in pos and code not in buys:
                        buys.append(code)
                        free -= 1
        pending_sell, pending_buy = sells, buys

    eq = pd.Series([x[1] for x in eq_rows], index=[x[0] for x in eq_rows])
    return eq, trades, total_cost, float(np.mean(expo_rows))


def stats(eq):
    eq = eq.dropna()
    tot = float(eq.iloc[-1] / eq.iloc[0] - 1) * 100
    mdd = float((eq / eq.cummax() - 1).min()) * 100
    out = {"total": round(tot, 2), "mdd": round(mdd, 2)}
    for name, d in (("r1m", 21), ("r3m", 63), ("r6m", 126), ("r1y", 252)):
        sub = eq.tail(d + 1)
        out[name] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
    return out


def main():
    inp = EInputs(pc.get_inputs().piv)
    for mode, cap, mp in (("E1", 10_000.0, 3), ("E1", 50_000.0, 4),
                          ("E2", 10_000.0, 3), ("E3", 10_000.0, 3)):
        eq, trades, cost, expo = simulate(inp, mode, capital=cap, max_pos=mp)
        s = stats(eq)
        s.update({"mode": mode, "capital": cap, "max_pos": mp,
                  "trades": len(trades), "cost": round(cost),
                  "avg_exposure": round(expo, 2)})
        print(json.dumps(s, ensure_ascii=False), flush=True)
        eq.to_pickle(f"results/r30_bt/event_{mode}_{int(cap)}_equity.pkl")
    print("X3 对照 (5万/R30): 全程 +640.68/-13.56 | 1m -7.41 3m +15.88 6m +94.77 1y +144.16", flush=True)


if __name__ == "__main__":
    main()
