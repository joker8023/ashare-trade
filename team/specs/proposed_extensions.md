# proposed_extensions — strategist 对 harness 的扩展请求

> 优先级：**P0 = 本批 spec 已经用到 / 不实现会算错**；**P1 = 相位与集中度控制需要**；
> **P2 = 结构性方案（等 batch_001 结果再决定是否值得实现）**。
> 全部只写在这里，不改 `team/harness.py`（那是 backtester 的写区）。

---

## P0 — 影响已交付 spec 的正确性

### P0-1 `exclude_star` 语义与「零售池」的精确含义
Lead 情报：旧 N5/R30 的 2026 选股里 35 个中有 16 个是 688（5 万账户买不到）。
**实测确认：本数据集 `data/pivots_long_clean.pkl` 没有北交所股票（0 只 8xx/4xx）**，
所以 `exclude_bj=true/false` 是空操作；「零售池」= `exclude_star=true`（剔 688/689，606 只，占 universe 12%）。

- `badd_*_retail_*` = `exclude_star=true, exclude_bj=true`
- `badd_*_full_*` = `exclude_star=false, exclude_bj=true`（把 688 放回来，复刻旧口径）

请在 `results.csv` 里输出 `n_hold_star`（当期持仓里 688/689 的只数）——
这是证明「零售池 vs 全池」差异来自科创板的直接证据，auditor 会查。

### P0-2 止损执行口径：**次日收盘**（Lead 已裁决，覆盖 PROTOCOL §1 的「当日收盘」）
PROTOCOL §1 原文是「当日收盘后判断，当日收盘执行」。Lead 的新情报证明这条会虚高：
同一 spec（N5/R30/ts12）**same-close 止损 +62.8%，次日收盘止损 +56.5%**（差 6.3pp）。
因此本批全部 spec 按 **t 日收盘触发 → t+1 收盘卖出** 执行。请：

1. 实现 `stop_exec` 全局口径 = `next_close`（默认）；
2. 对 G0 的 2 条基线与 G2 的 N10 平台（建议 6~8 条）**额外输出一列 `total_same_close`**，
   用于量化两个口径差多少——这正是 PROTOCOL §7 数字矛盾的根源之一；
3. 结果表里注明止损口径。

### P0-3 A 股 T+1：建仓当日不得止损卖出
t+1 收盘买入的票，当天收盘不能再卖。止损判定必须从**建仓次日起**开始；
否则会显著高估「买入即破位」的收益（预跑里 ts08 的高估主要来自这里）。

### P0-4 停牌/跌停不可成交
止损触发日若该股跌停（`close == low` 且跌幅接近 -10%/-20%）或停牌（当日 close 缺失），
**不能假设按当日收盘卖出**：顺延到下一个可成交日收盘，并按 PROTOCOL §1 记录。
请输出 `stop_events`、`stop_deferred_pct`（顺延比例）、`stop_limit_down_pct`。

### P0-5 三个 selector 在 `engine.FACTORS` 里不存在
PROTOCOL §2.1 允许、但 `engine.py` 未实现（我的 spec 里有 4 条用到）：

| selector | 用到 | 要求的定义（只用 ≤t 数据，越大越买） |
|---|---|---|
| `liq_rev_lowvol` | 3（batch_002 / G8） | `rk(-adv20) + rk(-rev20) + rk(-vol20)` 秩和（PROTOCOL 的「A」排序版）。注意：`strict_screens.screen_A` 是**筛选链**（amihud top10% → 低波一半 → rev20 top25），不是排序版，两者不等价——若你想实现筛选链版本，请另起名 `strict_A`，并在结果里标明。 |
| `oversold` | 3（batch_002 G12 / G14 / addendum? 无） | `strict_screens.screen_C` 的排序版：先取 `rev20` 最强的 5% 作为候选，再要求 `ret5 > -3%`（企稳），最后按 amihud 排序取 N。 |
| `breakout` | 0（本批未用） | 可延后：`strict_screens.screen_B`（close/60日高 ∈ (0.97,1.0] 再按 amihud 排序）。 |

### P0-6 两个别名（语义相同，别报 missing_selector）
`low_vol → engine.f_vol20`、`turnover → engine.f_turn20`、`amihud_industry_neutral → engine.f_amihud_neutral`。

