# M07/K12 复核：新切换机制解耦试点（batch_035_m07k12）

**一句话结论：K12 全灭——新切换机制 x 原生 amihud_60 腿 6 配全无 beat_all、最高 nbeat=2（仅 +0.01/+0.05pp 尘埃差），mdd 反恶化至 -34.48；结合 K11 交叉归因：切换机制无独立 alpha。**

- 基线：results/r30_bt/M07_final.json —— M07 total 1863.27 / mdd -27.05 / switches 3；六窗 1m -4.09 / 3m 17.28 / 6m 39.00 / 1y 164.05 / 2y 1474.08 / 3y 1677.53。
- K12 产出：results/r30_bt/sweep_beat_m07_k12.json（7 行 = base 校准行 + 6 新配，research/sweep_beat_m07_k12.py，机制复用 research/family_k11.py build_ns_k11，口径断言 RUN_START=2023-01-03 / EVAL_END=2026-11-12 / WINDOWS 一致）。
- 校准行核验：K12 内 base_M07 total 1863.27 / mdd -27.05 / 六窗与 M07_final 逐值一致。

## 1. K12 verdict（6 新配全灭）

| tag | hyst | total (dM07) | mdd | sw | nbeat | beat_all | 仅胜窗 |
| k12_h02_B / k12_h02_both | 0.02 | 1422.05 (-441.22) | -34.48 | 1 | 2 | false | 1m +0.01pp，1y +0.05pp |
| k12_h05_B / k12_h05_both | 0.05 | 1422.05 (-441.22) | -34.48 | 1 | 2 | false | 同上行全同 |
| k12_h10_B / k12_h10_both | 0.10 | 1354.29 (-508.98) | -34.48 | 0 | 0 | false | 无 |

- B/both 标签行全同：K12 两腿均为原生 M07 MaxInputs，legs 仅为与 K11 对称的矩阵标签（脚本 L17、L52、L70 明示），实质去重后为 3 个独立配置。
- 最好的两个 nbeat=2 全部来自四舍五入尘埃（1m -4.08 vs -4.09；1y 164.10 vs 164.05），其余四窗全负、3y 落后 -212pp；mdd 全员 -34.48（比 M07 深 7.43pp），mdd_better 全 false。
- 行为注记：h02/h05 全程锁 A 腿、仅在 2026-09-08 切一次 B；h10 switches=0 全程 A。原生影子 spread 极少穿透 hysteresis 带加刹车冻结，新机制在原生腿上约退化为几乎不切换。

## 2. T 线触发判定：未触发，不跑全套

任务规则：仅对 beat_all 或 nbeat_m07>=4 候选跑全套 T 线（前视重点加跨相位、ex-top3、滑点加倍、独立复算）。K12 最高 nbeat=2、无 beat_all → T 线套件不触发。前视一票 FAIL 约束：本次无候选进入 T 线，故无 FAIL 项；第 3 节为机制代码的前视静态核查加已实跑的截断抽查（证据备用）。

## 3. 前视核查（PASS，无 FAIL）

- hysteresis 比较输入：research/switch_engine.py L93-99 _rs 用 searchsorted(dates[sig_i], side=right)-1 取影子曲线小于等于信号日 t 的最后一根 bar，ra/rb 均为 t 及以前 trailing-60 回报；K11 补丁（family_k11.py L95-101）只改比较式（rb-ra>=_HYST）与刹车冻结门，不新增任何数据源 → 比较只用 t 及以前影子值。
- 刹车冻结门：_brake 由信号日 t 盘前持仓 mark-to-market 更新、执行 t+1，与 M07 刹车同信息集；freeze 只读状态不引入未来。
- 截断抽查实跑（复核人执行）：.venv/bin/python research/sweep_beat_m07_k11.py --check-trailing → TRUNC a60_a5 2024-06-03/2025-09-01 OK；SPOT amihud5 OK；trailing_check: ALL OK。K12 复用同一 build_ns_k11 代码路径，结论平移。

## 4. 机制 x 选股器交叉归因（K11 联合）

2x2（legs=B 口径，total / mdd / switches / nbeat）：

|  | 旧机制 ra>=rb | 新机制 hyst+刹车冻结 |
| 原生 amihud_60 | M07: 1863.27 / -27.05 / 3 / 基线 | K12 h02: 1422.05 / -34.48 / 1 / 2尘埃；h10: 1354.29 / -34.48 / 0 / 0 |
| a60_a5 新选股器 | K10 a60_a5_B: 1437.72 / -35.55 / 11 / 0 | K11 h05_B: 1680.98 / -29.74 / 5 / 0；h02_B: 1412.30 / -36.60 / 7 / 0；h10_B: 1488.83 / -29.74 / 4 / 0 |

- 固定选股器=a60_a5，只换机制（K10→K11）：switches 11→4~7（去 whipsaw 机械有效），total 最多 +243.26pp（h05_B），mdd -35.55→-29.74，但 nbeat 恒为 0，1m 窗增量冻结在约 -1.6pp —— 短窗墙纹丝不动。
- 固定选股器=原生，只换机制（M07→K12）：total -441pp、mdd -7.43pp、nbeat<=2 尘埃 —— 机制独立作用为负。
- 固定新机制，换选股器（K12 h05→K11 h05_B）：total 1422.05→1680.98（+258.93pp）——正向移动全部来自选股器维度，而非机制。
- K9 佐证：旧机制 x amihud_5 both 曾拿到 nbeat=3（新选股器行中唯一>=3），进一步说明窗口 alpha 藏在选股器x腿身份里。

**归因一句话：切换机制无独立 alpha——两种选股器下新机制均未翻转任何一个窗口（K12 最高 nbeat=2 且为尘埃差、mdd 反恶化；K11 去 whipsaw 成功但 nbeat 恒 0），窗口胜负由选股器 x 腿身份决定，机制只有减少切换次数的交互效应。**

## 5. 文件索引

- 本报告：team/audit/batch_035_m07k12/audit_m07k12_review.md
- K12 产出：results/r30_bt/sweep_beat_m07_k12.json；生产脚本：research/sweep_beat_m07_k12.py；机制：research/family_k11.py
- 对照：results/r30_bt/sweep_beat_m07_k11.json / results/r30_bt/sweep_beat_m07_k10.json / results/r30_bt/sweep_beat_m07_k9.json / results/r30_bt/M07_final.json
- 约束遵守：本目录内仅新增本报告 1 个文件。