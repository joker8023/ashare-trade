# M07-K20 评估频率试点复核（batch_051）

- 复核对象：R39 K20 开关评估频率试点（逐日评估 vs 网格评估）——首个动评估频率的 family，T 线从严。
- 基线：`results/r30_bt/M07_final.json`（M07 total +1863.27%，mdd −27.05%，trades 184，cost 50990，switches 3：2023-06-21→B / 2024-08-15→A / 2026-09-08→B；六窗 1m −4.09 / 3m +17.28 / 6m +39.00 / 1y +164.05 / 2y +1474.08 / 3y +1677.53；top3_share 26.4 / extop3_total 1351.75）。
- M07 执行口径（`research/run_m07_final.py`，K19 sweep 逐字复述一致）：5 万 / 现实费率（`cost_one_way=None`，`prior_check.py:148-153/234-237`）/ slip=0.002 / lot=100 / `stop_exec="next"` / `legacy_grid=False` / `full_liquidate=True` / MB 排除 / RUN_START=2023-01-03 / EVAL_END=2026-11-12 / 开关引擎 `sweep_beat_h1_v4.build_ns(0.18,0.08,0.6)`（逐日 trailing peak/trough 刹车，`sweep_beat_h1_v4.py:43`）/ RS60 trailing 比较（`eq.iloc[j]/eq.iloc[j-60]-1`，仅 A 网格信号日评估）/ 网格执行 `ei=sig_i+1` 即 t+1（`prior_check.py:196-201`）。
- 一句话结论：**FAIL（R39 交付物缺失：`research/evalfreq_k20.py` 与 `results/r30_bt/sweep_beat_m07_k20.json` 均不存在，逐行审计与 T 线无从执行；按“评估前视一票 FAIL”约束直接判 FAIL）。**

## 0. 输入核验 —— FAIL（阻塞项）

- `research/evalfreq_k20.py`：**不存在**（`ls` 报 No such file；`glob **/evalfreq*` 空；`grep -ril k20|evalfreq|eval_freq` 在 research/results/team 下仅命中 k1 文件与 batch_022 ledger 等误报，无 K20 实现痕迹）。
- `results/r30_bt/sweep_beat_m07_k20.json`：**不存在**（同上；`ls results/r30_bt/ | grep -i k20` 空；该目录最新 sweep 止于 k19，inventory 止于 k38）。
- 后果：任务 1（逐行审计）与任务 2（候选 T 线）**均无审计对象**，以下 §1 为“应审清单”（R39 交付后重审用），§2 触发集按 moot 规则记空。

## 1. 逐行审计 —— 未执行（文件缺失），R39 交付后必须逐项核查

K20 是首个动评估频率的 family（此前 K 系列只动过腿 R/刹车/RS 参数与持仓结构，未动“何时评估切换”），以下五项有一项不满足即一票 FAIL，R39 实现必须在文件头以口径声明逐字对照 M07：

1. 逐日比较只用 t 及以前影子值：逐日评估的 RS 比较必须形如 `shadow.eq.loc[:t]` trailing（M07 网格版为 `eq.iloc[j]/eq.iloc[j-60]-1` 且 `j<60→None` 守卫）；**严禁**在 t 日评估中使用 t 日收盘后才能确定的影子净值（如用 `eq.loc[t]` 当日值驱动 t 日翻转即前视——M07 网格版天然免疫，因信号→执行隔 t+1；逐日版若“当日评估当日翻转”则必须证明评估快照早于执行价时点）。
2. 翻转执行是否为 t+1 收盘：M07 口径 `exec_map: ei=sig_i+1`（`prior_check.py:196-201`）；逐日版每次模式翻转的首次调仓必须同样落在信号日下一交易日收盘（ffill），不得用信号日当日收盘执行。
3. 刹车动作时点与 M07 口径一致性：M07 刹车是逐日 trailing（peak 更新用当日组合市值，ON/OFF 打标当日，`sweep_beat_h1_v4.py:43-50`）；K20 若把“开关逐日化”与“刹车逐日化”混在一起，必须声明调仓日口径 vs 逐日口径的对照（刹车 ON/OFF 日与仓位缩放生效日的映射），并给出与 M07 `brake_log`（2023-06-26 ON … 2024-09-13 OFF）的对照行。
4. 费用/整手一致：`cost_one_way=None` 现实费率 + slip=0.002 + lot=100 + 5 万本金（`prior_check.py:148-237`）；逐日评估不得顺带改动费率/滑点/整手/止损执行（`stop_exec="next"`）。
5. 网格评估对照臂：K20 sweep 必须保留“网格评估”对照臂（同一参数、仅评估频率不同），否则逐日 vs 网格的差异无法归因；且 EVAL 窗/WINDOWS/RUN_START/EVAL_END 与 M07 同口径。