### P0-7 `dd_breaker` 的两个参数（batch_002 有 3 条）
`timing: {"type":"dd_breaker","dd_trigger":0.08,"dd_action":0.0}`：
- `dd_trigger`：策略**自身净值**从峰值回撤达到该比例时触发（0.08 = -8%）
- `dd_action`：触发后目标仓位（0.0 = 清仓到下次调仓日；0.5 = 降到半仓）
- 恢复：下一次调仓日恢复正常仓位（不做「回到前高才加仓」，那会变成择时）
若无法实现，请按 `dd_trigger=0.08, dd_action=0.0` 的默认值跑，并在 errors 里写 `DEFAULT_DD_PARAMS`。

> ⚠️ **batch_003 更新：dd_breaker 已被离线模拟证伪**，见文末 §FALSIFIED-1。`batch_002` 那 3 条照跑（当作反证），**不要再扩网格**。

---

## P1 — 相位与集中度（Lead 明确要求）

### P1-1 `rebalance_offset_days`（相位）— **这是本批第二重要的扩展**
Lead 实测相位极敏感：同一 amihud_60 N5 R30 零售池，
2011 锚点 +80.4%/-14.1%/5-6，**2024-01-02 锚点只有 +44.2%/-19.1%/3-6**；5 个相位里 N5 只有 1 个过、N8 有 2 个过。

请支持 top-level 可选字段 `"rebalance_offset_days": int`（默认 0）：
- 语义：把调仓网格整体平移该交易日数（+5 后移、-5 前移），仍然从 `warmup_start` 起算；
- 已备好 `team/specs/batch_001_phase_probe.json`（6 条：amihud_60 N5/N8 × offset {-5,0,+5}）；
- **请在 `results.csv` 输出 `anchor_first_date`**（2026 窗口内第一个调仓日），
  否则审计无法核对「同相位」是否真的同相位。

若短期不实现：请把该文件跳过并在 errors.csv 写 `NEED_rebalance_offset_days`，
**不要**把它混进批量结果（会造成 id 重复）。

### P1-2 `max_per_industry`（行业上限）
`selector.params: {"max_per_industry": 2}`：同一行业最多取 2 只（其余按因子顺序跳过）。
动机：N5 的行业集中度是 2026 回撤的主要来源（预跑 `amihud_neutral` 回撤 -13.8% vs `amihud` -23.7%），
但完全中性化代价太大（收益腰斩）。**上限 2 只是「保留 alpha、砍掉板块尾部」的折中**，比完全中性更值得测。
成本低（`engine.industry_map()` 已有），建议在 batch_001 之后加。

### P1-3 `stop_grace_days`（建仓后 k 日内不触发止损）
`exit.params: {"stop_grace_days": 3}`。与 P0-3（T+1）方向一致：
建仓当周的价格噪音不该触发止损。也是把「止损」从「价格保险」改成「趋势确认」的最小改动。

---

## P2 — 结构性方案（目前**不**放进任何 spec，等 batch_001/002 结果）

### P2-1 多 sleeve 错相位（Lead 提出，我认为这是最有希望的结构性方案）
**问题**：R30 的段数只有 6，相位运气可以决定达标与否（Lead 实测：同一参数 5 相位里 1~2 个过）。
**方案**：把资金等分成 k 份（k=2/3/5），每份独立跑 R30、各自选股、各自止损，
相位错开 `floor(30/k)` 个交易日（k=5 → 每 6 天一份）。
- 预期收益 ≈ 5 个相位的**平均**（把 1 个过相位的好运和 4 个坏相位的霉运平均掉），
  而不是最好相位的收益；但**回撤会显著下降**（错峰调仓 + 单票权重变成 1/(k·N)），
  且 `win_period` 的口径会变成「每个 sleeve 各自的段」——需要定义：先合成净值再算段，还是按 sleeve 平均。**建议：先合成总净值，再按 R=30 算段胜率**（与主口径可比），并额外报告 `sleeve_dispersion`。
- 实现：`"sleeves": {"count": 5, "offset_mode": "even"}`；等价于 k 个小账本 + 资金汇总。
- 代价：代码复杂度中等（≈ 把主循环包一层），但**不引入未来函数**，也不需要新数据。
- **决策点**：若 batch_001 里 N5/N8 的 5 相位通过率 ≤2/5，则 P2-1 是唯一能救「相位依赖」的路，值得实现。

