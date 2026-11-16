# batch_050_m07inv9 审计报告：inventory_k38.json vs BEAT_M07_SUMMARY.md §1（K1–K19）

- 方法：`.venv/bin/python team/audit/batch_050_m07inv9/verify_inv9.py` 独立重算 19 个 `results/r30_bt/sweep_beat_m07_k{1..19}.json`（整行解析，不采信 inventory/§1 的任何聚合值）。
- 口径： calibration 行 = `base_M07` 全 19 轮各 1 行 + `base_gbf07` 峰值参照行（仅 K14/K15/K16/K18 各 1 行）；“新配” = 排除这两类 calibration 行后的行；maxnbeat = 新配范围内的 `nbeat_m07` 最大值（与 inventory 口径一致；若含 `base_gbf07` 则 K14/K15/K16/K18 会虚高为 5）。

## 逐项结论

| # | 审计项 | 预期 | 独立重算 | 结论 |
|---|---|---|---|---|
| 1 | 19 个轮次文件齐全 | K1–K19 共 19 文件 | `sweep_beat_m07_k{1..19}.json` 全部存在（另有 `k16.notes.json` 说明文件，不计轮次） | PASS |
| 2a | 总行数 | 203（inventory `totalrows`） | 30+9+29+18+20+8+6+8+13+7+7+7+7+6+5+6+4+6+7 = **203** | PASS |
| 2b | 每轮行数序列（任务书写法 30/9/29/18/20/8/6/8/7/13/7/7/7/6/7/6/4/7/7） | 求和=203 | 按该写法求和=**206**；实测 K9=13（非7）、K10=7（非13，即 K9/K10 被对调）、K15=5（非7）、K18=6（非7）。§1 表格写法 30/9/29/18/20/8/6/8/13/7/7/7/7/6/5/6/4/6/7=203 与实测逐轮一致 | **FAIL（任务书行数串笔误；§1 表格 PASS）** |
| 3 | 新配 174+6=180、零重名（inventory `distinct`） | K1–K18 新配 174，K19 +6 = 180，无重名 | 新配总数 180、去重后 180、跨轮重名 0（`base_gbf07` 在 K14/15/16/18 复用已按 calibration 剔除，不计重名） | PASS |
| 4a | 校准行：K1–K13/K17 单行 | 每轮仅 1 行 `base_M07` | K1–K13、K17 均恰为 base_M07×1、无 base_gbf07 | PASS |
| 4b | 校准行：K14–K16/K18 双行 | base_M07 + base_gbf07 各 1 | K14/K15/K16/K18 均为 base_M07×1 + base_gbf07×1（新配 4/3/4/4，与 §1 的 6/4、5/3、6/4、6/4 一致） | PASS |
| 4c | 校准行：K19 双行（任务书说法） | 双行 | 实测 K19 仅 base_M07×1，**无 base_gbf07**（7 行 = 1+6，与 §1 表格 7/6 一致） | **FAIL（任务书“K18–K19 双行”中 K19 部分不成立；§1 表格 PASS）** |
| 4d | base_M07 逐字复现 | 19 轮一致 | 19 个数值字段（total 1863.27 / mdd −27.05 / trades 184 / 六窗等）全轮逐值一致；字节级差异仅为各轮附加描述键（combo/switch_same_m07/…），数值口径零偏差 | PASS |
| 5 | beat 全 0（inventory `beat`） | 19 轮 beat_all 全假 | `beat_all=true` 全局 0 行，`win_all=true` 全局 0 行；inventory beat=0 一致 | PASS |
| 6a | maxnbeat K1–K18 | 4/4/5/2/4/2/4/4/3/1/0/2/3/3/1/2/2/1（K1→K18） | 实测新配最大值完全一致；与 inventory maxnb 全键一致 | PASS |
| 6b | maxnbeat K19（任务书写法 0） | 0 | 实测 K19 新配最大 = **1**（r_B90_A90），inventory k19=1、§1 表格 K19=1 均与实测一致 | **FAIL（任务书尾值 0 笔误，应为 1；inventory 与 §1 表格 PASS）** |
| 7 | 最强行 K8 g_bf07_winA30 total 2400.29 | 全场最高、新配第一 | 全局 total 最大值 = K8 g_bf07_winA30 **2400.29**（nbeat 4；1m −4.09 与 M07 打平；3m 17.25 差 −0.03pp；mdd −24.17），与 §1 描述逐值一致 | PASS |
| 8 | §1 最强行/关键数字抽查 | 表格描述 | K1 k05_by05/k25_cut78 并列 nbeat 4（2022.84>1908.74，前者更高、后者 mdd −25.35 更浅）✓；K2 g_by05_cut78_bx15（4/6, mdd −22.87, 2400系外 total 2084.73）✓；K3 g_bf07（5/6 仅 1m −0.01pp, mdd −24.28, total 2128.41）✓；K4 r_A15B30（2/6, mdd −29.73）✓；K5 nobrake_gbf07（4/6, mdd −28.40）✓；K6 cut75_both（2/6, 3y 差 −49.35pp）✓；K7 g_bf085（4/6, 2182.70；g_bf080 2177.90 次之）✓；K9 amihud_5_both on/off 并列 3/6（total 同 1338.14）✓；K10 nbeat 最高 k10_a60_size_both（1m +3.55pp）且新配 total 最高 1437.72（k10_a60_a5_B）✓；K11 k11_h05_B total 1680.98、最高 nbeat 0 ✓；K12 h02/h05 B/both 四行并列 nbeat 2（1m +0.01、1y +0.05）✓；K13 k13_dynT10_both（赢 3m/2y/3y, total 1990.79, mdd −25.72）✓；K14 三行并列 nbeat 3 ✓；K17 k17_calmar_M07（6m/1y 各 +0.01pp）✓；K18 k18_amiprop_gbf07（仅赢 3m）✓；K19 r_B90_A90（唯一赢 1m +2.46pp）✓ | PASS |

## 总评

- inventory_k38.json 的四个聚合值（totalrows 203 / distinct 180 / beat 0 / maxnb 全 19 键）**与独立重算完全一致**：PASS。
- BEAT_M07_SUMMARY.md §1 表格（轮次、行数/新配、beat、最高 nbeat、最强行与关键数字）**与独立重算完全一致**：PASS。
- **任务书转述串存在 3 处笔误（均不影响 inventory 与 §1 本身的正确性）**：(a) 行数串把 K9/K10 对调且 K15/K18 写成 7（实测 5/6），按任务串求和得 206≠203；(b) “K14–K16/K18–K19 双行”中 K19 实为单 calibration 行；(c) maxnbeat 尾值写 0，实测为 1。
- 复算脚本：`team/audit/batch_050_m07inv9/verify_inv9.py`（本目录内新增，无其他目录写入）。
