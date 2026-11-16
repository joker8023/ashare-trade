# M07 K1–K7 总账独立复核台账（batch_022_m07ledger）

- 复核人：audit 子 agent（agent-13，只读重算，未改主流程）
- 对象：`BEAT_M07_SUMMARY.md` §1 表格（K1–K7逐格）＋ §2/§3 关键断言
- 口径：M07 = `results/r30_bt/M07_final.json`（total 1863.27，mdd −27.05，1m −4.09 / 3m 17.28 / 6m 39.00 / 1y 164.05 / 2y 1474.08 / 3y 1677.53）；beat = 六窗严格 `>`；win_all = beat_all && mdd_better
- 重算命令（.venv python，仓库根）：
  ```
  .venv/bin/python -c "import json; [print(k, len(json.load(open(f'results/r30_bt/sweep_beat_m07_k{k}.json')))) for k in range(1,8)]"
  # nbeat/beat_all 独立重算（逐行对照 M07 六窗严格大于口径）＋最强行数值核对，见本复核过程脚本记录
  ```

## §1 表头（120 行、113 独立新配、零重名、beat_all=0）

| 断言 | 重算值 | 结论 |
|---|---|---|
| 总行数 120 | 30+9+29+18+20+8+6 = 120 | PASS |
| 独立新配 113（排除 tag==base_M07） | 29+8+28+17+19+7+5 = 113 | PASS |
| 零重名（113 新配 tag 去重） | unique 113，无跨文件/文件内重复 | PASS |
| beat_all=0（全 120 行独立重算，与文件声明 0 mismatch） | 重算 beat_all=True 计 0，文件声明一致 | PASS |
| 每轮 base_M07 行逐字复现 | K1–K7 base 22 字段逐字一致，且与 M07_final 六窗/total/mdd 偏差 0.00 | PASS |

## §1 表格逐格

| 轮 | 行数/新配 | beat_all | 最高nbeat | 最强行 | 逐格结论 |
|---|---|---|---|---|---|
| K1 | 30/29 PASS | 0 PASS（重算 0） | 4 PASS | k25_cut78（4/6, mdd −25.35）数字 PASS，**选择偏差 FAIL**：同为 nbeat=4 的 k05_by05（total 2022.84 > k25 的 1908.74，diffs −0.02/−0.04/+0.23/+0.32/+5.36/+144.47）未被提及；文档按 mdd 更浅选 k25，但未声明并列与 tie-break 规则 | **PARTIAL（数字对、行不全）** |
| K2 | 9/8 PASS | 0 PASS | 4 PASS | g_by05_cut78_bx15（4/6, mdd −22.87, total 2084.73）三数与文件一致 PASS；并列 4 共 7 行（a/b/c/d/e/f/g），g 为其中 total 最高，选 g 合理 | PASS（建议备注 7 行并列） |
| K3 | 29/28 PASS | 0 PASS | 5 PASS（全域唯一 ≥5） | g_bf07（5/6，仅 1m 差 −0.01pp, mdd −24.28, total 2128.41）三数一致 PASS（−4.10 vs −4.09 = −0.01pp；mdd/total 逐值一致） | PASS |
| K4 | 18/17 PASS | 0 PASS | 2 PASS（仅 r_A15B30） | r_A15B30（2/6, mdd −29.73）一致 PASS；total 772.91（落后 −1090.36pp，长窗崩数量级） | PASS |
| K5 | 20/19 PASS | 0 PASS | 4 PASS | nobrake_gbf07（4/6, mdd −28.40）一致 PASS（−28.4 文件值一致）；并列 4 另有 nobrake_M07（total 2182.60 < 2243.52），选 total 高者合理 | PASS（建议备注 2 行并列） |
| K6 | 8/7 PASS | 0 PASS | 2 PASS（仅 cut75_both） | cut75_both（2/6，3y 差 −49.35pp）PASS（1628.18−1677.53 = −49.35pp；1m −4.09 打平、3m −0.02pp 均失败严格大于） | PASS |
| K7 | 6/5 PASS | 0 PASS | 4 PASS | g_bf080（4/6, total 2177.90）行内数字 PASS，但**选择与 batch_021 审计矛盾 FAIL**：同为 nbeat=4 的 g_bf085 total 2182.70 更高，batch_021 认定的“最强”是 g_bf085（total +319.43pp）；文档写 g_bf080（total 2177.90）且 §2“bf 轴 0.7 见顶”按 nbeat 口径成立（序列 1/4/3/5/4/4/4，峰值 bf0.7=5），但 K7 行内 total 峰值实为 bf0.85 | **FAIL（最强行选择）** |

- K1 并列明细：k05_by05 n=4（mdd −27.05 与 M07 持平、total 2022.84）、k25_cut78 n=4（mdd −25.35、total 1908.74）。文档“最强行”未声明 tie-break（total？mdd？），K1 按 mdd 选低 total 者、K5/K2 按 total 选高者、K7 选中 total 者，三轮规则不一致。
- K7 并列明细：g_bf075（4/6, 2141.87, −24.77）、g_bf080（4/6, 2177.90, −26.08）、g_bf085（4/6, 2182.70, −26.72）；按 total 最高应为 g_bf085，与 batch_021（agent-12）“最强的 g_bf085”一致，与本文档“g_bf080”矛盾。

