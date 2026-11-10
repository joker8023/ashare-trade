# Agent Team 研究协议 — A股 2026 目标 60% / 80% / 15%

> 版本 v1.0 · 2026-11-05 · 由 Leader 制定，所有成员必须遵守
> 工作目录：`/Users/joker/coding/ashare-trade`，Python：`.venv/bin/python`

## 0. 任务与成员

用户目标：在 A 股、只做多、不加杠杆、不做空的约束下，搜索 **不同选股策略 × 不同止盈止损策略 × R7/R15/R30**
的组合，列出 **所有** 在 2026 年同时满足以下三条的策略：

| 指标 | 阈值 | 说明 |
|---|---|---|
| 2026 收益率 | ≥ 60% | **2026 自然年至今总收益**（2026-01-05 ~ 2026-11-04，基数=2025-12-31 净值）。年化值同时报告，但**不作为主判定** |
| 胜率 | ≥ 80% | 主口径 = **完整调仓段胜率**（每段组合净收益>0 的比例）。同时报告按笔、按月胜率 |
| 最大回撤 | ≤ 15% | 2026 窗口内逐日净值最大回撤 |

成员与职责：
- **Lead**：规划轮次、维护台账 `team/LEDGER.md`、裁决冲突、对用户汇报；只写 `team/LEDGER.md`、`team/ROUNDS.md`、本协议。
- **strategist**：产出策略批次 `team/specs/batch_NNN.json` + 理由；只写 `team/specs/**`。
- **backtester**：维护统一回测器 `team/harness.py`、`team/run_batch.py`，跑批次并出结果；只写 `team/harness.py`、`team/run_batch.py`、`team/runs/**`（可选 `team/lib/**`）。
- **auditor**：对抗性审查，独立复算与攻击结果；只写 `team/audit/**`、`team/reviews/**`。

任何成员不得修改他人写区；需要修改时发消息请求。不得修改仓库根目录既有文件（除 Leader 授权的只读复用）。
**结论必须可复现**：所有数字来自 `team/runs/` 的 CSV/JSON，命令、代码版本、参数齐全。

## 1. 数据与执行约定（防未来函数）

- 数据：`data/pivots_long_clean.pkl`（2010-01-04 ~ 2026-11-04，5028 只，前复权 OHLCV + amount + shares）。
  字段：`open/high/low/close/volume/amount`，`shares` 为总股本（用于市值分位）。
- 指数：`results/_cache/index_{000905,000852,000300,000985}.pkl`（`risk_control._index_series`）。
- 债券：`data/bond_511880.pkl`（货基/债券 ETF，空仓停泊用，收益按收盘价 pct_change + 年化 3%/252 兜底）。
- 基础股票池（默认，可逐 spec 覆盖）：上市≥250 交易日、`adv20 > 5e6`、当日 close 非空、总市值在截面 **5%~30% 分位**（小微盘）。
- **信号**：只用 t 日收盘及以前的数据；**执行**：t+1 日收盘价（保守口径，不许用 t+1 开盘价做当日信号）。
- **止损/止盈**：每个交易日收盘后判断（用当日收盘价与截至当日的高点/成本），当日收盘执行；不得用当日最低价假设成交在更优价位。
  若涨跌停/停牌无法成交，按停牌前收盘 ffill，不计入可成交假设；审计需检查涨跌停日交易占比。
- 调仓：每 R 个交易日一次（R=7/15/30），调仓日 t 出信号，t+1 收盘换仓；中途被止损/止盈的仓位资金留现金（或按 spec 的 out_asset 停泊），不立即补仓，等下一调仓日。
- 成本（主口径）：**单边 0.5%**（佣金+印花+过户+滑点，保守）。敏感性：0.3% / 0.8%。
  另做「现实账本」核对：佣金 0.025%（最低 5 元）+ 卖出印花 0.05% + 过户 0.001% + 滑点 0.2%/边，5 万本金、100 股整手。
- 前视检查：把所有信号整体后移 1 个交易日重跑；若收益崩塌，标记 `LOOKAHEAD_RISK`。

## 2. 搜索空间

### 2.1 选股器（selector）
必须实现为「给定 t 日截面，返回排序因子/名单」的确定性函数，只用 ≤t 数据。首批允许：
- `amihud`（Amihud 非流动性，20日，越大越买）
- `amihud_5` / `amihud_60` / `amihud_smooth`
- `low_vol`（20/60日波动，越小越买）
- `rev20` / `rev5`（反转）
- `turnover`（低换手）
- `size`（小市值）
- `amount_level`（低成交额）
- 组合：`liq_rev`、`liq_lowvol`、`liq_size`、`triple`、`quad`、`liq_rev_lowvol`（A）、`breakout`（B）、`oversold`（C）
- `amihud_industry_neutral`、`amihud60_neutral`
- 过滤开关：`exclude_star`(688/689)、`exclude_bj`(4/8开头)、`exclude_chinext`(300)、价格区间、成交额下限、行业排除。
选股数 N：2/3/4/5/6/8/10/12/15/20/25。

