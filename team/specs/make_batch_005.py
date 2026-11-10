"""Batch 005 generator (strategist) — Round 2A：权重上限 / 分批止盈 / 波动目标。

Round 1 已收口（Lead）：C3（N6/TP50/主板/满仓）在 5 万新入金 realistic+fresh 口径下
+64.48% / -12.76% / wp 5-6，是唯一三线候选；但 **Top3 占 54.6%、剔除后仅 +25.3%**。
Round 2 只回答一个问题：**能否在 total≥60% 的前提下把 Top3 压到 ≤40%**。

三个新旋钮（都不加杠杆、不做空、只做多）：
  1) `selector.max_weight` + `rank_fill`：单票目标权重上限，超配部分按 amihud_60 rank N+1, N+2… 补足
  2) `exit.staged_take`：分批止盈（+30 卖 1/3、+50 卖 1/3、剩余持有到调仓）—— 对比一次性 TP50
  3) `portfolio.vol_target`：按 20 日组合实现波动缩放到 25%/30% 年化，**只降仓不加杠杆**

⚠️ 预注册预测（写在 ROUND2_PLAN.md，跑完对照，不许事后改口）：
  - max_weight 0.10 ≈ 等权 N10（实测 N10/TP50/0.9 = +39.3%）→ 大概率 total < 60%
  - max_weight 0.15 ≈ N7-8（实测 N7 +45~52%、N8 +44.8%）→ 大概率 total < 60%
  - 因此最可能的结论是「Top3 ≤40% 与 total ≥60% 不可兼得」；
    唯一有机会的是「cap 0.15~0.16 保留赢家主体 + 分批止盈压尾部」这一格。

Run: .venv/bin/python team/specs/make_batch_005.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "batch_005.json"
COST = {"one_way": 0.005, "capital": 50000, "lot_size": 100}
WINDOW = {"warmup_start": "2024-01-01", "eval_start": "2026-01-05", "eval_end": "2026-11-04"}
NO_TIMING = {"type": "none", "index": None, "ma": None, "out_asset": "cash"}
EXIT_KEYS = ("trailing_stop", "fixed_stop", "take_profit", "trailing_take", "max_hold_days")
SPECS = []

# 分批止盈方案（fraction = 触发时卖出当前持仓的比例）
STG_30_50 = [{"trigger": 0.30, "fraction": 0.3333}, {"trigger": 0.50, "fraction": 0.3333}]
STG_20_35 = [{"trigger": 0.20, "fraction": 0.3333}, {"trigger": 0.35, "fraction": 0.3333}]
STG_20_35_50 = [{"trigger": 0.20, "fraction": 0.3333}, {"trigger": 0.35, "fraction": 0.3333},
                {"trigger": 0.50, "fraction": 0.3333}]
STG_30_60_100 = [{"trigger": 0.30, "fraction": 0.3333}, {"trigger": 0.60, "fraction": 0.5},
                 {"trigger": 1.00, "fraction": 1.0}]


def S(sid, group, n, notes, *, tp=None, staged=None, cap=None, rank_fill=None,
      exposure=1.0, vol_target=None, phase=0):
    sel = {"type": "amihud_60", "n": n, "size_range": [0.05, 0.30], "min_adv": 5_000_000,
           "exclude_star": True, "exclude_bj": True, "exclude_chinext": True,
           "price_min": None, "price_max": None, "params": {}}
    if cap is not None:
        sel["max_weight"] = cap
        sel["rank_fill"] = True if rank_fill is None else rank_fill
    ex = dict.fromkeys(EXIT_KEYS)
    ex["take_profit"] = tp
    if staged is not None:
        ex["staged_take"] = staged
    port = {"exposure": exposure, "cash_asset": "cash"}
    if vol_target is not None:
        port["vol_target"] = vol_target
    d = {"id": sid, "group": group, "selector": sel, "rebalance_days": 30, "exit": ex,
         "timing": dict(NO_TIMING), "portfolio": port, "cost": dict(COST),
         "window": dict(WINDOW), "notes": notes}
    if phase:
        d["rebalance_offset_days"] = phase
    SPECS.append(d)


# =====================================================================
# G0 对照组（4）：C3 / C2 / 无 TP / 满仓无 TP
# =====================================================================
G0 = "G0_controls"
S("b005_G0_C3_N6_TP50_e100", G0, 6,
  "**C3 原版对照**：N6/TP50/主板/满仓/无权重上限。Round 1 收口候选（realistic+fresh +64.48%/-12.76%/wp 5-6/"
  "Top3 54.6%/剔除 Top3 +25.3%）。本批所有新方案都必须与它同口径逐位对比（±0.5pp）。", tp=0.50)
S("b005_G0_C2_N5_TP50_e90", G0, 5,
  "**C2 原版对照**：N5/TP50/0.90 敞口。Round 1 实测 realistic+fresh +59.94%（差 0.06pp 破线）。"
  "用它检验「新方案是不是只在 N5 上有效」。", tp=0.50, exposure=0.90)
S("b005_G0_C3_N6_nostop_e100", G0, 6,
  "C3 去掉 TP（满仓无止损）：隔离「TP50 到底贡献了什么」。Round 1 已知：无 TP 在主口径更高（+79.2% vs +75.7%）"
  "但 2025 回撤更差（-15.8% vs -9.8%），Top3 更高（69.2% vs 56.3%）。")
S("b005_G0_C3_N6_TP50_e90", G0, 6,
  "C3 但敞口 0.90：与满仓版对照，确认「满仓已不破线、不需要现金缓冲」这个 Round 1 结论在本批仍成立。",
  tp=0.50, exposure=0.90)

# =====================================================================
# A1 max_weight 单独（6）：核心假设「砍赢家权重 = 砍收益」
# =====================================================================
A1 = "A1_max_weight"
for cap in (0.08, 0.10, 0.12, 0.15):
    S(f"b005_A1_N6_TP50_cap{int(cap*100)}", A1, 6,
      f"N6/TP50/满仓 + 单票上限 {int(cap*100)}% + rank 补足（有效持仓 ≈ {1/cap:.1f} 只）。"
      f"假设：上限 {int(cap*100)}% 等价于把赢家权重从 16.7% 砍到 {int(cap*100)}%，"
      f"Top3 会降 3~8pp，但收益同步掉——参考 N7 +45~52%、N8 +44.8%、N10 +39~46%。"
      f"**这是本批最可能的失败点：Top3 降不到 40%，收益先跌破 60%。**", tp=0.50, cap=cap)
for cap in (0.12, 0.15):
    S(f"b005_A1_N5_TP50_cap{int(cap*100)}", A1, 5,
      f"N5/TP50/0.90 + 单票上限 {int(cap*100)}%：N5 每票 18%→{int(cap*100)}%，"
      f"有效持仓 {0.9/cap:.1f} 只。检验「cap 在更集中的底子上是否更有效」（Top3 基数更高，理论降幅更大）。",
      tp=0.50, cap=cap, exposure=0.90)
S("b005_A1_N6_TP50_cap16", A1, 6,
  "N6 单票上限 16%（≈1/6=16.67%，几乎不触发）：**负对照**。若它的 Top3 与 C3 相同（54.6%），"
  "说明 harness 的 max_weight 实现正确；若不同，说明实现有 bug 或 cap 有副作用。", tp=0.50, cap=0.16)

# =====================================================================
# A2 staged_take 单独（5）：分批止盈能否「压赢家尾部、少伤收益」
# =====================================================================
A2 = "A2_staged_take"
S("b005_A2_N6_stg30_50", A2, 6,
  "N6/满仓 + 分批止盈 [+30% 卖 1/3, +50% 卖 1/3, 剩余持有到调仓]（不用一次性 TP）。"
  "假设：与一次性 TP50 相比，分批止盈能让赢家再跑一段（保留 1/3~2/3 仓位），"
  "因此 total 高于 TP50 版（+75.7%），而 Top3 略低于 56.3%。**这是本批最有希望的一格。**",
  staged=STG_30_50)
S("b005_A2_N6_stg20_35", A2, 6,
  "N6 + 分批止盈 [+20% 卖 1/3, +35% 卖 1/3]：更早锁利，Top3 降幅更大、收益更低。"
  "用来画「止盈触发越早 → Top3 越低 → total 越低」的单调曲线。", staged=STG_20_35)
S("b005_A2_N6_stg20_35_50", A2, 6,
  "N6 + 三级止盈 [+20/+35/+50 各卖 1/3]（≈+50% 时清仓）：极端压集中度方案，"
  "假设 Top3 能压到 40% 附近，但 total 会掉到 55~65% —— 用来测「40% 这条线到底要付多少收益」。",
  staged=STG_20_35_50)
S("b005_A2_N6_stg30_60_100", A2, 6,
  "N6 + 阶梯止盈 [+30% 卖1/3, +60% 卖 1/2, +100% 清仓]：让赢家跑到翻倍才清，"
  "假设它能保住大部分收益（total 接近 75%）同时把 Top3 压到 45% 左右。", staged=STG_30_60_100)
S("b005_A2_N5_stg30_50", A2, 5,
  "N5/0.90 + 分批止盈 [+30/+50]：与 N6 版成对。N5 单票权重 18%，赢家更集中，"
  "分批止盈的理论收益更大；但费用也更高（每次部分卖出都付 0.5%）。",
  staged=STG_30_50, exposure=0.90)

# =====================================================================
# A3 vol_target 单独（4）：只降仓不加杠杆
# =====================================================================
A3 = "A3_vol_target"
for vt in (0.25, 0.30):
    S(f"b005_A3_N6_TP50_vt{int(vt*100)}", A3, 6,
      f"N6/TP50/满仓 + 目标波动 {int(vt*100)}% 年化（20 日实现波动，只降仓）："
      f"假设它在 10 月那段（组合波动飙升）自动降到 60~70% 仓位，从而把 mdd 从 -13.4% 压到 -10% 以内，"
      f"代价是 total 掉 8~15pp。**注意：这是「靠降仓换回撤」，不是结构改善，Top3 不会变低。**",
      tp=0.50, vol_target=vt)
S("b005_A3_N5_TP50_vt25", A3, 5,
  "N5/0.90 + 目标波动 25%：与 N6 版成对，检验 vol_target 在更高波动底子上是否更有效。",
  tp=0.50, exposure=0.90, vol_target=0.25)
S("b005_A3_N6_TP50_vt20", A3, 6,
  "N6/TP50 + 目标波动 20%（更激进降仓）：边界探针，用来确认 vol_target 的收益-回撤斜率不是线性幻觉。",
  tp=0.50, vol_target=0.20)

# =====================================================================
# A4 cap + staged（4）：正面组合——砍权重 + 锁赢家
# =====================================================================
A4 = "A4_cap_staged"
for cap in (0.12, 0.15):
    S(f"b005_A4_N6_cap{int(cap*100)}_stg30_50", A4, 6,
      f"N6 + 上限 {int(cap*100)}% + 分批止盈[+30/+50]：两个机制互补——上限削权重、止盈锁尾部，"
      f"理论上 Top3 能降到 42~48%（上限贡献 5~8pp、止盈贡献 3~5pp），"
      f"而 total 因为止盈让赢家继续跑而只掉 5~10pp。**这是「达标 + ≤40%」的唯一现实路径。**",
      staged=STG_30_50, cap=cap)
S("b005_A4_N6_cap10_stg30_50", A4, 6,
  "N6 + 上限 10% + 分批止盈[+30/+50]：更狠的 cap。若它能 Top3≤40% 且 total≥60%，就是结构突破；"
  "若 total 掉到 50% 以下，则证明 40% 这条线必须用收益买。",
  staged=STG_30_50, cap=0.10)
S("b005_A4_N5_cap15_stg30_50", A4, 5,
  "N5/0.90 + 上限 15% + 分批止盈：N5 的 Top3 基数最高（66%），理论降幅最大。",
  staged=STG_30_50, cap=0.15, exposure=0.90)

# =====================================================================
# A5 cap + vol_target（3）
# =====================================================================
A5 = "A5_cap_voltarget"
S("b005_A5_N6_cap12_vt25", A5, 6,
  "N6 + 上限 12% + vol_target 25%：把「权重分散」与「波动降仓」叠在一起，"
  "看 Top3 与 mdd 能否同时改善，以及总代价是否超 15pp。", tp=0.50, cap=0.12, vol_target=0.25)
S("b005_A5_N6_cap12_vt30", A5, 6,
  "N6 + 上限 12% + vol_target 30%：同上，降仓更温和。", tp=0.50, cap=0.12, vol_target=0.30)
S("b005_A5_N6_cap15_vt25", A5, 6,
  "N6 + 上限 15% + vol_target 25%：cap 更松、降仓更狠，用来判断哪个机制是主导。",
  tp=0.50, cap=0.15, vol_target=0.25)

# =====================================================================
# A6 三合一（3）
# =====================================================================
A6 = "A6_triple"
for cap in (0.12, 0.15):
    S(f"b005_A6_N6_cap{int(cap*100)}_stg30_50_vt25", A6, 6,
      f"N6 + 上限 {int(cap*100)}% + 分批止盈 + vol_target 25%：三机制全开。"
      f"若这一格仍然 Top3>40% 或 total<60%，则 Round 2 的方向 A 可以判定「关闭」。",
      staged=STG_30_50, cap=cap, vol_target=0.25)
S("b005_A6_N6_cap15_stg30_60_vt30", A6, 6,
  "N6 + 上限 15% + 阶梯止盈[+30/+60/+100] + vol_target 30%："
  "最保守的组合（尽量少伤收益、只削尾部），是「保 60% 优先」的那一手。",
  staged=STG_30_60_100, cap=0.15, vol_target=0.30)

# =====================================================================
# A7 机制归因（3）：把「Top3 变化」拆开看
# =====================================================================
A7 = "A7_attribution"
S("b005_A7_N6_TP50_cap10_nofill", A7, 6,
  "N6 + 上限 10% 但**不补足**（rank_fill=false）：此时总仓位只有 60%，其余现金。"
  "这是纯降杠杆，不是分散。用来分离「权重分散」与「整体降仓」两种效应——"
  "如果它与 cap10+补足 的 Top3 相近但收益更低，说明补足才是真分散。", tp=0.50, cap=0.10, rank_fill=False)
S("b005_A7_N6_nostop_cap15", A7, 6,
  "N6 + 上限 15%，**不用 TP**：cap 与 TP 的交互检验。若 Top3 比 cap15+TP50 更低，"
  "说明 TP 反而在保护大赢家（因为 TP 让它提前卖出、但 cap 已经在削权重）。", cap=0.15)
S("b005_A7_N8_TP50_cap12", A7, 8,
  "N8/TP50 + 上限 12%（≈8.3 只，cap 几乎不触发）：检验「先把 N 加到 8 再用 cap」"
  "与「N6 用 cap 补足到 8」是否等价。若不等价，说明 rank_fill 的补位顺序有价值。", tp=0.50, cap=0.12)

# =====================================================================
# A8 相位稳健性（2）：给最可能的达标格加 -5/+5
# =====================================================================
A8 = "A8_phase"
S("b005_A8_N6_cap15_stg30_50_pm5", A8, 6,
  "N6 + 上限 15% + 分批止盈，相位 -5：给最可能的「达标格」补一个相位点，"
  "避免又出现「只在 phase 0 成立」的结论。", staged=STG_30_50, cap=0.15, phase=-5)
S("b005_A8_N6_cap15_stg30_50_pp5", A8, 6,
  "N6 + 上限 15% + 分批止盈，相位 +5：同样的补点。", staged=STG_30_50, cap=0.15, phase=5)


def main():
    ids = [s["id"] for s in SPECS]
    assert len(ids) == len(set(ids)), [x for x in ids if ids.count(x) > 1][:3]
    for s in SPECS:
        for k in ("id", "selector", "rebalance_days", "exit", "timing", "portfolio", "cost", "window", "notes"):
            assert k in s, (s["id"], k)
        assert set(s["exit"]) >= set(EXIT_KEYS)
        assert s["notes"].strip() and len(s["notes"]) > 30, s["id"]
        # staged_take 与 take_profit 不能同时用（避免优先级歧义）
        assert not (s["exit"].get("staged_take") and s["exit"].get("take_profit")), s["id"]
    assert 30 <= len(SPECS) <= 50, len(SPECS)
    OUT.write_text(json.dumps(SPECS, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(f"wrote {len(SPECS)} -> {OUT}")
    print(" groups:", dict(sorted(Counter(s["group"] for s in SPECS).items())))
    print(" with max_weight:", sum(1 for s in SPECS if "max_weight" in s["selector"]))
    print(" with staged_take:", sum(1 for s in SPECS if s["exit"].get("staged_take")))
    print(" with vol_target:", sum(1 for s in SPECS if "vol_target" in s["portfolio"]))
    print(" with take_profit:", sum(1 for s in SPECS if s["exit"].get("take_profit")))


if __name__ == "__main__":
    main()
