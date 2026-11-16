# M07六窗全超自己K7 bf轴收尾独立复核（batch_021_m07k7）

- 复核对象：K7 bf轴收尾6行（results/r30_bt/sweep_beat_m07_k7.json：1 base_M07 + 5新：g_bf065/g_bf075/g_bf080/g_bf085 + m07_bf07单变量；脚本CFGS另有2联动 g_bf080_takeB90/g_bf080_bx20，因门控未触发而未跑，文件即PHASE1全集），目标为六窗全超M07且回撤更浅（win_all = beat_all 且 mdd_better，beat_all为六窗严格大于）。
- M07基线：results/r30_bt/M07_final.json（total 1863.27，mdd -27.05，1m -4.09 / 3m 17.28 / 6m 39.00 / 1y 164.05 / 2y 1474.08 / 3y 1677.53）。
- 复核人：review子agent（agent-12），只读复算 + 引K7模块重跑（只新增 team/audit/batch_021_m07k7/ 内文件，未改主流程）。
- 基准口径（与M07逐字一致，读码确认）：2020新浪口径ph0，RUN_START=2023-01-03，EVAL_END=2026-11-12，5万本金，现实费率（cost_one_way=None）+滑点0.002，整手100股，只做多，不加杠杆，legacy_grid=False，full_liquidate=True，stop=0.25/stop_exec=next，A腿N5/R20/take1.2/B腿N4/R30/take0.80，MaxInputs双腿cut/win、RS60、MB排除、刹车bx/by/bf可参；K7仅动bf（g系by05+cut双腿0.78+bx15固定；m07_bf07为M07口径单改bf0.7），其余逐字一致。
- 结论：FAIL —— K7共6行 beat_all=0（file-declared与独立重算一致）、win_all=0，最高nbeat仅4（三行，均卡死在1m+3m短窗）；K1-K7累计113新配 beat_all=0（120行含7校准行；任务书112为batch_020沿袭口径，把K1-K4的86行全计新配，实含4个base_M07校准行，真新配82+19+7+5=113，见第5节纠正表）。T1-T6本轮均未触发（K7无候选故T1/T3/T4 moot，见第6节），T6口径审查通过；batch_017遗留bf0.8 WARNING关闭（bf-nbeat序列1/4/3/5/4/4/4，峰值仍在bf0.7=5，bf0.8=4）。

## 0. 一句话结论与证伪数字