### P2-2 分批建仓（partial entry）
调仓日只建 50% 目标仓，t+2 / t+4 各补 25%（遇到止损则不再补）。
动机：R30 的 t+1 一次性收盘执行是单日价格运气；分批把执行价平均掉。
副作用：上涨市里略微降低收益（少赚两天的涨幅），但降低「买在阶段高点」的概率。
`"entry_schedule": [0.5, 0.25, 0.25]`。

### P2-3 半仓止损（`exit.half_on_stop`）
止损触发只卖 50%，剩余 50% 继续持有到调仓日。
动机：Lead 说旧策略 `win_trade` 只有 50-56%，全仓止损会把「暂时回撤后反弹」的票变成亏损笔；
半仓止损能同时改善 `win_trade` 与「不砍在最低点」。实现成本低，但会让 `win_trade` 定义复杂化
（一笔拆两条），需要先定义口径。

### P2-4 空仓停泊 `out_asset: "511880"`
`batch_002` 有 2 条（G10 择时臂）。PROTOCOL §2.3 允许，数据 `data/bond_511880.pkl` 已在。
若未实现，请按 cash 跑并标注。

---

## 附：请 `results.csv` 增加这些列（全部与「60% 是不是幻觉」直接相关）

| 列 | 为什么必须 |
|---|---|
| `group`（spec 里有） | 按组聚合，我按组写了假设，需要逐组验证 |
| `n_actual_holdings` | 5 万本金整手，N25 实际可能只买到 15 只 → 分散度是假的 |
| `cost_paid_pct` | R7 的费用占比必须看到数字才能关闭路线 |
| `exposure` | 止损/熔断后现金比例，直接决定收益来源是「选股」还是「空仓躲跌」 |
| `n_stop_events`, `stop_deferred_pct`, `stop_limit_down_pct` | 证明止损是「可成交的」而不是纸面收益 |
| `anchor_first_date` | 相位核对 |
| `total_same_close`（仅 6~8 条对照 spec） | 量化 same-close 止损的虚高幅度 |
| `win_trade`, `win_month`, `n_trades` | Lead 关心按笔胜率 50-56% 能否抬上去 |
| `top3_pnl_share` | PROTOCOL §5.6 单票依赖；旧结论靠 8 月 603838 之类的大赢家 |

---

# batch_003 新增（**P0，影响 57 条已交付 spec**）

## P0-8 `portfolio.exposure`（目标仓位 / 现金缓冲）— 本批唯一的旋钮
```json
"portfolio": {"exposure": 0.90, "cash_asset": "cash"}
```
**语义**：
- 每个调仓日，用 `exposure × 当前总资产` 买入目标 N 只（等权），其余留现金；
- 止损/止盈卖出后的资金仍留现金，直到下一调仓日（与 PROTOCOL §1 一致）；
- **不允许**因为持仓市值下跌而被动补仓（那不是 exposure，是杠杆）；即 exposure 是「建仓时的目标比例」，之后随市值漂移；
- 敞口列 `exposure` 你已经有了（实测 N5 是 0.985、N8 是 1.000，说明几乎满仓）——请在 batch_003 里让它反映**目标**敞口而非事后平均值，
  另加一列 `exposure_target` 便于核对；
- 与「杠杆」无关：exposure ≤ 1，现金收益 0。用户的约束是「只做多、不加杠杆、不做空」，现金缓冲完全合规，
  但报告里必须写明「平均资金使用率 X%」，否则用户会以为 60% 是满仓赚的。

**为什么这是核心旋钮（数据）**：N5 无止损 phase 0 的日净值线性缩放实测——
`1.00 → +73.3%/-13.9%`、`0.95 → +68.9%/-13.2%`、`0.90 → +64.6%/-12.6%`、`0.85 → +60.4%/-11.9%`、`0.80 → +56.2%/-11.2%`。
即「收益和回撤近似同比例缩放」→ 在 60%/15% 这条线上，敞口是最可靠的一个自由度。

