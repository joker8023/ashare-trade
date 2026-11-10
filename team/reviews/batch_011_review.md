# Batch 011 审查: G2 TP×staged 未超基线 + 三轮总判定 (008/009/010/011, 166 spec)

- 审查对象: `team/runs/batch_011_results.csv` (13 spec, 0 error) + `team/specs/batch_011.json` + `team/runs/batch_011_trades/`
- 口径: **2026-01-05 空仓起步 (fresh)**、现实费率 (佣金 0.025% 最低 5 元 + 印花 0.05% + 过户 0.001% + **滑点 0.2%/边**)、**5 万 / 100 股整手**、只做多无杠杆、t 日信号 t+1 收盘、TP/分批止盈 t 收盘触发 t+1 收盘卖 (next)、phase 0。
- 独立实现: `team/audit/batch_011/audit_011.py` + 自写分批止盈引擎 `team/audit/batch_011/staged_engine.py` (禁调 `team/harness.py`; staged 语义由 harness 逐笔反推: 每级每仓触发一次、次日按**当时股数×fraction**卖出、staged 存在时 TP 互斥——harness stg 文件 111 笔中 take_profit 出现 0 次 vs 同策略无 staged 基线 13 次)。产物 `team/audit/out/batch_011_audit.json` + `b011_champ/base_trades/equity.csv`。
- **结论先行: 本轮最佳新维度 `b011_G2_N4_R30_TP45_stg30_50_exp100` (+89.74%) 未超基线 (+91.23%), 差 −1.49pp (大于复算误差, 真实差距) → `FAIL_METRIC`。staged 是横向移动 (wt+7.5pp、exTop3 保留 60% 更优; total−1.5pp、mdd−1.8pp、top3 更差), 非突破。三轮总判定: 166 spec 中所有超基线条目均可归因 (敞口 / cap no-op / R20 噪声), objectively 无人用新维度在同敞口下超越基线。**

---

## 1. 独立复算 (fresh 5 万 realistic 整手)

| 候选 | harness fresh | 我的复算 | Δpp | mdd (我/harness) | wp | wm | wt | Calmar* | 判定 |
|---|---|---|---|---|---|---|---|---|---|
| 冠军 **b011_G2_N4_TP45_stg30_50_exp100** (N4/R30/TP45+stg/e100) | +89.7430% | **+89.3518%** | **−0.39** | −11.37%/−11.38% | 5/6 (83.3%) | 7/10 | 73.5% (34) / 70.0% (30) | **7.86** | **PASS** (未超基线 −1.5pp, 见 §3) |
| 基线 **b011_G5_BASELINE_N4R30TP45e09** | +91.2305% | **+91.3298%** | **+0.10** | −9.59%/−9.59% | 5/6 (83.3%) | 7/10 | 62.5% (24/24) | **9.52** | **PASS** |

*Calmar = total/|mdd|。基线复现 vs batch_006 +91.23% → **误差 0.00pp** (四连中)。

- staged 语义验证通过: 我的引擎 (staged 存在时 TP 互斥) 复算 Δ−0.39pp ≤ 0.5pp, 笔数 34 vs 30 (差 4 笔部分止盈切分, 同 R20 案量级); 我的冠军逐笔理由 = 24 rebalance + 10 staged_take, 与 harness (staged_take 23 笔含暖机、take_profit 0 笔) 结构一致。语义声明见 `staged_engine.py` 头注。
- 同轮佐证复算 (plain 引擎): size005_20 (+86.69%) Δ+0.33pp ✓; R30-noTP exp90 (+81.22%) Δ+0.18pp ✓ —— 双双未超基线, 与 harness 一致。
- sleeve 组 (3-sleeve/5-sleeve) 我的引擎不支持多相位多 sleeve (INVALID_SPEC 范围, 如实声明不硬算); 代以交叉验证: sleeve5_N4_exp90 +34.91% vs batch_006 5-sleeve harness +33.91% / 我的 +35.09% —— 跨批一致, sleeve 实现稳定; sleeve 本轮最佳 (+71.43%, exp100) 仍输单腿 e100 (+102.07%) 30pp, 2026 牛市分散即伤害。

## 2. 八项逐项 (冠军 staged e100 vs 基线 e90)