- 一句话：K7的5个bf新配无一六窗全超M07，最强的g_bf085以total +319.43pp但1m -0.01pp/3m -0.04pp双卡、mdd仅浅0.33止步4/6，bf轴峰值仍是已审计的g_bf07（5/6），两侧新点均未超越，判FAIL、bf轴收尾撞墙确认。
- 证伪数字（详见第3节，每项均给命令/文件/参数）：
  1. 全文件独立重算nbeat/beat_all/mdd_better/win_all（K1-K7共120行，M07六窗逐值对照严格大于口径）：0 mismatch；file-declared beat_all=True计0、win_all=True计0；全域唯一非base nbeat>=5仍是K3 g_bf07（已审计，batch_017 T1已触发）。命令：.venv/bin/python team/audit/batch_021_m07k7/work_k7scan.py（产物 part_k7scan.json）+ work_k7final.py。
  2. 独立复算误差：最强三行（g_bf080/g_bf085/m07_bf07）引K7模块run_one同参重跑，与K7文件total/mdd/trades/cost/switches/brakes/六窗最大偏差0.00，mode/switch_log/brake_log/nbeat逐项一致。命令：.venv/bin/python team/audit/batch_021_m07k7/work_k7deep.py（产物 part_k7deep.json）。
  3. 最强新配六窗差（候选减M07，pp）：g_bf085为 -0.01/-0.04/+0.29/+0.70/+5.51/+175.30（4/6，total 2182.70，mdd -26.72浅0.33）；g_bf080为 -0.02/-0.01/+0.36/+1.31/+12.03/+190.40（4/6，total 2177.90，mdd -26.08浅0.97）；g_bf075为 -0.01/-0.04/+0.23/+0.58/+5.42/+187.20（4/6）——与K1-K6最强行完全相同的1m+3m短窗墙（七轮不动；g_bf080的3m -0.01pp为全系列最接近破墙的一次，仍失败）。
  4. bf轴单调表（g系by05+cut78+bx15、ph0，nbeat序列1/4/3/5/4/4/4）：bf0.5为1/1819.65/-21.99；bf0.6为4/2084.73/-22.87；bf0.65为3/2088.74/-23.65；bf0.7为5/2128.41/-24.28；bf0.75为4/2141.87/-24.77；bf0.8为4/2177.90/-26.08；bf0.85为4/2182.70/-26.72。bf0.8（=4）与bf0.85（=4）均未超越bf0.7（=5），batch_017遗留bf0.8 WARNING关闭；total随bf单调+363pp但mdd同步单调加深4.73pp，回撤与窗口不可兼得。
  5. 跨文件一致性：m07_bf07（M07口径单改bf0.7）与K1 k01_bf07十一个字段逐值相等（total 1917.97/mdd -28.24/trades 184/cost 52548/六窗/nbeat=1全同）——K7引擎与K1引擎同口径互相印证；m07_bf07自身仅1/6（仅赢3y +11.39pp），说明bf0.7的edge只存在于g系组合上，单搬M07口径即失效。
  6. 联动门控：K7脚本PHASE2（g_bf080_takeB90/g_bf080_bx20）门控为g_bf080 nbeat_m07>=5，实测g_bf080 nbeat=4，门控未触发，文件6行恰为PHASE1全集（work_k7deep.py gate节已验证PHASE2 tags不在文件中）——按门控设计的正确跳过，不是漏跑。
- 认错条件触发情况（原文见第6节）：本轮T1-T6均未触发（T1/T3/T4因K7无beat_all或nbeat>=5候选而moot；T2最高nbeat=4且bf轴峰值仍在已审计g_bf07=5；T5五新行switch_log全部与M07逐字一致；T6口径检查通过）。家族层面撞墙确认（非认错线）。
- 报告文件：team/audit/batch_021_m07k7/audit_m07k7_review.md（本文件）；脚本/产物：work_k7scan.py、part_k7scan.json、work_k7dump.py、work_k7deep.py、part_k7deep.json、work_k7ax.py、work_k7ax2.py、work_k7win.py、work_k7cnt.py、work_k7final.py。
## 1. 复核对象与证据链

| 项目 | 值 |
|---|---|
| K7脚本 | research/sweep_beat_m07_k7.py：复用run_m07_final系build_ns（sweep_beat_h1_v4）+ MaxInputs shadow + run_strategy_switch；get_ns/get_shadows缓存；run_one落盘total/mdd/trades/cost/mode/switches/brakes/双log/六窗+nbeat_m07/beat_all/mdd_better/win_all/switch_same_m07；CFGS 8组（1 base + 5 bf/PHASE1 + 2联动/PHASE2门控）；支持--phase分阶段执行 |
| K7文件 | results/r30_bt/sweep_beat_m07_k7.json：6行（等于PHASE1全集），字段与K5/K6系一致（另含各窗_mdd/brake_log/switch_log） |
| 分组 | bf轴g系4组（bf0.65/0.75/0.80/0.85，by05+cut78+bx15固定）+ M07单变量m07_bf07 1组 + base校准1组；联动（takeB90/bx20）2组门控未跑 |
| 本次复核脚本与产物 | work_k7scan.py 到 part_k7scan.json（120行nbeat重算+bf轴表+候选挑选）；work_k7deep.py 到 part_k7deep.json（三行引模块重跑+m07_bf07跨文件对账+K3行定位+PHASE2门控验证）；work_k7final.py（全域file-declared计数）；work_k7dump/win/ax/ax2/cnt.py（取数备查） |

