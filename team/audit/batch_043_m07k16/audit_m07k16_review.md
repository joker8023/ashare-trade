# M07/K16 三重组合复核（batch_043_m07k16）

## 0. 一句话结论

FAIL：K16 全灭（4 个新三重 beat_all=0，最好 nbeat_m07=2）。双校准 16 个值偏差全 0.00（门限 0.01 内通过），去重抽查确认 K14/K15 确实未做，全文件 flag 独立重算 6/6 一致，最好行独立复算零偏差，5-6 号 both-delay 门限（需 core 出现 nbeat 至少 4）按规则正确跳过 —— 但无任何候选触及 T 线门限（beat_all 或 nbeat_m07 至少 4），全套 T 线按既有 moot 规则不再执行。峰值基座上的三重叠加至多 2/6，不及任一单机制（K14 最好 3/6），拮抗结论不变，纸面轨道维持 M07。

- 基线：results/r30_bt/M07_final.json —— total 1863.27 / mdd -27.05 / 六窗 1m -4.09 / 3m 17.28 / 6m 39.00 / 1y 164.05 / 2y 1474.08 / 3y 1677.53。
- K16 对象：results/r30_bt/sweep_beat_m07_k16.json（6 行 = 2 校准 + 4 新三重；生产者 research/sweep_beat_m07_k16.py 338 行，机制码复用 batch_037 已审计的 research/adaptive_k13.py，lock_mode=None 全程；附带 sidecar results/r30_bt/sweep_beat_m07_k16.notes.json 记录 5-6 号跳过原因，生产者写入、复核人仅读取）。
- 机器记录：team/audit/batch_043_m07k16/part_043_k16verify.json（双校准表、逐行 flag 重算、触发集判定、去重抽查、门限判定、独立复算值、前视 grep 计数）。

## 1. 双校准（门限 0.01，两行皆 PASS 到 0.00）

- base_M07 vs M07_final：total/mdd/六窗偏差 0.00（1863.27 / -27.05 / -4.09 / 17.28 / 39.00 / 164.05 / 1474.08 / 1677.53）。生产者自带同口径断言（check_calib：total/mdd 0.01）加 RUN_START/EVAL_END/WINDOWS 断言。
- base_gbf07 vs K3 g_bf07 行（results/r30_bt/sweep_beat_m07_k3.json 内 g_bf07 行）：8 值偏差 0.00（2128.41 / -24.28 / -4.10 / 17.29 / 39.30 / 164.90 / 1487.61 / 1875.48，nbeat=5）。峰值复现逐字一致（by05+cut78both+bx15+bf0.7）。

## 2. 去重声明核查（抽查 1 个组合：k16_T10both_enterB）

- 抽查对象：k16_T10both_enterB = g_bf07 x dynN(T10,both) + confirm-delay enterB（legs=both(native)，thresh=0.10，direction=enterB，mechanism=dynamicN+confirmDelay）。
- K14 全量规格：k14_dynT10_both（单机制 dynN）、k14_dynT05_both（单机制）、k14_dly_exitB（单机制 exitB）、k14_triple_T10xB（both/T10/exitB 三重）—— 无一与抽查对象四元组（legs/thresh/direction/mechanism）全同，最接近的 K14 三重方向为 exitB 而非 enterB。
- K15 全量规格：k15_dynT10_B、k15_dynT05_B（皆单机制 dynN）、k15_dly_enterB（单机制 enterB）—— K15 无任何三重行（门限未开按规则跳过，复核人已在 batch_041 实测 --triple 跳过），不可能与三重抽查对象重复。
- 其余 3 个 K16 三重的差异化同样逐项可验证：k16_T10B_exitB（B 腿收窄 vs K14 三重 both）、k16_T10B_enterB（腿加方向皆不同）、k16_T05both_exitB（阈值 T05 不同）。生产者文件头 dedup 证据与 import 时断言（K14_TRIPLE_SPEC 不在 K16 集合中，脚本能正常跑即断言通过）皆成立。去重声明：属实。

## 3. K16 判定（峰值基座上 4 个新三重，全灭）

