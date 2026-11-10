"""Batch 003 generator (strategist) — exposure（现金缓冲）× TP50 的邻域 + 3-sleeve 骨架。

背景（batch_001 + addendum 实测，非我的预跑）：
  * amihud 20d 全族 0 个 Tier A/B/C（最好 N4 ts10 +61.5%/-18.2%/胜率 50%）→ 路线关闭。
  * amihud_60 N5 R30 零售池 无止损：+77.0%/-13.87%/win_period 5-6（phase 0 全过）；
    但 mdd 是相位的函数：5 相位 -13.9%~-17.5%，只有 1/5 全过 → 收益稳健、回撤不稳健。
  * 止损在该因子上一律是收益杀手且几乎不降回撤（N5 ts10: +33.3%/-13.8%；N8 ts12: +34%/-12.4%/33%）
    → 止损维度在本轮关闭，不再做网格。
  * Lead 用「目标仓位 85~90% + 其余现金」把 N5 TP50 主板推成 3/5 相位全过。

本批只做三件事：exposure 邻域、TP 邻域、sleeve 骨架。新增字段 `portfolio.exposure`。

Run: .venv/bin/python team/specs/make_batch_003.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "batch_003.json"

COST = {"one_way": 0.005, "capital": 50000, "lot_size": 100}
WINDOW = {"warmup_start": "2024-01-01", "eval_start": "2026-01-05", "eval_end": "2026-11-04"}
NO_TIMING = {"type": "none", "index": None, "ma": None, "out_asset": "cash"}
EXIT_KEYS = ("trailing_stop", "fixed_stop", "take_profit", "trailing_take", "max_hold_days")

# 主板池：剔科创板(688/689) + 北交所 + 创业板(300/301)。这是 Lead 验证过的「零售可交易主板」。
MAINBOARD = dict(exclude_star=True, exclude_bj=True, exclude_chinext=True)

SPECS = []


def E(take_profit=None):
    e = dict.fromkeys(EXIT_KEYS)
    e["take_profit"] = take_profit
    return e


def S(sid, group, n, R, tp, exposure, notes, phase=0, pool=None, sleeves=None):
    d = {
        "id": sid,
        "group": group,
        "selector": dict({
            "type": "amihud_60", "n": n, "size_range": [0.05, 0.30], "min_adv": 5_000_000,
            "exclude_star": True, "exclude_bj": True, "exclude_chinext": True,
            "price_min": None, "price_max": None, "params": {},
        }, **(pool or {})),
        "rebalance_days": R,
        "exit": E(tp),
        "timing": dict(NO_TIMING),
        # 新增：目标仓位（其余留现金）。不改变选股，只改变资金使用率；不加杠杆、不做空。
        "portfolio": {"exposure": exposure, "cash_asset": "cash"},
        "cost": dict(COST),
        "window": dict(WINDOW),
        "notes": notes,
    }
    if sleeves:
        d["portfolio"]["sleeves"] = sleeves
    if phase:
        d["rebalance_offset_days"] = phase
    SPECS.append(d)


def pid(n, tp, exposure, phase):
    t = "TPnone" if tp is None else f"TP{int(round(tp*100))}"
    p = "p0" if phase == 0 else f"pm{abs(phase)}" if phase < 0 else f"pp{phase}"
    return f"b003_{n}_{t}_exp{int(round(exposure*100))}_{p}"


# =====================================================================
# C2 邻域：N{5,6,7} × TP{40,50,60} × exposure{0.85,0.90} × phase{0,-5}
#     假设：Lead 的 N5/TP50/0.85~0.90 不是孤立尖峰，而是 (N, TP, 仓位) 三维平台的内部点。
#     三重邻域同时平移，才叫「平台」；任何一维出现尖峰就说明是运气。
# =====================================================================
C2 = "C2_neighborhood"
N_NOTE = {
    5: "N5：Lead 的原始前沿，单票 20% 权重，top3 占 76% P&L（TP50 后降到 65%）",
    6: "N6：比 N5 分散一档，理论上 mdd 更低但 alpha 摊薄；是「平台中心」检验",
    7: "N7：继续分散，检验收益衰减是否线性（若不是线性说明 N6 附近有结构）",
}
TP_NOTE = {
    0.40: "TP40：更早止盈 → 段胜率更高、收益更低；用于确认 TP 维度的单调方向",
    0.50: "TP50：Lead 验证的最优档（月胜率 80%，win_trade 60%）",
    0.60: "TP60：几乎不触发（≈无止损），用于确认 TP50 的优势不是「越松越好」",
}
for n in (5, 6, 7):
    for tp in (0.40, 0.50, 0.60):
        for expo in (0.85, 0.90):
            for phase in (0, -5):
                S(pid(n, tp, expo, phase), C2, n, 30, tp, expo,
                  f"{N_NOTE[n]}；{TP_NOTE[tp]}；仓位 {int(expo*100)}%（其余现金）；"
                  f"相位 {phase:+d}。假设：该点在 (N,TP,敞口) 平台上，"
                  f"phase 0/-5 都应满足 total≥60% 且 mdd≤15% 且 win_period≥80%。",
                  phase=phase)

# =====================================================================
# C3 N6 TP50 深化：把胜率/收益都不足的相位（-10/+5/+10）铺开在敞口轴上
#     目的：找到「最差相位也能过」的敞口，而不是只挑好相位。
# =====================================================================
C3 = "C3_N6_TP50_phase"
PH_NOTE = {
    -10: "phase -10：Lead 实测 +63~68%/-13.9~-14.6%/胜率 100%（已过）—— 本处验证敞口更低时是否失收益",
    5: "phase +5：**唯一因胜率不达标（67%）而失败的相位**。假设提高敞口不能救胜率，"
       "只有换 N 或 TP 才能救；本组用来确认「胜率失败与敞口无关」",
    10: "phase +10：**唯一因收益不达标（+40~42%）而失败的相位**。假设降低敞口会进一步恶化，"
        "所以 phase +10 的解法只能是「提高敞口」或「换池」，本组给出上界",
}
for phase in (-10, 5, 10):
    for expo in (0.80, 0.85, 0.90, 0.95):
        S(f"b003_c3_N6_TP50_exp{int(expo*100)}_"
          + ("p0" if phase == 0 else (f"pm{abs(phase)}" if phase < 0 else f"pp{phase}")),
          C3, 6, 30, 0.50, expo,
          f"N6/TP50 主板；{PH_NOTE[phase]}；敞口 {int(expo*100)}%。"
          f"四条敞口连成一条线，用来判断「失败相位」是否可用敞口单独救回来。",
          phase=phase)

# =====================================================================
# C1 纯 no-stop 的敞口变体（6 条）：把「TP 的贡献」与「敞口的贡献」分离
#     若 no-stop + 0.85 也能三线过，说明 TP50 只是「变相降低平均仓位」，那就不需要 TP。
# =====================================================================
C1 = "C1_no_stop_exposure"
for expo in (0.85, 0.90):
    for phase in (0, -5, 5):
        S(pid(5, None, expo, phase), C1, 5, 30, None, expo,
          f"N5 无止盈（no-stop）+ 敞口 {int(expo*100)}%，相位 {phase:+d}。"
          f"**关键识别**：TP50 的作用是「兑现浮盈→降低后续平均仓位」，与直接降敞口在数学上可能等价。"
          f"若本条与 TP50 版的 total/mdd 接近，则 TP 维度可以砍掉，只留敞口（更少参数=更抗过拟合）。",
          phase=phase)

# =====================================================================
# C5 3-sleeve 骨架（1 条）：降低相位依赖的结构性方案
#     把资金等分 3 份，各自独立跑 R30、相位错开 -8/0/+8 个交易日，合成净值 = 三份均值。
# =====================================================================
S("b003_c5_sleeve3_N5_TP50_e90",
  "C5_sleeve3", 5, 30, 0.50, 0.90,
  "3-sleeve 骨架：N5/TP50/主板，资金三等分，每份 exposure 0.90（合计仍是 0.90 投资、0.10 现金），"
  "三份相位错开 -8/0/+8 个交易日。**假设**：单一 R30 网格的 mdd 是相位函数（-13.9~-17.5%），"
  "三份错峰后各自的回撤不回叠，合成净值 mdd 应落在 -11~-14%，而收益 ≈ 三相位均值（≈80%）→ "
  "这是唯一同时保住收益与回撤的结构性方案。"
  "**口径（必须按此报）**：① 合成净值 = 三份净值算术平均（每份 1/3 资金），"
  "② win_period 用合成净值按 R=30 算完整段，③ 另报每个 sleeve 自己的 total/mdd/win_period 与 "
  "三者的 max-min（sleeve_dispersion），④ win_trade 合并三份的全部个股交易算，⑤ **不许**把三个 sleeve "
  "当三个独立策略分别报告或调参。",
  sleeves={"count": 3, "offsets": [-8, 0, 8], "alloc": "equal"})

# =====================================================================
# C6 池子对照（2 条）：确认「主板」这个池子约束的贡献（不是无关网格，是归因）
# =====================================================================
S("b003_c6_N5_TP50_e90_p0_chinext_on", "C6_pool_control", 5, 30, 0.50, 0.90,
  "N5/TP50/敞口90%，但**创业板放回池子**（只剔 688/689）。与 C2 的 N5/TP50/0.90/phase0 成对，"
  "差值 = 创业板对收益/回撤的贡献。Lead 说主板更好，本条是归因证据。",
  pool=dict(exclude_chinext=False))
S("b003_c6_N5_TP50_e90_p0_fullpool", "C6_pool_control", 5, 30, 0.50, 0.90,
  "N5/TP50/敞口90%，**全池**（含 688/689，仅剔北交所=空操作）。与主板成对，"
  "差值 = 科创板贡献；同时验证 addendum 里「零售池优于全池」的结论在 TP50 下是否仍成立。",
  pool=dict(exclude_star=False, exclude_chinext=False))


def validate(specs):
    ids = [s["id"] for s in specs]
    assert len(ids) == len(set(ids)), [x for x in ids if ids.count(x) > 1][:5]
    for s in specs:
        for k in ("id", "selector", "rebalance_days", "exit", "timing", "portfolio", "cost", "window", "notes"):
            assert k in s, (s["id"], k)
        assert set(s["exit"]) == set(EXIT_KEYS)
        assert 0.5 <= s["portfolio"]["exposure"] <= 1.0, s["id"]
        assert s["rebalance_days"] in (7, 15, 30)
        assert s["notes"].strip()
        assert s["selector"]["type"] == "amihud_60"
    return True


def main():
    validate(SPECS)
    OUT.write_text(json.dumps(SPECS, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(f"wrote {len(SPECS)} specs -> {OUT}")
    print(" groups:", dict(sorted(Counter(s["group"] for s in SPECS).items())))
    print(" N:", dict(sorted(Counter(s["selector"]["n"] for s in SPECS).items())))
    print(" TP:", dict(sorted(Counter(str(s["exit"]["take_profit"]) for s in SPECS).items())))
    print(" exposure:", dict(sorted(Counter(s["portfolio"]["exposure"] for s in SPECS).items())))
    print(" phase:", dict(sorted(Counter(s.get("rebalance_offset_days", 0) for s in SPECS).items())))
    print(" pool: mainboard", sum(1 for s in SPECS if s["selector"]["exclude_chinext"]),
          "| chinext-on", sum(1 for s in SPECS if not s["selector"]["exclude_chinext"]),
          "| star-on", sum(1 for s in SPECS if not s["selector"]["exclude_star"]))
    assert 50 <= len(SPECS) <= 70, len(SPECS)
    print("all specs carry portfolio.exposure:", all("exposure" in s["portfolio"] for s in SPECS))


if __name__ == "__main__":
    main()