口径核对（读K7脚本源码+重跑）：capital=50000、slip=0.002、lot=100、cost_one_way=None、RUN_START/EVAL_END/MB/legacy_grid/full_liquidate/stop=0.25/stop_exec=next/N-R/rebal/take/exposure/factor=amihud_60/phase=0与run_m07_final.py逐字一致（K7无phase参数，恒0）。K7 base_M07行total/mdd/trades/cost/mode/switches/brakes/六窗与M07_final.json逐值一致（见第2节表）。

## 2. 独立复算（三行重跑 + 全文件重算 + 校准行）

方法：先引K7模块run_one（与落盘同一函数、重跑非复制统计值）重跑g_bf080、g_bf085、m07_bf07（ph0/slip0.002）逐字段对比；再对全文件120行按M07六窗独立重算nbeat/beat_all/mdd_better/win_all；最后base行与M07_final逐值对比。

命令：.venv/bin/python team/audit/batch_021_m07k7/work_k7deep.py（产物 part_k7deep.json）+ work_k7scan.py（产物 part_k7scan.json）。

| 指标 | g_bf080自跑 | 文件 | 差 | g_bf085自跑 | 文件 | 差 | m07_bf07自跑 | 文件 | 差 |
|---|---|---|---|---|---|---|---|---|---|
| total/mdd | 2177.90/-26.08 | 相同 | 0.00 | 2182.70/-26.72 | 相同 | 0.00 | 1917.97/-28.24 | 相同 | 0.00 |
| trades/cost/mode | 184/59037/B | 相同 | 0 | 184/59252/B | 相同 | 0 | 184/52548/B | 相同 | 0 |
| switches/brakes | 3/3 | 相同 | 0 | 3/3 | 相同 | 0 | 3/3 | 相同 | 0 |
| 六窗 | -4.11/17.27/39.36/165.36/1486.11/1867.93 | 相同 | 0.00 | -4.10/17.24/39.29/164.75/1479.59/1852.83 | 相同 | 0.00 | -4.10/17.21/38.92/163.75/1465.91/1688.92 | 相同 | 0.00 |
| switch/brake_log | 与M07逐字一致/3对 | 相同 | 一致 | 与M07逐字一致/3对 | 相同 | 一致 | 与M07逐字一致/3对 | 相同 | 一致 |

数值字段最大偏差0.00，K7数字可复现。全文件重算0 mismatch；file-declared beat_all/win_all全0；base_M07行与M07_final六窗/total/mdd逐值偏差0.00。
## 3. 证伪清单执行结果

### (a) K7最强行六窗差（候选减M07，pp）

| 行 | 1m | 3m | 6m | 1y | 2y | 3y | nbeat | total_gap | mdd_gap |
|---|---|---|---|---|---|---|---|---|---|
| g_bf085 | -0.01 | -0.04 | +0.29 | +0.70 | +5.51 | +175.30 | 4 | +319.43 | +0.33 |
| g_bf080 | -0.02 | -0.01 | +0.36 | +1.31 | +12.03 | +190.40 | 4 | +314.63 | +0.97 |
| g_bf075 | -0.01 | -0.04 | +0.23 | +0.58 | +5.42 | +187.20 | 4 | +278.60 | +2.28 |
| g_bf065 | 0.00打平 | -0.06 | +0.11 | +0.04 | -2.82 | +179.70 | 3 | +225.47 | +3.40 |
| m07_bf07 | -0.01 | -0.07 | -0.08 | -0.30 | -8.17 | +11.39 | 1 | +54.70 | -1.19 |

五新行1m无一严格胜出（最好打平）、3m全败——短窗墙第七轮（K1-K7）纹丝不动。g_bf080的3m -0.01pp是全系列最接近破墙的一次，仍失败；全域唯一赢过3m的行仍是K3 g_bf07（17.29大于17.28）。mdd_better在四行g系为True，但beat_all=0故win_all全0，回撤优势救不了晋级。

### (b) bf轴（g系by05+cut78+bx15、ph0）+ WARNING关闭