## P0-9 `portfolio.sleeves`（多 sleeve 错相位）— 1 条 spec 依赖
```json
"portfolio": {"exposure": 0.90, "cash_asset": "cash",
              "sleeves": {"count": 3, "offsets": [-8, 0, 8], "alloc": "equal"}}
```
**语义**：资金等分 `count` 份，第 i 份用调仓网格整体平移 `offsets[i]` 个交易日后独立运行（独立选股、独立止盈、
独立现金），合成净值 = 各份净值的算术平均（每份起始资金 1/count）。
`offsets` 为空时 = 均匀分摊 `floor(R/count)`。

**必须按这个口径报告（否则结论不可比）**：
1. 合成净值（三份均值）的 `total / ann / mdd / win_period / win_month / win_trade`；
2. `win_period` 用**合成净值**按 R=30 算完整段（与主口径一致），**不要**按 sleeve 平均段胜率；
3. 额外一列 `sleeve_dispersion` = 各 sleeve `total` 的 max−min，以及各自 `mdd/win_period`（证明不是靠某一个 sleeve 撑起来的）；
4. `win_trade` 合并所有 sleeve 的个股交易；
5. **禁止**把 sleeves 拆成独立策略分别调参或分别报告成「多个达标策略」。

**为什么值得实现**：R30 的 mdd 是相位函数（Lead 实测 5 相位 −13.9% ~ −17.5%），
而 sleeve 把 3 个相位的净值平均，回撤不同时到达 → 合成 mdd 预期落在 −11%~−14%，收益 ≈ 相位均值（≈80%）。
这是**唯一一个既不牺牲收益又能压回撤**的结构性方案（见 §FALSIFIED-1/2 为什么止损和熔断都做不到）。

---

# FALSIFIED — 已用数据证伪，**不要再为其实现代码或扩网格**

## FALSIFIED-1 组合层回撤熔断（dd_breaker）在 amihud_60 上是灾难
用 N5/R30 零售池 phase 0 的逐日净值做规则模拟（触发后次日降仓，下一调仓日或回撤恢复到 trigger/2 时复位）：

| trigger | cut | 复位方式 | total | mdd |
|---|---|---|---|---|
| 无熔断 | — | — | **+73.3%** | **−13.9%** |
| 0.06 | 清仓 | 下一调仓日 | +33.4% | −8.5% |
| 0.08 | 清仓 | 下一调仓日 | +5.6% | −11.6% |
| 0.08 | 半仓 | 恢复 trigger/2 | +43.9% | −12.3% |
| 0.10 | 清仓 | 下一调仓日 | +3.0% | −11.8% |
| 0.12 | 半仓 | 下一调仓日 | +71.1% | −13.9% |
| 0.15 | 任意 | 任意 | +73.3% | −13.9%（从不触发） |

**原因**：该策略在 2026 有 4 次约 −12% 的回撤（3 月底、4 月初、6 月中、7 月底各一次），
其中 3 次在 2~3 周内完全恢复；熔断每次都在低点清仓、错过反弹。**只有 10 月底那次是不恢复的**，
但熔断无法区分这两种回撤。→ `batch_002` 的 3 条照跑作反证，`batch_003` 不再包含。

## FALSIFIED-2 个股止损（trailing / fixed）在 amihud_60 上是收益杀手、且几乎不降回撤
| spec | total | mdd | win_period |
|---|---|---|---|
| N5 无止损 | **+77.0%** | −13.87% | 5/6 |
| N5 ts10 | +33.3% | −13.8% | 4/6 |
| N5 ts12 | +30.9% | −14.3% | 3/6 |
| N5 ts15 | +36.0% | −13.9% | 3/6 |
| N5 fs10 | +56.1% | −14.8% | 4/6 |
| N5 fs12 | +60.6% | −13.9% | 4/6 |
| N8 ts12 | +34.1% | −12.4% | 2/6 |

**原因**：Amendment（next-close 执行）+ 该因子的收益来自少数大赢家（top3 = 76% P&L），
止损正好砍在赢家的必经回撤上，而它想防的「组合级下跌」是个股同涨同跌、止损救不了。
→ **止损相关 spec 全部关闭**（`batch_001`/`addendum` 已跑完的保留作证据，后续不再新增）。
（`batch_002` 里还有 60 余条止损 spec，建议**直接跳过**，只跑它的 G10/G8/G11 非止损部分，省时间且减少多重检验分母。）