| # | 项 | 冠军 | 基线 |
|---|---|---|---|
| 1 | 独立复算 (≤0.5pp) | **PASS** (Δ−0.39pp; staged 语义经逐笔验证) | **PASS** (Δ+0.10pp) |
| 2 | 成本 0.8%/边 | +76.38%/−12.54%/wp83.3% ≈ 基线 +76.23% — 高成本下打平, 仍 Tier A | **PASS** (+77.13%→+76.23%, 仍 Tier A) |
| 3 | phase 五档 | 49.70/96.51/**89.35**/89.88/77.80 (3 档 Tier; −5 档 +96.5 为峰) vs 基线 46.75/87.21/**91.33**/73.33/65.89 — **横向**: 冠军赢 −10/−5/+5/+10 四档、仅输锚点 phase 0; 中位数冠军更高, 但注册比较只认 phase 0 | **PASS** (3 档达标) |
| 4 | 2025 OOS | **PASS** (+144.81%/−11.11%/wp100%/7段/wt75.6%/41笔; harness 待对: CSV total_2025 见 JSON) — 2025 反超基线 +23pp, 年份机制不同, 不救 2026 结论 | **PASS** (+121.07%/wp100%) |
| 5 | 剔 Top3 | +53.72%, 保留 **60.1%** (603580/603838/605003) — staged 真优点: 比基线 (35.1%) 轻得多 | 保留 35.1% (已知集中) |
| 6 | 前视近似 (phase+1) | +71.05% (Δ−18pp; 含网格位移, 非纯前视, 读数保守) — 无崩塌但时序敏感 | **PASS** (真 sig_lag: +84.98%, Δ−6.3pp) |
| 7 | Wilson/bootstrap | 描述: wp 下界 **43.6%** / wt 下界 **56.9%** (staged 按笔胜率可证性最佳的一次) / boot p5 +29.6%; **spread P(冠军>基线)=46.7%** (p50 −0.55%) | 描述: wp 43.6% / wt 42.7% / boot p5 +36.7% |
| 8 | 整手可买性 | **PASS** (skipped_lot 0, stale 1/1, 10 次 staged 部分卖出均为非整手零股、与 harness 一致, 费用 2419=4.8% ≈ harness 4.79%) | **PASS** (skipped 0, 费用 4.3%) |

**冠军定性**: staged 把 TP45 的“一刀清”换成“+30% 先兑现 1/3”: 按笔胜率 62.5%→**73.5%** (+11pp, 四轮最佳)、exTop3 保留 35%→**60%**、phase 中位数更高 —— 但代价是 total −1.5pp、mdd −1.8pp、top3 64→67%。**用胜率/分散换收益的横向移动, 注册锚点 (phase 0) 输, 不得申报突破** (Tier A 数字合格但被基线支配 −1.5pp, 记 PASS_WITH_CAVEAT, 采用否决)。

## 3. 三轮总判定: 166 spec 中所有超 +91.23% 条目归因 (008/009/010/011: 54+62+37+13)

| # | 条目 | fresh | 归因 (已审计证据) |
|---|---|---|---|
| 1 | b008_G3_N4R30TP45e100 (008) | +102.07% | **敞口 1.0 vs 0.9** (+10.8pp 档差, batch_006 收益型已知; 本轮 R7 最佳仅 +69.3% → R7 方向证伪, batch_008 FAIL_METRIC) |
| 2-4 | b009 cap25/cap35_exp100 + b009_G6 e100 (009) | +102.07% (三者字节一致) | **cap no-op**: md5 + 逐笔双实锤与 e100 同一序列; +10.8pp 全系敞口; 新维度零突破 (G1 ≤28%/G2 ≤70%/G4 ≤77%/G5 ≤91.03%), batch_009 FAIL_METRIC |
| 5 | b010_G6_N4R30TP45e100 (010) | +102.07% | 同条目 1 (敞口差) |
| 6 | b010_G1_N4_R20_TPnone_exp100 (010) | +102.33% | **敞口+R20 噪声复合**: vs e100 仅 +0.26pp (同 010 R20 噪声量级); TP 谱单档尖峰 (batch_010 §2) |
| 7 | b010_G2_N5_R40_TPnone_exp100 (010) | +98.93% | exp1.0 但**输 e100 3.1pp** —— 高敞口仍输 plain e100, 反证无突破 |
| 8 | b010_G5_N4_R20_stg30_50_exp100 (010) | +92.93% | exp1.0, 输 e100 **9.1pp**; staged+R20 组合仍输 plain (010 §4) |
| 9 | b010_G1_N4_R20_TPnone_exp90 (010) | +91.72% | **R20 噪声**: +0.49pp < 复算/惯例噪声 (±0.8pp); TP 谱孤立尖峰; phase 对打 2-3; spread P(>0)=52.3% (batch_010 FAIL_METRIC) |
| 10 | b011_G5_N4R30TP45e100 (011) | +102.07% | 同条目 1 (敞口差; 本轮最佳新维度仅 +89.74%) |
| — | 4 条 BASELINE + b009 cap25/35_exp90 (009) | = +91.2305% | **标尺本身** (cap_exp90 = 基线字节一致, no-op 佐证) |

