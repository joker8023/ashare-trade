# M07“六窗全超自己”K6信号源级独立复核（batch_020_m07k6）

- 复核对象：K6信号源级sweep 8配（`results/r30_bt/sweep_beat_m07_k6.json`：1 base_M07 + 7新：因子3配 both_amihud/Aleg_amihud/Bleg_amihud + MAX-cut非对称4配 cut75_both/cut85_both/asym_A78B82/asym_A82B78），目标：六窗全超M07且回撤更浅（`win_all = beat_all && mdd_better`，beat_all为六窗严格>）。
- M07基线：`results/r30_bt/M07_final.json`（total 1863.27，mdd −27.05，1m −4.09/3m 17.28/6m 39.00/1y 164.05/2y 1474.08/3y 1677.53）。
- 复核人：review子agent（agent-10），只读复算 + 自写引擎重跑（仿 `research/valid_m07_k3ph.py` 结构，只新增 `team/audit/batch_020_m07k6/` 内文件，未改主流程）。
- 基准口径（与M07逐字一致，读码确认）：2020新浪口径ph0，RUN_START=2023-01-03，EVAL_END=2026-11-12，5万本金，现实费率+滑点0.002，整手100股，只做多，不加杠杆，legacy_grid=False，full_liquidate=True，stop=0.25/stop_exec=next，A腿N5/R20/take1.2/B腿N4/R30/take0.80；K6仅动因子串（amihud_60↔amihud）与MAX-cut（0.75/0.78/0.82/0.85），其余逐字一致。
- 结论：**FAIL** —— K6共8行 `beat_all=0`、`win_all=0`，最高nbeat仅2（cut75_both，赢6m/1y两个中窗、1m打平0.00）；K1–K4累计86行叠加K5的19新配、K6的7新配，**累计112配 beat_all=0**（任务书“125配”为K6按20配的前置假设，实际K6脚本CFGS仅8行、SKIPPED 4个引擎不支持的非原生因子，见§5）。T1–T6认错条件本轮均未触发（无beat_all/nbeat>=5候选故T1/T3/T4 moot，见§6），T6口径审查通过（无未来函数、无口径漂移；size+MAX交互因size从未进引擎而moot，见§4）。

## 0. 一句话结论与证伪数字

- 一句话：K6的7个信号源新配无一六窗全超M07，最强的cut75_both以2/6（1m打平、3m差−0.02pp）+mdd更深0.31止步，因子行（amihud短窗）全线崩−310~−689pp，判FAIL、信号源级撞墙确认。
- 证伪数字（详见§3，每项均给命令/文件/参数）：
  1. 独立复算误差：最强三行（cut75_both/Aleg_amihud/asym_A82B78）自跑与K6文件total/mdd/六窗**最大偏差0.00**，trades/cost/mode/switch_log一致性逐项一致。命令：`.venv/bin/python team/audit/batch_020_m07k6/work_k6deep.py`（产物`part_k6deep.json:repro`）。
  2. 全文件独立重算nbeat/beat_all/win_all/mdd_better：**0 mismatch**；base_M07行与M07_final六窗/total/mdd逐值偏差0.00（脚本assert级校准通过才落盘）。命令：`.venv/bin/python team/audit/batch_020_m07k6/work_k6scan.py`（产物`part_k6scan.json`）。
  3. 最强新配六窗差（cut75_both−M07，pp）：**0.00/−0.02/+0.16/+0.03/−0.01/−49.35**（2/6，total 1630.77落后232.50，mdd −27.36深0.31）——1m打平（严格>失败）+3m差−0.02pp，与K1–K5最强行的**短窗墙同构**（K1 k05_by05的−0.02/−0.04、K5 nobrake的−0.01/−0.04）。
  4. 因子行崩盘数量级：both_amihud nbeat0，total **1215.52**（落后**−647.75**），六窗−0.19/−11.17/−12.00/−75.59/−590.36/−689.24，切换13次（节拍全漂）；Bleg_amihud nbeat0 total 1048.76（−814.51，mdd −34.69深7.64，终态mode A）；Aleg_amihud nbeat1（仅赢1m +0.01）total 1487.70（−375.57），切换5次。
  5. 跨相位（自跑同口径 vs 已审计`batch_017/part_gph.json` M07相位值）：cut75_both ph5 total 524.92 vs 755.73（**−230.81**，1/6）/ ph15 681.45 vs 609.80（+71.65，4/6，mdd浅6.90但1m/3m仍败−0.04/−0.07）；Aleg_amihud ph5 −137.84（1/6）/ ph15 +465.96（3/6，1m/3m/6m全败）；asym_A82B78 ph5 total −1.36（5/6但mdd −33.33深1.72→双杀）/ ph15 −100.88（1/6）。**无一异相位同时满足total反超+mdd更浅+六窗≥5**。
  6. 滑点加倍（cut75_both@0.004 total **1428.18**/mdd −26.47/cost 45188→**73730**费用连贯上升，对同成本M07@0.004 total 1595.72/mdd −27.63/六窗−4.45/15.87/35.85/153.00/1333.42/1472.71）：六窗差 **+0.01/+0.03/−0.09/−0.44/−1.41/−14.57** → 2/6，total落后167.54——墙在双倍成本下纹丝不动（且mdd浅1.16亦救不了2/6）。