### 2.2 离场规则（exit）
- `none`：持有到下一调仓日。
- `trailing_stop`：从持仓期收盘最高点回撤 s 卖出（s=6%~20%）。
- `fixed_stop`：从成本价回撤 s 卖出。
- `take_profit`：从成本价上涨 p 卖出（p=10%~50%）。
- `trailing_take`：从持仓期最高浮盈回吐 g 卖出。
- `max_hold`：持有超过 h 日强制卖出。
- 组合规则可叠加（如 trailing_stop 12% + take_profit 30%）。
- 只允许「先止损后止盈」的确定性优先级；同一日同时触发按止损处理（保守）。

### 2.3 择时/停泊（timing，可选）
- `none`；`index_ma`（000905/000852/000300，MA10/15/20/30，t 日信号 t+1 生效；空仓停现金或 511880）。
- `dd_breaker`（组合自身回撤触发降仓/清仓）。
- 主矩阵先不加择时；择时作为第二轮增强项。

### 2.4 调仓周期
R ∈ {7, 15, 30}。R7 必须单独报告换手/费用占比（历史结论：R7 费用吃掉 10-20% 本金）。

## 3. 指标定义（harness 必须逐项输出）

窗口 = 2026-01-05 ~ 2026-11-04，基数 = 2025-12-31 收盘净值（策略从 2024 年起预热/持仓可延续）。
- `total_2026`：期末/基数-1。
- `ann_2026`：`(1+total)^(252/n_days)-1`，`n_days` = 窗口交易日数（201）。
- `mdd_2026`：窗口内逐日净值最大回撤（≤0）。
- `win_period`：完整调仓段（段长 ≥ 0.8R 且已结束）净收益>0 的占比；同时输出 `n_periods`、每段收益。
- `win_trade`：所有已平仓个股头寸（含止损/调仓卖出）净收益>0 的占比；输出 `n_trades`。
- `win_month`：2026 日历年月度净值收益>0 的月份占比（首月基数=2025-12-31）。
- 其他：`vol`、`sharpe`、`calmar`、`avg_win`、`avg_loss`、`profit_factor`、`turnover`、`cost_paid_pct`、`exposure`、`max_single_name_pnl_share`、`top3_pnl_share`。
- 稳健性窗口：2025 全年、2025H2、2024 全年（同参数，不重新调参）。

## 4. 判定分层

| 层级 | 条件 | 用途 |
|---|---|---|
| **Tier A** | total_2026≥60% 且 mdd≤15% 且 win_period≥80% 且 auditor=PASS | 用户要的「符合条件」 |
| Tier A-ann | ann_2026≥60% 且 mdd≤15% 且 win_period≥80% 且 PASS | 年化口径的放宽版，单独列表，不混入 Tier A |
| Tier B | total_2026≥60% 且 mdd≤15%，胜率未达标 | 接近项，标注差多少 |
| Tier C | 三项中满足两项 | 仅作研究参考 |

**不许**把不同窗口/口径拼在一起冒充达标。每行必须写明窗口与胜率口径。

## 5. 对抗性审查清单（auditor 必做）

对每个 Tier A/A-ann/B 候选：
1. **独立复算**：不调用 `team/harness.py`，从原始 pkl 重新实现关键路径，结果误差 ≤0.5pp；否则 REJECT。
2. **前视**：信号整体 +1 日重跑；报告收益变化。
3. **成本压力**：0.8% 单边；仍须 Tier B 以上，否则标注 fragile。
4. **参数邻域**：N±1、R±2、止损±2pp 的 9 宫格；不允许「孤立尖峰」（邻域中位收益 < 候选 50% 即 OVERFIT_RISK）。
5. **OOS**：2025 全年同参数；要求 2025 total > 0 且 win_period ≥ 60%，否则 OVERFIT_RISK（目标虽是 2026，但 2026 只有 10 个月）。
6. **单票依赖**：剔除 P&L 贡献 Top3 股票后重跑；收益保留 <50% 或回撤恶化 >50% 则 CONCENTRATION_RISK。
7. **胜率口径攻击**：检查是否通过缩短亏损段、剔除亏损段、只算盈利笔等方式抬高胜率；按笔/按月必须同时报告。
8. **样本量与多重检验**：记录本轮尝试 spec 数；对 top 候选做 bootstrap（日收益 1000 次重采样）给出 5% 分位；提示 data-snooping。
9. **数据完整性**：停牌/涨跌停/缺失价 ffill 的处理；幸存者偏差无法修复，须在结论中声明。
10. **可交易性**：5 万本金、100 股整手、最低佣金 5 元下复算；R7 换手费用是否吃掉收益。

