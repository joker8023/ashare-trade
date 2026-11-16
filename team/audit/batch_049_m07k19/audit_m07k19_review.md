# M07-K19 长持有期腿试点复核（batch_049）

- 复核对象：R37 K19 长持有期试点 —— 首个动腿调仓周期的 family（B 单腿改 R60/R90/R120 × 双腿同改 A60/B60、A90/B90、A120/B120，共 6 新配），T 线从严。
- 基线：`results/r30_bt/M07_final.json`（M07 total +1863.27%，mdd −27.05%，trades 184，cost 50990，switches 3：2023-06-21→B / 2024-08-15→A / 2026-09-08→B；六窗 1m −4.09 / 3m +17.28 / 6m +39.0 / 1y +164.05 / 2y +1474.08 / 3y +1677.53）。
- M07 执行口径（K19.`M07P` 与 `research/sweep_beat_m07_k18.py` 一致）：5 万 / 现实费率（`cost_one_way=None`）/ slip=0.002 / lot=100 / `stop_exec="next"` / `legacy_grid=False` / `full_liquidate=True` / MB 排除 / RUN_START=2023-01-03 / EVAL_END=2026-11-12 / `prior_check.run_strategy` + `sweep_beat_h1_v4.build_ns(0.18,0.08,0.6)` 开关引擎。
- 时序注记：本复核启动时 `research/sweep_beat_m07_k19.py` 尚未落盘；复核中 R37 交付实现（mtime 2026-11-16T09:44:05Z），`results/r30_bt/sweep_beat_m07_k19.json` 截至落盘仍缺失 —— 结果行以下均为本复核独立实跑（`work_049_k19verify.py` → `part_049_k19.json`），未动 `results/`。
- 一句话结论：**FAIL（K19 六新配 beat_all=0、最高 nbeat=1，六窗全超 M07 且回撤更浅的策略仍不存在；实现本身前视检查通过、基线校准零偏差）。**

## 1. R 网格前视审计 —— PASS（抽查，代码级）

- 网格构造（`team/audit/prior_check.py:100-108`）：`range(300+phase, n-1, R)`，信号日索引 `sig_i`，执行 `exec_map: ei=sig_i+1`（`prior_check.py:196-201`；开关引擎 `switch_engine.py:60-68` 双网格 `sig_a/sig_b` 分取 A/B 腿各自 rebal，执行同样 t+1）。R 仅改变采样步长，信号→执行时序关系不变。
- 信号快照（`prior_check.py:74-96` `Inputs.picks`）：选股全部取 `signal_day` 当日 `.loc[t]` —— amihud60 = trailing 60 日 rolling 均值（含 t，不含 t 之后）、adv20 trailing、seasoned 用 `c.shift(250)`（纯过去）、cap 用静态股本快照（与 M07 同口径，非 K19 新增面）。执行价取 t+1 日 ffill 收盘。
- 开关 RS 比较（`switch_engine.py:95-99` `_rs`）：`eq.iloc[j]/eq.iloc[j-60]-1`，trailing 60 日，有 `j<rs_lookback→None` 守卫；切换评估仅 A 网格信号日（`:171`）。R 增大只减少评估频次，不引入未来数据。
- K19 新增面仅为 `a_rebal/b_rebal` 取值（20/30→60/90/120），腿输入类 `MaxInputs`、刹车参数、RS 回看均逐字 M07。**长周期前视一票项：通过。**

## 2. 双校准行独立复算 —— base_M07 零偏差（K19 无 gbf07 校准行，仅此一行）

- 命令：`team/audit/batch_049_m07k19/work_049_k19verify.py`（import K19 模块复用 `single_row`，产物只落本目录），后台运行 exit 0。
- `part_049_k19.json: checks.base_calib_exact=true`：total **1863.27** / mdd **−27.05** / trades **184** / cost **50990.0** / switches **3** / 六窗 −4.09/17.28/39.00/164.05/1474.08/1677.53 / `switch_same_m07=true` —— 与 `M07_final.json` **逐项零偏差**，M07 champion 地位维持。

## 3. K19 六新配结果（本复核独立实跑，ph0）与合理性检查

| tag | R | total | mdd | trades | cost | switches | nbeat | beat_all | mdd_better |
|---|---|---|---|---|---|---|---|---|---|
| r_B60_A20 | A20/B60 | 1318.79 | −28.15 | 179 | 42876 | 6 | 0 | false | false |
| r_B90_A20 | A20/B90 | 1480.55 | −25.72 | 181 | 47376 | 4 | 0 | false | true |
| r_B120_A20 | A20/B120 | 1384.81 | −27.34 | 172 | 44326 | 4 | 0 | false | false |
| r_B60_A60 | A60/B60 | 284.64 | −31.87 | 64 | 5860 | 6 | 0 | false | false |
| r_B90_A90 | A90/B90 | 186.01 | −26.70 | 46 | 3542 | 8 | **1**（仅 1m −1.63>−4.09） | false | true |
| r_B120_A120 | A120/B120 | 123.41 | −26.63 | 33 | 2491 | 4 | 0 | false | true |

- 换手/费用随 R 下降（自洽）：B 单腿臂 trades 184→179/181/172、cost 50990→42876/47376/44326，总体下降（B90 处 179→181 / 42876→47376 小幅回升，系开关轨迹改变所致：switches 6 vs 4，两臂所处模式时长不同，非单调是合理的）；双腿臂 trades **64→46→33**、cost **5860→3542→2491** 严格单调递减。
- switches 非单调（6/4/4 与 6/8/4）自洽：switches 是 RS 触发的模式切换次数（A 网格评估），不是调仓次数；R 改变同时改变影子曲线形态与评估采样，切换次数无单调性要求。`switch_same_m07` 六行全 false（预期内：影子一变 RS 轨迹必变）。
- 双腿长 R total 坍塌（284/186/123%）与 top3_share 飙升（43.3/58.9/57.0%，extop3 仅 184.79/76.99/63.13）互为印证：调仓过疏→持仓陈旧→收益集中于少数旧仓，与 J04 系对 A 腿频率敏感一致，无前视红旗。
- K1–K18 前提复核（附带）：18 个 sweep 共 **174 新配 beat_all=0**（22 校准行），与 inventory_k36（totalrows 196 / distinct 174 / beat 0）一致；nbeat≥4 行 23 条（k1/k2/k3/k5/k7/k8，最高 g_bf07 nbeat=5）均为往期 batch 已覆盖、beat_all=false，不在本 batch T 线范围。

## 4. 候选 T 线 —— 触发集为空，按 moot 规则跳过

- K19 触发集（beat_all 或 nbeat_m07≥4）：**空**（最高 r_B90_A90 nbeat=1，仅 1m 窗 −1.63>−4.09，其余五窗全败；beat_all 全 false；win_all 全 false）。
- 故跨相位 / ex-top3 / 滑点加倍 / 独立复算全套 T 线 moot，不跑。K19 关闭条件：若 R37 后续以其它相位/参数重启长 R，需按 T 线从严（长 R 相位敏感更大，参考 batch_007 R60 教训）重审。

## 5. 判决

- **Verdict: FAIL（目标未达成：六窗全超 M07 且回撤更浅的策略在 K1–K19 共 180 新配中仍不存在；K19 实现审计 PASS ≠ 目标 PASS）。**
- Paper-track 保持 M07；K19 不上线。

*复核子 agent agent-54；工作目录 /Users/joker/coding/ashare-trade；本目录新增文件：audit_m07k19_review.md（本报告）、work_049_k19verify.py、part_049_k19.json、tline_stdout.log。其它目录零新增。*
