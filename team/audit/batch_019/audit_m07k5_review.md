# M07“六窗全超自己”K5换引擎族独立复核（batch_019）

- 复核对象：K5换引擎族19配（`results/r30_bt/sweep_beat_m07_k5.json`：1 base_M07 + 19新机制：单腿×2 / 锁定×4 / 去刹车×2 / RS变体×4 / 止盈止损联动×4 / AB角色互换×3），目标：六窗全超M07且回撤更浅（`win_all = beat_all && mdd_better`，beat_all为六窗严格>）。
- M07基线：`results/r30_bt/M07_final.json`（total 1863.27，mdd −27.05，1m −4.09/3m 17.28/6m 39.00/1y 164.05/2y 1474.08/3y 1677.53）。
- 复核人：review子agent（agent-8），只读复算 + 自写引擎重跑（仿 `research/valid_m07_k3ph.py` 结构，只新增 `team/audit/batch_019/` 内文件，未改主流程）。
- 基准口径（与M07逐字一致，读码确认）：2020新浪口径，RUN_START=2023-01-03，EVAL_END=2026-11-12，5万本金，现实费率+滑点0.002，整手100股，只做多，不加杠杆，legacy_grid=False，full_liquidate=True；K5仅动机制（leg/lock_mode/bx/rs/stop-take联动/N-R），其余逐字一致。
- 结论：**FAIL** —— K5共20行（1校准+19新机制）`beat_all=0`、`win_all=0`，最高nbeat仅4（nobrake_gbf07 / nobrake_M07，均卡死在1m+3m短窗−0.01~−0.04pp+mdd更深）；K1–K4累计86配叠加K5的19新配，**105配 beat_all=0**，换引擎族同样撞墙。T1–T6认错条件本轮均未触发（无beat_all/nbeat>=5候选故T1/T3/T4 moot，见§6），T6口径审查通过（无未来函数、无口径漂移）。

## 0. 一句话结论与证伪数字

- 一句话：K5的19个新机制无一六窗全超M07，最强的去刹车gbf07以4/6+mdd更深1.35pp止步（1m −0.02pp/3m −0.04pp双卡），B腿直跑长窗崩−1296pp、AB互换崩−1400pp级，判FAIL、换引擎族撞墙确认。
- 证伪数字（详见§3，每项均给命令/文件/参数）：
  1. 独立复算误差：最强两行（nobrake_M07 / nobrake_gbf07）自跑与K5文件**数值字段最大偏差0.00**（total/mdd/trades/cost/switches/brakes/六窗逐值一致，mode字符串一致；产物`part_k5deep.json`中maxdev=1系mode相等布尔True参与取max的记录 artifact，数值dev全0.00），brake_log空数组、switch_log与M07逐字一致双双复现。命令：`.venv/bin/python team/audit/batch_019/work_k5deep.py`（产物`part_k5deep.json`）。
  2. 最强新机制六窗差（候选−M07，pp）：nobrake_gbf07为 **−0.02/−0.04/+0.19/+0.40/+0.94/+161.59**（4/6，total +380.25，mdd −28.40深1.35）；nobrake_M07为 **−0.01/−0.04/+0.29/+0.72/+5.94/+111.19**（4/6，total +319.33，mdd −32.10深5.05）——与K1–K3最强行（k05_by05、g、g_bf07）完全相同的**1m+3m短窗−0.01~−0.04pp墙**（§3b）。
  3. 单腿/B腿直跑差距数量级：legB_only nbeat2，total **567.08**（落后M07 **−1296.19pp**），mdd −31.81（深4.76），仅赢1m(+0.05)/3m(+0.64)，6m起全线崩（6m −11.58/1y −124.46/2y −1094.62/3y −1189.25）；legA_only nbeat0，total 1270.62（−592.65），mdd **−45.40**（深18.35，回撤爆炸）。
  4. 其余机制全崩：lock系最高nbeat1（lockB/lockB_gbf07赢单个短窗，total落后1300pp+）；rs30/rs120/g_rs30/g_rs120全nbeat0（total落后340~740pp）；pair联动最高nbeat2（g_pair_lo，total −112.52）；swap_NR/swap_full/g_swap_NR全nbeat0，total **336~479**（落后M07 **−1384~−1527pp**）。
  5. 跨相位（nobrake_gbf07自跑，M07侧引已审计`team/audit/batch_017/part_gph.json`）：ph5 total **871.22** vs M07 755.73（+115.49，六窗6/6但mdd −34.67深3.06→win_all仍失败）；ph15 total **546.03** vs 609.80（**−63.77**，0/6，mdd −32.55深5.40）——去刹车edge无跨相位稳健性。
  6. 滑点加倍（nobrake_gbf07@0.004自跑 total **1930.99**/mdd −29.11/cost 98212，对同成本M07@0.004：total 1595.72/mdd −27.63/六窗−4.45/15.87/35.85/153.00/1333.42/1472.71，引自batch_016/017已审计产物）：六窗差 **0.00/+0.05/+0.13/+0.37/+11.22/+151.46**，5/6——1m打平（−4.45 vs −4.45，严格>失败）+ mdd深2.48，墙在双倍成本下纹丝不动。
