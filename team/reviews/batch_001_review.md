# Batch 001 对抗性审查（107 spec，Tier A=0）

- 审查对象：`team/runs/batch_001_results.csv`（107 spec，0 error）、`batch_001add_results.csv`（39）、`batch_001phase_results.csv`（6）
- 独立实现：`team/audit/prior_check.py`（未 import harness/engine/ledger）
- 结论：**批次「无一条三线全过」的结论成立**；harness 口径基本正确，但**尾随止损类 spec 的独立复算偏差可达 8.5pp**（>0.5pp 容差）→ 批次判定 `PASS_WITH_WARNINGS`（不影响 Tier 结论）。

---

## 1. 分层计数（复核）

| Tier | 官方 | 我复核 |
|---|---|---|
| A（三线全过） | 0 | **0** |
| A-ann | 0 | 0 |
| B（收益+回撤过、胜率差） | 0 | **0** |
| C（三项过两项） | 0 | 0 |
| error | 0 | 0 |

107 条全部 `tier=none`。最接近的：N4_R30_ts10 **+66.2% / −18.2% / wp 3/6**；N2_R30_none +61.1% / −27.0%；N3_R30_none +57.9% / −21.6%。
→ **瓶颈是回撤**：在 0.5%/边 + 新网格 + stop_next 下，没有任何高收益 spec 把 mdd 压到 −15% 以内（最好的高收益 spec 也在 −18% 上下）。这与旧 20 日策略审计（FAIL_METRIC：−17.7%）方向一致。

---

## 2. 独立复算（5 条，含 2 条基线 + Top total + tp50 + 零售池）

| spec | harness total | 我的复算 | Δpp | harness mdd | 我的 mdd | h_wp / m_wp | h_wt / m_wt |
|---|---|---|---|---|---|---|---|
| g0_amihud_N5_R30_none | 47.38% | 47.59% | **−0.20** | −18.25% | −18.25% | 0.667 / 0.667 | 0.514 / 0.514 |
| g0_amihud_N5_R30_ts12 | 46.50% | 45.15% | **+1.36** | −17.69% | −17.70% | 0.667 / 0.500 | 0.500 / 0.486 |
| g3_amihud_N4_R30_ts10（Top total） | 66.22% | 57.74% | **+8.48** | −18.22% | −18.19% | 0.500 / 0.500 | 0.519 / 0.500 |
| g6_amihud_N5_R30_tp50 | 40.31% | 40.48% | **−0.17** | −18.25% | −18.25% | 0.833 / 0.833 | 0.514 / 0.514 |
| g13_retail_amihud_N5_R30_ts12 | 39.07% | 35.58% | **+3.49** | −15.51% | −16.72% | 0.500 / 0.500 | 0.441 / 0.441 |

- **无止损 / 止盈类**（none、tp50）复算误差 **≤0.2pp**，与 §5.1 容差一致；
- **尾随止损类**（ts12、ts10）误差 1.4–**8.5pp**，且 N 越小越大（N4 ts10 最大）。
- 已核实：**选股、市值池、因子完全一致**（cap 相关系数 1.0；2026 六个调仓日 picks 逐位相同）。差异只来自 **止损后的成交路径**：我的引擎在 t+1 收盘无条件卖出（含跌停/停牌日按 ffill 价成交），harness 在跌停/停牌时**顺延到可成交日**（`stop_deferred_pct`）。
- 我的 N4 tt10 里只有 1 笔止损发生在跌停日（且是 +25.7% 的盈利止损），所以 8.5pp 不是单笔跌停造成，而是**止损路径分叉后的复利放大**（trade 数 86 vs 89）。需要 backtester 用 `b001_g3_amihud_N4_R30_ts10` 对拍定位到具体交易。
- **方向判断**：harness 的跌停顺延比我的引擎更接近真实（我的引擎在跌停价卖出是不可成交的），所以 **harness 的 +66.2% 更可信、我的 57.7% 更保守**；这不改变「该 spec 仍 mdd −18.2% / wp 50% 不达标」的结论。

---

## 3. 关键候选逐条判定