- k16_T10both_enterB（三重 T10/both + enterB）：total 2203.93（比峰值 +75.52，全文件新行最高），mdd -23.58（比峰值浅 0.70），trades 169，nbeat 2（仅赢 2y 1481.16 vs M07 1474.08、3y 1937.14 vs 1677.53；输 1m -4.83、3m 17.01、6m 22.27、1y 121.22）。把峰值原有的 5 个窗胜压到只剩 2 个。
- k16_T10B_exitB（三重 T10/B-only + exitB）：total 2043.65（比峰值 -84.76），mdd -23.65，nbeat 1（仅赢 3y 1802.29；2y 1468.72 以 5.36 落败，其余四窗皆输）。
- k16_T10B_enterB（三重 T10/B-only + enterB）：total 2121.32（比峰值 -7.09），mdd -23.58，nbeat 1（仅赢 3y 1864.10；2y 1424.46 输 49.62）。
- k16_T05both_exitB（三重 T05/both + exitB）：total 1710.67（比峰值 -417.74，且是全文件唯一 total 跌破 M07 1863.27 的行），mdd -26.47，nbeat 1（仅赢 3m 18.81 vs 17.28；1m -6.37 为全文件最差，6m/1y/2y/3y 全输）。
- beat_all=True 计数 = 0（全部 6 行），win_all=True 计数 = 0。文件 flag 与独立重算 nbeat/beat_all/mdd_better/win_all：6/6 一致。
- 行为签名符合设计（延迟如预期生效，但只平移不加窗口）：两 enterB 行首尾两切各推迟约一格（06-21 到 07-21，09-08 到 10-14），与 K15 enterB 在峰值上的延迟签名一致；两 exitB 行中切推迟（08-15 到 09-12），与 K14 exitB 签名一致。dynN 一如既往只改仓位不改时点。
- 5-6 号（best/second-best x both-direction delay）：门限要求 core 出现 nbeat 至少 4，实测最高 nbeat=2（k16_T10both_enterB），按规则正确跳过，sidecar 有书面 note。复核人判定：跳过合规。

## 4. T 线触发集与执行

- 门限（beat_all 或 nbeat 至少 4）对 4 个新三重：触发集为空（最好成绩 2）。全套 T 线腿（跨相位、ex-top3、滑点加倍、独立复算）检验的是晋级候选的稳健性，对非候选 moot —— 与 batch_023/033/035/037/039/041 同规则，本轮不执行。
- 文件内唯一 nbeat 至少 4 的行是 base_gbf07（nbeat=5，校准行，非叠加候选）。其完整 4 腿 T 线已在 batch_037 执行（跨相位 FAIL、绝对滑点 FAIL、1m 硬缺口）—— 不重跑，结论沿用。
- 前视抽查：research/sweep_beat_m07_k16.py 全文无 shift(- 回看、无 searchsorted（0 处）；3 处 iloc 命中皆为尾窗收益数学（eq/sub 首尾取值，t 及之前）；机制码为 batch_037 已审计 adaptive_k13.py 逐字复用（build_ns_k13_dynN 与 build_ns_k13_dly 各经本文件三重构造器调用，无新增时间信息源）。前视一票：PASS，无否决。
- 独立复算抽查（复核人执行）：.venv/bin/python research/sweep_beat_m07_k16.py --only k16_T10both_enterB 输出 total 2203.93 / mdd -23.58 / 六窗与文件逐项一致（偏差 0.0），nbeat=2 确认。文件最好行确为真实计算，非手填。

## 5. 三重组合空间穷尽声明

- 全空间：dynN（thresh T10/T05 x legs both/B-only = 4）x confirm-delay（enterB/exitB/both = 3）= 12 个三重。
- 已测 5/12：K14 测 1（T10/both/exitB，nbeat=3）；K16 测 4（T10/both/enterB=2、T10/B/exitB=1、T10/B/enterB=1、T05/both/exitB=1）；K15 三重 0（门限未开跳过）。
- 未测 7/12：(T05,both,enterB)、(T05,B,exitB)、(T05,B,enterB)、(T10,both,both)、(T10,B,both)、(T05,both,both)、(T05,B,both)，其中 3 个是 5-6 号 both-delay 方向（含被门限挡掉的 best/second-best x both-delay）。
- 是否值得：不值得。证据链 —— (a) 已测 5 个三重最好 2/6，低于任一组成单机制在峰值上的成绩（dynT10_both 3/6、exitB 延迟 3/6），叠加严格减窗无一例外；(b) T05 系单机制已证弱（K14 T05 nbeat=1、K15 T05_B nbeat=0），以 T05 为底的三重（本轮 T05/both/exitB total 跌破 M07）在剩余 7 个中占 4 个，期望更低；(c) both-delay 是 exitB/enterB 的严格超集（更多延迟），而延迟在本轮已证只平移时点不增加正交增益。剩余 7 个的期望上界不超过已测最好（2/6），触及 T 线门限（4/6 或 beat_all）的概率可忽略。声明：峰值 x dynN x 确认延迟三重空间实质穷尽，不建议继续采样。

## 6. 裁决

- FAIL：K16 0/4（beat_all=0，最好 nbeat=2，win_all=0）。全域 beat_all 保持 0。任何 K16 行与任何三重变体不得上线。
- T1（beat_all）未触发。T2（nbeat 至少 4）无新叠加触发。纸面轨道维持 M07。
- 交付物（仅本目录）：本报告 + part_043_k16verify.json。合规：未新增本目录外任何文件；未触碰引擎、口径、结果文件；K16 产物（17:06 落盘）仅被读取并以 --only 方式独立复算，未覆写。