- 认错条件触发情况（原文见§6）：**本轮T1–T6均未触发**（T1/T3/T4因无beat_all或nbeat>=5候选而moot；T2最高nbeat=4无更高邻点；T5最强两行switch逐字一致；T6七项口径检查通过）。家族层面撞墙确认（非认错线，见§6）。
- 报告文件：`team/audit/batch_019/audit_m07k5_review.md`（本文件）；脚本/产物：`work_k5scan2.py`→`part_k5scan.json`、`work_gap_prep.py`→`part_gap_prep.json`、`work_k5dump.py`、`work_k5logchk.py`、`work_k5deep.py`→`part_k5deep.json`。

## 1. 复核对象与证据链

| 项目 | 值 |
|---|---|
| K5脚本 | `research/sweep_beat_m07_k5.py`（181行）：`run_switch`（switch/lock/nobrake/rs/pair/swap统一入口）+ `run_leg`（单腿复用shadow）+ base校准assert（六窗逐窗<0.01） |
| K5文件 | `results/r30_bt/sweep_beat_m07_k5.json`：20行（1 base + 19机制），字段= K2/K4 schema + mechanism（tag/kind/mechanism/params/total/mdd/trades/cost/mode/switches/brakes/switch_log/brake_log/六窗+各窗_mdd/nbeat_m07/beat_all/mdd_better/win_all/switch_same_m07） |
| 机制分组 | 单腿legA/legB ×2；锁定lockA/lockB/lockA_gbf07/lockB_gbf07 ×4；去刹车nobrake_M07/nobrake_gbf07 ×2；RS变体rs30/rs120/g_rs30/g_rs120 ×4；止盈止损联动pair_hi/pair_lo/g_pair_hi/g_pair_lo ×4；AB互换swap_NR/swap_full/g_swap_NR ×3 |
| 本次复核脚本/产物 | `team/audit/batch_019/work_k5scan2.py`→`part_k5scan.json`（20行schema+nbeat重算+候选挑选）；`work_k5deep.py`→`part_k5deep.json`（最强两行复跑+exTop3+ph5/ph15+slip04，共5次switch引擎运行） |

口径核对（读K5脚本源码+复跑）：capital=50000、slip=0.002（T4另跑0.004）、lot=100、cost_one_way=None、RUN_START/EVAL_END/MB/legacy_grid/full_liquidate/stop_exec=next/factor=amihud_60与`run_m07_final.py`一致；phase仅本复核自用且同相位对比口径成立。K5 base_M07行total/mdd/六窗与`M07_final.json`逐值一致（`part_k5scan.json`：base dev全0.00；脚本177–179行六窗assert通过才落盘）。

## 2. 独立复算（最强两行）

方法：自写脚本（仿`valid_m07_k3ph.py`结构，不import主引擎统计函数，公式自写），用K5同口径参数重跑nobrake_M07与nobrake_gbf07（ph0/slip0.002，复用`K.get_shadows`/`K.get_ns`缓存路径），逐字段对比。

命令：`.venv/bin/python team/audit/batch_019/work_k5deep.py`（产物`part_k5deep.json`前两节）。

| 指标 | nobrake_M07自跑 | 文件 | 差 | nobrake_gbf07自跑 | 文件 | 差 |
|---|---|---|---|---|---|---|
| total/mdd | 2182.60/−32.10 | 同 | 0.00 | 2243.52/−28.40 | 同 | 0.00 |
| trades/cost/mode/switches/brakes | 184/59488/B/3/0 | 同 | 0 | 184/61046/B/3/0 | 同 | 0 |
| 1m/3m/6m | −4.10/17.24/39.29 | 同 | 0.00 | −4.11/17.24/39.19 | 同 | 0.00 |
| 1y/2y/3y | 164.77/1480.02/1788.72 | 同 | 0.00 | 164.45/1475.02/1839.12 | 同 | 0.00 |
| brake_log | [] | [] | 一致（bx=10永不触发证实） | [] | [] | 一致 |
| switch_log | 与M07逐字一致 | same=true | 一致 | 与M07逐字一致 | same=true | 一致 |

