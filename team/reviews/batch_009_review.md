# Batch 009 审查: 新维度挑战 N4 基线 + cap 诚实性核查

- 审查对象: `team/runs/batch_009_results.csv` (62 spec, 0 error) + `team/specs/batch_009.json` + `team/runs/batch_009_trades/` (21 个逐笔文件)
- 口径: **2026-01-05 空仓起步 (fresh)**、现实费率 (佣金 0.025% 最低 5 元 + 印花 0.05% + 过户 0.001% + **滑点 0.2%/边**)、**5 万 / 100 股整手**、只做多无杠杆、t 日信号 t+1 收盘、TP t 收盘触发 t+1 收盘卖 (next)、phase 0。
- 独立实现: `team/audit/batch_009/audit_newdim.py` (禁调 `team/harness.py`, 只用 `data/pivots_long_clean.pkl` + 审计员自写 `team/audit/prior_check.py`), 产物 `team/audit/out/batch_009_audit.json` + `b009_champ/nocap/base_{trades,equity}.csv`。
- **结论先行: “新维度超越基线”主张 `FAIL_METRIC`——新维度零突破。名义冠军 cap25_exp100 (+102.07%) 与无 cap 的 e100 是同一交易序列 (md5 + 逐笔双实锤), cap 在 N4/0.25 档是 no-op; +10.84pp 全部来自敞口 1.0 vs 0.9 (batch_006 已知结论), 不得作为新维度胜利申报。同敞口 (exp0.9) 下最佳新维度 (G4 stg +77.0% / G2 +70.0% / G1 +28.1%) 全部落后基线 +91.23%。冠军作为策略本身 = 已知的收益型 e100, 维持 `PASS_WITH_WARNINGS`。**

---

## 1. cap 诚实性核查 (本轮核心)

| 文件 | md5 | fresh_total | 说明 |
|---|---|---|---|
| `b009_G3_N4_TP45_cap25_exp100.csv` | `abef41c5…` | +102.0690% | 名义冠军 |
| `b009_G3_N4_TP45_cap35_exp100.csv` | `abef41c5…` (同) | +102.0690% | 字节一致 |
| `b009_G6_N4R30TP45e100.csv` | `abef41c5…` (同) | +102.0690% | 无 cap 版, 字节一致 |
| `b009_G3_N4_TP45_cap25_exp90.csv` | `d0a4ec9f…` | +91.2305% | — |
| `b009_G6_BASELINE_N4R30TP45e09.csv` | `d0a4ec9f…` (同) | +91.2305% | 基线, 与 cap25_exp90 字节一致 |

- **harness 侧三处字节一致** (7 项指标 fresh_total/mdd/wp/wm/wt/n_trades/top3 全等 + 整文件 md5 相同): cap25/cap35 对结果是 **no-op**。且 harness `max_realized_weight` 在三者同为 **0.3334 (> cap 0.25)**, `weight_overflow_pct` 却为 0.0 —— cap 参数未实际约束仓位 (N4 等权 25% + 漂移至 33%, 0.25 档从不触发)。
- **我的引擎独立证实**: cap25 (weight_cap=0.25) vs nocap 复算序列逐笔**完全一致** (`seq_identity_mine_champ_vs_nocap=True`), 两者 fresh 同为 +102.3514%。
- **逐笔对拍** (窗口内, fresh 口径): 我的冠军 24 笔 vs harness 冠军 fresh 子集 24 笔, **(code, entry_date, exit_date) 24/24 全对, 进出价最大差 0.0000**; 股数成固定比例 (中位 0.279, 极差 0.23~0.29), 系 fresh 5 万 vs harness 连续口径约 18 万权益基数之比, 收益率口径下完全抵消 (Δ+0.28pp)。harness 文件另含 4 笔 2025-12-11 建仓、2026-01-26 了结的 carryover (连续口径暖机所致, fresh 指标已剔除, 与我的 fresh_start 一致, n=24 对齐)。
- **反证 cap 机制存在但方向错误**: cap15_exp100 (+48.17%, n_hold 6.65, 42 笔) 明显不同 —— cap 0.15 强制分散到 ~7 只, 把收益从 +102% 砍到 +48%。即: 起约束的 cap 只有伤害, 不起约束的 cap (0.25/0.35) 只是装饰。

