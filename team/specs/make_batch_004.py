"""Batch 004 generator (strategist) — C5 sleeve 深化（集中度第一优先）+ 满仓候选 + 相位补全。

依据 batch_003 官方结果（harness md5 7d962a16…，56 条 + 1 条 sleeve）与 Lead 裁决：
  * phase 0 主口径 Tier A 有 24 条；`N5/TP50/0.90` = +69.98%/-11.78%/4-6(83.3%)/win_trade 60%。
  * 3-sleeve 合成（官方跑批）= +85.07%/-13.64%/5-6(83.3%)/win_trade 66.0%/fresh +75.03%，
    但 sleeve_dispersion 24.9pp（-8 +94.9 / 0 +70.0 / +8 +89.1）→ 结构有效但相位方差仍大。
  * **集中度成为第一约束**：N6/TP50 top3 占 54.2%，剔除 Top3 后只剩 +23.7%（Lead 实测）。
  * Lead 裁决：官方 Tier A 用 phase 0，但必须公开 5 相位表；`phase_pass_count ≥3/5` 才算「稳健 Tier A」；
    敞口可写进结论但要并列满仓口径，<1.0 才加 `EXPOSURE_ADJUSTED`。
  * 已知结构性事实：+5 相位段胜率恒 67%、+10 相位 N5 收益恒 43~57%，与 exp/N/TP 无关 → 只能改结构。

本批四件事，全部围绕「降集中度 / 相位稳健 / 满仓可行性」，不再扩 amihud_20d：
  A 相位补全（N5/TP50/0.90 缺 3 档）
  B sleeve 深化（6 条：N6 版、5-sleeve 版、不同 offset 三元组、两个更高敞口版）
  C 满仓（exposure 1.0）候选 —— 争取一个不需要 `EXPOSURE_ADJUSTED` 的达标解
  D 诊断与稳健性（TP 冗余、容量、深微盘、N8、以及 2 条择时）

Run: .venv/bin/python team/specs/make_batch_004.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "batch_004.json"
COST = {"one_way": 0.005, "capital": 50000, "lot_size": 100}
WINDOW = {"warmup_start": "2024-01-01", "eval_start": "2026-01-05", "eval_end": "2026-11-04"}
NO_TIMING = {"type": "none", "index": None, "ma": None, "out_asset": "cash"}
EXIT_KEYS = ("trailing_stop", "fixed_stop", "take_profit", "trailing_take", "max_hold_days")
SPECS = []


def S(sid, group, n, tp, exposure, notes, phase=0, min_adv=5_000_000, size_range=(0.05, 0.30),
      sleeves=None, timing=None):
    d = {
        "id": sid, "group": group,
        "selector": {"type": "amihud_60", "n": n, "size_range": list(size_range),
                     "min_adv": min_adv, "exclude_star": True, "exclude_bj": True,
                     "exclude_chinext": True, "price_min": None, "price_max": None, "params": {}},
        "rebalance_days": 30,
        "exit": dict({**dict.fromkeys(EXIT_KEYS), "take_profit": tp}),
        "timing": timing or dict(NO_TIMING),
        "portfolio": {"exposure": exposure, "cash_asset": "cash"},
        "cost": dict(COST), "window": dict(WINDOW), "notes": notes,
    }
    if sleeves:
        d["portfolio"]["sleeves"] = sleeves
    if phase:
        d["rebalance_offset_days"] = phase
    SPECS.append(d)


def ph(x):
    return "p0" if x == 0 else (f"pm{abs(x)}" if x < 0 else f"pp{x}")


# =====================================================================
# A. 相位补全：N5/TP50/0.90 缺 -10 / +5 / +10（N6 的 5 相位已齐）
# =====================================================================
A = "A_phase_complete"
for phase in (-10, 5, 10):
    S(f"b004_A_N5_TP50_exp90_{ph(phase)}", A, 5, 0.50, 0.90,
      f"N5/TP50/0.90 相位 {phase:+d}：补齐 5 相位表（已知 p0 +70.0/-11.8/83%、pm5 +80.6/-13.7/83%）。"
      f"这是「phase_pass_count ≥3/5」判定所需的最后一格。若 +5 仍 67%、+10 仍 <55%，"
      f"则该配置的相位通过数定格在 3/5，不能称「稳健 Tier A」。",
      phase=phase)

# =====================================================================
# B. sleeve 深化（6 条）—— 集中度第一优先
#    口径（与 batch_003 的 C5 完全一致，不得改）：
#      资金等分 count 份；每份用调仓网格整体平移 offsets[i] 个交易日独立运行（独立选股/止盈/现金）；
#      合成净值 = 各份净值算术平均（每份起始 1/count）；
#      win_period 用**合成净值**按 R=30 算完整段（不是按 sleeve 平均）；
#      win_trade 合并所有 sleeve 的个股交易；另报各 sleeve 的 total/mdd/win_period + dispersion。
#    ⚠️ 额外要求：本批 6 条都必须输出**合成净值的 top3_pnl_share / max_single_name_pnl_share**，
#      因为「sleeve 能不能降集中度」是本轮第一问题。
# =====================================================================
B = "B_sleeve_deep"
SLEEVE_NOTE = ("口径：资金等分 {cnt} 份、offsets {off}、每份独立 R30、合成净值=各份均值；"
               "wp 用合成净值按 R30 算段；win_trade 合并；另报各 sleeve 明细 + dispersion。")
S("b004_B_N6_TP50_exp90_sleeve3", B, 6, 0.50, 0.90,
  "N6/TP50/0.90 3-sleeve（offsets -8/0/+8）" + SLEEVE_NOTE.format(cnt=3, off="-8/0/+8") +
  " 假设：N6 比 N5 每 sleeve 多 1 只票（n_hold_avg 5.66 vs 4.74），三个 sleeve 合计最多 18 个不同标的，"
  "**top3 占比应从 N5 单相位的 54% 降到 35% 以下**。这是集中度问题的直接解法。",
  sleeves={"count": 3, "offsets": [-8, 0, 8], "alloc": "equal"})
S("b004_B_N5_TP50_exp95_sleeve3", B, 5, 0.50, 0.95,
  "N5/TP50/0.95 3-sleeve：把每份敞口从 0.90 提到 0.95（合计资金使用率 95%），"
  "换取收益 +5~6pp，检验「sleeve 的 mdd 余量（-13.6%）能不能换成收益」。"
  "若 mdd 仍 ≤ -15% 且 total ≥90%，则这是收益最高的稳健解。",
  sleeves={"count": 3, "offsets": [-8, 0, 8], "alloc": "equal"})
S("b004_B_N5_TP50_exp90_sleeve5", B, 5, 0.50, 0.90,
  "N5/TP50/0.90 **5-sleeve**（offsets -12/-6/0/+6/+12）：把相位覆盖从 3 份加到 5 份（≈每 6 天一份）。"
  "假设：合成收益 ≈ 5 相位均值、mdd 因 5 条曲线错峰而进一步下降，top3 占比最低。"
  "**这是「多 sleeve 错相位」的完整形态**（batch_003 只验了 3 份）。",
  sleeves={"count": 5, "offsets": [-12, -6, 0, 6, 12], "alloc": "equal"})
S("b004_B_N5_TP50_exp90_sleeve3_alt1", B, 5, 0.50, 0.90,
  "N5/TP50/0.90 3-sleeve，offset 三元组换成 **-10/-2/+6**：与 -8/0/+8 只差 2 天，"
  "但若能给出显著不同的 total/mdd，说明「sleeve 结果本身也依赖 offset 选择」→ 那是新的相位运气，不是稳健性。"
  "**这是对 sleeve 结构本身的稳健性检验（不是参数搜索）**。",
  sleeves={"count": 3, "offsets": [-10, -2, 6], "alloc": "equal"})
S("b004_B_N5_TP50_exp90_sleeve3_alt2", B, 5, 0.50, 0.90,
  "N5/TP50/0.90 3-sleeve，offset 三元组 **-6/+2/+10**：第二个替代三元组。"
  "三条 sleeve spec（-8/0/+8、-10/-2/+6、-6/+2/+10）构成 sleeve 结果的分布；"
  "若三者 total 的 max-min > 15pp，则「sleeve 达标」也只是抽到了好签，必须诚实报告。",
  sleeves={"count": 3, "offsets": [-6, 2, 10], "alloc": "equal"})
S("b004_B_N6_TP50_exp100_sleeve3", B, 6, 0.50, 1.00,
  "N6/TP50/**满仓 1.00** 3-sleeve：去现金缓冲的 sleeve 版。若它能三线全过，"
  "就是**唯一不需要 `EXPOSURE_ADJUSTED` 标注**的稳健解（收益全部来自选股，不是仓位调节）。"
  "同时检验「满仓 + sleeve 分散」是否已足够压回撤。",
  sleeves={"count": 3, "offsets": [-8, 0, 8], "alloc": "equal"})

# =====================================================================
# C. 满仓（exposure 1.0）候选 —— 争取一个免标注的达标解
#    Lead：C3 e1.0 realistic 是 4/5（只差 -10 相位 mdd 0.37pp）→ 满仓路线的余量已经非常薄，
#    所以这里只补 4 格，用来确认「满仓 + N6/TP50」在 p0 与 pm10 的真实数字。
# =====================================================================
C = "C_full_exposure"
S("b004_C_N6_TP50_exp100_p0", C, 6, 0.50, 1.00,
  "N6/TP50/满仓 phase 0：满仓基准。若 total ≥75% 而 mdd 仍 ≤ -14%，则「不需要现金缓冲」成立，"
  "后续对用户就报这一条（无 EXPOSURE_ADJUSTED）。")
S("b004_C_N6_TP50_exp100_pm10", C, 6, 0.50, 1.00,
  "N6/TP50/满仓 phase -10：Lead 实测此档 mdd -15.37%（差 0.37pp 破线）。本条用官方口径复核；"
  "若仍是 -15.3~-15.4%，则「4/5 相位稳健」的结论必须写清「差 0.4pp」，不能四舍五入成通过。",
  phase=-10)
S("b004_C_N6_TP40_exp100_pm10", C, 6, 0.40, 1.00,
  "N6/**TP40**/满仓 phase -10：TP40 在 pm10 曾拿到 mdd -13.7%（比 TP50 低 1.6pp）。"
  "若收紧止盈能把这一步的 mdd 压到 -15% 内且 total 仍 ≥65%，则满仓 + TP40 是免标注解。",
  phase=-10)
S("b004_C_N5_TP50_exp100_p0", C, 5, 0.50, 1.00,
  "N5/TP50/满仓 phase 0：N5 满仓的收益上界（预跑 ≈+80%），同时看 mdd 是否破线。"
  "若 N5 满仓也 ≤ -15%，那 Phase 0 的最优解会从 0.90 敞口移到满仓，敞口标注问题自动消失。")

# =====================================================================
# D. 诊断与稳健性（每条一个独立问题，不构成网格）
# =====================================================================
D = "D_diag"
S("b004_D_N6_nostop_exp90_p0", D, 6, None, 0.90,
  "N6 无止损 0.90 phase 0：与 N6/TP50/0.90（+67.1/-12.1/83）成对。"
  "**参数精简检验**：若两者几乎相同，则参数本质只有 (N, exposure) 两个，TP 只是尾部保险，"
  "对用户应报「2 个参数」而不是 3 个（抗过拟合的诚实表述）。")
S("b004_D_N6_nostop_exp90_pm5", D, 6, None, 0.90,
  "N6 无止损 0.90 phase -5：N5 在 pm5 上 TP50 的 mdd（-13.7%）明显优于 no-stop（-16.3%）。"
  "本条检验 N6 是否同样如此 → 决定 TP 的定位是「坏相位回撤保险」还是「纯冗余」。",
  phase=-5)
S("b004_E_N6_TP50_exp90_adv10m_p0", D, 6, 0.50, 0.90,
  "N6/TP50/0.90 但成交额门槛 500 万 → **1000 万**：容量压力检验。"
  "若收益只掉 5pp 以内 → 60% 不是靠不可交易的极小票；若掉 15pp+ → 必须向用户声明容量上限。",
  min_adv=10_000_000)
S("b004_E_N6_TP50_exp90_size02_15_p0", D, 6, 0.50, 0.90,
  "N6/TP50/0.90 但市值分位 5-30% → **2-15%**（更深微盘）：检验「越小越好」是否成立。"
  "若更深微盘更差，说明 5-30% 这个默认口径不是调出来的，是原始设定。",
  size_range=(0.02, 0.15))
S("b004_F_N8_TP50_exp90_p0", D, 8, 0.50, 0.90,
  "N8/TP50/0.90 phase 0：N7 的 total 只有 48-52%，N8 大概率更弱；"
  "放这一条只为确认 N 的收益衰减单调，从而把 N 锁死在 5-6，不再往 N 上加预算。")
S("b004_G_N6_TP50_exp90_idx905ma20", D, 6, 0.50, 0.90,
  "N6/TP50/0.90 + 中证500 MA20 择时（空仓停现金）：**唯一的另一种「结构」手段**。"
  "已知 2026 中证500 全年 -11%，MA20 会长期空仓 → 预期把收益砍半；"
  "但它也可能正好跳过 +5/+10 那两个坏相位。跑它是为了给出「择时能不能救相位」的正式反证。",
  timing={"type": "index_ma", "index": "000905", "ma": 20, "out_asset": "cash"})
S("b004_G_N6_TP50_exp90_idx852ma15", D, 6, 0.50, 0.90,
  "N6/TP50/0.90 + 中证1000 MA15：1000 是小微盘更近的代理。若它也砍掉收益，"
  "则「择时」在只做多小盘上彻底关闭（与 README §六的历史结论一致）。",
  timing={"type": "index_ma", "index": "000852", "ma": 15, "out_asset": "cash"})


def main():
    ids = [s["id"] for s in SPECS]
    assert len(ids) == len(set(ids)), [x for x in ids if ids.count(x) > 1][:3]
    for s in SPECS:
        for k in ("id", "selector", "rebalance_days", "exit", "timing", "portfolio", "cost", "window", "notes"):
            assert k in s, (s["id"], k)
        assert set(s["exit"]) == set(EXIT_KEYS)
        assert 0.5 <= s["portfolio"]["exposure"] <= 1.0
        assert s["notes"].strip() and len(s["notes"]) > 30, s["id"]
    OUT.write_text(json.dumps(SPECS, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(f"wrote {len(SPECS)} -> {OUT}")
    print(" groups:", dict(sorted(Counter(s["group"] for s in SPECS).items())))
    print(" sleeve specs:", [s["id"] for s in SPECS if "sleeves" in s["portfolio"]])
    print(" phase:", dict(sorted(Counter(s.get("rebalance_offset_days", 0) for s in SPECS).items())))
    print(" exposure:", dict(sorted(Counter(s["portfolio"]["exposure"] for s in SPECS).items())))
    print(" timing:", dict(sorted(Counter(s["timing"]["type"] for s in SPECS).items())))


if __name__ == "__main__":
    main()