数值字段最大偏差**0.00** → K5数字可复现，通过复现性部分。注：产物中maxdev=1为mode字符串相等布尔True参与max的记录artifact（dev明细数值项全0.00/0），非实质偏差。

## 3. 证伪清单执行结果

### (a) 最强新机制六窗差（nobrake两行 − M07，pp）

| 行 | 1m | 3m | 6m | 1y | 2y | 3y | nbeat | total_gap | mdd_gap |
|---|---|---|---|---|---|---|---|---|---|
| nobrake_M07 | −0.01 | −0.04 | +0.29 | +0.72 | +5.94 | +111.19 | 4 | +319.33 | −5.05 |
| nobrake_gbf07 | −0.02 | −0.04 | +0.19 | +0.40 | +0.94 | +161.59 | 4 | +380.25 | −1.35 |

两行均赢6m/1y/2y/3y、输1m/3m——与K1最强k05_by05（−0.02/−0.04）、K2最强g（−0.01/−0.03）、K3最强g_bf07（−0.01/+0.01）**同一短窗墙**：1m缺口−0.01~−0.02pp为舍入无关的结构性落后（区间不重叠论证见batch_017 §3a，同理适用），3m缺口−0.04pp五轮纹丝不动。且两行mdd全部更深（去刹车代价：−32.10/−28.40 vs −27.05），win_all双杀。

### (b) 单腿/B腿直跑差距数量级（文件值，§2复算方法已验证引擎可信）

| 行 | nbeat | total | total_gap | mdd | mdd_gap | 六窗差 |
|---|---|---|---|---|---|---|
| legA_only | 0 | 1270.62 | −592.65 | −45.40 | −18.35 | −1.57/−5.25/−6.10/−11.75/−89.29/−392.43（全败，mdd爆炸） |
| legB_only | 2 | 567.08 | **−1296.19** | −31.81 | −4.76 | +0.05/+0.64/−11.58/−124.46/−1094.62/−1189.25（仅赢1m/3m，长窗崩−1000pp级） |

B腿直跑的2个短窗微弱优势（+0.05/+0.64pp）与其−1296pp的total鸿沟相比无意义；A腿单跑回撤深18.35pp，不可实盘。单腿家族死刑。

### (c) 其余机制（文件值，nbeat重算0 mismatch见`part_k5scan.json`）

- 锁定系：lockA nbeat0（total 1354.29/−508.98，mdd −34.48）、lockB nbeat1（total 531.00，赢3m +0.69一个短窗）、lockA_gbf07 nbeat0、lockB_gbf07 nbeat1（赢3m +0.69）。锁定=放弃切换，total落后500~1300pp。
- RS变体：rs30/rs120/g_rs30/g_rs120全nbeat0（total 1123~1519，落后340~740pp；rs30系切换17次，节拍全漂移）。
- 止盈止损联动：pair_hi nbeat1、pair_lo nbeat1、g_pair_hi nbeat0、g_pair_lo nbeat2（total 1753.74/−112.52，最接近的联动行仍差112pp+4窗）。
- AB互换：swap_NR/swap_full/g_swap_NR全nbeat0，total **336.24~479.14**（落后 **−1384~−1527pp**，全场最低三行）——N/R对调即摧毁长窗（2y差−1000pp级）。
- K5的20行：nbeat分布为4×2、2×2、1×4、0×12（含base），`beat_all=0`、`win_all=0`全文件成立（`part_k5scan.json`重算mismatches为空）。

### (d) 跨相位（nobrake_gbf07自跑 vs 已审计M07相位值）

| 相位 | nobrake_gbf07 total | M07 total | total差 | 同相位nbeat | mdd |
|---|---|---|---|---|---|
| ph0 | 2243.52 | 1863.27 | +380.25 | 4/6 | −28.40/−27.05（深） |
| ph5 | 871.22 | 755.73 | +115.49 | 6/6（−7.07>−9.34、7.22>4.60、35.01>31.77、76.12>68.11、725.18>688.75、772.49>643.60） | −34.67/−31.61（深3.06→win_all失败） |
| ph15 | 546.03 | 609.80 | **−63.77** | 0/6 | −32.55/−27.15（深5.40） |