## 2. K1–K19 前提与 K20 T 线触发集

- K1–K19 前提（inventory_k38）：totalrows 203 / distinct **180** / beat **0** —— “180 新配 beat_all=0”成立。各文件 max nbeat：k1:4 / k2:4 / k3:5 / k5:4 / k7:4 / k8:4，其余 ≤3（k19:1）。
- K20 触发集（beat_all 或 nbeat_m07≥4）：**空（moot）**—— K20 sweep 文件不存在，无候选可评估；故跨相位 / ex-top3 / 滑点加倍 / 独立复算全套 T 线按 moot 规则跳过，不跑。
- 历史 nbeat≥4 行（k1/k2/k3/k5/k7/k8，最高 g_bf07 nbeat=5，beat_all 均为 false）属往期 batch 已覆盖范围，不在本 batch T 线范围（同 batch_049 §3 处理）。

## 3. 开关时点/次数变化核查 —— 未执行（无 K20 结果）

- M07 参照：switches 3（2023-06-21→B / 2024-08-15→A / 2026-09-08→B），brakes 3 对（2023-06-26 ON … 2024-09-13 OFF）。
- R39 交付后：必须逐候选给出 switch_log / brake_log 与 M07 的 diff（逐日评估预期 switches 只增不减；若某候选 switches 反而减少，需解释影子形态变化），并检查开关时点是否出现“信号日非交易日对齐漂移”。

## 4. 判决

- **Verdict: FAIL（输入缺失：无实现可审、无结果可验；评估前视一票 FAIL。六窗全超 M07 且回撤更浅的策略在 K1–K19 共 180 新配中仍不存在，K20 未能提供新证据）。**
- Paper-track 保持 M07；K20 不上线。
- 重启条件：R39 落盘 `research/evalfreq_k20.py` + `results/r30_bt/sweep_beat_m07_k20.json` 后，按 §1 五项清单重审，任一 beat_all / nbeat≥4 候选跑全套 T 线后方可改判。

*复核子 agent agent-57；工作目录 /Users/joker/coding/ashare-trade；本目录新增文件：audit_m07k20_review.md（本报告）。其它目录零新增。
## 5. 真实产出复核（R39 落盘后，2026-11-16T12:45-46Z；第0-4节时序保留）

- 落盘确认：research/evalfreq_k20.py（110 行）、research/sweep_beat_m07_k20.py（136 行）、results/r30_bt/sweep_beat_m07_k20.json（6 行 = base + 5 新）。R39 自带 base_M07 校准断言，本复核独立重验同样通过。
- 六行摘要：daily_M07 total 1963.03 / mdd -26.35 / trades 317 / cost 97391 / switches 33 / nbeat 4；daily1_M07 1625.43 / -27.28 / 245 / 54280 / 17 / nbeat 3；daily_gbf07 1795.18 / -25.27 / 285 / 88489 / 25 / nbeat 4；daily1_gbf07 1755.11 / -28.05 / 240 / 58288 / 15 / nbeat 3；daily_M07_brakeD 数值与 daily_M07 一致（tag/brake_daily/brake_log 除外）。beat_all 全 0，win_all 全 0。

### 5.1 逐行审计 —— PASS（前视一票项通过，口径声明兑现）