| id | total | mdd | wp | wt | 判定 | 理由 |
|---|---|---|---|---|---|---|
| b001_g3_amihud_N4_R30_ts10 | +66.2% | **−18.2%** | 50% | 51.9% | **FAIL_METRIC** | mdd、wp 双不达标；且 N=4 集中度极高 |
| b001_g1_amihud_N2_R30_none | +61.1% | **−27.0%** | 66.7% | 54.5% | **FAIL_METRIC** | N=2，mdd 灾难级 |
| b001_g3_amihud_N5_R30_ts10 | +51.6% | −16.6% | 66.7% | 48.5% | FAIL_METRIC | total/mdd/wp 三条全不达标 |
| b001_g6_amihud_N5_R30_tp50 | +40.3% | −18.2% | 83.3% | 51.4% | FAIL_METRIC | total/mdd 不达标 |
| b001_g13_retail_* | ≤39.1% | −15.5% | 50% | 44.1% | FAIL_METRIC | 零售池（剔 688）后收益崩、wp 50% |

**随机 5 个非 Tier 对照**（seed=20261105）：total `+1.0%, +0.9%, +1.8%, −11.8%, −25.6%`，全部远低于 60% → 批次不是「差一点」，而是**结构上整体不达标**。

---

## 4. Addendum 的唯一 A：PHASE_LUCK，不可采信

`badd_g1_amihud60_N5_R30_retail_none`：total +77.0%，mdd −13.87%，wp 5/6，win_trade 55.9%，**phase_pass_count = 1/5**，flags = `LOW_WIN_TRADE, PHASE_LUCK`。
→ 按 §11.2，相位 1/5 不能算 Tier A；且 win_trade 55.9% < 60%（§11.4 需明说「段胜率靠少数大赢家」）。**不能写进交付清单**。

---

## 5. Harness 口径复核（读代码 + 对拍）

| 检查项 | 结论 |
|---|---|
| 网格排到末端（§10.1） | ✅ `_grid_positions` 用 `i+1 < nD`，最后信号 2026-10-27 |
| stop_exec=next（§11.1） | ✅ t 收盘触发、t+1 收盘卖；跌停/停牌顺延并统计 |
| win_period 只计完整段 | ✅ 段长 == R 且两端都是执行日；partial 单独输出 |
| 成本主口径 0.5%/边 | ✅ fixed 模式；realistic 为次口径（含滑点 0.2%/边） |
| 逐笔/月度/2025/2024 OOS | ✅ 全部输出 |
| 无未来函数 | ✅ 因子只用 ≤t；执行 t+1；`picks_at` 在 t 日 |
| 已知限制 | ✅ 文档声明：shares 当前快照、涨跌停买入未建模、幸存者偏差 |
| 复算一致性 | ⚠️ 无止损/止盈 ≤0.2pp；**尾随止损 1.4–8.5pp**（跌停顺延语义差异，harness 更真实） |

**给 backtester 的对拍请求**：用 `b001_g3_amihud_N4_R30_ts10` 逐笔对比（我这边 trades 在 `team/audit/out/` 未单独落盘，可现场重跑），定位是哪几笔止损的 exit_date/exit_px 不同；确认 harness 的顺延逻辑后，批次数字以 harness 为准。

---

## 6. 结论

- **Batch 001：0 条三线全过，结论成立**（与我的独立审计一致：2026 是下跌市，amihud 小微盘策略的回撤在 −16%~−27%，没有一条能把 mdd 压到 −15% 内）。
- **Harness：PASS_WITH_WARNINGS** —— 口径正确、无前视；但尾随止损类的独立复算偏差超 0.5pp 容差（1.4–8.5pp），需对拍；不影响「无 Tier A」的结论（harness 更高，我的更低，两者都远未过线）。
- Addendum 唯一的 A（retail amihud60 none）phase 1/5 → **PHASE_LUCK，不可写进交付清单**。

### 复现
```bash
.venv/bin/python team/audit/prior_check.py run --json team/audit/out/prior_run.json
# 对拍 spec: b001_g0_amihud_N5_R30_none / ts12 / g3_amihud_N4_R30_ts10 / g6_tp50 / g13_retail_ts12
```