ph5的6/6被mdd一票否决（win_all要求mdd更浅），ph15 total+六窗+mdd三杀。去刹车edge无跨相位稳健性，与batch_017 g_bf07的T1触发同构（本轮因无候选而判moot，见§6）。

### (e) ex-top3与滑点加倍（备查：无候选故moot，但作为撞墙数量级证据执行）

- ex-top3（同脚本trades net_pnl独立重算，DataFrame路径）：nobrake_M07 top3_share **26.3%**、nobrake_gbf07 **26.3%**（M07为26.4%）——去刹车未引入集中赌博，但因无候选而不改变晋级结论。
- 滑点加倍（nobrake_gbf07@0.004自跑 vs 同成本M07@0.004引用值§0-6）：total **1930.99**（−312.53pp），cost 59488→**98212**（费用连贯上升，无漏计）；六窗差0.00/+0.05/+0.13/+0.37/+11.22/+151.46 → **5/6**，total +335.27，但1m打平（−4.45 vs −4.45，严格>失败）+ mdd深2.48（−29.11 vs −27.63）→ 仍无beat_all、无win_all。**墙在双倍成本下纹丝不动**。

### (f) 切换/刹车节拍

- nobrake两行ph0 switch_log与M07**逐字一致**（3次：2023-06-21→B，2024-08-15→A，2026-09-08→B；复跑switch_same=true）→ 去刹车增量纯属暴露度（无刹车降仓），无择时运气，T5未触发。
- nobrake两行brake_log=[]（复跑brake_empty=true）→ bx=10永不触发机制成立。
- lock四行switches=0（锁定无切换，与机制披露一致）、刹车仍活跃（含刹车披露一致：lockA 1对、lockB 2对、lockA_gbf07 6对、lockB_gbf07 3对，ON/OFF成对 well-formed）。
- leg两行switches=0/brakes=0/mode=A或B（单腿无switch无刹车，与披露一致）。

## 4. 未来函数与口径审查（读码：K5脚本全181行、`research/switch_engine.py`锁逻辑、`research/sweep_beat_h1_v4.py:35-51`刹车语义）

1. 单腿`run_leg`（K5脚本106–125行）：直接复用`get_shadows`的ra/rb——即M07同口径`pc.run_strategy`（capital 50000/slip 0.002/lot 100/cost_one_way=None/同RUN_START/EVAL_END/legacy_grid=False/full_liquidate=True，phase=0）——**执行与费用口径与M07腿完全一致**；无switch/无刹车已在mechanism字段披露，非隐藏口径漂移。
2. 锁定`lock_mode`（`switch_engine.py:43/87/171`）：原生引擎参数（docstring载明回归断言在`run_switch_backtest.py`）；lock下`desired=mode`恒成立、RS比较被短路（171行`lock_mode is None`门控），**无新增前视面**；执行/调仓/费用走同一`do_rebalance`/`buy_cost/sell_cost`路径，同口径。
3. 去刹车`bx=10.0`：刹车ON条件为`(peak−eq)/peak >= BRAKE_X`（`sweep_beat_h1_v4.py:43`），bx=10即需1000%回撤=**永不触发**，by/bf保留但恒惰（alloc乘子恒1.0）；`brake_log=[]`复跑证实。费用方向一致：去刹车后cost上升（nobrake_M07 59488>50990、nobrake_gbf07 61046>57657；slip04下98212），**无漏计、无双计**。
4. RS变体（rs=30/120）：仅`rs_lookback`阈值，trailing RS（`switch_engine.py:93-99` searchsorted right−1），无前视。
5. 止盈止损联动（b_take+stop）：均为原生策略参数（take进CFG_B、stop进CA）；stop作用于双腿全局——mechanism字段已披露“全局stop”，非隐藏漂移；执行t+1（stop_exec=next，沿用batch_016结论）偏保守。
6. AB互换（swap_*）：仅N/R（n/rebal）对调，MAX窗（win_a=40/win_b=20）、band/gate保留原腿标签——属**不完全互换**（设计选择，已在§5记录；结果崩−1400pp级，无达标误判风险）。全为静态参数，无前视。
7. `judge`严格>与`win_all=mdd>−27.05`（K5脚本76–81行）与K2/K4逐字一致；base校准assert（177–179行）通过。
8. 已知caveat（非FAIL，与M07同口径故对比公平）：ffill盯市、静态快照伪市值、幸存者偏差、单样本（沿用batch_016 §4第7条）。