## 2. 独立复算 (fresh 5 万 realistic 整手)

| 候选 | harness fresh | 我的复算 | Δpp | mdd (我/harness) | wp | wm | wt | Calmar* | 判定 |
|---|---|---|---|---|---|---|---|---|---|
| 冠军 **b009_G3_N4_TP45_cap25_exp100** (=e100) | +102.0690% | **+102.3514%** | **+0.28** | −11.37%/−11.38% | 5/6 (83.3%) | 7/10 | 62.5% (24/24) | **9.00** | **PASS** (策略本身; 新维度主张见 §5) |
| 无 cap **b009_G6_N4R30TP45e100** | +102.0690% | **+102.3514%** | **+0.28** | 同上 | 同上 | 同上 | 同上 | 9.00 | 与冠军逐笔一致 (no-op 佐证) |
| 基线 **b009_G6_BASELINE_N4R30TP45e09** | +91.2305% | **+91.3298%** | **+0.10** | −9.59%/−9.59% | 5/6 (83.3%) | 7/10 | 62.5% (24/24) | **9.52** | **PASS** |

*Calmar = total/|mdd|。基线复现 vs batch_006 +91.23% → **误差 0.00pp**。冠军−基线 = +10.84pp (harness) / +11.02pp (我的), 全部落在敞口差 (1.0 vs 0.9) 里, 与 batch_006 收益型/均衡型档差 (+102.35 vs +91.33) 一致。

---

## 3. 同敞口比较: 新维度有无真突破 (harness fresh 口径)

exp0.9 档 (与基线同敞口, 新维度 only, 基线/cap90 除外):

| 候选 | fresh_total | 与基线差 | mdd | wp |
|---|---|---|---|---|
| G4_N4_stg30_50_exp90 (分批止盈) | +76.98% | **−14.25pp** | −9.59% | 83.3% |
| G4_N4_stg20_35_exp90 | +70.24% | −21.0pp | −10.22% | 83.3% |
| G2_oversold_N6_TP45_exp90 (最佳选股器) | +70.04% | −21.2pp | −9.68% | 66.7% |
| G2_oversold_N4_TP45_exp90 | +57.95% | −33.3pp | −18.90% (破线) | 66.7% |
| G1 最佳 (指数择时 bond/cash, 4 条并列) | +28.11%/+27.36% | −63pp | −6.4% | 83.3%/33.3% |
| 其余 G2 (liq_rev/lowvol/size/turnover/neutral…) | +0%~+11% | −80pp 以上 | — | ≤66.7% |

exp1.0 档 (与 e100 同敞口): G5_N4_TP50_vt25 **+91.03%** (输 e100 **11.0pp**, 且 TP 不同); G4_N4_stg30_50_exp100 +89.74% (输 12.3pp)。

→ **同敞口下没有任何新维度达到基线**: G1 择时把组合变成 “8 笔低波债券化产品” (+28%, n_trades=8, 达标但无意义); G2 选股器全灭 (最高 +70%, 且 oversold N4 mdd 破线); G4 分批止盈最接近但仍差 14pp; G5 vol-target 在更高敞口下仍输基线。**新维度零突破, FAIL_METRIC。**

## 4. 八项逐项 (冠军 = cap25_exp100 实即 e100; 基线 e09)