## FALSIFIED-3 R15 臂在 amihud_60 上整体失效
`addendum` A3 四条：R15 的 mdd 全部 −20.8% ~ −25.1%，total +7.9% ~ +15.1%，win_period 38%~54%。
→ 短周期在高换手成本（15.6% 本金）+ 该因子下不可行。`batch_002` 里 R15 的补集 spec 建议跳过。

## FALSIFIED-4 行业中性（amihud60_neutral）在该池上是负收益
`addendum` A5 两条：N5 −4.8%/−20.0%，N8 ts12 −3.5%/−15.7%。
→ 行业中性把 alpha 一起中性掉了。**不要**再和「主板 + 现金缓冲」叠加。

---

# batch_005（Round 2A）新增 — 三个结构旋钮（P0）

## P0-10 `selector.max_weight` + `selector.rank_fill`
```json
"selector": {"type": "amihud_60", "n": 6, "max_weight": 0.15, "rank_fill": true}
```
**语义**：
- 单票**目标权重**上限 `max_weight`（0.05~1.0）。等权时 `w = exposure/n`；若 `w > max_weight` 则截到 `max_weight`。
- `rank_fill=true`：截出来的资金按 amihud_60 排序的 **N+1、N+2…** 依次补足，每只同样受 `max_weight` 约束，
  直到资金用完（留 `exposure` 内的现金尾差）或候选耗尽。
- `rank_fill=false`：不补足，剩余资金留现金（= 纯降杠杆，用于归因，见 `b005_A7_N6_TP50_cap10_nofill`）。
- 调仓日按目标权重建仓；**持有期内不再平衡**（除非 TP/止损触发）——避免引入日频再平衡的隐性收益。
- **必须输出**：`n_effective_holdings`（实际建仓只数）、`max_realized_weight`（建仓后最大单票权重）、
  `weight_overflow_pct`（被截掉的资金占比）、`n_fill_names`（补位只数）。
- 与整手兼容：按目标权重算目标金额 → 取整手 → 残余现金；不要求精确到小数股。

## P0-11 `exit.staged_take`（分批止盈）
```json
"exit": {"staged_take": [{"trigger": 0.30, "fraction": 0.3333}, {"trigger": 0.50, "fraction": 0.3333}]}
```
**语义**：
- `trigger` = 相对**成本价**的涨幅阈值；`fraction` = 触发时卖出**当前剩余持仓**的比例（不是初始仓位）。
- t 日收盘触发 → **t+1 收盘卖出**（与 `stop_exec=next` 一致）；涨跌停/停牌顺延到下一可成交日。
- 多次触发按 `trigger` 升序依次判定；同日触发多个阈值时**按顺序全部执行**（例：跳空 +55% 时先卖 1/3 再卖 1/3）。
- 卖出后的资金留现金到下一调仓日（与 PROTOCOL §1 一致），**不立即补仓**。
- **与 `take_profit` 互斥**（本批 35 条已强制互斥）；若两者同时出现，`normalize_spec` 应报 `INVALID_EXIT_COMBO`。
- **必须输出**：`n_staged_sells`、`staged_realized_pnl`、`pct_position_remaining_at_exit`。

## P0-12 `portfolio.vol_target`（目标波动，只降仓）
```json
"portfolio": {"exposure": 1.0, "cash_asset": "cash", "vol_target": 0.25}
```
**语义**：
- 用**组合自身**过去 20 个交易日的日收益标准差 × √252 作为实现波动 `vol20`。
- 调仓日（或每日，二选一但必须写清）计算 `exposure_t = min(base_exposure, vol_target / vol20)`；
  **只降不升**（不加杠杆）；信号用 t−1 及以前的数据，t 日生效。
- 建议实现为**每日重算、但只在调仓日调整仓位**（与本项目其他策略一致，避免日频再平衡产生额外收益）。
- **必须输出**：`avg_exposure`、`min_exposure`、`pct_days_below_90pct`（用于判断它是不是「靠长期低仓凑回撤」）。
- 若 `avg_exposure < 0.75`，请在结果里标 `LOW_EXPOSURE_DRAG`——那说明收益是降仓换来的，不是选股。

## 归因要求（本批特有）
`batch_005` 的每一条都请额外输出：`top3_pnl_share`、`ex_top3_total`、`n_effective_holdings`、`avg_exposure`。
验收标准是 **Top3 ≤40% 且 total ≥60% 且 mdd ≥−15% 且 wp ≥80%**，四者同时成立才算结构改善。