| bf | tag（文件） | nbeat | total | mdd | 赢窗 |
|---|---|---|---|---|---|
| 0.5 | g_bf05（K3） | 1 | 1819.65 | -21.99 | 仅3y |
| 0.6 | g_by05_cut78_bx15（K2，即batch_017所记g） | 4 | 2084.73 | -22.87 | 6m/1y/2y/3y |
| 0.65 | g_bf065（K7） | 3 | 2088.74 | -23.65 | 6m/1y/3y |
| 0.7 | g_bf07（K3） | 5 | 2128.41 | -24.28 | 除1m外五窗 |
| 0.75 | g_bf075（K7） | 4 | 2141.87 | -24.77 | 6m/1y/2y/3y |
| 0.8 | g_bf080（K7） | 4 | 2177.90 | -26.08 | 6m/1y/2y/3y |
| 0.85 | g_bf085（K7） | 4 | 2182.70 | -26.72 | 6m/1y/2y/3y |

nbeat序列1/4/3/5/4/4/4：非单调（bf0.65回落至3），峰值bf0.7=5；bf0.8=4小于5、bf0.85=4小于5，因此batch_017遗留bf0.8 WARNING关闭（单调递增假设被证伪，峰值确认为局部峰而非跳板）。total随bf单调+363.05pp但mdd同步单调加深4.73pp——bf越大刹车越弱，收益与回撤同向放大，六窗全超不可兼得。

### (c) m07_bf07单变量（M07口径仅改bf0.6到0.7）

total 1917.97（+54.70）、mdd -28.24（深1.19）、nbeat=1（仅3y）。与K1 k01_bf07十一个字段逐值相等（见0.5节）——同口径跨批次可复现；同时证明bf0.7的edge不独立存在，必须配合g系（by05+cut78+bx15）组合，单搬M07口径即失效（1/6且mdd更深，双杀）。

### (d) PHASE2联动门控（备查：门控行未跑，moot但须留痕）

- 门控语义：g_bf080_takeB90（B腿take 0.80到0.90）/g_bf080_bx20（刹车bx 0.15到0.20）仅当g_bf080 nbeat_m07>=5才跑；实测g_bf080 nbeat=4，门控未触发，文件6行等于PHASE1全集（work_k7deep.py gate节：PHASE2 tags不在文件中）——正确跳过，非漏跑。
- 跨相位/ex-top3/滑点加倍：按任务书第1条仅对beat_all或nbeat>=5候选执行；K7最高nbeat=4、无候选，因此moot（与batch_018/019/020同口处置）。备查观察（非晋级依据）：K7五新行switch_log全部与M07逐字一致（择时零漂移，墙不在切换节拍）；mdd_better四行但beat_all全0。
## 4. T6口径审查（K7脚本读码）

1. 数据与窗口：pivots_2020_clean.pkl、RUN_START/EVAL_END/grid（300步/30步）与M07同一引用（sweep_beat_h1_v4导入），无新增数据源。2. 本金/费率/滑点/整手：50000/cost_one_way=None/slip=0.002/lot=100逐字一致。3. 执行：stop=0.25/stop_exec=next、legacy_grid=False、full_liquidate=True一致。4. 因子原生性：K7只用amihud_60（引擎原生），未触batch_020遗留的非原生因子（size/amount_level/liq_size/amihud_5），size与MAX交互moot延续。5. 未来函数：复用已审计build_ns/run_strategy_switch（shadow+信号日切片），K7新增仅为CFGS参数与门控分支，无手写回测器、无未来引用，通过。6. 文件-脚本一致性：文件6行等于PHASE1全集，PHASE2缺席与门控记录一致，无口径外点。

## 5. 累计数纠正表（per-file rows/base/new）

| 文件 | rows | base_M07校准 | 新配 | beat_all |
|---|---|---|---|---|
| K1 | 30 | 1 | 29 | 0 |
| K2 | 9 | 1 | 8 | 0 |
| K3 | 29 | 1 | 28 | 0 |
| K4 | 18 | 1 | 17 | 0 |
| K5 | 20 | 1 | 19 | 0 |
| K6 | 8 | 1 | 7 | 0 |
| K7 | 6 | 1 | 5 | 0 |
| 合计 | 120 | 7 | 113 | 0 |