- 认错条件触发情况（原文见§6）：**本轮T1–T6均未触发**（T1/T3/T4因无beat_all或nbeat>=5候选而moot；T2最高nbeat=2无更高邻点；T5最强行switch逐字一致；T6八项口径检查通过）。家族层面撞墙确认（非认错线，见§6）。
- 报告文件：`team/audit/batch_020_m07k6/audit_m07k6_review.md`（本文件）；脚本/产物：`work_k6scan.py`→`part_k6scan.json`、`work_k6deep.py`→`part_k6deep.json`。

## 1. 复核对象与证据链

| 项目 | 值 |
|---|---|
| K6脚本 | `research/sweep_beat_m07_k6.py`（116行）：`build_ns_ab`（复刻刹车语义的字符串补丁+factor_a/factor_b按mode路由）+ `get_shadows`（MaxInputs双腿shadow，factor可变）+ `run_one`（switch引擎，phase/slip可参）+ base校准；CFGS 8组（1 base + 7新）；SKIPPED披露4个引擎不支持的非原生因子 |
| K6文件 | `results/r30_bt/sweep_beat_m07_k6.json`：8行，字段= K2/K4/K5 schema（tag/factor_a/factor_b/cut/win/total/mdd/trades/cost/mode/switches/brakes/switch_log/brake_log/六窗+nbeat/beat_all/mdd_better/win_all/switch_same） |
| 分组 | 因子both/Aleg/Bleg ×3；MAX-cut cut75/cut85/asym_A78B82/asym_A82B78 ×4 |
| 本次复核脚本/产物 | `team/audit/batch_020_m07k6/work_k6scan.py`→`part_k6scan.json`（8行schema+nbeat重算+候选挑选）；`work_k6deep.py`→`part_k6deep.json`（最强三行复跑+exTop3+ph5/ph15×3+slip04，共10次switch引擎运行） |

口径核对（读K6脚本源码+复跑）：capital=50000、slip=0.002（T4另跑0.004）、lot=100、cost_one_way=None、RUN_START/EVAL_END/MB/legacy_grid/full_liquidate/stop/stop_exec/N-R/rebal/take/exposure与`run_m07_final.py`逐字一致；phase仅本复核自用且同相位对比口径成立。K6 base_M07行total/mdd/六窗与`M07_final.json`逐值一致（`part_k6scan.json` base dev全0.00）。

## 2. 独立复算（最强三行）

方法：自写脚本（仿`valid_m07_k3ph.py`结构，不import主引擎统计函数，total/mdd/六窗公式自写），用K6同口径参数重跑cut75_both、Aleg_amihud、asym_A82B78（ph0/slip0.002），逐字段对比。

命令：`.venv/bin/python team/audit/batch_020_m07k6/work_k6deep.py`（产物`part_k6deep.json:repro`）。

| 指标 | cut75自跑 | 文件 | 差 | Aleg自跑 | 文件 | 差 | A82B78自跑 | 文件 | 差 |
|---|---|---|---|---|---|---|---|---|---|
| total/mdd | 1630.77/−27.36 | 同 | 0.00 | 1487.70/−27.25 | 同 | 0.00 | 1825.92/−25.35 | 同 | 0.00 |
| trades/cost/mode | 184/45188/B | 同 | 0 | 203/48107/B | 同 | 0 | 184/51606/B | 同 | 0 |
| 六窗 | −4.09/17.26/39.16/164.08/1474.07/1628.18 | 同 | 0.00 | −4.08/11.89/34.14/126.82/1078.42/1367.29 | 同 | 0.00 | −4.11/15.13/33.36/153.38/1411.56/1643.71 | 同 | 0.00 |
| switch_same/brake | true/3对 | 同 | 一致 | false/2对 | 同 | 一致 | true/3对 | 同 | 一致 |