结论：**未发现未来函数，未发现口径不一致，未发现费用漏计/双计**，T6未触发。

## 5. 对K5文件的逐项核对

- 20行 = 1 base + 19机制（单腿2/锁定4/去刹车2/RS变体4/联动4/互换3），与脚本CFGS（127–154行）逐一对应，无缺行、无FAIL行。
- `beat_all`全false、`win_all`全false；nbeat_m07分布4×2/2×2/1×4/0×12；max nbeat=4。独立重算nbeat（`part_k5scan.json`）mismatches为空。
- `switch_same_m07`：仅base与nobrake两行为true，其余全false（单腿/锁定天然false，rs/pair/swap节拍漂移）。
- 与K1–K4交叉一致性：gbf07基座行（lockA_gbf07等）cut/bx/bf参数与K3 g_bf07一致；nobrake_M07基座=M07逐字参数+bx10。
- 措辞修正：K5脚本docstring称unanimous/反转逻辑“跳过”（14行）——诚实披露未测方向，不构成缺陷；swap系“角色互换”实为N/R-only互换（§4-6），建议后续改称“慢腿快腿N/R对调”以免误读（文档瑕疵，不影响数字）。

## 6. 认错条件（原文，沿用batch_017 §6并适配“超M07”目标；T1已在batch_017对g_bf07触发，本轮为延续线）

- T1（相位运气）：若候选相对M07的total优势在异相位下反转，则认错ph0优势主要来自相位运气。K5无beat_all/nbeat>=5候选 → **moot，未触发**；家族层面观察（非认错线）：nobrake_gbf07 ph15 total −63.77/0/6+mdd深5.40，去刹车edge同样无跨相位稳健性。
- T2（邻域过拟合）：若邻域内出现nbeat更高者，则认错最优点为噪声峰。K5最高nbeat=4，无更高者 → **未触发**。
- T3（集中赌博）：若剔除Top3后候选total转负或落后M07 ex-top3，则认错增量来自少数彩票股。无候选 → **moot，未触发**（备查：最强两行top3_share均为26.3%，与M07 26.4%一致，非集中）。
- T4（成本鲁棒）：若同成本基线候选对M07 nbeat<3或mdd不再更浅，则认错edge不具成本鲁棒性。无候选 → **moot，未触发**（备查：nobrake_gbf07@0.004对同成本M07为5/6但1m打平+mdd深2.48，墙在双倍成本下依然成立）。
- T5（择时运气）：若复现switch_log与M07不一致，则认错增量来自切换时点漂移。最强两行逐字一致 → **未触发**（增量纯属去刹车暴露度）。
- T6（前视/口径）：若发现任一未来函数或口径（本金/费率/整手/起止/网格/执行/费用）不一致，直接判FAIL。§4八项检查通过 → **未触发**。

## 7. verdict与建议

- verdict：**FAIL**（K5 19新机制 beat_all=0、win_all=0；K1–K5累计**105配 beat_all=0**；最强新机制（去刹车）以1m/3m短窗−0.01~−0.04pp+mdd更深双卡止步4/6，单腿/B腿直跑/AB互换分别以−592/−1296/−1400pp级差距出局；家族T1类失败延续，无FAIL项但目标落空故不判PASS_WITH_WARNINGS）。
- 差距数量级总表（相对M07 total 1863.27/mdd −27.05）：去刹车 +319~+380pp但mdd深1.35~5.05（4/6）；单腿A −592.65pp/mdd深18.35（0/6）、单腿B −1296.19pp（2/6）；锁定 −508~−1357pp；RS变体 −340~−740pp；联动 −112~−585pp；互换 −1384~−1527pp（0/6）。
- 建议：① 终结“六窗全超M07+mdd更浅”硬目标下的阈值/机制双线搜索（105配0全胜，短窗墙−0.01~−0.04pp五轮不动）；② 任何后续方向（若重启）须先过跨相位total≥4胜+T6口径双门槛再谈晋级；③ paper-track维持M07（batch_016结论不变），K5任何行不得实盘。
- 本报告产物清单（仅`team/audit/batch_019/`）：`audit_m07k5_review.md`、`work_k5scan.py`、`work_k5scan2.py`、`part_k5scan.json`、`work_gap_prep.py`、`part_gap_prep.json`、`work_k5dump.py`、`work_k5logchk.py`、`work_k5deep.py`、`part_k5deep.json`。