| # | 项 | 冠军 | 基线 |
|---|---|---|---|
| 1 | 独立复算 (≤0.5pp) | **PASS** (Δ+0.28pp; 24/24 骨架全对 + md5 实锤 cap no-op) | **PASS** (Δ+0.10pp) |
| 2 | 成本 0.8%/边 | **PASS** (+87.79%/−12.42%/wp83.3%, 仍 Tier A; 费用 14.9% 本金) | **PASS** (+77.13%/−10.49%/wp83.3%) |
| 3 | phase 五档 | **PASS** (51.72/99.38/**102.35**/87.55/76.93; −5/0/+10 三档达标; −10 仅 +51.7%) | **PASS** (−5/0/+10 三档达标, 见 batch_008) |
| 4 | 2025 OOS | **PASS** (+139.54%/−10.84%/wp100%/7段/wt68.75%/32笔; harness total_2025 +137.73%/wp100% 一致) | **PASS** (+121.07%/wp100%) |
| 5 | 剔 Top3 | **CONCENTRATION_RISK** (+38.50%, 保留 **37.6%**, 与 006 收益型 37.6% 完全一致——身份佐证) | CONCENTRATION_RISK (保留 35.1%, 已知) |
| 6 | 前视 +1 日 | **PASS** (+96.06%, Δ−6.3pp, wp 83.3% 不变) | **PASS** (+84.98%) |
| 7 | Wilson/bootstrap | 描述: wp 下界 **43.6%** / wt 下界 **42.7%** / boot p5 **+38.95%** (P(负) 0.3%) | 描述: wp 43.6% / wt 42.7% / boot p5 +36.74% |
| 8 | 整手可买性 | **PASS** (skipped_lot 0, stale 1/1, 无涨跌停阻塞, 费用 2474=4.9% 本金 ≈ harness 4.93%) | **PASS** (skipped 0, 费用 4.3%) |

冠军 Top3 = 603580/603838/603261 (61.7%, top1 25.6%), 与 batch_006 收益型同一批票 —— 第三处身份佐证。

**最终判定**:
- **“batch_009 新维度超越 N4 TP45 e0.9 基线” → `FAIL_METRIC`**: (a) 名义冠军是 no-op cap 包装的已知 e100, md5 + 逐笔双实锤, cap 对 N4 (等权 25%) 在 0.25/0.35 档不起约束 (且 realized weight 33.3% > cap 却 overflow 0, 参数未生效); (b) +10.84pp 全部来自敞口 1.0 vs 0.9, 为 batch_006 已知档差; (c) 同敞口下最佳新维度差基线 14pp 起 (G4 stg +77.0%, G2 +70.0%, G1 +28.1%)。**不得把 +102.07% 作为新维度胜利申报。**
- **冠军作为策略 → `PASS_WITH_WARNINGS`** (= batch_006 收益型 N4_TP45_exp100: Top3 61.9% / wt Wilson 下界 42.7% / 2024 尾部 +35.5%/-33.8% 引 batch_006 §10, 本轮 ex-Top3 保留 37.6% 与 006 一字不差)。
- **基线 → 复算 `PASS`, 维持 `PASS_WITH_WARNINGS`**。
- 副产品: cap15 证明“硬分散伤收益” (+102%→+48%); G1 指数择时在 2026 把组合降成 8 笔现金类 (+28%/−6.4%), 属择时误伤范例, 不得反向申报为“稳健型胜利”。

---

## 5. 复现

```bash
cd /Users/joker/coding/ashare-trade
.venv/bin/python team/audit/batch_009/audit_newdim.py --out team/audit/out/batch_009_audit.json
# 读数: team/audit/out/batch_009_audit.json (champ/nocap/base + :cost08/:phase/:oos2025/:exTop3/:lag1 + bootstrap + md5 + seq_identity_*)
# 明细: team/audit/out/b009_champ_trades.csv (=nocap 序列), team/runs/batch_009_trades/b009_G3_N4_TP45_cap25_exp100.csv
md5 team/runs/batch_009_trades/b009_G3_N4_TP45_cap25_exp100.csv team/runs/batch_009_trades/b009_G6_N4R30TP45e100.csv  # abef41c5… 一致
md5 team/runs/batch_009_trades/b009_G3_N4_TP45_cap25_exp90.csv team/runs/batch_009_trades/b009_G6_BASELINE_N4R30TP45e09.csv  # d0a4ec9f… 一致
```

证据文件: `team/runs/batch_009_results.csv` (冠军 +102.0690%/−11.3786%/5-6/7-10/62.5%/24笔/top3 61.89%/费用4.93%; 基线 +91.2305%/−9.5911%/5-6/7-10/62.5%/24笔/top3 62.22%) / `team/audit/out/batch_009_audit.json` (我的: 冠军 +102.3514% Δ+0.28pp / 基线 +91.3298% Δ+0.10pp, 八项全量) / `team/runs/batch_009_trades/` (md5 实锤) / `team/specs/batch_009.json` (62 spec)。
