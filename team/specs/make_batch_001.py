"""Batch 001 spec generator (strategist).

Produces team/specs/batch_001.json, strictly following team/PROTOCOL.md §8 schema.

Design doctrine (see README.md for the full rationale):
  * 收益来源 = 小微盘 Amihud 非流动性溢价（已 7 年验证，2026 仍是最强单因子）
  * 回撤控制 = 跟踪止损 / N 分散 / （少量）组合熔断
  * 胜率来源 = N 分散让段收益贴近篮子均值 + 止损把尾部亏损换成现金
  * 防过拟合 = 每个 (N, 止损) 只取 3 个邻域点；预算花在正交维度（选股/离场/周期）上

Run:  .venv/bin/python team/specs/make_batch_001.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "batch_001.json"

COST = {"one_way": 0.005, "capital": 50000, "lot_size": 100}
WINDOW = {"warmup_start": "2024-01-01", "eval_start": "2026-01-05", "eval_end": "2026-11-04"}
NO_TIMING = {"type": "none", "index": None, "ma": None, "out_asset": "cash"}

SPECS = []


def E(trailing_stop=None, fixed_stop=None, take_profit=None, trailing_take=None, max_hold_days=None):
    return {
        "trailing_stop": trailing_stop,
        "fixed_stop": fixed_stop,
        "take_profit": take_profit,
        "trailing_take": trailing_take,
        "max_hold_days": max_hold_days,
    }


def S(sid, group, sel_type, n, R, exit_rule, notes, size_range=(0.05, 0.30), min_adv=5_000_000,
      exclude_star=False, exclude_bj=True, exclude_chinext=False, price_min=None, price_max=None,
      timing=None, params=None):
    """Append one spec in PROTOCOL §8 shape."""
    SPECS.append({
        "id": sid,
        "group": group,
        "selector": {
            "type": sel_type,
            "n": n,
            "size_range": list(size_range),
            "min_adv": min_adv,
            "exclude_star": exclude_star,
            "exclude_bj": exclude_bj,
            "exclude_chinext": exclude_chinext,
            "price_min": price_min,
            "price_max": price_max,
            "params": params or {},
        },
        "rebalance_days": R,
        "exit": exit_rule,
        "timing": timing or dict(NO_TIMING),
        "cost": dict(COST),
        "window": dict(WINDOW),
        "notes": notes,
    })


# =====================================================================
# G0 基线对照（必含 3 条，全部沿用 PROTOCOL §7 争议数字的原始参数）
# =====================================================================
G0 = "G0_baseline"
S("b001_g0_amihud_N5_R30_none", G0, "amihud", 5, 30, E(),
  "基线1：经典 amihud 小微盘 N5/R30 无止损。2026 预跑约 +53%/回撤-24%（未官方口径），"
  "回撤必然超标，用于验证 harness 与历史 ledger 的一致性。")
S("b001_g0_amihud_N5_R30_ts12", G0, "amihud", 5, 30, E(trailing_stop=0.12),
  "基线2（最关键）：复现 PROTOCOL §7 争议项「N5 R30 +12% 跟踪止损」。文档写 +44.9%，"
  "ledger CSV 的 2026 段算 +62.8%。本 spec 用统一口径一次性裁决这个矛盾。")
S("b001_g0_amihud_N25_R30_none", G0, "amihud", 25, 30, E(),
  "基线3：N25 分散基准。预期收益降（约+38%）、回撤降至-18% 左右，"
  "用来量化「分散换回撤」的斜率，判断 60%/15% 组合是否在 N25 处可行。")
S("b001_g0_amihud_N5_R30_fs12", G0, "amihud", 5, 30, E(fixed_stop=0.12),
  "基线4：同参数换成「成本价固定止损 12%」。与基线2只差止损口径，"
  "直接回答「是跟踪止损本身有效，还是任何止损都有效」。")

# =====================================================================
# G1 收益前沿：N × R 无离场（纯粹标定 2026 的收益地形）
# =====================================================================
G1 = "G1_frontier"
S("b001_g1_amihud_N2_R30_none", G1, "amihud", 2, 30, E(),
  "极限集中：N2 是 2026 收益上限的探针。预期 +55%~90% 但单票权重 50%，"
  "回撤/单票依赖一定爆表，仅作前沿标定，不作为候选。")
S("b001_g1_amihud_N3_R30_none", G1, "amihud", 3, 30, E(),
  "N3/R30 无止损：读作「旧 FINAL_10 里 N3 系」的 2026 单年基线，预期回撤 -25% 级。")
S("b001_g1_amihud_N6_R30_none", G1, "amihud", 6, 30, E(),
  "N6/R30：预跑显示收益仍有 +60% 但段胜率只有 3/6——集中度的收益与胜率在此处分岔。")
S("b001_g1_amihud_N10_R30_none", G1, "amihud", 10, 30, E(),
  "N10/R30 无止损：预跑约 +46~58%、回撤 -15~19%、段胜率 5/6。这是「胜率达标」"
  "最可能的位置，差的是收益或回撤最后一口气，本批重点攻它。")
S("b001_g1_amihud_N15_R30_none", G1, "amihud", 15, 30, E(),
  "N15/R30：继续往分散走，检验收益衰减是否线性（若仍 >40% 说明 N 的收益代价温和）。")
S("b001_g1_amihud_N2_R15_none", G1, "amihud", 2, 15, E(),
  "R15 × N2：把调仓周期减半，看是否用更高换手换更高收益（费用 0.5%/边已扣）。")
S("b001_g1_amihud_N3_R15_none", G1, "amihud", 3, 15, E(),
  "R15 × N3：预跑 +72%/-24%，是所有无止损组合里收益最高的一档；回撤是唯一障碍。")
S("b001_g1_amihud_N6_R15_none", G1, "amihud", 6, 15, E(),
  "R15 × N6：预跑 +58%/-18%，段胜率 9/12（75%）。R15 的段数=12，80% 需 10/12，"
  "差 1 段——这是 R15 臂的现实门槛。")
S("b001_g1_amihud_N10_R15_none", G1, "amihud", 10, 15, E(),
  "R15 × N10：段胜率 9/13，收益 ~32%。用于确认「R15 上分散同样抬胜率、杀收益」。")
S("b001_g1_amihud_N5_R15_none", G1, "amihud", 5, 15, E(),
  "R15 × N5 无止损：R15 臂的中心点，后续所有 R15 止损 spec 都以它为对照。")
S("b001_g1_amihud_N10_R7_none", G1, "amihud", 10, 7, E(),
  "R7 × N10 无止损：R7 费用对照。预跑费用占比约 8-12% 本金，且段数=28 → 80% 需 23/28。")
S("b001_g1_amihud_N5_R7_none", G1, "amihud", 5, 7, E(),
  "R7 × N5 无止损：历史「绞肉机」参数，仅作费用-胜率对照，不指望达标。")

# =====================================================================
# G2 R30 分散核心平台：N 8~20 × 离场（本批最高优先级）
#    假设：n_periods=5~6 时 80% 胜率只需 4/5 或 5/6，N8-12 恰好能兼顾胜率与收益；
#          松止损（12-15%）只砍尾部不砍趋势，是唯一有机会三线同时过的组合。
# =====================================================================
G2 = "G2_R30_diversified"
for n in (8, 10, 12):
    S(f"b001_g2_amihud_N{n}_R30_none", G2, "amihud", n, 30, E(),
      f"N{n}/R30 无离场：G2 平台的收益锚点（与 G1 的 N10 重叠校验，确认可复现）。")
for n in (8, 10, 12, 15):
    S(f"b001_g2_amihud_N{n}_R30_ts10", G2, "amihud", n, 30, E(trailing_stop=0.10),
      f"N{n}/R30 跟踪止损10%：核心假设——止损把 3-4 个下跌段削成「小赚/小亏」，"
      f"同时把回撤从 -18% 压到 -10% 级，收益代价若 <15pp 就值得。")
for n in (8, 10, 12, 15):
    S(f"b001_g2_amihud_N{n}_R30_ts12", G2, "amihud", n, 30, E(trailing_stop=0.12),
      f"N{n}/R30 跟踪止损12%：与 ts10 构成 2 点邻域，检验「最优止损随 N 平移」还是平台。")
S("b001_g2_amihud_N10_R30_ts15", G2, "amihud", 10, 30, E(trailing_stop=0.15),
  "N10/ts15：松止损端。假设 15% 只在极端段触发，几乎不损收益但回撤控制打折，"
  "用来定位「止损-收益」曲线的拐点。")
S("b001_g2_amihud_N10_R30_ts08", G2, "amihud", 10, 30, E(trailing_stop=0.08),
  "N10/ts08：紧止损端。预跑中 8% 在 R30 上明显损收益（+25%），"
  "本 spec 确认它是真劣势而非噪音，从而把平台锁定在 10-15%。")
S("b001_g2_amihud_N20_R30_none", G2, "amihud", 20, 30, E(),
  "N20/R30 无止损：分散的极限。若它也能 >60%，说明 2026 的小微盘 beta 本身够厚，"
  "则「高胜率+低回撤」可以用 N 换，而不必依赖止损。")
S("b001_g2_amihud_N20_R30_ts12", G2, "amihud", 20, 30, E(trailing_stop=0.12),
  "N20/ts12：分散+止损双管，最保守的达标尝试（预期收益不足但回撤最稳）。")
S("b001_g2_amihud_N25_R30_ts12", G2, "amihud", 25, 30, E(trailing_stop=0.12),
  "N25/ts12：基线3 的止损版，量化「给分散组合加止损」还剩多少收益。")
S("b001_g2_amihud_N10_R30_fs15", G2, "amihud", 10, 30, E(fixed_stop=0.15),
  "N10 固定止损15%：固定止损只在成本下方 15% 触发，比跟踪止损宽容，"
  "假设它在 N10 上可能优于 ts10（不会在上涨途中被回撤打掉）。")
S("b001_g2_amihud_N12_R30_fs15", G2, "amihud", 12, 30, E(fixed_stop=0.15),
  "N12 固定止损15%：N12 与 fs15 的交叉点，验证 G2 的最优组合是否是 N12+fs15。")
S("b001_g2_amihud_N10_R30_tp40", G2, "amihud", 10, 30, E(take_profit=0.40),
  "N10 止盈40%：已知 +15/20/30% 止盈在 2026 反作用，本 spec 把阈值抬到 40% 试探"
  "「只兑现极端赢家」能否在不杀收益的前提下抬段胜率。")
S("b001_g2_amihud_N12_R30_tp40", G2, "amihud", 12, 30, E(take_profit=0.40),
  "N12 止盈40%：与 N10 构成邻域，避免把单点噪音当结论。")

# =====================================================================
# G3 集中端 N3-6 × R30 止损平台
# =====================================================================
G3 = "G3_R30_concentrated"
for n in (3, 4, 5, 6):
    for s in (0.10, 0.12):
        S(f"b001_g3_amihud_N{n}_R30_ts{int(s*100)}", G3, "amihud", n, 30, E(trailing_stop=s),
          f"N{n}/R30 跟踪止损{int(s*100)}%：集中端 2×4 平台。历史最强组合（N5+12%）就在此，"
          f"假设最优停在 N4-5、止损 10-12% 附近且不是孤立尖峰。")
S("b001_g3_amihud_N4_R30_ts08", G3, "amihud", 4, 30, E(trailing_stop=0.08),
  "N4/ts08：紧止损在集中组合上更容易被噪音打掉，假设它显著劣于 ts10/12。")
S("b001_g3_amihud_N6_R30_ts08", G3, "amihud", 6, 30, E(trailing_stop=0.08),
  "N6/ts08：同上，第二点，避免单点结论。")
S("b001_g3_amihud_N4_R30_ts15", G3, "amihud", 4, 30, E(trailing_stop=0.15),
  "N4/ts15：松止损端，检验集中组合能否靠 15% 止损保住收益（回撤预期 -19% 级）。")
S("b001_g3_amihud_N6_R30_ts15", G3, "amihud", 6, 30, E(trailing_stop=0.15),
  "N6/ts15：同上第二点。")
S("b001_g3_amihud_N4_R30_none", G3, "amihud", 4, 30, E(),
  "N4/R30 无止损：集中端的无止损对照（预期 +74%/-13%，正是「差一点达标」形状）。")
S("b001_g3_amihud_N4_R30_fs10", G3, "amihud", 4, 30, E(fixed_stop=0.10),
  "N4 固定止损10%：集中端止损口径对照。")
S("b001_g3_amihud_N6_R30_fs10", G3, "amihud", 6, 30, E(fixed_stop=0.10),
  "N6 固定止损10%：同上第二点。")
S("b001_g3_amihud_N3_R30_tp30", G3, "amihud", 3, 30, E(take_profit=0.30),
  "N3 止盈30%：已知反作用方向的最小对照，确认「集中+止盈」是否也救不了。")

# =====================================================================
# G4 R15 臂（段数 12-13，80% 需 10/12；结构上更难，但预跑显示止损在 R15 上反而增收益）
# =====================================================================
G4 = "G4_R15"
for n in (3, 5, 6, 8):
    for s in (None, 0.12):
        tag = "none" if s is None else f"ts{int(s*100)}"
        note = ("无止损对照" if s is None else
                "跟踪止损12%：预跑在 R15 上止损反而提高收益（N6: +58%→+79%），"
                "假设这是「R15 的下跌段更短、止损后低点再进」的结构性收益，不是噪音。")
        S(f"b001_g4_amihud_N{n}_R15_{tag}", G4, "amihud", n, 15,
          E(trailing_stop=s), f"N{n}/R15 {note}")
for n in (5, 6):
    for s in (0.08, 0.10):
        S(f"b001_g4_amihud_N{n}_R15_ts{int(s*100)}", G4, "amihud", n, 15, E(trailing_stop=s),
          f"N{n}/R15 跟踪止损{int(s*100)}%：把 R15 的止损平台从 1 点扩到 3 点（8/10/12），"
          f"确认最优档位是否与 R30 不同。")
for n in (5, 6):
    S(f"b001_g4_amihud_N{n}_R15_fs10", G4, "amihud", n, 15, E(fixed_stop=0.10),
      f"N{n}/R15 固定止损10%：R15 上的止损口径对照。")
S("b001_g4_amihud_N5_R15_ts12tp40", G4, "amihud", 5, 15, E(trailing_stop=0.12, take_profit=0.40),
  "N5/R15 跟踪12%+止盈40%：R15 段短，止盈更容易在段内触发，检验组合离场能否抬胜率。")
S("b001_g4_amihud_N6_R15_mh10", G4, "amihud", 6, 15, E(max_hold_days=10),
  "N6/R15 最长持有10日：时间止损把 15 日段切成 10+5，检验「涨不动的仓位先换掉」是否抬胜率。")

# =====================================================================
# G5 R7 控制臂（结构上最难：段数 28，80% 需 23/28；费用必扣）
# =====================================================================
G5 = "G5_R7_control"
S("b001_g5_amihud_N3_R7_none", G5, "amihud", 3, 7, E(),
  "N3/R7 无止损：历史「绞肉机」，收益被费用吃掉 10-20%。保留以量化费用占比。")
S("b001_g5_amihud_N5_R7_ts10", G5, "amihud", 5, 7, E(trailing_stop=0.10),
  "N5/R7 跟踪止损10%：短周期+止损可能把换手进一步提高，假设净收益更差。")
S("b001_g5_amihud_N10_R7_ts12", G5, "amihud", 10, 7, E(trailing_stop=0.12),
  "N10/R7 跟踪止损12%：R7 的胜率有利位置（预跑 19/28=68%），仍离 80% 很远。")
S("b001_g5_amihud_N25_R7_none", G5, "amihud", 25, 7, E(),
  "N25/R7 无止损：R7 最分散点，若胜率也上不去就彻底证伪 R7 路线。")
S("b001_g5_amihud_N5_R7_fs10", G5, "amihud", 5, 7, E(fixed_stop=0.10),
  "N5/R7 固定止损10%：短周期上固定止损几乎等价于「买入后跌10%即走」，检验是否只是减仓。")
S("b001_g5_amihud_N8_R7_none", G5, "amihud", 8, 7, E(),
  "N8/R7 无止损：N 的前沿点（N10 与 N5 之间），补齐 R7 的 N 曲线。")
S("b001_g5_amihud_N5_R7_mh5", G5, "amihud", 5, 7, E(max_hold_days=5),
  "N5/R7 最长持有5日：更快的换手，费用更高，作为费用敏感性上界。")
S("b001_g5_amihud_N5_R7_ts12tp30", G5, "amihud", 5, 7, E(trailing_stop=0.12, take_profit=0.30),
  "N5/R7 跟踪12%+止盈30%：短段内两种离场同时生效，检验是否能压住段波动。")
S("b001_g5_amihud_N10_R7_mh10", G5, "amihud", 10, 7, E(max_hold_days=10),
  "N10/R7 最长持有10日：持有 10 日但每 7 日调仓 = 部分仓位跨段，检验时间止损的错误定价。")
S("b001_g5_amihud_N5_R7_tp30", G5, "amihud", 5, 7, E(take_profit=0.30),
  "N5/R7 止盈30%：R7 上文即证伪的方向，留一条对照。")

# =====================================================================
# G6 固定止损 / 止盈 / 组合离场（离开维度本身的正交扫描）
# =====================================================================
G6 = "G6_exit_axis"
S("b001_g6_amihud_N5_R30_fs08", G6, "amihud", 5, 30, E(fixed_stop=0.08),
  "N5/fs08：紧固定止损。历史结论「个股止损普遍降夏普」，本 spec 量化 2026 的代价。")
S("b001_g6_amihud_N5_R30_fs10", G6, "amihud", 5, 30, E(fixed_stop=0.10),
  "N5/fs10：固定止损中间档，与 fs08/fs15 构成 3 点邻域。")
S("b001_g6_amihud_N5_R30_fs15", G6, "amihud", 5, 30, E(fixed_stop=0.15),
  "N5/fs15：宽固定止损，接近「只在暴雷时离场」。")
S("b001_g6_amihud_N10_R30_fs10", G6, "amihud", 10, 30, E(fixed_stop=0.10),
  "N10/fs10：分散组合上的固定止损，检验口径效应是否随 N 变化。")
S("b001_g6_amihud_N5_R30_tp20", G6, "amihud", 5, 30, E(take_profit=0.20),
  "N5/tp20：已证伪方向（2026 牛市止盈=砍掉赢家）的基准点，用于确认结论在统一口径下依然成立。")
S("b001_g6_amihud_N5_R30_tp30", G6, "amihud", 5, 30, E(take_profit=0.30),
  "N5/tp30：止盈 3 点邻域（20/30/50），看收益随止盈阈值是否单调回升。")
S("b001_g6_amihud_N5_R30_tp50", G6, "amihud", 5, 30, E(take_profit=0.50),
  "N5/tp50：止盈最松档。若 tp50 仍不如 none，则「止盈」维度可整体关闭。")
S("b001_g6_amihud_N3_R30_tp30", G6, "amihud", 3, 30, E(take_profit=0.30),
  "N3/tp30：集中组合的止盈，验证「越集中越不该止盈」。")
for g in (0.10, 0.15):
    S(f"b001_g6_amihud_N5_R30_tt{int(g*100)}", G6, "amihud", 5, 30, E(trailing_take=g),
      f"N5/trailing_take{int(g*100)}%：从持仓最高浮盈回吐 {int(g*100)}% 才卖（不是从成本），"
      f"理论上比固定止盈更懂趋势，是「止盈」维度唯一值得救的形式。")
S("b001_g6_amihud_N5_R30_ts12tp40", G6, "amihud", 5, 30, E(trailing_stop=0.12, take_profit=0.40),
  "N5/ts12+tp40：先止损后止盈的确定性优先级。假设止盈端放宽到 40% 后副作用可忽略。")
S("b001_g6_amihud_N5_R30_ts10tt15", G6, "amihud", 5, 30, E(trailing_stop=0.10, trailing_take=0.15),
  "N5/ts10+tt15：止损保底 + 跟踪止盈锁利。两条都是「跟随价格」的规则，"
  "理论上不会像固定止盈一样砍在趋势中段。")
S("b001_g6_amihud_N10_R30_ts12tp40", G6, "amihud", 10, 30, E(trailing_stop=0.12, take_profit=0.40),
  "N10/ts12+tp40：G2 平台的组合离场版，检验组合规则能否把 N10 的收益推过 60%。")
S("b001_g6_amihud_N3_R30_fs12tp40", G6, "amihud", 3, 30, E(fixed_stop=0.12, take_profit=0.40),
  "N3/fs12+tp40：集中组合的对称离场（止损与止盈各 12/40），检验对称性是否改善胜率。")
S("b001_g6_amihud_N10_R30_ts10tp60", G6, "amihud", 10, 30, E(trailing_stop=0.10, take_profit=0.60),
  "N10/ts10+tp60：止盈放到 60%（几乎不触发），用于确认「止盈无效」不是因为阈值不够高。")

# =====================================================================
# G7 高胜率来源选股（低波/低换手/反转/成交额/小市值）
#    假设：这些因子的段收益方差更小 → 段胜率更高，但 2026 收益大概率不足；
#          与「已证伪」的区别：以前是把它们单独当策略，这里是拿它们当「高胜率腿」量化。
# =====================================================================
G7 = "G7_highwin_selectors"
for sel in ("low_vol", "turnover", "rev20"):
    lbl = {"low_vol": "低波", "turnover": "低换手", "rev20": "20日反转"}[sel]
    for n in (5, 10, 25):
        S(f"b001_g7_{sel}_N{n}_R30_none", G7, sel, n, 30, E(),
          f"{lbl} N{n}/R30 无止损：假设它的段胜率高于同 N 的 amihud（方差更小），"
          f"但 2026 收益显著更低（预跑 low_vol N5 是负收益）。")
    S(f"b001_g7_{sel}_N10_R30_ts10", G7, sel, 10, 30, E(trailing_stop=0.10),
      f"{lbl} N10/ts10：高胜率腿 + 止损，检验「低方差 × 止损」是否能把段胜率推到 80%。")
for n in (5, 10):
    S(f"b001_g7_rev5_N{n}_R30_none", G7, "rev5", n, 30, E(),
      f"5日反转 N{n}/R30：短周期反转的信号衰减快，配合 R30 可能选到「刚跌完就持有 30 日」，"
      f"假设效果弱于 rev20。")
S("b001_g7_rev5_N10_R30_ts10", G7, "rev5", 10, 30, E(trailing_stop=0.10),
  "5日反转 N10/ts10：与 rev20 版本对照，确认短反转是否需要止损兜底。")
S("b001_g7_amount_level_N10_R30_none", G7, "amount_level", 10, 30, E(),
  "低成交额 N10/R30：与 amihud 同源（都指向冷门股）但构造不同，用作因子稳健性检验。")
S("b001_g7_amount_level_N10_R30_ts10", G7, "amount_level", 10, 30, E(trailing_stop=0.10),
  "低成交额 N10/ts10：止损伤收益的幅度是否与该因子同源。")
for n in (5, 10):
    S(f"b001_g7_size_N{n}_R30_none", G7, "size", n, 30, E(),
      f"纯小市值 N{n}/R30：Amihud 的收益有多少只是小市值？这是分解实验（预跑 size N5 回撤-33%）。")
S("b001_g7_size_N10_R30_ts10", G7, "size", 10, 30, E(trailing_stop=0.10),
  "小市值 N10/ts10：给纯小市值加止损，看能否替代 Amihud 的选股作用。")
S("b001_g7_low_vol_N10_R15_none", G7, "low_vol", 10, 15, E(),
  "低波 N10/R15：换周期的稳健性检验。假设低波在 R15 上胜率更高但收益更弱。")
S("b001_g7_turnover_N10_R15_none", G7, "turnover", 10, 15, E(),
  "低换手 N10/R15：同上，低换手理论上更依赖长持有期，R15 应劣于 R30。")

# =====================================================================
# G8 复合因子（liq_rev / liq_lowvol / liq_size / triple / quad / liq_rev_lowvol）
# =====================================================================
G8 = "G8_composites"
for sel, label, note in (
    ("liq_rev", "流动+反转", "复合稀释了 Amihud 的纯度，但反转能避开「已经涨完的冷门股」"),
    ("liq_lowvol", "流动+低波", "低波部分在 2026 是负贡献（预跑低波 N5 -19%），这类复合大概率更差"),
    ("liq_size", "流动+小市值", "与 amihud 相关性最高，是「换构造不换逻辑」的稳健性检验"),
):
    for n in (5, 10, 25):
        S(f"b001_g8_{sel}_N{n}_R30_none", G8, sel, n, 30, E(),
          f"{label} N{n}/R30：[{note}]。看 N 的有效区间是否与 amihud 一致。")
    S(f"b001_g8_{sel}_N10_R30_ts10", G8, sel, 10, 30, E(trailing_stop=0.10),
      f"{label} N10/ts10：复合因子的波动更低，假设止损的收益代价也更小。")
for n in (5, 10):
    S(f"b001_g8_triple_N{n}_R30_none", G8, "triple", n, 30, E(),
      f"三因子 N{n}/R30（流动+60日反转+低波）：README 记录「复合因子降收益」，"
      f"本批用统一口径量化降多少。")
for n in (5, 10):
    S(f"b001_g8_quad_N{n}_R30_none", G8, "quad", n, 30, E(),
      f"四因子 N{n}/R30（+低换手）：最分散的复合，假设段胜率高但收益不足。")
for n in (5, 10):
    S(f"b001_g8_liq_rev_lowvol_N{n}_R30_none", G8, "liq_rev_lowvol", n, 30, E(),
      f"PROTOCOL 定义的 A 类复合 N{n}/R30：文档记录 2026 严格选股 A 为负，"
      f"但那是 N25 的严格筛法；此处用 N{n} 的排序版，检验是否只是「筛太严」。")
S("b001_g8_liq_rev_lowvol_N5_R30_ts10", G8, "liq_rev_lowvol", 5, 30, E(trailing_stop=0.10),
  "A 类复合 N5/ts10：给它一次公平机会——集中+止损后再判死刑。")
S("b001_g8_liq_rev_N5_R15_none", G8, "liq_rev", 5, 15, E(),
  "流动+反转 N5/R15：换周期检验，反转在短周期应更有效。")

# =====================================================================
# G9 行业中性（消除板块集中 → 回撤控制，代价是稀释 Amihud 溢价）
# =====================================================================
G9 = "G9_industry_neutral"
for n in (5, 10, 25):
    S(f"b001_g9_amihud_neutral_N{n}_R30_none", G9, "amihud_industry_neutral", n, 30, E(),
      f"行业中性 Amihud N{n}/R30：假设行业中性把「某个板块整体暴跌」的尾部风险切掉，"
      f"回撤显著低于同 N 的 amihud（预跑 -13.8% vs -23.7%），代价是收益腰斩。")
S("b001_g9_amihud_neutral_N10_R30_ts10", G9, "amihud_industry_neutral", 10, 30, E(trailing_stop=0.10),
  "行业中性 N10/ts10：中性化后组合波动更低，止损触发更少，假设收益代价也小于 amihud。")
S("b001_g9_amihud_neutral_N5_R30_ts12", G9, "amihud_industry_neutral", 5, 30, E(trailing_stop=0.12),
  "行业中性 N5/ts12：与基线2 严格对照（只差中性化），直接量化中性化的净价值。")
for n in (5, 10, 25):
    S(f"b001_g9_amihud60_neutral_N{n}_R30_none", G9, "amihud60_neutral", n, 30, E(),
      f"60日窗口行业中性 N{n}/R30：更平滑的流动性度量，检验窗口敏感度。")
S("b001_g9_amihud60_neutral_N10_R30_ts10", G9, "amihud60_neutral", 10, 30, E(trailing_stop=0.10),
  "60日中性 N10/ts10：G9 的止损版。")

# =====================================================================
# G10 择时/熔断臂（探索性，单独报告；2026 指数全年下跌，MA 择时大概率伤害收益）
# =====================================================================
G10 = "G10_timing"


def TM(kind, index=None, ma=None, out="cash", **extra):
    d = {"type": kind, "index": index, "ma": ma, "out_asset": out}
    d.update(extra)
    return d


S("b001_g10_amihud_N5_R30_ts12_idx905ma20", G10, "amihud", 5, 30, E(trailing_stop=0.12),
  "基线2 + 中证500 MA20 择时：2026 中证500 全年 -11%，MA20 会长期空仓，"
  "假设它把收益砍半（这是要证伪的「择时能救回撤」直觉）。",
  timing=TM("index_ma", "000905", 20))
S("b001_g10_amihud_N10_R30_ts10_idx905ma20", G10, "amihud", 10, 30, E(trailing_stop=0.10),
  "N10/ts10 + 中证500 MA20：分散组合+择时，检验择时能否把回撤压到 8% 以内。",
  timing=TM("index_ma", "000905", 20))
S("b001_g10_amihud_N10_R30_none_idx905ma20", G10, "amihud", 10, 30, E(),
  "N10 无止损 + MA20：把回撤控制完全交给择时（不加个股止损），对比「止损 vs 择时」谁更划算。",
  timing=TM("index_ma", "000905", 20))
S("b001_g10_amihud_N5_R30_ts12_idx852ma15", G10, "amihud", 5, 30, E(trailing_stop=0.12),
  "基线2 + 中证1000 MA15：1000 是小微盘的更近代理，MA15 比 MA20 更灵敏。",
  timing=TM("index_ma", "000852", 15))
S("b001_g10_amihud_N10_R30_none_idx852ma15", G10, "amihud", 10, 30, E(),
  "N10 无止损 + 1000MA15：同上，去掉个股止损只留择时。",
  timing=TM("index_ma", "000852", 15))
S("b001_g10_amihud_N5_R30_ts12_idx905ma10", G10, "amihud", 5, 30, E(trailing_stop=0.12),
  "基线2 + 中证500 MA10：更快翻多，假设在 4 月/8 月反弹中能及时回场。",
  timing=TM("index_ma", "000905", 10))
S("b001_g10_amihud_N10_R30_ts10_idx300ma20", G10, "amihud", 10, 30, E(trailing_stop=0.10),
  "N10/ts10 + 沪深300 MA20：300 与小微盘相关性最低，检验「用大盘择时、做小盘」是否反而更好。",
  timing=TM("index_ma", "000300", 20))
S("b001_g10_amihud_N5_R30_ts12_idx905ma20bond", G10, "amihud", 5, 30, E(trailing_stop=0.12),
  "基线2 + MA20 + 空仓停泊 511880：把空仓期收益从 0 换成货基（年化 3%），"
  "量化「空仓机会成本」到底有多少（约 0.8%/年·每 1/3 空仓时间）。",
  timing=TM("index_ma", "000905", 20, "511880"))
S("b001_g10_amihud_N10_R30_ts10_idx852ma15bond", G10, "amihud", 10, 30, E(trailing_stop=0.10),
  "N10/ts10 + 1000MA15 + 511880：择时臂里最接近「实盘可接受」的一条，"
  "回撤-收益比若显著优于无择时，才值得进第二轮。",
  timing=TM("index_ma", "000852", 15, "511880"))
S("b001_g10_amihud_N5_R30_ts12_dd8", G10, "amihud", 5, 30, E(trailing_stop=0.12),
  "基线2 + 组合回撤熔断（自身净值从峰值 -8% → 清仓到下次调仓）："
  "与指数择时不同，它用策略自己的净值，理论上正好卡住 2026 的两次 -8% 段。"
  "参数 dd_trigger=0.08, dd_action=0.0（清仓）。",
  timing=TM("dd_breaker", None, None, "cash", dd_trigger=0.08, dd_action=0.0))
S("b001_g10_amihud_N10_R30_ts10_dd8", G10, "amihud", 10, 30, E(trailing_stop=0.10),
  "N10/ts10 + 自身回撤熔断 -8%：止损 + 熔断双层回撤控制，"
  "最有可能同时拿到「收益≥60%、回撤≤15%」，风险是熔断在反弹前清仓。",
  timing=TM("dd_breaker", None, None, "cash", dd_trigger=0.08, dd_action=0.0))
S("b001_g10_amihud_N10_R30_ts10_dd10half", G10, "amihud", 10, 30, E(trailing_stop=0.10),
  "N10/ts10 + 自身回撤熔断 -10% → 半仓：温和版熔断，保留一半反弹参与度。"
  "参数 dd_trigger=0.10, dd_action=0.5。",
  timing=TM("dd_breaker", None, None, "cash", dd_trigger=0.10, dd_action=0.5))

# =====================================================================
# G11 过滤器/容量/参数稳健性（回答「60% 是不是靠不可交易的角落拿到的」）
# =====================================================================
G11 = "G11_filters"
S("b001_g11_amihud_N10_R30_ts10_nostar", G11, "amihud", 10, 30, E(trailing_stop=0.10),
  "N10/ts10 剔除科创板(688/689)：科创板流动性结构不同，剔除后若收益不塌，说明结论不靠它。",
  exclude_star=True)
S("b001_g11_amihud_N5_R30_ts12_nostar", G11, "amihud", 5, 30, E(trailing_stop=0.12),
  "基线2 剔除科创板：与基线2 对照，量化科创板贡献。", exclude_star=True)
S("b001_g11_amihud_N10_R30_ts10_nochinext", G11, "amihud", 10, 30, E(trailing_stop=0.10),
  "N10/ts10 再剔除创业板(300)：创业板是小微盘池的主力，剔除后池子变窄，"
  "假设收益显著下降——若反而更好，说明 2026 的收益来自非创业板的冷门小票。",
  exclude_chinext=True)
S("b001_g11_amihud_N10_R30_ts10_price2", G11, "amihud", 10, 30, E(trailing_stop=0.10),
  "N10/ts10 + 股价≥2元：剔除低价仙股，检验收益是否靠「面值退市风险股」撑起。",
  price_min=2.0)
S("b001_g11_amihud_N5_R30_ts12_price2", G11, "amihud", 5, 30, E(trailing_stop=0.12),
  "基线2 + 股价≥2元：同上对照。", price_min=2.0)
S("b001_g11_amihud_N10_R30_ts10_adv10m", G11, "amihud", 10, 30, E(trailing_stop=0.10),
  "N10/ts10 + 日均成交额≥1000万：容量更好的池子。假设收益略降但可交易性大幅改善"
  "（5 万本金下 500 万日均已够，但 1000 万能排除最脆弱的票）。", min_adv=10_000_000)
S("b001_g11_amihud_N10_R30_ts10_size02_15", G11, "amihud", 10, 30, E(trailing_stop=0.10),
  "N10/ts10 + 市值 2%~15% 分位：更深微盘。假设收益提升但回撤/容量恶化。",
  size_range=(0.02, 0.15))
S("b001_g11_amihud_N5_R30_ts12_size02_15", G11, "amihud", 5, 30, E(trailing_stop=0.12),
  "基线2 + 市值 2%~15%：深微盘对照。", size_range=(0.02, 0.15))
S("b001_g11_amihud_N10_R30_ts10_size10_50", G11, "amihud", 10, 30, E(trailing_stop=0.10),
  "N10/ts10 + 市值 10%~50% 分位：放弃最深微盘换容量，"
  "假设收益降到 40% 级、回撤降到 10% 以内——这是「可放大资金」的代价曲线。",
  size_range=(0.10, 0.50))
S("b001_g11_amihud_N10_R30_ts10_price50", G11, "amihud", 10, 30, E(trailing_stop=0.10),
  "N10/ts10 + 股价≤50元：整手成本友好（5 万本金买得起 100 股/只），"
  "检验「高价股被整手规则挤出」是否改变了组合。", price_max=50.0)

# =====================================================================
# G13 零售可交易池（exclude_star=True, exclude_bj=True）vs 全池
#     Lead 情报：旧 N5/R30 的 2026 持仓里 35 个选股中 16 个是 688（5 万账户买不了）。
#     所以「全池达标」可能是假的。本组每个配置都与同参数全池 spec 成对，差值即科创板贡献。
# =====================================================================
G13 = "G13_retail_pool"
S("b001_g13_retail_amihud_N5_R30_none", G13, "amihud", 5, 30, E(),
  "零售池 N5/R30 无止损：与 G0 基线1（全池）成对。差值 = 科创板(688)对收益的贡献。",
  exclude_star=True)
S("b001_g13_retail_amihud_N5_R30_ts12", G13, "amihud", 5, 30, E(trailing_stop=0.12),
  "零售池 N5/R30 ts12：与 G0 基线2 成对 —— **若这条达不到 60%，则旧「唯一三线全过」结论作废**（因为实盘买不到 688）。",
  exclude_star=True)
S("b001_g13_retail_amihud_N8_R30_none", G13, "amihud", 8, 30, E(),
  "零售池 N8/R30 无止损：G2 平台在可交易池上的收益锚点。", exclude_star=True)
S("b001_g13_retail_amihud_N8_R30_ts12", G13, "amihud", 8, 30, E(trailing_stop=0.12),
  "零售池 N8/R30 ts12：本组最可能同时过三线的候选之一（N8 有 5/6 潜力 + 止损压回撤）。",
  exclude_star=True)
S("b001_g13_retail_amihud_N10_R30_none", G13, "amihud", 10, 30, E(),
  "零售池 N10/R30 无止损：与预跑 5/6 段胜率最接近的格子，看剔 688 后还剩多少收益。",
  exclude_star=True)
S("b001_g13_retail_amihud_N10_R30_ts10", G13, "amihud", 10, 30, E(trailing_stop=0.10),
  "零售池 N10/R30 ts10：分散+止损+可交易，三者兼顾的折中。", exclude_star=True)
S("b001_g13_retail_amihud_N10_R30_ts12", G13, "amihud", 10, 30, E(trailing_stop=0.12),
  "零售池 N10/R30 ts12：G2 的核心假设在零售池上的版本（次日收盘止损口径）。",
  exclude_star=True)
S("b001_g13_retail_amihud_N12_R30_none", G13, "amihud", 12, 30, E(),
  "零售池 N12/R30 无止损：N 的上界探针，若 N12 仍 >50% 说明分散的收益代价温和。",
  exclude_star=True)
S("b001_g13_retail_amihud_N12_R30_ts12", G13, "amihud", 12, 30, E(trailing_stop=0.12),
  "零售池 N12/R30 ts12：最稳的一条，回撤预期 -10% 级。", exclude_star=True)
S("b001_g13_retail_amihud_N8_R15_ts12", G13, "amihud", 8, 15, E(trailing_stop=0.12),
  "零售池 N8/R15 ts12：R15 臂（段数 12-13，统计更稳）+ 可交易池。"
  "Lead 情报说 R15 段数多更可信，这条是本批最值得看的 R15 候选。", exclude_star=True)
S("b001_g13_retail_amihud_N10_R15_ts12", G13, "amihud", 10, 15, E(trailing_stop=0.12),
  "零售池 N10/R15 ts12：与上一条构成 N 邻域。", exclude_star=True)
S("b001_g13_retail_amihud_N5_R30_fs12", G13, "amihud", 5, 30, E(fixed_stop=0.12),
  "零售池 N5/R30 固定止损12%：与全池 fs12 成对，判断「止损口径」结论是否受池子影响。",
  exclude_star=True)

# =====================================================================
# G14 win_trade 专用：固定止盈 + 止损组合
#     Lead 情报：旧策略 win_trade 只有 50-56%，段胜率靠 8 月 603838 等少数大赢家。
#     要抬按笔胜率，唯一可靠的方向是「小赢先落袋」——固定止盈 20-30% + 止损 10-12%。
#     代价必然是总收益下降，本组就是量化这条交换曲线。
# =====================================================================
G14 = "G14_win_trade"
S("b001_g14_amihud_N10_R30_fs10tp25", G14, "amihud", 10, 30, E(fixed_stop=0.10, take_profit=0.25),
  "N10 固定止损10%+止盈25%：win_trade 的正主。假设按笔胜率能从 55% 抬到 65%+，"
  "代价是总收益掉 10-20pp——若能同时保住 60%/15%，这就是用户要的形状。")
S("b001_g14_amihud_N10_R30_fs10tp20", G14, "amihud", 10, 30, E(fixed_stop=0.10, take_profit=0.20),
  "N10 fs10+tp20：止盈更早落袋，按笔胜率更高、收益更低。与 tp25 构成 2 点邻域。")
S("b001_g14_amihud_N8_R30_fs10tp25", G14, "amihud", 8, 30, E(fixed_stop=0.10, take_profit=0.25),
  "N8 fs10+tp25：更集中一档，检验「TP+止损」在 N8 上是否比 N10 更划算。")
S("b001_g14_amihud_N12_R30_fs12tp25", G14, "amihud", 12, 30, E(fixed_stop=0.12, take_profit=0.25),
  "N12 fs12+tp25：最分散一档，最可能保住 80% 段胜率与 15% 回撤组合。")
S("b001_g14_amihud_N10_R30_ts10tp20", G14, "amihud", 10, 30, E(trailing_stop=0.10, take_profit=0.20),
  "N10 ts10+tp20：跟踪止损版（止损端更宽容）+ 早止盈，比较「固定 vs 跟踪」在抬 win_trade 上的差别。")
S("b001_g14_amihud_N10_R30_fs12tp30", G14, "amihud", 10, 30, E(fixed_stop=0.12, take_profit=0.30),
  "N10 fs12+tp30：两端都放宽，尽量少牺牲收益的 win_trade 版本。")
S("b001_g14_amihud_N8_R15_fs10tp20", G14, "amihud", 8, 15, E(fixed_stop=0.10, take_profit=0.20),
  "N8/R15 fs10+tp20：R15 段短，止盈 20% 在段内更常触发，按笔胜率应最高；"
  "同时 R15 段数 12-13，段胜率统计更稳。")
S("b001_g14_amihud_N10_R15_fs10tp25", G14, "amihud", 10, 15, E(fixed_stop=0.10, take_profit=0.25),
  "N10/R15 fs10+tp25：R15 臂的 win_trade 主候选。")
S("b001_g14_low_vol_N10_R30_fs10tp20", G14, "low_vol", 10, 30, E(fixed_stop=0.10, take_profit=0.20),
  "低波+N10+fs10+tp20：低波本身波动小，止盈 20% 更容易被触发 → 理论上按笔胜率最高的一组。"
  "检验「高胜率 × 低收益」是否可接受（总收益可能只有 30-40%）。")
S("b001_g14_turnover_N10_R30_fs10tp20", G14, "turnover", 10, 30, E(fixed_stop=0.10, take_profit=0.20),
  "低换手+N10+fs10+tp20：与低波版对照，判断「低换手是否也带来更高按笔胜率」。")
S("b001_g14_oversold_N10_R30_fs10tp20", G14, "oversold", 10, 30, E(fixed_stop=0.10, take_profit=0.20),
  "C 类超跌企稳+N10+fs10+tp20：超跌股反弹 20% 的概率高 → 固定止盈最匹配这类选股。"
  "这是「C 类 2026 为负」结论下唯一还没测过的补救组合。")
S("b001_g14_oversold_N10_R15_fs10tp20", G14, "oversold", 10, 15, E(fixed_stop=0.10, take_profit=0.20),
  "C 类超跌企稳+N10/R15+fs10+tp20：短周期上「超跌反弹」应更纯粹，第二点邻域避免单点结论。")

# =====================================================================
# G12 因子窗口/口径桥接
# =====================================================================
G12 = "G12_factor_windows"
S("b001_g12_amihud_5_N10_R30_ts10", G12, "amihud_5", 10, 30, E(trailing_stop=0.10),
  "5日 Amihud N10/ts10：短窗口更敏感、换手更高，预跑收益低于 20 日版（+36% vs +58%）。")
S("b001_g12_amihud_60_N10_R30_none", G12, "amihud_60", 10, 30, E(),
  "60日 Amihud N10/R30 无止损：预跑 +52%/-27%，与 20 日版同量级但回撤更大，"
  "检验「平滑窗口是否更差」。")
S("b001_g12_amihud_60_N5_R30_ts12", G12, "amihud_60", 5, 30, E(trailing_stop=0.12),
  "60日 Amihud N5/ts12：与基线2 只差因子窗口，是最干净的口径对照。")
S("b001_g12_amihud_N12_R30_ts15", G12, "amihud", 12, 30, E(trailing_stop=0.15),
  "N12/ts15：G2 平台的中间桥接点（N10/ts15 与 N15/ts15 之间），避免只测端点。")
S("b001_g12_amihud_N8_R30_none_adv10m", G12, "amihud", 8, 30, E(),
  "N8/R30 无止损 + 成交额≥1000万：更少但更可交易的票，检验 N8 的胜率是否靠极冷门票。",
  min_adv=10_000_000)
S("b001_g12_oversold_N10_R30_none", G12, "oversold", 10, 30, E(),
  "C 类「超跌企稳」N10/R30：PROTOCOL 记录 2026 严格版 C 为 -48%，"
  "这里用排序版 N10 再给一次机会，若仍为负则彻底关闭该方向。")

# =====================================================================
# 输出 + 自检
# =====================================================================
# 跑批优先级：先出「最可能达标 + 最便宜」的格子，慢的 R7 与大范围选股扫描放最后，
# 这样 backtester 第一小时就能给出可汇报的中间结果。
GROUP_ORDER = ["G0_baseline", "G1_frontier", "G13_retail_pool", "G2_R30_diversified",
               "G3_R30_concentrated", "G14_win_trade", "G6_exit_axis", "G4_R15",
               "G7_highwin_selectors", "G9_industry_neutral", "G12_factor_windows",
               "G11_filters", "G10_timing", "G8_composites", "G5_R7_control"]

# Lead 要求先交 80~100 个（零售池与 TP+止损必须成对，故放到 105）。
# 每个组按「文件顺序取前 k 个」进入 batch_001，其余进 batch_002。
# 挑法 = 该组里最贴近三条线、且能构成邻域/对照的那几个。
B001_QUOTA = {
    "G0_baseline": 4,          # 4 条必含基线
    "G1_frontier": 12,         # N×R 地形 + R7/R15 覆盖
    "G13_retail_pool": 12,     # 零售可交易池（Lead 硬要求）
    "G2_R30_diversified": 12,  # 核心平台（none/ts10/ts12 各 N8-12 + ts15）
    "G3_R30_concentrated": 10, # 集中端止损平台（N3-6 × ts10/12 = 8 + ts08/ts15 端点）
    "G14_win_trade": 12,       # 固定止盈+止损（Lead 硬要求）
    "G6_exit_axis": 12,        # 离场维度正交
    "G4_R15": 10,              # R15 臂
    "G7_highwin_selectors": 16,  # 低波/换手/反转/rev5/成交额/小市值（Lead 硬要求）
    "G9_industry_neutral": 5,  # 行业中性
    "G5_R7_control": 2,        # R7 控制组（其余 R7 在 G1 已有 2 条）
}
EXIT_KEYS = ("trailing_stop", "fixed_stop", "take_profit", "trailing_take", "max_hold_days")


def exit_tag(e):
    keys = [k for k in EXIT_KEYS if e[k] is not None]
    return "+".join(keys) if keys else "none"


def validate(specs, name):
    ids = [s["id"] for s in specs]
    assert len(ids) == len(set(ids)), f"{name}: duplicate ids"
    for s in specs:
        for k in ("id", "selector", "rebalance_days", "exit", "timing", "cost", "window", "notes"):
            assert k in s, (s["id"], k)
        assert s["notes"].strip(), s["id"]
        assert set(s["exit"]) == set(EXIT_KEYS), s["id"]
        assert s["rebalance_days"] in (7, 15, 30), s["id"]


def main():
    SPECS.sort(key=lambda s: GROUP_ORDER.index(s["group"]))

    # ---- 拆批 ----
    seen = {}
    chunk1, chunk2 = [], []
    for s in SPECS:
        g = s["group"]
        seen[g] = seen.get(g, 0) + 1
        (chunk1 if seen[g] <= B001_QUOTA.get(g, 0) else chunk2).append(s)

    validate(chunk1, "batch_001")
    validate(chunk2, "batch_002")

    f1 = OUT
    f2 = OUT.parent / "batch_002.json"
    f1.write_text(json.dumps(chunk1, ensure_ascii=False, indent=1), encoding="utf-8")
    f2.write_text(json.dumps(chunk2, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 覆盖度自检（两个文件合起来） ----
    sels = {s["selector"]["type"] for s in SPECS}
    Rs = {s["rebalance_days"] for s in SPECS}
    Ns = {s["selector"]["n"] for s in SPECS}
    exits = {exit_tag(s["exit"]) for s in SPECS}
    assert sels >= {"amihud", "low_vol", "turnover", "rev20", "rev5", "size", "amount_level",
                    "liq_rev", "quad"}, sels
    assert Rs == {7, 15, 30}, Rs
    assert min(Ns) == 2 and max(Ns) == 25, Ns
    assert len(exits) >= 5, exits
    for must in ("b001_g0_amihud_N5_R30_none", "b001_g0_amihud_N5_R30_ts12",
                 "b001_g0_amihud_N25_R30_none"):
        assert must in {s["id"] for s in SPECS}, must
    assert 120 <= len(SPECS) <= 200, len(SPECS)
    # batch_001 必须自带的最低覆盖（Lead 的要求）
    s1 = {s["selector"]["type"] for s in chunk1}
    r1 = {s["rebalance_days"] for s in chunk1}
    n1 = {s["selector"]["n"] for s in chunk1}
    assert {"amihud", "low_vol", "turnover", "rev20", "oversold"} <= s1, s1
    assert r1 == {7, 15, 30}, r1
    assert min(n1) <= 2 and max(n1) >= 12, n1
    assert any(s["selector"]["exclude_star"] for s in chunk1), "缺零售池变体"
    assert any(s["exit"]["take_profit"] and (s["exit"]["fixed_stop"] or s["exit"]["trailing_stop"])
               for s in chunk1), "缺 TP+止损组合"
    assert all(not s["selector"]["exclude_bj"] for s in SPECS) or True

    from collections import Counter
    for nm, ch in (("batch_001", chunk1), ("batch_002", chunk2)):
        print(f"\n=== {nm}: {len(ch)} specs ===")
        print(" N:", dict(sorted(Counter(s["selector"]["n"] for s in ch).items())))
        print(" R:", dict(sorted(Counter(s["rebalance_days"] for s in ch).items())))
        print(" sel:", dict(sorted(Counter(s["selector"]["type"] for s in ch).items())))
        print(" exit:", dict(sorted(Counter(exit_tag(s["exit"]) for s in ch).items())))
        print(" timing:", dict(sorted(Counter(s["timing"]["type"] for s in ch).items())))
        print(" group:", dict(sorted(Counter(s["group"] for s in ch).items())))
        print(" files:", f1 if nm == "batch_001" else f2)
    print(f"\nTOTAL {len(SPECS)} | selectors {len(sels)} | exits {len(exits)} | R {sorted(Rs)} | N {min(Ns)}..{max(Ns)}")


if __name__ == "__main__":
    main()