- 逐日比较只用 t 及以前影子值（evalfreq_k20.py 54-71 行）：daily 在 do_rebalance(i, sig_i) 内以 sig_i=_t（= 执行日_ei-1）做 _rs(shadow, sig_i)；_rs（switch_engine.py 93-99 行）取 searchsorted(dates[sig_i])-1 的 trailing 60 日比值，j小于60返回None守卫；daily1 确认项（62-70 行）用 sig_i-1 同样纯过去。影子曲线复用 M07 同口径 trailing 策略引擎。无未来函数。
- 翻转 t+1 收盘（72-76 行）：EXECMAP_ADD 对每个 _t 设 _ei=_t+1+sig_lag（sig_lag=0），setdefault 不覆盖网格映射（网格日两种映射一致）；选股用信号日 sig_day=dates[_t] 因子数据（引擎168-190行），执行价取 t+1 日 ffill 收盘。与 M07 的 ei=sig_i+1 同形。
- 刹车默认调仓日（91-94 行 + 头注释 18-20 行）：_brake_gate = brake_daily or sig_i in sig_a/sig_b；默认 False 时非网格信号日的逐日翻转不更新刹车（只继承状态做仓位缩放），与 M07 口径一致；对照臂 brakeD（brake_daily=True）已声明。base_M07 的 switch_same_m07=true 且 brake_log 与 M07 逐字一致，补丁在 grid 模式下数学恒等。
- 费用/整手（sweep_beat_m07_k20.py 53-56 行）：5 万 / cost_one_way=None / slip=0.002 / lot=100 / stop_next / legacy_grid=False / full_liquidate=True / MB / RUN_START/EVAL_END / RS60 / bx0.18by0.08bf0.6 —— 与 run_m07_final.py 逐字一致（base 校准零偏差为证）。
- 网格评估对照臂保留（base_M07 行），归因可比。第1节五项清单逐项关闭。

### 5.2 独立复算 + T 线（work_051_k20verify.py 输出 part_051_k20.json，本目录）

- 独立复算：daily_M07 / daily_gbf07 与 JSON 全部数值 + switch_log + brake_log 逐字一致（recompute_exact=true）。brakeD 路径同样确定性重现（brake_log 与 JSON brakeD 逐字一致）。
- brakeD 数值恒等机制（已实证）：两路径各 311 笔 rebalance 买入，分歧刹车窗（2024-05-20至06-20，brakeD-ON vs daily-OFF）内买入 0 笔（网格 rebalance 因 picks 未变被 skip_block 跳过）——刹车旗差异从未与真实买入重合，故净值曲线恒等。这是数值逐字一致但 brake_log 不同的合理解释，非隐藏前视。
- 跨相位（daily_M07，ph 5/10/15 vs M07 ph0）：nbeat 0/0/0，total 676.45/282.81/688.17（vs ph0 1963.03），mdd -33.51/-31.78/-27.96，switches 37/55/36 —— 相位一动 edge 全失，total 坍塌。跨相位 FAIL。
- ex-top3：daily_M07 extop3_total 1441.42（top3_share 25.5）vs M07 1351.75（26.4）——集中度相当、绝对值略高，但长窗 2y/3y 照败，不改变 beat_all=0。ex-top3 不救。
- 滑点加倍（slip 0.004）：daily_M07 total 1509.70（cost 144342，增加46951）、nbeat 0；daily_gbf07 total 1359.72、nbeat 0。高频切换对成本高度敏感。滑点 FAIL。

### 5.3 短窗全超但长窗崩机制确认

- 更早切入：首次翻转 2023-06-06转B，比 M07（2023-06-21转B）早约 11 个交易日吃到涨幅，短窗（1m/3m/6m/1y 差值 +0.56/+4.34/+5.46/+10.00）领先的来源。
- 鞭梭代价：switches 33 对 3（2024-03 单月 8 翻、2024-10/11 与 2025-08、2026-10 三簇密集翻转），trades 317 对 184，cost 97391 对 50990（+91%）；daily1 确认版把 switches 压到 17 但 total 反跌至 1625.43（确认滞后、两头挨打）。长窗 2y/3y 差值 -121.28/-92.17 即 churn + 鞭梭的累积税。
- mdd -26.35 对 -27.05 虽浅 0.70，但 beat_all=0 则 win_all=false，目标（六窗全超且回撤更浅）未达成。

### 5.4 判决（维持 FAIL）

- Verdict: FAIL（K20 实现审计 PASS，但目标未达成：最好行 daily_M07 nbeat=4（达 T 线门槛，已跑全套 T 线）但 beat_all=0，长窗崩 + 跨相位归零 + 滑点加倍归零；daily_gbf07 同 nbeat=4、total 更低，亦败）。
- Paper-track 保持 M07；K20（含 brakeD 对照）不 provision、不上线。

*第5节复核子 agent agent-57；新增本目录文件：work_051_k20verify.py、part_051_k20.json、tline_stderr.log（空）。其它目录零新增。*
*