数值字段最大偏差**0.00** → K6数字可复现。注：cut75_both与asym_A82B78的ph0 switch_log与M07逐字一致（3次：2023-06-21→B，2024-08-15→A，2026-09-08→B）；Aleg_amihud节拍漂移（5次切换，见§3f）。

## 3. 证伪清单执行结果

### (a) 最强新配六窗差（cut75_both − M07，pp）

| 行 | 1m | 3m | 6m | 1y | 2y | 3y | nbeat | total_gap | mdd_gap |
|---|---|---|---|---|---|---|---|---|---|
| cut75_both | 0.00 | −0.02 | +0.16 | +0.03 | −0.01 | −49.35 | 2 | −232.50 | −0.31 |
| Aleg_amihud | +0.01 | −5.39 | −4.86 | −37.23 | −395.66 | −310.24 | 1 | −375.57 | −0.20 |
| asym_A82B78 | −0.02 | −2.15 | −5.64 | −10.67 | −62.52 | −33.82 | 0 | −37.35 | +1.70 |

cut75_both赢6m/1y两个中窗、1m打平（严格>失败，主因之一）、3m差−0.02pp——与K1–K5最强行完全相同的**短窗墙**（1m∈{打平,−0.01,−0.02}、3m∈{−0.02,−0.03,−0.04}六轮不动）。asym_A82B78是全场唯一mdd更浅行（−25.35浅1.70）但nbeat=0（六窗全败，1m −0.02/3m −2.15起即崩），mdd_better救不了晋级。

### (b) 因子行崩盘数量级（文件值，§2复算方法已验证引擎可信）

| 行 | nbeat | total | total_gap | mdd | 六窗差 |
|---|---|---|---|---|---|
| both_amihud | 0 | 1215.52 | **−647.75** | −28.78 | −0.19/−11.17/−12.00/−75.59/−590.36/−689.24（全败，切换13次） |
| Bleg_amihud | 0 | 1048.76 | **−814.51** | −34.69（深7.64） | −1.53/−5.18/−6.02/−12.64/−402.20/−541.38（全败，终态mode A，切换12次） |
| Aleg_amihud | 1 | 1487.70 | −375.57 | −27.25 | +0.01/−5.39/−4.86/−37.23/−395.66/−310.24（仅赢1m +0.01pp，切换5次） |

amihud（20日）相对amihud_60（60日）的短窗化=把B腿拖成高频换手（13/12次切换 vs M07的3次）+长窗崩−400~−690pp。因子方向死刑：短因子无一胜出中长窗。

### (c) MAX-cut非对称行（文件值，nbeat重算0 mismatch）

- cut75_both（双腿cut 0.80→0.75）：nbeat2（§3a），trades 184/cost 45188（低于M07的50990，换手略降但total仍落后232pp）。
- cut85_both（双腿cut→0.85）：nbeat0，total 1614.56（−248.71），六窗全败（−0.91/−3.22/−7.19/−14.13/−199.40/−225.18），切换节拍漂移（same=false）。放宽MAX过滤即引入彩票尾部，长窗−200pp级惩罚。
- asym_A78B82（cut_a 0.78/cut_b 0.82）：文件值与base**逐值相同**（total/mdd/六窗差全0.00，switch_same=true）——两侧cut一紧一松恰好零净效应（边际MAX股票从未被选中），非引擎bug（费用/笔数口径一致），属诊断性零结果。
- asym_A82B78（cut_a 0.82/cut_b 0.78）：nbeat0但mdd −25.35（全场最浅，+1.70），total 1825.92（−37.35，最接近M07的total），六窗−0.02/−2.15/−5.64/−10.67/−62.52/−33.82。回撤与窗口不可兼得。

### (d) 跨相位（自跑同相位 vs 已审计M07相位值`batch_017/part_gph.json`）

| 行@相位 | 自跑total | M07 total | 差 | 同相位nbeat | mdd |
|---|---|---|---|---|---|
| cut75@ph5 | 524.92 | 755.73 | **−230.81** | 1 | −31.52/−31.61（浅0.09） |
| cut75@ph15 | 681.45 | 609.80 | +71.65 | 4 | −20.25/−27.15（浅6.90，但1m/3m仍败） |
| Aleg@ph5 | 617.89 | 755.73 | **−137.84** | 1 | −23.87/−31.61 |
| Aleg@ph15 | 1075.76 | 609.80 | +465.96 | 3 | −24.56/−27.15（1m/3m/6m全败） |
| A82B78@ph5 | 754.37 | 755.73 | −1.36 | 5 | −33.33/−31.61（深1.72→total+mdd双杀） |
| A82B78@ph15 | 508.92 | 609.80 | **−100.88** | 1 | −28.08/−27.15（深） |