- 穷举确认: 程序扫描四批 CSV fresh_total > 91.23% + 1e-9, 共 16 行 = 上表 10 条策略行 + 6 条标尺行 (4 基线 + 2 cap90), **无遗漏** (`team/audit/out/batch_011_audit.json` → `tri:over_baseline`)。
- **objectively 是否有人超越基线**: 在**同敞口 (exp0.9) + 注册锚点 (phase 0)** 下, **没有** —— 最接近的三次是 R20 +0.49pp (噪声)、staged −1.49pp (横向)、G4 stg −14.3pp/G2 −21pp/G1 −63pp (完败)。所有超标尺条目一经剔除敞口差/恒等序列/噪声, 全部落回标尺之下。**新维度四轮零突破** (008 R7 / 009 全维度 / 010 R 轴+ensemble+cap / 011 缺口)。
- 副产品 (成立项): staged 按笔胜率 73.5% (四轮最高, Wilson 下界 56.9% 唯一接近可证)、exTop3 保留 60%、OOS 2025 反超 —— 建议作为**画像补充维度** (高胜率/低集中偏好资金) 而非收益突破申报; 采用顺位仍在基线之后。

**最终判定**:
- **“batch_011 新维度 (TP×staged/size/noTP/sleeve) 超越基线” → `FAIL_METRIC`**: 最佳 staged −1.49pp (真实差距, 大于复算误差)、size005_20 −4.5pp、noTP −10pp、sleeve 最佳 −19.8pp。
- 冠军 staged 作策略 → **PASS_WITH_CAVEAT** (Tier A 数字合格: +89.74%/−11.38%/wp83.3%/wm7-10/wt70%; 被基线支配, 不采用; 其 wt/分散优点如实记录)。
- 基线 → 复算 **PASS** (Δ+0.10pp), 四轮维持 batch_006 `PASS_WITH_WARNINGS` (Top3 62% / 2024 尾部 / wt 下界 42.7%)。

---

## 4. 复现

```bash
cd /Users/joker/coding/ashare-trade
.venv/bin/python team/audit/batch_011/audit_011.py --out team/audit/out/batch_011_audit.json
# 读数: team/audit/out/batch_011_audit.json (champ/base + :cost08/:phase/:oos2025/:exTop3/:lag1 + bootstrap + spread_boot + corr:size/noTP + tri:over_baseline/tri:nspec)
# 引擎: team/audit/batch_011/staged_engine.py (头注含 staged 语义与 TP 互斥声明)
# 明细: team/audit/out/b011_champ_trades.csv vs team/runs/batch_011_trades/b011_G2_N4_R30_TP45_stg30_50_exp100.csv
```

证据文件: `team/runs/batch_011_results.csv` (冠军 +89.7430%/−11.3786%/5-6/7-10/70.0%/30笔/top3 67.41%/费用4.79%; 基线 +91.2305%/−9.5911%/5-6/7-10/62.5%/24笔/top3 62.22%) / `team/audit/out/batch_011_audit.json` (我的: 冠军 +89.3518% Δ−0.39pp / 基线 +91.3298% Δ+0.10pp, 八项+spread+corr+tri 全量) / `team/specs/batch_011.json` (13 spec) / 前三轮 reviews (`team/reviews/batch_008_review.md`, `batch_009_review.md`, `batch_010_review.md`)。
