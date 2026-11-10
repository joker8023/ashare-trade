"""Batch 007 generator (strategist) — Round 4：**N4 以外的策略族**（其他族，77 条）。

背景：batch_006 已证明 N4 单组合在 fresh 5 万口径下强（TP45@1.0 = +102.1%/−11.4%），
且 sleeve 的 fresh 数字因资本 bug 作废（真实五等分 sleeve5 = +35.09%）。
用户要求「再多考虑其他策略」→ 本批**不再重复 N4 × exposure × TP 单组合**，只测其他族：

  G1 R 轴（26）：N4/N5 × R20/30/40/60 × TP{40,45,50,60} × exp{0.6,0.8,0.9,1.0}（筛后）
     —— Lead 快扫：**R60 +61.0/−11.8/wp100/wt83.3**、R40 +70.8/−13.8/wp100/wt78 → 高胜率方向
  G2 其他选股器（24）：低波/vol60/反转/低换手/小市值/低成交/liq_rev/liq_size/quad/triple/
     liq_lowvol/行业中性 × N{5,10} × R{30,60} × TP50 × exp{0.6,0.9}
  G3 价值（6）：value_em 的 EP/BP/SP × N{10,20} × R60 × exp{0.9,0.6}（需 harness 接新数据）
  G4 ETF/指数轮动（10）：510300/510500/159915 × MA20/60 + 动量 + 511880 混合（仅 2026，无 OOS）
  G5 行业/事件（6）：行业动量 top3 ×2；amount spike / gap / breakthrough × R5/R10 ×4
  G6 ensemble（5）：N4R30 + N4R60 / 债券 / 低波 的 70/30、50/50 合成

优先级（时间有限时按此顺序跑）：**G1 > G2 > G6 > G3 > G5 > G4**。

Run: .venv/bin/python team/specs/make_batch_007.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "batch_007.json"
COST = {"one_way": 0.005, "capital": 50000, "lot_size": 100}
WINDOW = {"warmup_start": "2024-01-01", "eval_start": "2026-01-05", "eval_end": "2026-11-04"}
NO_TIMING = {"type": "none", "index": None, "ma": None, "out_asset": "cash"}
EXIT_KEYS = ("trailing_stop", "fixed_stop", "take_profit", "trailing_take", "max_hold_days")
MAINBOARD = {"exclude_star": True, "exclude_bj": True, "exclude_chinext": True}
SPECS = []


def S(sid, group, notes, *, sel="amihud_60", n=4, R=30, tp=None, exposure=1.0,
      params=None, pool=None, extra_sel=None, timing=None, out_asset="cash",
      sleeves=None, ensemble=None, universe=None, phase=0):
    selector = dict({
        "type": sel, "n": n, "size_range": [0.05, 0.30], "min_adv": 5_000_000,
        "exclude_star": True, "exclude_bj": True, "exclude_chinext": True,
        "price_min": None, "price_max": None, "params": params or {},
    }, **(pool or {}))
    if extra_sel:
        selector.update(extra_sel)
    ex = {k: None for k in EXIT_KEYS}
    ex["take_profit"] = tp
    port = {"exposure": exposure, "cash_asset": out_asset, "fresh_start": True}
    if sleeves:
        port["sleeves"] = sleeves
    if ensemble:
        port["ensemble"] = ensemble
    d = {"id": sid, "group": group, "selector": selector, "rebalance_days": R, "exit": ex,
         "timing": dict(timing or NO_TIMING), "portfolio": port, "cost": dict(COST),
         "window": dict(WINDOW), "notes": notes}
    d["timing"]["out_asset"] = out_asset
    if universe:
        d["universe"] = universe          # ETF/指数族：标出「非股票横截面」
    if phase:
        d["rebalance_offset_days"] = phase
    SPECS.append(d)


# =====================================================================
# G1 R 轴（26）—— 最高优先：Lead 快扫显示 R40/R60 是「高段/笔胜率」方向
# =====================================================================
G1 = "G1_R_axis"
# R40/R60 × N4/N5 × TP50 × exp{0.6,0.8,0.9,1.0} = 16
for R in (40, 60):
    for n in (4, 5):
        for e in (0.6, 0.8, 0.9, 1.0):
            tag = int(round(e * 100))
            S(f"b007_G1_N{n}_R{R}_TP50_exp{tag}", G1,
              f"N{n} / **R{R}** / TP50 / 敞口 {tag}%。Lead 快扫：R60 = +61.0/−11.8/**wp 100%**/**wt 83.3%**、"
              f"R40 = +70.8/−13.8/wp 100%/wt 78%。**R 越长，段数越少（R60 只有 3~4 段）→ 段胜率天然容易 100%，"
              f"但统计功效更差**。本格假设：R40/R60 的「高胜率」是真实的（每次持仓期都赚钱），"
              f"但它可能只是「把 2026 的上涨平均摊到更少的段里」，必须用月胜率与按笔胜率交叉验证。",
              n=n, R=R, tp=0.50, exposure=e)
# TP 轴：R60 × N4 × TP{40,45,60} × exp{0.9,1.0} = 6
for tp in (0.40, 0.45, 0.60):
    for e in (0.9, 1.0):
        tag = int(round(e * 100))
        S(f"b007_G1_N4_R60_TP{int(tp*100)}_exp{tag}", G1,
          f"N4 / R60 / TP{int(tp*100)} / 敞口 {tag}%：R60 下的止盈敏感性。"
          f"R60 的持仓期长 2 倍，止盈阈值的影响被放大——TP40 更早锁利（按笔胜率↑、收益↓），"
          f"TP60 接近 no-stop。假设最优 TP 在 R60 上会比 R30 的 TP45 更高。",
          n=4, R=60, tp=tp, exposure=e)
# R20 与 R30 对照各 2 = 4
for R, e in ((20, 0.9), (20, 1.0)):
    S(f"b007_G1_N4_R{R}_TP50_exp{int(round(e*100))}", G1,
      f"N4 / R{R} / TP50 / 敞口 {int(round(e*100))}%：R 轴的下端。R20 段数 ~9-10，"
      f"统计功效比 R60 好，但换手费用高。用来确认「R 越长越省费用但段数越少」的权衡。",
      n=4, R=R, tp=0.50, exposure=e)
for R, e in ((30, 0.9), (30, 1.0)):
    S(f"b007_G1_N4_R{R}_TP45_exp{int(round(e*100))}", G1,
      f"N4 / R30 / TP45 / 敞口 {int(round(e*100))}%：**同批控制组**（batch_006 的冠军组合重跑），"
      f"用于把 R 轴的每一格与同批次口径对齐。期望 +102.1/−11.4（exp1.0）与 +91.2/−9.6（exp0.9）。",
      n=4, R=R, tp=0.45, exposure=e)

# =====================================================================
# G2 其他选股器（24）：12 个族 × 2 格（N5/R60/0.9 与 N10/R60/0.6）
#     假设：它们的 2026 收益都弱于 amihud_60，但可能提供「低相关/低回撤」价值。
# =====================================================================
G2 = "G2_other_selectors"
SELECTORS = [
    ("low_vol", "低波(vol20)", "段收益方差小 → 月胜率高、回撤浅；Round 1 实测 2026 收益极低（N5 −19%），"
                               "但帕累托不卡收益门槛，只看它是否落在低回撤端"),
    ("vol60", "低波(vol60)", "更平滑的低波定义，换手更低"),
    ("rev20", "20日反转", "唯一在 2026 仍为正的替代族（预跑 N5 +7%），与 amihud 相关性低"),
    ("rev5", "5日反转", "短反转，信号衰减快，适合 R60 这种长持有？未必——假设它更适合短 R"),
    ("turnover", "低换手", "与 amihud 同源（冷门股），但构造不同；假设比 amihud 更稳、更慢"),
    ("size", "纯小市值", "Amihud 的收益有多少只是小市值？分解实验"),
    ("amount_level", "低成交额", "与 amihud 同源的另一种构造，稳健性检验"),
    ("liq_rev", "流动+反转", "复合稀释 alpha，但反转提供独立性"),
    ("liq_size", "流动+小市值", "与 amihud 相关性最高，换构造不换逻辑"),
    ("quad", "四因子", "最分散的复合，假设胜率高但收益低"),
    ("triple", "三因子", "流动+60日反转+低波"),
    ("amihud60_neutral", "行业中性 amihud_60", "切掉板块尾部，用收益换回撤"),
]
for sel, label, note in SELECTORS:
    S(f"b007_G2_{sel}_N5_R60_exp90", G2,
      f"{label} / N5 / R60 / TP50 / 敞口 90%。{note}。"
      f"**这是本族的「收益端」取样点**（N5 比 N10 更集中）。", sel=sel, n=5, R=60, tp=0.50, exposure=0.90)
    S(f"b007_G2_{sel}_N10_R60_exp60", G2,
      f"{label} / N10 / R60 / TP50 / 敞口 60%。{note}。"
      f"**这是本族的「稳健端」取样点**（N10 + 低敞口）。两格一起，用来判断该族是落在帕累托的"
      f"低回撤端（有价值）还是被 N4 全面支配（无价值）。", sel=sel, n=10, R=60, tp=0.50, exposure=0.60)

# =====================================================================
# G3 价值（6）：value_em 的 EP/BP/SP（需 harness 接数据）
# =====================================================================
G3 = "G3_value"
for sel, label in (("value_ep", "EP（盈利收益率 = 1/PE）"), ("value_bp", "BP（账面市值比 = 1/PB）"),
                   ("value_sp", "SP（营收市值比 = 1/PS）")):
    for n, e in ((10, 0.90), (20, 0.60)):
        S(f"b007_G3_{sel}_N{n}_R60_exp{int(round(e*100))}", G3,
          f"{label} / N{n} / R60 / TP50 / 敞口 {int(round(e*100))}%（**需 harness 接 `data/value_em.pkl`**）。"
          f"我已实测：价值组合与 amihud 名单重叠仅 0.07/6（Jaccard 0.01），但**低 PB 组合 2026 亏 −6.8%**，"
          f"且「剔最贵 1/3」会让 amihud 从 +93.5% 掉到 +35.3% → **2026 价值方向与 alpha 相反**。"
          f"本组只作「低相关/低回撤对照」，**不指望它赚钱**；若它的 mdd 明显更低，可作为防守 sleeve 的候选。",
          sel=sel, n=n, R=60, tp=0.50, exposure=e,
          params={"data": "value_em", "winsor": "cross_section_p1_p99"})

# =====================================================================
# G4 ETF / 指数轮动（10）：仅 2026，无预热/OOS —— 只作探索
# =====================================================================
G4 = "G4_etf_rotation"
ETF_NOTE = ("**数据限制（必须写进结论）**：`data/minute_etf/` 只有 5 分钟线（159915/510300/510500），"
            "日线需从 5 分钟聚合；159915 仅 471 天、510300/510500 更短 → **没有 2024 预热、没有 OOS**，"
            "结果只能标「仅探索」。")
for code, name in (("510300", "沪深300ETF"), ("510500", "中证500ETF"), ("159915", "创业板ETF")):
    for ma in (20, 60):
        S(f"b007_G4_etf_{code}_MA{ma}", G4,
          f"{name}({code}) / 收盘 > MA{ma} 则持有 ETF，否则空仓停现金；R=5（周频复核）。"
          f"假设：2026 指数全年下跌（中证1000 −14%），MA 趋势策略应长期空仓 → 收益接近 0、回撤很小。"
          f"在帕累托图上它会落在「左下角」（低收益低回撤）。{ETF_NOTE}",
          sel="etf_ma", n=1, R=5, exposure=1.0,
          params={"code": code, "ma": ma, "asset": "etf"}, universe="etf")
S("b007_G4_etf_510300_mom60", G4,
  "沪深300ETF / 60 日动量 > 0 则持有，否则空仓停现金；R=20（月度复核）。与 MA60 对照，看「动量」与「均线」哪个更抗噪。"
  + ETF_NOTE, sel="etf_mom", n=1, R=20, exposure=1.0,
  params={"code": "510300", "lookback": 60}, universe="etf")
S("b007_G4_etf_510500_mom60", G4,
  "中证500ETF / 60 日动量 > 0 则持有，否则空仓停现金；R=20。中证500 在 2026 −11.3%，动量信号大概率长期空仓。" + ETF_NOTE,
  sel="etf_mom", n=1, R=20, exposure=1.0, params={"code": "510500", "lookback": 60}, universe="etf")
S("b007_G4_etf_510300_MA20_bond", G4,
  "沪深300ETF / MA20 + 空仓停 511880：把空仓期收益从 0 换成货基（年化 ~3%），量化「空仓不白躺」的贡献。" + ETF_NOTE,
  sel="etf_ma", n=1, R=5, exposure=1.0, out_asset="511880",
  params={"code": "510300", "ma": 20}, universe="etf")
S("b007_G4_etf_159915_MA20_bond", G4,
  "创业板ETF / MA20 + 空仓停 511880：159915 是三个 ETF 里波动最大、数据最长（471 天）的一个。" + ETF_NOTE,
  sel="etf_ma", n=1, R=5, exposure=1.0, out_asset="511880",
  params={"code": "159915", "ma": 20}, universe="etf")

# =====================================================================
# G5 行业轮动 / 事件（6）
# =====================================================================
G5 = "G5_industry_event"
S("b007_G5_ind_mom_top3_R20", G5,
  "行业动量 top3（industry_map 的 120 个 industry_group，20 日涨幅排序，等权持有组内按 amihud_60 前 3 只），"
  "R=20。**industry_map 是静态快照（非 PIT）**，行业分类变更会造成前视；且 120 组里只有 ~50 组有足够票。"
  "假设：2026 行业轮动剧烈（7 月 −19.7%、10 月 −15.6%），动量大概率在拐点被反复打脸。",
  sel="industry_momentum", n=3, R=20, tp=0.50, exposure=0.90,
  params={"top_k": 3, "lookback": 20, "map": "industry_map"})
S("b007_G5_ind_mom_top3_R60", G5,
  "行业动量 top3 / R=60：与 R20 那份成对，把持有期拉长 3 倍以压低换手。"
  "**industry_map 是静态快照（非 PIT）**，且 120 个 industry_group 里只有约 50 组有足够票可选；"
  "假设：R60 在行业轮动上更可能「买在高点、卖在低点」，预期劣于 R20。",
  sel="industry_momentum", n=3, R=60, tp=0.50, exposure=0.90,
  params={"top_k": 3, "lookback": 60, "map": "industry_map"})
S("b007_G5_amount_spike_R5", G5,
  "成交额突增事件（当日 amount > 20 日均量 ×3）后买入，持有 R=5 天：追「资金进场」。"
  "假设 2026 小微盘的放量常是短期见顶信号（README：量比因子为负向），故预期为负。",
  sel="amount_spike", n=5, R=5, tp=None, exposure=0.90, params={"mult": 3.0})
S("b007_G5_amount_spike_R10", G5,
  "成交额突增事件（当日 amount > 20日均量×3）后买入 / R=10：与 R5 那份成对，持有期翻倍以观察是否反转。"
  "假设：若 R5 为负而 R10 转正，说明放量是「短期噪音」而非「见顶」；若两者都负，则该事件族关闭。",
  sel="amount_spike", n=5, R=10, tp=None, exposure=0.90, params={"mult": 3.0})
S("b007_G5_gap_down_R5", G5,
  "向下跳空事件（open/prev_close − 1 < −3%）后买入 R=5：测「恐慌缺口回补」。"
  "假设：小微盘缺口回补概率约 50%，扣掉 1% 双边成本后基本无效。",
  sel="gap_event", n=5, R=5, tp=None, exposure=0.90, params={"thresh": -0.03, "direction": "down"})
S("b007_G5_breakout20_R10", G5,
  "20 日新高突破（close >= 20 日最高 ×0.99）后买入 R=10：经典动量。"
  "README 已证伪动量（IC 显著为负），此处是用事件式定义再验一次。",
  sel="breakout_event", n=5, R=10, tp=None, exposure=0.90, params={"lookback": 20})

# =====================================================================
# G6 ensemble（5）：按日净值合成，各份资本按权重拆分
# =====================================================================
G6 = "G6_ensemble"
ENS = ("**合成口径**：各 leg 按权重拆分资本（不是各用全资本！sleeve 的 bug 就是这条），"
       "每 leg 独立 100 股整手与现实费率，合成净值 = Σ wᵢ × NAVᵢ / Σ wᵢ，"
       "段胜率用合成净值按 R 算。")
S("b007_G6_ens_N4R30_N4R60_70_30", G6,
  "N4R30(TP45) + N4R60(TP50) 70/30 合成：两个 R 的相位不同 → 可能同时抬月胜率与降回撤。"
  "假设：R60 的 wp 100% 与 R30 的 +102% 收益互补，70/30 后 total ≈ 0.7×102 + 0.3×61 ≈ 90%，mdd 取中间。" + ENS,
  sel="ensemble", n=4, R=30, exposure=1.0,
  ensemble=[{"leg": {"selector": "amihud_60", "n": 4, "R": 30, "tp": 0.45}, "weight": 0.70},
            {"leg": {"selector": "amihud_60", "n": 4, "R": 60, "tp": 0.50}, "weight": 0.30}])
S("b007_G6_ens_N4R30_N4R60_50_50", G6,
  "N4R30(TP45) + N4R60(TP50) 50/50 合成：更均衡的两相位组合。" + ENS,
  sel="ensemble", n=4, R=30, exposure=1.0,
  ensemble=[{"leg": {"selector": "amihud_60", "n": 4, "R": 30, "tp": 0.45}, "weight": 0.50},
            {"leg": {"selector": "amihud_60", "n": 4, "R": 60, "tp": 0.50}, "weight": 0.50}])
S("b007_G6_ens_N4R30_bond_70_30", G6,
  "N4R30(TP45) 70% + 511880 债券 30%：**纯降杠杆对照**（等价于 exposure 0.7 但现金有 ~3% 年化）。"
  "假设：它的 total 应与 N4 TP45 exp0.7 几乎相同（+62.8% 量级），用于验证 ensemble 实现是否正确。" + ENS,
  sel="ensemble", n=4, R=30, exposure=1.0,
  ensemble=[{"leg": {"selector": "amihud_60", "n": 4, "R": 30, "tp": 0.45}, "weight": 0.70},
            {"leg": {"selector": "bond_511880", "weight": 0.30}}])
S("b007_G6_ens_N4R30_bond_50_50", G6,
  "N4R30(TP45) 50% + 债券 50%：半仓版，对应「稳健型」的低回撤端。" + ENS,
  sel="ensemble", n=4, R=30, exposure=1.0,
  ensemble=[{"leg": {"selector": "amihud_60", "n": 4, "R": 30, "tp": 0.45}, "weight": 0.50},
            {"leg": {"selector": "bond_511880", "weight": 0.50}}])
S("b007_G6_ens_N4R30_lowvol_70_30", G6,
  "N4R30(TP45) 70% + 低波 N10 30%：用**低相关腿**降回撤（低波与 amihud 相关性低）。"
  "假设：低波腿 2026 收益低（−19%~+7%），但波动小 → 组合 mdd 可能比纯降杠杆更低。" + ENS,
  sel="ensemble", n=4, R=30, exposure=1.0,
  ensemble=[{"leg": {"selector": "amihud_60", "n": 4, "R": 30, "tp": 0.45}, "weight": 0.70},
            {"leg": {"selector": "low_vol", "n": 10, "R": 60, "tp": 0.50}, "weight": 0.30}])


def main():
    ids = [s["id"] for s in SPECS]
    assert len(ids) == len(set(ids)), [x for x in ids if ids.count(x) > 1][:3]
    for s in SPECS:
        for k in ("id", "selector", "rebalance_days", "exit", "timing", "portfolio", "cost", "window", "notes"):
            assert k in s, (s["id"], k)
        assert s["notes"].strip() and len(s["notes"]) > 40, s["id"]
        assert s["portfolio"].get("fresh_start") is True, s["id"]
        assert 0.2 <= s["portfolio"]["exposure"] <= 1.0
    assert 60 <= len(SPECS) <= 80, len(SPECS)
    # 不能重复 batch_006 的 N4 单组合主网格（除 2 条同批控制）
    ctrl = [s["id"] for s in SPECS if s["group"] == "G1_R_axis" and "R30" in s["id"]]
    assert len(ctrl) == 2, ctrl
    OUT.write_text(json.dumps(SPECS, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(f"wrote {len(SPECS)} -> {OUT}")
    print(" groups:", dict(sorted(Counter(s["group"] for s in SPECS).items())))
    print(" R:", dict(sorted(Counter(s["rebalance_days"] for s in SPECS).items())))
    print(" n:", dict(sorted(Counter(s["selector"]["n"] for s in SPECS).items())))
    print(" selectors:", dict(sorted(Counter(s["selector"]["type"] for s in SPECS).items())))
    print(" exposure:", dict(sorted(Counter(s["portfolio"]["exposure"] for s in SPECS).items())))
    print(" universe!=stock:", sum(1 for s in SPECS if s.get("universe")), "| ensemble:", sum(1 for s in SPECS if "ensemble" in s["portfolio"]))


if __name__ == "__main__":
    main()
