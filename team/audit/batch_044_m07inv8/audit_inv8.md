# batch_044_m07inv8 审计报告：inventory_k32 vs BEAT_M07_SUMMARY §1（K1–K16）

- 审计人：复核子agent agent-46；日期 2026-11-16；工作目录 /Users/joker/coding/ashare-trade；Python .venv/bin/python（heredoc，无新增脚本，符合“只新增本目录内文件”约束）。
- 审计对象：
  - A: results/r30_bt/inventory_k32.json（任务指定）
  - B: BEAT_M07_SUMMARY.md §1（标题“十六轮 sweep（Lead 独立复验：186 行、167 独立新配、零重名、beat_all=0）”+ K1–K16 表格 + 第32行脚本/结果清单）。
- 方法：独立重算（不信任任何现成 inventory 合计）。用 glob + 正则 `k\\d+\\.json$` 枚举 16 个 sweep 文件，逐行统计 rows / 新配（排除校准 tag）/ beat_all / nbeat_m07（新配口径与全口径双算）、校准 tag、跨文件 tag 重名、K8 最强行 total。
- 委派语纠正（Lead 已确认，本报告按纠正后口径核对）：
  1. 行数字串以“30/9/29/18/20/8/6/8/13/7/7/7/7/6/5/6=186”为准（原串把 K9/K10 写反为 7/13、K15 写成 7，求和 188 对不上 186）。
  2. glob 会命中 results/r30_bt/sweep_beat_m07_k16.notes.json 附文件，盘点时须排除，仅计 k<数字>.json。

## 结论一览

| # | 核对项 | 预期（纠正后） | 独立重算 |  verdict |
|---|---|---|---|---|
| 0 | inventory_k32.json 文件存在 | 存在 | **不存在**（results/r30_bt/ 下最新为 inventory_k30.json；find/inventory\* 仅 k16/k19/k22/k24/k26/k28/k30，无 k32） | **FAIL** |
| 1 | K1–K16 行数 30/9/29/18/20/8/6/8/13/7/7/7/7/6/5/6=186 | 186 | 30+9+29+18+20+8+6+8+13+7+7+7+7+6+5+6 = **186 PASS**（已排除 k16.notes.json；该附文件为 dict 非 list，若误纳入会抛 TypeError/多计） | **PASS** |
| 2 | 新配 29+8+28+17+19+7+5+7+12+6+6+6+6+4+3+4=167，零重名 | 167 distinct、无重复 | distinct **167**，跨 K1–K16 非校准 tag **零重复**（Counter dup=[]） | **PASS** |
| 3 | 校准行 K1–K13 单行、K14–K16 双行 | K1–K13=[base_M07]；K14–K16=[base_M07, base_gbf07] | 逐文件 tag 清单与之一字不差（见明细） | **PASS** |
| 4 | beat（beat_all）全 0 | 16 轮 beat 和=0 | 16 文件 beat_all 合计 **0**（逐文件 beat=0） | **PASS** |
| 5 | maxnbeat 4/4/5/2/4/2/4/4/3/1/0/2/3/3/1/2 | 新配口径序列 | 新配口径重算 **4/4/5/2/4/2/4/4/3/1/0/2/3/3/1/2 一字不差 PASS**；注：全口径下 K14–K16 max=5，系校准行 base_gbf07(nbeat=5) 所致，非新配 | **PASS（附口径注）** |
| 6 | 最强行 K8 g_bf07_winA30 total 2400.29 | total=2400.29 | K8 文件中该 tag total=**2400.29**，nbeat=4，mdd=-24.17；为 K8 并列最高 nbeat 组中 total 最高 | **PASS** |
| 7 | 与 inventory_k30 的衔接自洽性 | k30=K1–K15（180行/163 distinct） | inventory_k30.json 实测 totalrows=180、distinct=163、beat=0、maxnb(K1–K15)=4/4/5/2/4/2/4/4/3/1/0/2/3/3/1；180+K16(6行)=186、163+K16新配(4)=167，自洽 | **PASS（旁证）** |

**总 verdict：源数据（16 个 sweep）与 §1 全部内容一致 → 内容 PASS；但目标产物 inventory_k32.json 缺失 → 文件存在性 FAIL。** 建议由 Lead/owner 按 K16（含双校准行）口径生成 inventory_k32.json 后，本报告其余 PASS 项可直接作为其内容验收依据。

## 独立重算证据（.venv/bin/python，heredoc）

### 逐文件 tag 清单（行数/校准/新配）