审查结论枚举：`PASS` / `PASS_WITH_WARNINGS` / `FAIL_METRIC` / `FAIL_OVERFIT` / `FAIL_LOOKAHEAD` / `FAIL_DATA` / `INVALID_SPEC`。
每个 FAIL 必须给出可复现的证据（命令/文件/数字）。

## 6. 轮次工作流

1. Lead 发轮次 brief（写入 `team/ROUNDS.md`），strategist 产出 `batch_NNN.json`（含 60~200 个 spec，必须含基线对照）。
2. backtester 校验 schema → 跑批 → `team/runs/batch_NNN_results.csv` + `batch_NNN_summary.md`（Top 表 + 分布 + 失败原因统计）。
3. auditor 独立审查 Tier A/A-ann/B 候选 + 随机 5 个对照 → `team/reviews/batch_NNN_review.md`，逐 id 给结论。
4. Lead 汇总 `team/LEDGER.md`（只收录审计后的数字），决定下一批方向；向用户汇报本轮增量。
5. 未达标就继续下一批，直到用户叫停。每批必须带来**新维度**，不许重复已证伪的组合。

## 7. 已证伪/已知结论（不要重复烧算力）

- 动量因子在 A 股 IC 显著为负；复合因子提升 IC 但降收益。
- 个股固定止损在宽基小盘组合上普遍降夏普；但 2025-2026 小盘牛市中跟踪止损对特定 N 有效（待审计复核）。
- 止盈（+15/20/30%）在 2026 上涨市多为反作用。
- 严格选股 A/C 在 2026 单年为负；B 突破也弱。
- R7 换手费用极高（历史 10-20% 本金），除非净收益显著覆盖。
- 指数 MA 择时在 2026-11-04 为空仓信号；会大幅改变 2026 收益路径，须单独报告敞口。
- 已有结论「唯一三线全过：N5 R30 +12% 跟踪止损」**存在数字矛盾**（文档写 2026 +44.9%/年化64.9%，但 `results/signals/ledger_N5_R30_STOP0.12_TAKENone.csv` 的 2026 段算出 +62.8%/年化84.2%）。必须查清后再引用。
- 幸存者偏差未修正；数据仅含当前上市股票。

## 8. 文件与命名

```
team/
  PROTOCOL.md            # 本文件（Lead）
  LEDGER.md              # 主台账（Lead）
  ROUNDS.md              # 轮次记录（Lead）
  specs/batch_001.json   # strategist
  specs/README.md
  harness.py             # backtester
  run_batch.py           # backtester
  runs/batch_001_results.csv
  runs/batch_001_summary.md
  runs/batch_001_equity/ # 可选，仅 Tier 候选
  audit/*.py             # auditor 独立复算
  reviews/batch_001_review.md
```

spec JSON 为数组，每个元素至少包含：
```json
{
  "id": "b001_amihud_N5_R30_ts12",
  "selector": {"type": "amihud", "n": 5, "size_range": [0.05, 0.30],
               "min_adv": 5000000, "exclude_star": false, "exclude_bj": true,
               "exclude_chinext": false, "price_min": null, "price_max": null, "params": {}},
  "rebalance_days": 30,
  "exit": {"trailing_stop": 0.12, "fixed_stop": null, "take_profit": null,
           "trailing_take": null, "max_hold_days": null},
  "timing": {"type": "none", "index": null, "ma": null, "out_asset": "cash"},
  "cost": {"one_way": 0.005, "capital": 50000, "lot_size": 100},
  "window": {"warmup_start": "2024-01-01", "eval_start": "2026-01-05", "eval_end": "2026-11-04"},
  "notes": "为什么提这个组合"
}
```

## 9. 汇报纪律

- 成员之间用 `send_message`，消息含：状态、文件路径、关键数字、下一步、阻塞项。
- 对用户只由 Lead 汇报；任何成员不得把未审计结果说成「达标」。
- 所有「达标」必须同时给：窗口、口径、n_periods、成本假设、审计结论。
- 禁止编造数字；跑不动就报告失败原因。

---

## 10. v1.1 修正（2026-11-05 21:40，Lead）

### 10.1 调仓网格必须排到数据末端
- 正确做法：从预热期固定相位（`dates[300]`）起，每 R 个交易日一个调仓日，**一直生成到最后一个可执行的调仓日**（`i+1 < len(dates)`），之后到 2026-11-04 的尾段是 partial。
- 旧脚本 `range(300, len(dates)-R-2, R)` 会**漏掉最后一个调仓日**：R=30 时 2026-09-07 之后本应在 2026-10-27 再调仓，旧口径却把 9-08 的持仓硬拿到 11-04。这既不是策略定义，也会系统性污染 2026 收益（可能正也可能负）。
- 凡使用旧口径（`engine.returns_series`、`ledger_10k.py`、`strict_screens.py`、`TARGET_40_10.md` 里的 2026 数字）的结果，必须用新网格重跑后才能进入台账。
- `win_period` 分母只含 **完整段**（段起点 + R 个交易日 ≤ 数据末端）；partial 尾段计入净值与 total，但不计入胜率分母，并单独输出 `last_partial_ret`。