## §2 关键断言核对

| §2 断言 | 复核报告支撑 | 结论 |
|---|---|---|
| 短窗墙 1m/3m 缺口 −0.01~−0.06pp，滑点加倍同成本基线仍差 −0.01pp，区间不重叠/舍入无关 | batch_017 §3a（1m 区间不重叠论证）＋证伪项 1/5（g_bf07 同成本基线 5/6、1m −0.01pp 纹丝不动，total +239.24pp） | PASS |
| 短窗+回撤 vs 长窗互斥：去刹车三败换四胜 | batch_019 证伪项 2（nobrake 两行均为 4/6 且 mdd 更深 −32.10/−28.40）撞墙确认；“三败换四胜”字面表述在 batch_019 未逐字出现，按 4/6+mdd更深理解通过 | PASS（表述建议澄清） |
| B 腿直跑赢 1m/3m 但长窗崩 −1000pp 级 | batch_019 证伪项 3（legB_only total 567.08，落后 −1296.19pp，仅赢 1m +0.05/3m +0.64） | PASS |
| phase 强变量：偏离 ph0 腿 total 腰斩（spread 1253~1601pp）；等权袖 nbeat 全 0 | batch_018 证伪项 2（p0_p15 组腿 spread 1253~1601pp）＋ K4 独立重算 11 袖 nbeat 全 0 | PASS |
| 引擎因子二值：非 amihud_60 即 amihud20（后者全窗被支配） | batch_020 证伪项 4（both_amihud 0/6、−689.24pp；Bleg 0/6；Aleg 仅 1m +0.01 的 1/6） | PASS |
| bf 依赖 cut/bx/by 联动（m07_bf07≠g_bf07） | K7 重算：m07_bf07 n=1/total 1917.97 vs g_bf07 n=5/total 2128.41；batch_021 §0/§3 | PASS |
| bf 轴 0.7 见顶、0.65 有坑 | batch_021 证伪项 4（bf-nbeat 序列 1/4/3/5/4/4/4：0.7=5 峰值，0.65=3 凹坑；total 随 bf 单调 +363pp 但 mdd 同步加深 4.73pp）；batch_017 T2（bf0.8 WARNING 关闭） | PASS（见顶指 nbeat，非 total；K7 total 峰值实为 bf0.85=2182.70，文档未澄清口径） |

## §3 认错线核对

| 认错线 | 文档断言 | 报告支撑 | 结论 |
|---|---|---|---|
| T1 相位运气 | 触发（g_bf07 与 K2-g 跨相位 total 五连败） | batch_017 证伪项 2（g_bf07 ph5/7/10/14/15 差 −67.62/−45.56/−86.95/−125.80/−82.02；K2-g 同样五连败） | PASS |
| T2 邻域过拟合 | 未触发（最高 5；bf 轴峰值局部峰；bf0.8 WARNING 关闭） | batch_017 证伪项 3（bf 轴单调递增、bf0.8 未测残留风险转 WARNING）＋ batch_021（序列 1/4/3/5/4/4/4，峰值仍 bf0.7=5，WARNING 关闭） | PASS |
| T3 集中赌博 | 未触发（g_bf07 ex-top3 +194.18pp 超 M07 去顶后） | batch_017 证伪项 4（g_bf07 extop3 1545.93 vs M07 1351.75，+194.18pp；top3_share 26.3%） | PASS |
| T4 成本鲁棒 | 未触发（滑点加倍同成本基线仍 5/6 且 total +239.24pp） | batch_017 证伪项 5（g_bf07@0.004 total 1834.96 vs M07@0.004 total 1595.72，+239.24pp，5/6，mdd 浅 2.91pp） | PASS |
| T5 择时运气 | 未触发（最强行 switch 与 M07 逐字一致） | batch_017 证伪项 6（g_bf07 ph0 switch_log 与 M07 逐字一致，3 次） | PASS |
| T6 前视/口径 | 未触发（独立复算多轮 0 偏差） | batch_016/017/018/019/020/021 六轮复算均为 0 偏差（本次重算 nbeat/beat_all 与文件声明 0 mismatch 交叉印证） | PASS |
| 报告映射 | batch_016（M07 vs J04）/017（K3）/018（K4）/019（K5）/020_m07k6（K6）/021_m07k7（K7） | 六个目录与评审文件均存在且内容对应（本台账 §2/§3 逐项引用） | PASS |

## 总结论

- §1 表头与 K2–K6 各格：**PASS**；K1 最强行：**PARTIAL**（k05_by05 并列 n=4 且 total 更高未列）；K7 最强行：**FAIL**（应为 g_bf085/total 2182.70，与 batch_021 矛盾，文档写 g_bf080/total 2177.90）。
- §2/§3：**全部 PASS**（有报告支撑；两处表述建议澄清：“三败换四胜”字面、“bf 见顶”指 nbeat 而非 total）。
- §4 裁决“累计 113 新配 beat_all=0、win_all=0，T1 已触发：不提供策略”：数字与 T1 状态均复核通过，裁决逻辑成立。