说明：A82B78@ph5的5/6是异相位值（目标相位ph0该行nbeat=0），且total落后+mdd更深，不构成“漏网候选”（晋级目标只认ph0；即便跨相位口径下win_all亦失败）。cut75 ph15的4/6+mdd浅是K6全场最接近跨相位稳健的点，但1m/3m短窗仍败（−0.04/−0.07）——同一堵墙。

### (e) ex-top3与滑点加倍（备查：无候选故moot，但作为撞墙数量级证据执行）

- ex-top3（同脚本trades net_pnl独立重算）：cut75_both top3_share **26.6%** / ex-top3 total **1178.67**（vs M07 1351.75，落后173.08）；Aleg 28.8%/1043.99；A82B78 27.6%/1302.42（vs M07 1351.75仍落后49.33）。三行集中度与M07（26.4%）同量级，**无集中赌博也救不了落后**。
- 滑点加倍（cut75_both@0.004 total **1428.18**/mdd −26.47/cost **73730** vs 同成本M07@0.004 total 1595.72/mdd −27.63/六窗−4.45/15.87/35.85/153.00/1333.42/1472.71）：六窗差+0.01/+0.03/−0.09/−0.44/−1.41/−14.57 → **2/6**，total落后167.54（mdd虽浅1.16但nbeat不过半）。**墙在双倍成本下纹丝不动**（ph0的2/6原样复制到同成本口径）。

### (f) 切换/刹车节拍

- cut75_both/asym_A82B78 ph0 switch_log与M07**逐字一致**（3次）→ 增量（正负皆有）纯属持仓差异，无择时运气，T5未触发。
- cut75刹车3对（ON/OFF日期漂移：末两对ON提前至2024-02-22/恢复10.04–10.08 vs M07的2024-01-31/19.70），系持仓路径差异的正常结果（batch_016 §3e措辞延续）。
- 因子行节拍全漂移：both_amihud 13次、 Bleg_amihud 12次（终态mode A）、Aleg_amihud 5次切换，`switch_same`全false——短因子=择时漂移器，长窗崩的机制解释。
- 费用方向一致：cut75 cost 45188<M07 50990（换手略降）；slip04下73730单调上升，无漏计；因子行cost 36335~48494（换手高但单笔小，无费用异常）。

## 4. 未来函数与口径审查（读码：K6脚本全116行、`prior_check.py:51-98`因子矩阵、`design_r30_grid8.py:23-47`门限、`fresh2_max.py:15-31` MAX过滤）

1. 因子前视：`amihud`/`amihud60`均为`rolling(20/60, min_periods).mean()` trailing均值（`prior_check.py:63-64`）；MAX过滤`maxret = ret.rolling(max_win).max()` trailing（`fresh2_max.py:18`）；gate `ret60/ret10 = close/close.shift(60/10)` trailing（`design_r30_grid8.py:27-28`）；seasoned `close.shift(250).notna()` trailing；市值截面`cap.loc[t]`分位为**同t截面**（与M07同一口径，无前视）。`picks(t)`只用`t`时刻已实现量 → **只用t及以前数据**，通过。
2. factor_a/factor_b路由（K6脚本44行字符串补丁）：按mode选择传入`picks`的`factor`串，`amihud_60↔amihud`二选一（`prior_check.py:86`三元，**其余任意字符串一律回退amihud20**——引擎原生约束，非K6引入）。与刹车补丁同bar语义（contemporaneous），无新增前视面。
3. **size因子+MAX彩票过滤的交互**：**moot**——size/amount_level/liq_size/amihud_5四个非原生因子在引擎层不受支持（`Inputs.picks`签名外），K6脚本以SKIPPED披露未测（102行），**没有任何一行实际混用size排序与MAX过滤**，故不存在已发生的冲突；该交互仍是未探明方向（见§7），不是已审计结论。
4. `judge`严格>与`win_all`（K6脚本86–90行）与K2/K4/K5逐字一致；base校准（`part_k6scan.json` base dev全0.00）通过。
5. 已知caveat（非FAIL，与M07同口径故对比公平）：ffill盯市、静态快照伪市值、幸存者偏差、单样本（沿用batch_016 §4第7条）。

结论：**未发现未来函数，未发现口径不一致，未发现费用漏计/双计**，T6未触发。发现未来函数直接FAIL条款本轮不启用。

## 5. 对K6文件的逐项核对

