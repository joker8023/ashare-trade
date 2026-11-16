# M07/K15 剩余交叉复核（batch_041_m07k15）

## 0. 一句话结论

FAIL：K15 全灭（3 个新叠加 beat_all=0，最好 nbeat_m07=1 且仅赢 3y）。双校准 16 个值偏差全 0.00（门限 0.01 内通过），全文件 flag 独立重算 5/5 一致，最好行独立复算零偏差，triple 按规则正确跳过 —— 但无任何候选触及 T 线门限（beat_all 或 nbeat_m07 至少 4），全套 T 线按既有 moot 规则不再执行。结合 K14（最好 nbeat=3，三重叠加无增益），峰值基座与自适应机制的交叉空间至此彻底穷尽，纸面轨道维持 M07。

- 基线：results/r30_bt/M07_final.json —— total 1863.27 / mdd -27.05 / 六窗 1m -4.09 / 3m 17.28 / 6m 39.00 / 1y 164.05 / 2y 1474.08 / 3y 1677.53。
- K15 对象：results/r30_bt/sweep_beat_m07_k15.json（5 行 = 2 校准 + 3 新；生产者 research/sweep_beat_m07_k15.py 328 行，复用 batch_037 已审计的 research/adaptive_k13.py，lock_mode=None 全程）。
- 机器记录：team/audit/batch_041_m07k15/part_041_k15verify.json（双校准表、逐行 flag 重算、触发集判定）与 work_041_k15verify.py（复核人独立执行脚本）。

## 1. 双校准（门限 0.01，两行皆 PASS 到 0.00）

- base_M07 vs M07_final：total/mdd/六窗偏差 0.00（1863.27 / -27.05 / -4.09 / 17.28 / 39.00 / 164.05 / 1474.08 / 1677.53）。生产者自带同口径断言（total/mdd 0.01）加 RUN_START/EVAL_END/WINDOWS 断言。
- base_gbf07 vs K3 g_bf07 行（results/r30_bt/sweep_beat_m07_k3.json）：8 值偏差 0.00（2128.41 / -24.28 / -4.10 / 17.29 / 39.30 / 164.90 / 1487.61 / 1875.48，nbeat=5）。峰值复现逐字一致（by05+cut78both+bx15+bf0.7）。

## 2. K15 判定（峰值基座上 3 个剩余新叠加，全灭）

- k15_dynT10_B（峰值 x dynN T=0.10，B 腿单腿）：total 2161.12（比峰值 +32.71，全文件最高），mdd -23.65（比峰值浅 0.63，全文件最浅），trades 187，nbeat 1（仅赢 3y 1906.53 vs M07 1677.53；输 1m -4.49 vs -4.09、3m 16.07 vs 17.28、6m 37.86 vs 39.00、1y 161.83 vs 164.05、2y 1459.54 vs 1474.08）。把峰值原有的 5 个窗胜压到只剩 3y 一个。
- k15_dynT05_B（峰值 x dynN T=0.05，B 腿单腿）：total 1867.47（比峰值 -260.94，比 M07 仅 +4.20），mdd -26.50，nbeat 0（六窗全输，最接近的是 6m 36.16 vs 39.00）。
- k15_dly_enterB（峰值 x confirm-delay enterB，延迟 A->B）：total 2112.54（比峰值 -15.87），mdd -24.75，trades 194，nbeat 1（仅赢 3y 1811.47；1m -4.13 vs -4.09 以 0.04pp 落败，其余四窗皆输）。
- beat_all=True 计数 = 0（全部 5 行）。文件 flag 与独立重算 nbeat/beat_all/mdd_better：5/5 一致。
- 行为：两 dyn 行 switch_log 与峰值逐项一致（06-21 B / 08-15 A / 09-08 B）—— N 只改变仓位不改变切换时点，与 K13 在 M07 基座、K14 在峰值上的表现一致。enterB 行首尾两切各推迟约一格（06-21 -> 07-21，09-08 -> 10-14），与 K13 enterB 在 M07 基座上的延迟签名一致；延迟如设计生效（dly_pending=2/dly_confirmed=2/dly_cancelled=0），但只平移不增加窗口。
- triple 行：按脚本规则正确缺席。复核人实测 .venv/bin/python research/sweep_beat_m07_k15.py --triple 输出 skip note（core 最大 nbeat=1，低于开门线 4），exit 0，未写文件。

## 3. T 线触发集与执行

- 门限（beat_all 或 nbeat 至少 4）对 3 个新叠加：触发集为空（最好成绩 1）。全套 T 线腿（跨相位、ex-top3、滑点加倍、独立复算）检验的是晋级候选的稳健性，对非候选 moot —— 与 batch_023/033/035/037/039 同规则，本轮不执行。
- 文件内唯一 nbeat 至少 4 的行是 base_gbf07（nbeat=5，校准行，非叠加候选）。其完整 4 腿 T 线已在 batch_037 执行（跨相位 FAIL、绝对滑点 FAIL、1m 硬缺口）—— 不重跑，结论沿用。
- 前视抽查：生产者全文无 shift(- 回看、无新增 searchsorted/iloc 未来索引（3 处 iloc 命中皆为尾窗收益数学，t 及之前取值；机制码为 batch_037 已审计 adaptive_k13.py 逐字复用）。本轮实际执行的全是已审计锚点路径；文件内自带但本轮未执行的 triple 构造器（build_ns_k15_triple）同样只组合已审计锚点（margin 按信号日更新、confirm-delay 门控），未引入新的时间信息源。前视一票：PASS，无否决。
- 独立复算抽查（复核人执行）：.venv/bin/python research/sweep_beat_m07_k15.py --only k15_dynT10_B -> total 2161.12 / mdd -23.65 / 六窗与文件逐项一致（偏差 0.0），nbeat=1 确认。文件峰值行与最好行皆为真实计算，非手填。

## 4. 穷尽结论（峰值 x 自适应）

一句话：拮抗且穷尽 —— K14 已证双腿 dynN、exitB 延迟、三重叠加在峰值上把 5/6 压到至多 3/6；K15 补上剩余三块拼图（B 腿单腿 dynN T10/T05、enterB 延迟），最好仅 1/6，且 dynT10_B 用 total 新高（+32.71）换掉峰值 4 个既有窗口胜；两轮 triple 开门线（需 core 出现 nbeat 至少 4）从未达到，enterB 三重组合按规则未生成 —— 在峰值腿已处局部最优时，时点与仓位扰动只减窗口不加正交增益，该方向无可采样的剩余正交维度。

覆盖对照：K14（both 腿 dynN T10/T05、exitB 延迟、T10xB 三重）+ K15（B 腿 dynN T10/T05、enterB 延迟；enterB 三重因门限未开而跳过）= 峰值 x 自适应交叉全部可测组合中 6 个实测全灭、1 个按既有门限规则跳过。声明：峰值 x 自适应交叉彻底穷尽。

## 5. 裁决

- FAIL：K15 0/3（beat_all=0，最好 nbeat=1，win_all=0）。全域 beat_all 保持 0。任何 K15 行与任何三重变体不得上线。
- T1（beat_all）未触发。T2（nbeat 至少 4）无新叠加触发。纸面轨道维持 M07。
- 交付物（仅本目录）：本报告 + work_041_k15verify.py + part_041_k15verify.json。合规：未新增本目录外任何文件；未触碰引擎、口径、结果文件；K15 产物（并行回测于 16:51 落盘）仅被读取并以 --only 方式独立复算，未覆写。