- k1.json 30 ['base_M07', k01_bf07…k29 共29新] → rows 30 / new 29 / cal [base_M07]
- k2.json 9 ['base_M07', a_by05_cut78…h 共8新] → rows 9 / new 8 / cal [base_M07]
- k3.json 29 ['base_M07', a_winA30…g_winA30 共28新，含 g_bf07] → rows 29 / new 28 / cal [base_M07]
- k4.json 18 ['base_M07', sleeve…r_A15B30… 共17新] → rows 18 / new 17 / cal [base_M07]
- k5.json 20 ['base_M07', legA_only…g_swap_NR 共19新] → rows 20 / new 19 / cal [base_M07]
- k6.json 8 ['base_M07', both_amihud…asym_A82B78 共7新] → rows 8 / new 7 / cal [base_M07]
- k7.json 6 ['base_M07', g_bf065/g_bf075/g_bf080/g_bf085/m07_bf07 共5新] → rows 6 / new 5 / cal [base_M07]
- k8.json 8 ['base_M07', g_bf07_rs70/g_bf07_winA30/g_bf07_rs70_winA30/g_bf07_cut75/g_bf07_cut75_rs70/g_bf07_stop22/g_bf07_takeB90 共7新] → rows 8 / new 7 / cal [base_M07]
- k9.json 13 ['base_M07', k9_size_B_on…k9_amihud_5_both_off 共12新] → rows 13 / new 12 / cal [base_M07]
- k10.json 7 ['base_M07', k10_a60_size_B…k10_a60_a5_both 共6新] → rows 7 / new 6 / cal [base_M07]
- k11.json 7 ['base_M07', k11_h02_B…k11_h10_both 共6新] → rows 7 / new 6 / cal [base_M07]
- k12.json 7 ['base_M07', k12_h02_B…k12_h10_both 共6新] → rows 7 / new 6 / cal [base_M07]
- k13.json 7 ['base_M07', k13_dynT05_B…k13_dly_exitB 共6新] → rows 7 / new 6 / cal [base_M07]
- k14.json 6 ['base_M07', 'base_gbf07', k14_dynT10_both/k14_dynT05_both/k14_dly_exitB/k14_triple_T10xB 共4新] → rows 6 / new 4 / cal 双行
- k15.json 5 ['base_M07', 'base_gbf07', k15_dynT10_B/k15_dynT05_B/k15_dly_enterB 共3新] → rows 5 / new 3 / cal 双行
- k16.json 6 ['base_M07', 'base_gbf07', k16_T10both_enterB/k16_T10B_exitB/k16_T10B_enterB/k16_T05both_exitB 共4新] → rows 6 / new 4 / cal 双行
- 合计 rows=186；新配 distinct=167（29+8+28+17+19+7+5+7+12+6+6+6+6+4+3+4）；跨文件非校准 tag 重复=[]。

### beat / maxnbeat（双口径）

- 逐文件 beat_all 合计：16 个文件各 beat=0 → 总 0。PASS。
- maxnbeat（新配口径，即排除 base_M07/base_gbf07 后取 max(nbeat_m07)）：
  - K1 4（k05_by05 total 2022.84 / k25_cut78 并列）、K2 4、K3 5（g_bf07 total 2128.41）、K4 2（r_A15B30）、K5 4、K6 2（cut75_both）、K7 4、K8 4、K9 3、K10 1、K11 0、K12 2、K13 3（k13_dynT10_both total 1990.79）、K14 3、K15 1（k15_dynT10_B total 2161.12）、K16 2（k16_T10both_enterB total 2203.93）→ 与 §1 表格及任务序列一致。
  - 全口径 max：K14/K15/K16=5（均为校准行 base_gbf07 nbeat=5 贡献；base_M07=0）。inventory_k30.json 的 maxnb 亦采用新配口径（k14:3、k15:1），与本审计一致。

### K8 最强行

- sweep_beat_m07_k8.json 全行 (tag, nbeat, total, mdd)：base_M07(0,1863.27,-27.05)、g_bf07_rs70(4,2022.83,-24.28)、**g_bf07_winA30(4,2400.29,-24.17)**、g_bf07_rs70_winA30(4,2298.59,-24.17)、g_bf07_cut75(4,1904.82,-25.02)、g_bf07_cut75_rs70(1,1730.27,-25.02)、g_bf07_stop22(2,2029.43,-24.89)、g_bf07_takeB90(0,1658.10,-24.32)。最强行 total 2400.29 确认，nbeat=4，mdd=-24.17 与 §1 一致。

### inventory_k30 旁证

- results/r30_bt/inventory_k30.json：totalrows=180、distinct=163、beat=0；maxnb={k1:4,k2:4,k3:5,k4:2,k5:4,k6:2,k7:4,k8:4,k9:3,k10:1,k11:0,k12:2,k13:3,k14:3,k15:1}；cal 中 K1–K13 单 base_M07、K14/K15 双行。恰为 K1–K15 子集：180+6(K16)=186、163+4(K16)=167。§1 的 K16 行（6/4、maxnbeat 2）与 k16.json 实测一致。

## 说明与建议

- 本次唯一 FAIL 是产物缺失，不是数据造假：16 个 sweep 源文件自洽且与 §1 全对上。若补建 inventory_k32.json，期望内容应为 totalrows=186、distinct=167、beat=0、maxnb={k1:4,…,k16:2}（新配口径）、cal 延续 K1–K13 单行/K14–K16 双行。
- 易错点已验证：k16.notes.json（dict 结构）必须排除在盘点 glob 之外；maxnbeat 必须注明新配口径，否则 K14–K16 会被误算成 5。
- 约束遵守：本次仅新增 team/audit/batch_044_m07inv8/audit_inv8.md（含本文件），未改动其他文件。

## 补记（存在性复检，Lead 时序澄清后）

- **存在性复检PASS（时序误判关闭）**：results/r30_bt/inventory_k32.json 已于 17:10 落盘（569B；本审计初检时该文件尚不存在，故原 #0 FAIL 系时序误判，现关闭）。
- 内容比对（独立重算 vs 文件）：totalrows=186 ✓、distinct=167 ✓、beat=0 ✓、maxnb 全16文件={k1:4,k2:4,k3:5,k4:2,k5:4,k6:2,k7:4,k8:4,k9:3,k10:1,k11:0,k12:2,k13:3,k14:3,k15:1,k16:2} ✓（新配口径，与本报告重算一字不差）。
- 差异说明：该 k32 文件仅含 totalrows/distinct/beat/maxnb 四键（无 cal 键；k30 另有 cal），故“校准行单/双行”仍以 sweep 源文件实测为准（K1–K13 单 base_M07、K14–K16 双行 PASS）。
- 最终总 verdict 更新为：**全 PASS**（含存在性）。
