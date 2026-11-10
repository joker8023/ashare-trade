"""Batch 001 addendum generator (strategist) — amihud_60 定向确认集。

为什么单独一个文件：Lead 已独立跑出前沿「amihud_60 N5/N8 R30 零售池三线全过」，
本文件是对该前沿的**定向确认 + 相位加固**，不是第二轮网格搜索。
按 Lead 要求不改已交付的 batch_001.json（避免与 backtester 抢文件）。

写盘：
  team/specs/batch_001_addendum.json   — 39 个（可直接跑）
  team/specs/batch_001_phase_probe.json — 6 个（依赖 harness 的 rebalance_offset_days，可选）

Run: .venv/bin/python team/specs/make_batch_001_addendum.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
COST = {"one_way": 0.005, "capital": 50000, "lot_size": 100}
WINDOW = {"warmup_start": "2024-01-01", "eval_start": "2026-01-05", "eval_end": "2026-11-04"}
NO_TIMING = {"type": "none", "index": None, "ma": None, "out_asset": "cash"}
EXIT_KEYS = ("trailing_stop", "fixed_stop", "take_profit", "trailing_take", "max_hold_days")

# 本数据集没有北交所（universe 里 0 只 8xx/4xx），所以 exclude_bj 是空操作；
# 「零售池」实质 = 剔除科创板 688/689（606 只，占 12%），这是 5 万账户真买不到的部分。
RETAIL = dict(exclude_star=True, exclude_bj=True)
FULL = dict(exclude_star=False, exclude_bj=True)

SPECS = []


def E(trailing_stop=None, fixed_stop=None, take_profit=None, trailing_take=None, max_hold_days=None):
    return {"trailing_stop": trailing_stop, "fixed_stop": fixed_stop, "take_profit": take_profit,
            "trailing_take": trailing_take, "max_hold_days": max_hold_days}


def tag(e):
    keys = [k for k in EXIT_KEYS if e[k] is not None]
    return "_".join({"trailing_stop": "ts", "fixed_stop": "fs", "take_profit": "tp",
                     "trailing_take": "tt", "max_hold_days": "mh"}[k] for k in keys) or "none"


def num(e):
    """ts12 / fs10tp20 这类数值后缀。"""
    out = []
    for k, pre in (("trailing_stop", "ts"), ("fixed_stop", "fs"), ("take_profit", "tp"),
                   ("trailing_take", "tt"), ("max_hold_days", "mh")):
        v = e[k]
        if v is None:
            continue
        out.append(f"{pre}{int(v*100)}" if k != "max_hold_days" else f"mh{int(v)}")
    return "".join(out) or "none"


def S(sid, group, sel, n, R, ex, notes, pool=None, extra=None, **selkw):
    d = {
        "id": sid,
        "group": group,
        "selector": dict({
            "type": sel, "n": n, "size_range": [0.05, 0.30], "min_adv": 5_000_000,
            "exclude_star": False, "exclude_bj": True, "exclude_chinext": False,
            "price_min": None, "price_max": None, "params": {},
        }, **(pool or {}), **selkw),
        "rebalance_days": R,
        "exit": ex,
        "timing": dict(NO_TIMING),
        "cost": dict(COST),
        "window": dict(WINDOW),
        "notes": notes,
    }
    if extra:
        d.update(extra)
    SPECS.append(d)
    return d


A1 = "A1_amihud60_R30"
# ---- (1) amihud_60 × N × R30 × 池 × 离场 ----
S("badd_g1_amihud60_N3_R30_retail_none", A1, "amihud_60", 3, 30, E(),
  "零售池 N3/R30 无止损：Lead 实测 +140%/-19.7%。这是「收益天花板」端，"
  "回撤必然超标；用途是量化「N3→N5 分散换掉多少收益」。", pool=RETAIL)
S("badd_g1_amihud60_N3_R30_retail_ts12", A1, "amihud_60", 3, 30, E(trailing_stop=0.12),
  "零售池 N3/ts12：如果 12% 跟踪止损能把 N3 的 -19.7% 回撤压到 15% 内而收益仍有 80%+，"
  "那才是最激进的达标解。注意次日收盘止损口径会削掉一部分止损收益。", pool=RETAIL)
S("badd_g1_amihud60_N5_R30_retail_none", A1, "amihud_60", 5, 30, E(),
  "**核心确认项**：零售池 N5/R30 无止损 = Lead 实测的三线全过样本（+80.4%/-14.1%/5/6）。"
  "本 spec 的唯一任务就是用统一 harness 复现它；而且必须同时报告 5 个相位的结果。", pool=RETAIL)
S("badd_g1_amihud60_N5_R30_retail_ts08", A1, "amihud_60", 5, 30, E(trailing_stop=0.08),
  "零售池 N5/ts08：紧止损端。Lead 的 -14.1% 回撤刚好贴线，8% 止损是用来买安全垫的；"
  "若收益掉到 55% 以下就说明 15% 回撤这条线只能用无止损拿。", pool=RETAIL)
S("badd_g1_amihud60_N5_R30_retail_ts10", A1, "amihud_60", 5, 30, E(trailing_stop=0.10),
  "零售池 N5/ts10：主推候选——回撤预期 -9~-11%，收益若仍 ≥60% 就是「有余量的达标」而不是贴线达标。", pool=RETAIL)
S("badd_g1_amihud60_N5_R30_retail_ts12", A1, "amihud_60", 5, 30, E(trailing_stop=0.12),
  "零售池 N5/ts12：与无止损版只差止损，直接测出「跟踪止损对 amihud_60 的净贡献」正负。", pool=RETAIL)
S("badd_g1_amihud60_N5_R30_retail_ts15", A1, "amihud_60", 5, 30, E(trailing_stop=0.15),
  "零售池 N5/ts15：松止损端。与 ts10/ts12 构成 3 点邻域，用于确定止损平台（不是尖峰）。", pool=RETAIL)
S("badd_g1_amihud60_N8_R30_retail_none", A1, "amihud_60", 8, 30, E(),
  "**核心确认项 2**：零售池 N8/R30 无止损（Lead 实测 +62%/-14.3%/5/6）。"
  "N8 比 N5 的相位依赖更轻（5 相位里 2 个过），是本批最可能「稳」的达标点。", pool=RETAIL)
S("badd_g1_amihud60_N8_R30_retail_ts10", A1, "amihud_60", 8, 30, E(trailing_stop=0.10),
  "零售池 N8/ts10：N8 已经 5/6，加止损只是买回撤安全垫（-14.3% → 预期 -10%）；"
  "关键是收益会不会跌破 60%。", pool=RETAIL)
S("badd_g1_amihud60_N8_R30_retail_ts12", A1, "amihud_60", 8, 30, E(trailing_stop=0.12),
  "零售池 N8/ts12：同上，12% 档。若 N8/ts10 与 ts12 都 ≥60% 且回撤 ≤12%，"
  "这一对就是「平台」而不是单点运气。", pool=RETAIL)
S("badd_g1_amihud60_N8_R30_retail_ts15", A1, "amihud_60", 8, 30, E(trailing_stop=0.15),
  "零售池 N8/ts15：松止损端，补全 N8 的 10/12/15 平台。", pool=RETAIL)
S("badd_g1_amihud60_N10_R30_retail_none", A1, "amihud_60", 10, 30, E(),
  "零售池 N10/R30 无止损：更分散一档。假设回撤进一步降到 -12% 内、收益 50-55%，"
  "用来判断「用 N 换回撤」在 amihud_60 上是否比「用止损换回撤」更省收益。", pool=RETAIL)
S("badd_g1_amihud60_N10_R30_retail_ts10", A1, "amihud_60", 10, 30, E(trailing_stop=0.10),
  "零售池 N10/ts10：双层回撤控制（分散+止损），最保守的达标尝试。", pool=RETAIL)
S("badd_g1_amihud60_N10_R30_retail_ts12", A1, "amihud_60", 10, 30, E(trailing_stop=0.12),
  "零售池 N10/ts12：N10 的止损版，与 N10/none 成对。", pool=RETAIL)
S("badd_g1_amihud60_N12_R30_retail_none", A1, "amihud_60", 12, 30, E(),
  "零售池 N12/R30 无止损：N 的上界探针。", pool=RETAIL)
S("badd_g1_amihud60_N12_R30_retail_ts12", A1, "amihud_60", 12, 30, E(trailing_stop=0.12),
  "零售池 N12/ts12：最稳的一条，用于画「N-收益-回撤」的右端。", pool=RETAIL)
# 全池对照（含 688/689）
S("badd_g1_amihud60_N5_R30_full_none", A1, "amihud_60", 5, 30, E(),
  "全池（含科创板）N5/R30 无止损：与零售池同参数成对，差值 = 科创板贡献。"
  "Lead 说零售池反而更好 → 本 spec 就是验证这句话。", pool=FULL)
S("badd_g1_amihud60_N5_R30_full_ts10", A1, "amihud_60", 5, 30, E(trailing_stop=0.10),
  "全池 N5/ts10：全池的止损版，检查「零售池更优」是否是止损后才出现的差异。", pool=FULL)
S("badd_g1_amihud60_N5_R30_full_ts12", A1, "amihud_60", 5, 30, E(trailing_stop=0.12),
  "全池 N5/ts12：同上第二点。", pool=FULL)
S("badd_g1_amihud60_N8_R30_full_none", A1, "amihud_60", 8, 30, E(),
  "全池 N8/R30 无止损：与零售池 N8 成对。", pool=FULL)
S("badd_g1_amihud60_N8_R30_full_ts12", A1, "amihud_60", 8, 30, E(trailing_stop=0.12),
  "全池 N8/ts12：成对第二点。", pool=FULL)
S("badd_g1_amihud60_N10_R30_full_ts12", A1, "amihud_60", 10, 30, E(trailing_stop=0.12),
  "全池 N10/ts12：全池的分散端。", pool=FULL)
S("badd_g1_amihud60_N3_R30_full_none", A1, "amihud_60", 3, 30, E(),
  "全池 N3/R30 无止损：最高收益端在含 688 时会不会更夸张，用于判断「不可交易的收益」有多大。",
  pool=FULL)

A2 = "A2_amihud60_exit"
# ---- (2) 零售池 N5/N8 R30 的固定止损/止盈/组合（win_trade 维度）----
S("badd_g2_amihud60_N5_R30_retail_fs10", A2, "amihud_60", 5, 30, E(fixed_stop=0.10),
  "零售池 N5 固定止损10%：与 ts10 成对，回答「amihud_60 上跟踪与固定哪个更省收益」。", pool=RETAIL)
S("badd_g2_amihud60_N5_R30_retail_fs12", A2, "amihud_60", 5, 30, E(fixed_stop=0.12),
  "零售池 N5 固定止损12%：同上第二点。", pool=RETAIL)
S("badd_g2_amihud60_N8_R30_retail_fs10", A2, "amihud_60", 8, 30, E(fixed_stop=0.10),
  "零售池 N8 固定止损10%：N8 上固定止损应比 N5 更少误伤（单票权重低）。", pool=RETAIL)
S("badd_g2_amihud60_N8_R30_retail_fs12", A2, "amihud_60", 8, 30, E(fixed_stop=0.12),
  "零售池 N8 固定止损12%：与 fs10 构成 2 点邻域。", pool=RETAIL)
S("badd_g2_amihud60_N5_R30_retail_tp20", A2, "amihud_60", 5, 30, E(take_profit=0.20),
  "零售池 N5 止盈20%：**专测 win_trade**。Lead 说旧策略按笔胜率只有 50-56%，"
  "固定止盈 20% 是把「浮盈」变「已实现盈利」最直接的办法，代价是砍掉大赢家。", pool=RETAIL)
S("badd_g2_amihud60_N8_R30_retail_tp30", A2, "amihud_60", 8, 30, E(take_profit=0.30),
  "零售池 N8 止盈30%：放宽一档，尽量少牺牲总收益的前提下抬按笔胜率。", pool=RETAIL)
S("badd_g2_amihud60_N5_R30_retail_tt40", A2, "amihud_60", 5, 30, E(trailing_take=0.40),
  "零售池 N5 trailing_take40%：从最高浮盈回吐 40% 才卖（不是从成本），"
  "既锁利又不砍在趋势中段——这是「止盈」维度最可能不反作用的形式。", pool=RETAIL)
S("badd_g2_amihud60_N8_R30_retail_tt40", A2, "amihud_60", 8, 30, E(trailing_take=0.40),
  "零售池 N8 trailing_take40%：与 N5 成对。", pool=RETAIL)
S("badd_g2_amihud60_N5_R30_retail_fs10tp20", A2, "amihud_60", 5, 30,
  E(fixed_stop=0.10, take_profit=0.20),
  "零售池 N5 止损10%+止盈20%：win_trade 正主。假设按笔胜率 55%→68%，"
  "总收益掉到 55-65%。若它同时能过三线，就是「胜率口径最硬」的达标解。", pool=RETAIL)
S("badd_g2_amihud60_N8_R30_retail_ts12tp30", A2, "amihud_60", 8, 30,
  E(trailing_stop=0.12, take_profit=0.30),
  "零售池 N8 止损12%+止盈30%：把「低回撤」与「高按笔胜率」两个目标放进同一条 spec。", pool=RETAIL)

A3 = "A3_amihud60_R15"
# ---- (3) 零售池 N5/N8 R15 × trailing ----
S("badd_g3_amihud60_N5_R15_retail_ts10", A3, "amihud_60", 5, 15, E(trailing_stop=0.10),
  "零售池 N5/R15 ts10：R15 段数 12-13，段胜率的统计功效比 R30（6 段）高得多，"
  "是降低相位依赖的第二条路。假设 80% 需 10/12，很难，但 9/12 也有 75%，"
  "配合 R30 的 5/6 可以构成「口径交叉验证」。", pool=RETAIL)
S("badd_g3_amihud60_N5_R15_retail_ts12", A3, "amihud_60", 5, 15, E(trailing_stop=0.12),
  "零售池 N5/R15 ts12：同上第二点。", pool=RETAIL)
S("badd_g3_amihud60_N8_R15_retail_ts10", A3, "amihud_60", 8, 15, E(trailing_stop=0.10),
  "零售池 N8/R15 ts10：更分散+更多段数，理论上段胜率最高的一条。", pool=RETAIL)
S("badd_g3_amihud60_N8_R15_retail_ts12", A3, "amihud_60", 8, 15, E(trailing_stop=0.12),
  "零售池 N8/R15 ts12：与上一条构成 2 点邻域。", pool=RETAIL)

A5 = "A5_amihud60_neutral"
# ---- (附加) 行业中性版 amihud_60：用行业中性换回撤，给贴线回撤买余量 ----
S("badd_g5_amihud60neutral_N5_R30_retail_none", A5, "amihud60_neutral", 5, 30, E(),
  "行业中性 amihud_60 N5/R30 零售池：剔除科创板后池子更偏成长，行业集中度风险上升；"
  "行业中性化可以把「某板块整体崩塌」切掉。假设回撤比 amihud_60 低 3-5pp、收益低 10-15pp。",
  pool=RETAIL)
S("badd_g5_amihud60neutral_N8_R30_retail_ts12", A5, "amihud60_neutral", 8, 30, E(trailing_stop=0.12),
  "行业中性 amihud_60 N8/ts12：中性化+分散+止损三重回撤控制，"
  "是「宁可少赚也要把 15% 回撤做实」的那条路。", pool=RETAIL)

PHASE = "P0_phase_probe"
PHASE_SPECS = []


def P(sid, n, offset, notes):
    d = S(sid, PHASE, "amihud_60", n, 30, E(), notes, pool=RETAIL)
    SPECS.pop()          # 相位探针只进 phase_probe 文件，不进 addendum 主文件
    d["rebalance_offset_days"] = offset
    PHASE_SPECS.append(d)


P("bphase_amihud60_N5_R30_retail_offm5", 5, -5,
  "相位 -5：把 R30 的调仓网格整体前移 5 个交易日。Lead 实测 2024-01-02 锚点下 N5 只有 +44.2%/-19.1%/3-6，"
  "本 spec 与 off0/off+5 一起给出「相位分布」，用来判断达标是真 alpha 还是锚点运气。")
P("bphase_amihud60_N5_R30_retail_off0", 5, 0,
  "相位 0：默认锚点（= A1 的核心确认项，此处重复一次以便相位文件自洽可比）。")
P("bphase_amihud60_N5_R30_retail_offp5", 5, 5,
  "相位 +5：后移 5 个交易日。")
P("bphase_amihud60_N8_R30_retail_offm5", 8, -5,
  "相位 -5（N8）：N8 在 Lead 的 5 相位里 2 过，本 spec 检查它在 -5 相位是否仍达标。")
P("bphase_amihud60_N8_R30_retail_off0", 8, 0,
  "相位 0（N8）：与 A1 的 N8 无止损同参数，用于相位文件内部比较。")
P("bphase_amihud60_N8_R30_retail_offp5", 8, 5,
  "相位 +5（N8）。")


def validate(specs, name, min_n=1):
    ids = [s["id"] for s in specs]
    assert len(ids) == len(set(ids)), f"{name}: dup ids"
    assert len(specs) >= min_n, (name, len(specs))
    for s in specs:
        for k in ("id", "selector", "rebalance_days", "exit", "timing", "cost", "window", "notes"):
            assert k in s, (s["id"], k)
        assert set(s["exit"]) == set(EXIT_KEYS), s["id"]
        assert s["rebalance_days"] in (7, 15, 30)
        assert s["notes"].strip(), s["id"]
    return True


def main():
    validate(SPECS, "addendum", 30)
    validate(PHASE_SPECS, "phase_probe", 3)
    f1 = HERE / "batch_001_addendum.json"
    f2 = HERE / "batch_001_phase_probe.json"
    f1.write_text(json.dumps(SPECS, ensure_ascii=False, indent=1), encoding="utf-8")
    f2.write_text(json.dumps(PHASE_SPECS, ensure_ascii=False, indent=1), encoding="utf-8")

    from collections import Counter
    print(f"addendum: {len(SPECS)} specs -> {f1}")
    print(" groups:", dict(sorted(Counter(s["group"] for s in SPECS).items())))
    print(" N:", dict(sorted(Counter(s["selector"]["n"] for s in SPECS).items())))
    print(" R:", dict(sorted(Counter(s["rebalance_days"] for s in SPECS).items())))
    print(" pool: retail", sum(s["selector"]["exclude_star"] for s in SPECS),
          "| full", sum(not s["selector"]["exclude_star"] for s in SPECS))
    print(" exits:", dict(sorted(Counter(tag(s["exit"]) for s in SPECS).items())))
    print(f"phase probe: {len(PHASE_SPECS)} specs -> {f2}  (needs rebalance_offset_days)")
    print("\nall addendum ids:")
    for s in SPECS:
        print(" ", s["id"], "|", num(s["exit"]), "| star_excl=", s["selector"]["exclude_star"])


if __name__ == "__main__":
    main()