- 8行 = 1 base + 7新（因子3/MAX-cut 4），与脚本CFGS（92–101行）逐一对应，无缺行、无FAIL行。
- `beat_all`全false、`win_all`全false；nbeat_m07分布：2×1、1×1、0×6；max nbeat=2。独立重算（`part_k6scan.json`）mismatches为空。
- `switch_same_m07`：true仅base/cut75_both/asym_A78B82/asym_A82B78（cut系保节拍），因子行全false。
- **计数口径澄清**：任务书“累计125配”以K6=20配为前置假设；实际K6脚本CFGS仅8行（1校准+7新），SKIPPED 4个非原生因子并落盘声明。故累计口径（沿用batch_019：K1–K4行数86 + K5新19 + K6新7）= **112配 beat_all=0**，不是125。差异来自K6产出规模，非复核口径变更。
- 措辞修正：K6 docstring称cut变体“MAX-cut asym”为切分位非对称（win保持40/20）——准确；asym_A78B82的零净效应已在§3c解释为边际股票从未入选，非“参数无效”误判。

## 6. 认错条件（原文，沿用batch_017 §6并适配“超M07”目标；T1已在batch_017对g_bf07触发，本轮为延续线）

- T1（相位运气）：若候选相对M07的total优势在异相位下反转，则认错ph0优势主要来自相位运气。K6无beat_all/nbeat>=5候选 → **moot，未触发**；家族层面观察（非认错线）：cut75 ph5 total −230.81反转、Aleg ph5 −137.84反转、A82B78 ph15 −100.88反转——信号源edge同样无跨相位稳健性。
- T2（邻域过拟合）：若邻域内出现nbeat更高者，则认错最优点为噪声峰。K6最高nbeat=2，无更高者 → **未触发**。
- T3（集中赌博）：若剔除Top3后候选total转负或落后M07 ex-top3，则认错增量来自少数彩票股。无候选 → **moot，未触发**（备查：最强三行top3_share 26.6/28.8/27.6%与M07 26.4%同量级，ex-top3仍落后M07 49~308pp）。
- T4（成本鲁棒）：若同成本基线候选对M07 nbeat<3或mdd不再更浅，则认错edge不具成本鲁棒性。无候选 → **moot，未触发**（备查：cut75@0.004对同成本M07为2/6+mdd浅1.16，墙在双倍成本下依然成立）。
- T5（择时运气）：若复现switch_log与M07不一致，则认错增量来自切换时点漂移。最强行（cut75_both）逐字一致 → **未触发**（因子行漂移但nbeat≤1，无晋级误判风险）。
- T6（前视/口径）：若发现任一未来函数或口径（本金/费率/整手/起止/网格/执行/费用）不一致，直接判FAIL。§4五项检查通过 → **未触发**。

## 7. verdict与建议

- verdict：**FAIL**（K6 7新配 beat_all=0、win_all=0；K1–K6累计**112配 beat_all=0**；最强新配（cut75_both）以1m打平/3m差−0.02pp+mdd更深0.31止步2/6，因子短窗化/MAX放宽/AB非对称cut全部出局；家族T1类失败延续，无FAIL项但目标落空故不判PASS_WITH_WARNINGS）。
- 差距数量级总表（相对M07 total 1863.27/mdd −27.05）：因子行 −376~−815pp（0~1/6，切换5~13次）；cut75 −232.50pp（2/6,mdd深0.31）；cut85 −248.71pp（0/6）；asym_A78B82 ±0.00pp零净效应（0/6）；asym_A82B78 −37.35pp但mdd浅1.70（0/6）。
- 全域结论：在当前数据与引擎下，**同切换族（阈值/cut/刹车/RS/相位袖/单腿/锁定/去刹车/联动/互换/因子-cut信号源）不存在六窗全超M07且回撤更浅的策略**——六个正交族112配零全胜，且短窗墙（1m∈{打平,−0.01,−0.02pp}、3m∈{−0.02,−0.03,−0.04pp}）六轮纹丝不动。
- 唯一残留的未探明方向（**不是达标、不是晋级依据**，重启须重立T线）：① 非原生因子（size/amount_level/liq_size/amihud_5）需新`Inputs`实现+全套T1–T6重审（含size×MAX交互这个本轮moot项）；② batch_017遗留bf0.8邻点（单调轴未测完）。除此之外阈值/机制/信号源三线搜索应终结；paper-track维持M07，K6任何行不得实盘。
- 本报告产物清单（仅`team/audit/batch_020_m07k6/`）：`audit_m07k6_review.md`、`work_k6scan.py`、`part_k6scan.json`、`work_k6deep.py`、`part_k6deep.json`。
