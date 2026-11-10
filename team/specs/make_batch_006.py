"""Batch 006 generator (strategist) — Round 3：fresh 5 万多目标帕累托（**N4 重心版**）。

Lead 2026-11-05 发现（官方 harness，fresh、现实费率、整手、TP50、主板、phase 0）：
  * **N4 全面支配 N5/N6**：full **+98.72% / MDD −11.38% / wp 5-6 / wm 7-10 / wt 62.5% / 24 笔**
  * N4 敞口阶梯：0.9 +86.0/−9.6、0.8 +71.8/−8.9、0.7 +62.8/−8.9、0.6 +48.6/−6.5、0.3 +19.9/−3.3
  * N4 no-stop +97.2/−12.0；N3 full +85.8/−16.4；N2 no-stop +96.7/−20.0（wp 67 / wm 50，差）
  * Top3 仍约 61%（603580/603838/603261/002199）→ 集中度未解，但**新目标不卡这项**

因此本批重心改为：
  G1 **N4 主网格 36** = N4 × exposure{0.3..1.0 八档} × TP{40,50,60,none}（32）+ exp{0.9,1.0} × TP{45,55}（4）
  G2 N 横切 9 = N2/N3/N5/N7 × {1.0, 0.7} × TP50（8）+ N3 no-stop@1.0（1）
  G3 分散对照 6 = N8/10/12/16/20/25 × TP50 @1.0
  G4 N4 防守/离场 4 = staged[30/50]、staged[20/35]、fs10、vt20
  G5 N4 相位 3 = phase −10 / −5 / +5
  G6 sleeve 3 = 3-sleeve N4 ×{0.7,0.9}、5-sleeve N4 ×0.9
  G7 控制组 3 = C3(N6@1.0)、C2(N5@0.9)、C5(3-sleeve N5@0.9)

Run: .venv/bin/python team/specs/make_batch_006.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "batch_006.json"
COST = {"one_way": 0.005, "capital": 50000, "lot_size": 100}
WINDOW = {"warmup_start": "2024-01-01", "eval_start": "2026-01-05", "eval_end": "2026-11-04"}
NO_TIMING = {"type": "none", "index": None, "ma": None, "out_asset": "cash"}
EXIT_KEYS = ("trailing_stop", "fixed_stop", "take_profit", "trailing_take", "max_hold_days")
STG_30_50 = [{"trigger": 0.30, "fraction": 0.3333}, {"trigger": 0.50, "fraction": 0.3333}]
STG_20_35 = [{"trigger": 0.20, "fraction": 0.3333}, {"trigger": 0.35, "fraction": 0.3333}]
SPECS = []


def S(sid, group, n, notes, *, tp=None, staged=None, fs=None, ts=None, max_hold=None,
      exposure=1.0, vol_target=None, sleeves=None, timing=None, out_asset="cash", phase=0):
    selector = {"type": "amihud_60", "n": n, "size_range": [0.05, 0.30], "min_adv": 5_000_000,
                "exclude_star": True, "exclude_bj": True, "exclude_chinext": True,
                "price_min": None, "price_max": None, "params": {}}
    ex = {k: None for k in EXIT_KEYS}
    ex["take_profit"] = tp
    ex["fixed_stop"] = fs
    ex["trailing_stop"] = ts
    ex["max_hold_days"] = max_hold
    if staged is not None:
        ex["staged_take"] = staged
    tm = dict(timing or NO_TIMING)
    tm["out_asset"] = out_asset
    port = {"exposure": exposure, "cash_asset": out_asset, "fresh_start": True}
    if vol_target is not None:
        port["vol_target"] = vol_target
    if sleeves:
        port["sleeves"] = sleeves
    d = {"id": sid, "group": group, "selector": selector, "rebalance_days": 30, "exit": ex,
         "timing": tm, "portfolio": port, "cost": dict(COST), "window": dict(WINDOW), "notes": notes}
    if phase:
        d["rebalance_offset_days"] = phase
    SPECS.append(d)


# =====================================================================
# G1 N4 主网格（36）—— **最高优先级，先跑这 36 条**
#     Lead 实测 N4 full = +98.72% / −11.38% / wp 5-6 / wm 70% / wt 62.5%
# =====================================================================
G1 = "G1_N4_core"
for e in (0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00):
    for tp in (0.40, 0.50, 0.60, None):
        tag = int(round(e * 100))
        ttag = "nostopTP" if tp is None else f"TP{int(tp * 100)}"
        base = ("**N4 控制组：必须复现 Lead 的 fresh +98.72% / MDD −11.38% / wp 5-6 / wm 7-10 / wt 62.5%。**"
                if (abs(e - 1.0) < 1e-9 and tp == 0.50) else
                "N4 是 fresh 口径下的最优点（更高收益 + 更低回撤 + 更高按笔胜率，全面支配 N5/N6）——"
                "本格用来确认它的 TP 敏感性：TP 越高越接近 no-stop（收益高、回撤也高），"
                "TP 越低越早锁利（按笔胜率升、收益降）。")
        S(f"b006_G1_N4_{ttag}_exp{tag}", G1, 4,
          f"N4 / {('无止盈' if tp is None else f'TP{int(tp * 100)}')} / 敞口 {tag}% / 主板 / R30。{base}",
          tp=tp, exposure=e)
for e in (0.90, 1.00):
    for tp in (0.45, 0.55):
        tag = int(round(e * 100))
        S(f"b006_G1_N4_TP{int(tp * 100)}_exp{tag}", G1, 4,
          f"N4 / TP{int(tp * 100)} / 敞口 {tag}%：TP 的 45/55 两档只在高敞口下补点，"
          f"用于确认 TP50 不是孤立尖峰（若 TP45/50/55 的 fresh_total 差 <3pp，则 TP 维度可视为平台）。",
          tp=tp, exposure=e)

# =====================================================================
# G2 N 横切（9）：确认 N4 是局部最优还是噪声
# =====================================================================
G2 = "G2_N_cross"
for n in (2, 3, 5, 7):
    for e in (1.00, 0.70):
        tag = int(round(e * 100))
        S(f"b006_G2_N{n}_TP50_exp{tag}", G2, n,
          f"N{n} / TP50 / 敞口 {tag}%：N4 的两个邻居（N3、N5）已实测 —— N3 full +85.8/−16.4、"
          f"N5 fresh +64.48/−12.76。本条补上 N2/N7 与 0.7 档，用来判断 N4 的优势是**平台**还是**孤立尖峰**："
          f"若 N3/N4/N5 的 fresh_total 依次为 86/99/64，则 N4 明显突起，需要警惕过拟合。",
          tp=0.50, exposure=e)
S("b006_G2_N3_nostopTP_exp100", G2, 3,
  "N3 / 无止盈 / 满仓：N3 TP50 是 +85.8/−16.4；去掉止盈看它是「止盈救了它」还是「止盈伤了它」。",
  tp=None, exposure=1.00)

# =====================================================================
# G3 分散对照（6）：只留少量，证明 N8+ 在 fresh 5 万下不可用
# =====================================================================
G3 = "G3_diversify_control"
for n in (8, 10, 12, 16, 20, 25):
    S(f"b006_G3_N{n}_TP50_exp100", G3, n,
      f"N{n} / TP50 / 满仓（对照）。5 万 + 100 股整手下，N{n} 每票 {50000/n:.0f} 元 → "
      f"{'基本可买一手' if n <= 8 else '多数 30 元以上的票买不起一手'}，"
      f"实际有效持仓会明显少于 {n}。本组的作用是**证明分散在 5 万本金下已经失效**，"
      f"而不是寻找更优解（Round 1 实测 N8 +44.8%、N10 +39~46%、N12 +26%）。",
      tp=0.50, exposure=1.00)

# =====================================================================
# G4 N4 的防守/离场（4）：在新最优点上重测一遍 overlay
# =====================================================================
G4 = "G4_N4_overlay"
S("b006_G4_N4_stg30_50", G4, 4,
  "N4 + 分批止盈[+30 卖1/3, +50 卖1/3]（替换 TP50）。Round 2 在 N6 上 staged 是最强收益增强"
  "（主口径 +81.3%、按笔 66.7% 全场最高）。N4 的 TP50 已是 +98.72%，staged 有可能把它推到 >100%。",
  staged=STG_30_50)
S("b006_G4_N4_stg20_35", G4, 4,
  "N4 + 更早分批止盈[+20/+35]：假设它把按笔胜率从 62.5% 推到 68%+，代价是收益掉 8~12pp —— "
  "这是「高胜率型」画像在 N4 上的候选。", staged=STG_20_35)
S("b006_G4_N4_fs10", G4, 4,
  "N4 + 固定止损 10%（叠加 TP50）。Round 1/2 两次实测止损在 amihud_60 上是纯伤害；"
  "在 N4 上再测一次是为了确认「更集中的底子 + 止损」是否仍无价值。", tp=0.50, fs=0.10)
S("b006_G4_N4_vt20", G4, 4,
  "N4 + 目标波动 20%（只降仓）。N4 的回撤本来就只有 −11.38%，vol_target 若把它压到 −8% 内"
  "且收益守住 80%，就是「稳健型」的强候选。", tp=0.50, vol_target=0.20)

# =====================================================================
# G5 N4 相位（3）：确认不是 phase 0 运气
# =====================================================================
G5 = "G5_N4_phase"
for ph in (-10, -5, 5):
    S(f"b006_G5_N4_TP50_exp100_p{'m' if ph < 0 else 'p'}{abs(ph)}", G5, 4,
      f"N4 / TP50 / 满仓 / 相位 {ph:+d}：**这是本轮最关键的三条之一**。Lead 的 +98.72% 是 phase 0；"
      f"若在 −5/+5 相位掉到 60% 以下，则 N4 的优势也是相位运气（Round 1 已证明 R30 的 mdd 是相位的函数）。"
      f"先给 3 档，够判断方向即可。", tp=0.50, phase=ph)

# =====================================================================
# G6 sleeve（3）：N4 底子上的错相位，看能否再降回撤
# =====================================================================
G6 = "G6_sleeve_N4"
for e in (0.70, 0.90):
    tag = int(round(e * 100))
    S(f"b006_G6_sleeve3_N4_TP50_exp{tag}", G6, 4,
      f"3-sleeve（−8/0/+8）N4/TP50 × 敞口 {tag}%。Round 2 的 sleeve 在 N5 上 fresh 只有 +54.90%（整手摩擦），"
      f"N4 每 sleeve 每票约 {50000*e/3/4:.0f} 元 —— 比 N5/3-sleeve 的 3200 元好得多，"
      f"所以 sleeve 在 N4 上**第一次有可能不被整手打垮**。假设：mdd 降到 −8% 内、收益守住 75%。",
      tp=0.50, exposure=e, sleeves={"count": 3, "offsets": [-8, 0, 8], "alloc": "equal"})
S("b006_G6_sleeve5_N4_TP50_exp90", G6, 4,
  "5-sleeve（−12/−6/0/+6/+12）N4/TP50 × 敞口 90%：把相位覆盖做到 5 份，代价是每份只有 9000 元、"
  "每票 2250 元（整手摩擦重新变紧）。用于检验「相位分散」与「整手摩擦」的净效应。",
  tp=0.50, exposure=0.90, sleeves={"count": 5, "offsets": [-12, -6, 0, 6, 12], "alloc": "equal"})

# =====================================================================
# G7 控制组（3）：C3 / C2 / C5 的 fresh 对照（保留，用于画像表横向对比）
# =====================================================================
G7 = "G7_controls"
S("b006_G7_C3_N6_TP50_exp100", G7, 6,
  "**C3 控制组**：N6/TP50/满仓。必须复现 Round 2 的 fresh **+64.48% / −12.76% / wp 5-6（±0.5pp）**；"
  "与 N4 同批跑，才能证明「N4 优于 N6」不是跨批次的口径差异。", tp=0.50)
S("b006_G7_C2_N5_TP50_exp90", G7, 5,
  "**C2 控制组**：N5/TP50/0.90。Round 2 fresh = +59.94%。", tp=0.50, exposure=0.90)
S("b006_G7_C5_sleeve3_N5_TP50_exp90", G7, 5,
  "**C5 控制组**：3-sleeve N5/TP50/0.90。Round 2 fresh = +54.90%。",
  tp=0.50, exposure=0.90, sleeves={"count": 3, "offsets": [-8, 0, 8], "alloc": "equal"})


def main():
    ids = [s["id"] for s in SPECS]
    assert len(ids) == len(set(ids)), [x for x in ids if ids.count(x) > 1][:3]
    for s in SPECS:
        for k in ("id", "selector", "rebalance_days", "exit", "timing", "portfolio", "cost", "window", "notes"):
            assert k in s, (s["id"], k)
        assert set(s["exit"]) >= set(EXIT_KEYS)
        assert s["notes"].strip() and len(s["notes"]) > 40, s["id"]
        assert s["portfolio"].get("fresh_start") is True, s["id"]
        assert not (s["exit"].get("staged_take") and s["exit"].get("take_profit")), s["id"]
        assert 0.2 <= s["portfolio"]["exposure"] <= 1.0
    assert 60 <= len(SPECS) <= 100, len(SPECS)
    # N4 主网格必须是文件最前面的一批（跑批顺序 = 优先级）
    first_ids = [s["id"] for s in SPECS[:36]]
    assert all(s.startswith("b006_G1_N4_") for s in first_ids), "G1 必须在最前"
    OUT.write_text(json.dumps(SPECS, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(f"wrote {len(SPECS)} -> {OUT}")
    print(" groups:", dict(sorted(Counter(s["group"] for s in SPECS).items())))
    print(" N:", dict(sorted(Counter(s["selector"]["n"] for s in SPECS).items())))
    print(" exposure:", dict(sorted(Counter(s["portfolio"]["exposure"] for s in SPECS).items())))
    print(" TP:", dict(sorted(Counter(str(s["exit"]["take_profit"]) for s in SPECS).items())))
    print(" with sleeves:", sum(1 for s in SPECS if "sleeves" in s["portfolio"]))
    print(" N4 total:", sum(1 for s in SPECS if s["selector"]["n"] == 4))


if __name__ == "__main__":
    main()