纠正说明：batch_020的累计112配系把K1-K4的86行（含4校准行）全计新配（86+19+7=112）；按文件实际tags，真新配为82+19+7=108（K1-K6），加K7的5等于113。beat_all=0不受计数口径影响（file-declared与独立重算双0）。命令：.venv/bin/python team/audit/batch_021_m07k7/work_k7cnt.py。

## 6. 认错条件（原文沿用batch_017第6节并适配超M07目标；T1已在batch_017对g_bf07触发，本轮为延续线）

- T1（相位运气）：若候选相对M07的total优势在异相位下反转，则认错ph0优势主要来自相位运气。K7无beat_all/nbeat>=5候选，moot、未触发；家族延续线为batch_017已对g_bf07触发（T1认错成立并延续，K7的bf轴峰值仍是该行，其5/6不计入晋级）。
- T2（邻域过拟合）：若邻域内出现nbeat更高、或同nbeat但total/mdd双优的点，则认错最优点为噪声峰。K7新增最高nbeat=4（小于5），无更高新邻点，未触发；且bf轴两侧（0.65侧3/6、0.75/0.80/0.85侧4/6）均低于峰值g_bf07=5，峰值为局部峰的证据增强（非认错线，属撞墙确认）。
- T3（集中赌博）：若剔除Top3后候选total转负或落后M07 ex-top3，则认错增量来自少数彩票股。无候选，moot、未触发。
- T4（成本鲁棒）：若同成本基线候选对M07 nbeat<3或mdd不再更浅，则认错edge不具成本鲁棒性。无候选，moot、未触发。
- T5（择时运气）：若复现switch_log与M07不一致，则认错增量来自切换时点漂移。K7五新行switch_same_m07全部True（与M07三切换逐字一致），未触发。
- T6（前视/口径）：若发现任一未来函数或口径（本金/费率/整手/起止/网格/执行/费用）不一致，直接判FAIL。第4节六项检查通过，未触发。

## 7. verdict与全域结论更新

- verdict：FAIL（K7的5新配 beat_all=0、win_all=0；K1-K7累计113新配 beat_all=0；最强新配g_bf085以1m -0.01pp/3m -0.04pp、mdd仅浅0.33止步4/6；bf轴峰值仍是已审计g_bf07=5且T1认错延续；无FAIL项但目标落空故不判PASS_WITH_WARNINGS）。
- 差距数量级总表（相对M07 total 1863.27/mdd -27.05）：bf轴total为+225到+319pp但短窗全灭（1m最好打平、3m全败）；m07_bf07单变量+54.70pp但1/6且mdd更深1.19；mdd_better四行（浅0.33到3.40）救不了beat_all。
- 全域结论：在当前数据与引擎下，同切换族（阈值/cut/刹车/RS/相位袖/单腿/锁定/去刹车/联动/互换/因子-cut信号源/bf轴）不存在六窗全超M07且回撤更浅的策略——七轮正交族113新配零全胜，且短窗墙（1m在打平/-0.01/-0.02pp、3m在-0.01到-0.07pp）七轮纹丝不动。
- 唯一残留的未探明方向（不是达标、不是晋级依据，重启须重立T线）：非原生因子（size/amount_level/liq_size/amihud_5）需新Inputs实现+全套T1-T6重审（含size与MAX交互这个moot延续项）。bf轴已探明终结（WARNING关闭），阈值/机制/信号源/bf四线搜索应终结；paper-track维持M07，K7任何行不得实盘。
- 本报告产物清单（仅 team/audit/batch_021_m07k7/）：audit_m07k7_review.md、work_k7scan.py、part_k7scan.json、work_k7dump.py、work_k7deep.py、part_k7deep.json、work_k7ax.py、work_k7ax2.py、work_k7win.py、work_k7cnt.py、work_k7final.py。