### 10.2 两个 2026 口径都要报
- `total_2026`：连续口径，基数 = 2025-12-31 净值，允许 2025 年建仓带入 2026（标准年收益）。
- `fresh_2026`：2026-01-05 空仓起步，只在 2026 年第一个调仓日建仓，之前现金；用于检验「年初才入场」的可实施性。
- 主判定用 `total_2026`；若 `total_2026 - fresh_2026 > 10pp`，审计必须解释（通常是带入仓位/相位运气），并在结论中降级为 `PASS_WITH_WARNINGS`。

### 10.3 已知待查
- `results/signals/ledger_N5_R30_STOP0.12_TAKENone.csv` 的 2026 段（连续口径）+62.8%/-11.87%，但它的调仓网格漏了 2026-10-27，尾段被拉长；且文档写 +44.9%。两个数字都可能来自不同口径，全部作废重算。
- 2026 年等权小微盘（seasoned+ADV>500万+市值5-30%）全年仅 -1.85%，最大回撤 -24.7%；中证1000 -16.0%。任何「2026 +60%」都必须解释 alpha 来源，不能只靠 beta。

---

## 11. v1.2 修正（2026-11-05 22:05，Lead）— 执行时点与相位

### 11.1 止损/止盈执行时点（主口径改为次日收盘）
- t 日收盘观察到触发条件后，**t+1 日收盘**执行卖出（`exit.stop_exec = "next"`），这是主口径。
- `same`（当日收盘价成交）只作为乐观敏感性，必须单独标注，不得进入 Tier A 主判定。理由：收盘价在 15:00 才最终确定，同一收盘价成交隐含了「看到收盘价再以该价成交」的乐观假设；旧结论靠 `same` 多出约 6pp。
- 调仓换仓仍是 t 日收盘出信号、t+1 日收盘执行（与旧口径一致）。

### 11.2 调仓相位（phase）
- 固定相位只是任意选择：R30 在 2026 的 7 个相位点会显著改变结果。主口径固定 `phase=0`（2024-01-01 起每 R 日）；审查必须至少跑 **phase = -10/-5/0/+5/+10 个交易日** 五档，报告收益/回撤/胜率分布。
- Tier A 要求：五档中至少 3 档同时满足三项（或中位数满足），否则标 `PHASE_LUCK`，降级为 Tier B。

### 11.3 成本口径的裁决
- 主口径仍用 0.5%/边（保守，覆盖滑点）。现实费率（佣金+印花+过户+0.2%滑点）作为第二口径；两者都要报。
- 若一个策略只在现实费率下达标、0.5% 下不达标 → 标 `COST_FRAGILE`，列入 Tier B 并注明「依赖低成本假设」。
- 5 万本金、100 股整手是最终可交易性核对，不用于主矩阵（会引入整手噪声）。

### 11.4 胜率口径的裁决
- 主口径 = 完整调仓段胜率（用户历史文档一直用「持仓段胜率」，与此一致）。
- 必须同时报 `win_trade`（按笔）与 `win_month`；若 win_trade < 60%，在结论中明确写「段的胜率主要来自少数大赢家，按笔胜率仅 X%」，不得只报 80% 就宣称达标。
- R30 的 win_period 分母只有 5~7，80% 的统计噪声很大；审查必须附 bootstrap 区间，并同时看 R7/R15 的更多段。

---

## 12. v1.3 停牌/跌停成交口径（2026-11-06，Lead 裁决）

- **停牌日**（原始收盘为 NaN）按**停牌前收盘 ffill** 估值与成交，**不得视为“不可成交”而顺延**；`exit.suspend_exec` 默认 `ffill`。
- **跌停日**仍按“不可成交”顺延到下一可成交日（`defer`）；涨停买入同理不顺延（买不进）。
- 该口径是**保守近似**：真实停牌无法成交；若复牌跳空上涨，ffill 低估收益；若跳空下跌，ffill 高估。审计必须报告停牌卖出笔数/占比，并对 `ffill` vs `defer` 做敏感性。
- 本次触发案例：603580 在 2026-07-07~07-13 停牌；ffill @30.60 vs defer @33.67，R60 差 3~4pp；修复后 N5 R60 TP50 e0.9 = **65.64%**（auditor 0.00pp）。
- 所有含 TP/止损的策略必须用此口径；旧结果若用 defer 需重跑或标注。
