# M07“六窗全超自己”K3独立复核（batch_017）

- 复核对象：K1/K2/K3三轮正交回测（`results/r30_bt/sweep_beat_m07_k1.json` 30配 / `sweep_beat_m07_k2.json` 9配 / `results/r30_bt/sweep_beat_m07_k3.json` 29配），目标：六窗全超M07且回撤更浅（`win_all = beat_all && mdd_better`）。
- M07基线：`results/r30_bt/M07_final.json`（total 1863.27，mdd −27.05，1m −4.09/3m 17.28/6m 39.00/1y 164.05/2y 1474.08/3y 1677.53）。
- 复核人：review子agent（agent-4），只读复算 + 自写引擎重跑（仿 `research/valid_m07_k3ph.py` 结构，只新增 `team/audit/batch_017/` 内文件，未改主流程）。
- 基准口径（与M07逐字一致）：2020新浪口径，RUN_START=2023-01-03，EVAL_END=2026-11-12，5万本金，现实费率+滑点0.002，整手100股，只做多，不加杠杆，legacy_grid=False，full_liquidate=True。
- 结论：**FAIL** —— K1+K2+K3共68配（去重66）`beat_all=0`、`win_all=0`，晋级目标未达成；唯一nbeat≥5候选g_bf07止步5/6（1m差−0.01pp），且T1相位运气认错条件**触发**（异相位total 5连败）。1m缺口为舍入无关的端点结构墙（区间不重叠论证，见§3a）。

## 0. 一句话结论与证伪数字

- 一句话：三轮68配无一六窗全超M07，最接近的g_bf07以5/6+mdd浅2.77pp止步，1m落后0.01pp且异相位total全败，判FAIL、不晋级。
- 证伪数字（详见§3，每项均给命令/文件/参数）：
  1. 独立复算误差：g_bf07自跑与K3文件15字段（total/mdd/trades/cost/mode/switches/六窗/nbeat/mdd_better/switch_same）**最大偏差0.00pp**，switch_log/brake_log逐字一致；M07@滑点0.004自跑与batch_016产物`part2_slip.json`8字段逐值一致（total 1595.72）。命令：`.venv/bin/python team/audit/batch_017/work_audit_m07k3_gbf07.py`（产物`part_gbf07.json`）。
  2. 多相位同口径total差（候选−M07，同相位，pp）：g_bf07为 ph0 **+265.14**（但nbeat仅5/6）、ph5 **−67.62**、ph7 **−45.56**、ph10 **−86.95**、ph14 **−125.80**、ph15 **−82.02**（异相位5连败）；同相位nbeat为4/0/1/2/2，无一相位≥5。兜底候选g（K2）同样total 5连败（−114.35/−45.56/−128.39/−108.90/−87.03）。M07相位数据复用同口径审计自跑`part_gph.json`（命令`.venv/bin/python team/audit/batch_017/work_audit_m07k3_gph.py`）。
  3. 邻域稳健性：K1+K2+K3最高nbeat=5（仅g_bf07），次高4（K1：k05/k25；K2：a/b/c/d/e/f/g；K3：s_rs70/g_bx20/g_rs70/g_winA30）；g_bf07的bf轴邻点bf0.5→nbeat1、bf0.6→nbeat4、bf0.7→nbeat5（单调递增，bf0.8未测，残留风险）；g_winA30以total 2400.08/mdd −22.95双优于g_bf07但nbeat仅4。T2严格线（邻域出现nbeat更高者）未触发。
  4. 剔除Top3：g_bf07 top3_share **26.3%**、extop3_total **1545.93**，超M07 ex-top3（1351.75）**+194.18pp**，非集中赌博（同脚本trades独立重算；g为26.3%/1512.95，+161.20pp）。
  5. 成本压力：滑点加倍（0.002→0.004）g_bf07 total **1834.96**（−293.45pp），对原M07基线0/6；**同成本基线**（M07@0.004：total 1595.72，mdd −27.63，六窗−4.45/15.87/35.85/153.00/1333.42/1472.71）下g_bf07为**5/6**（差值−0.01/+0.06/+0.12/+0.41/+9.66/+176.61），total **+239.24**、mdd浅**2.91pp**——1m墙在双倍滑点下纹丝不动（−0.01pp）。
  6. 切换节拍与口径：g_bf07 ph0 switch_log与M07**逐字一致**（2023-06-21→B，2024-08-15→A，2026-09-08→B，3次）；跨相位switches为3/10/8/13/12/12（M07为3/9/7/13/12/10），终态ph5/7/14/15为A模式，相位敏感互证；刹车同日期、幅度漂移（末次OFF提前至2024-08-16恢复6.15 vs M07的2024-09-13恢复18.53），系持仓路径漂移正常现象。T6：同引擎源码，仅cut/by/bx/bf阈值差异（trailing截面分位/同bar盯市），无未来函数、无口径不一致（读码`research/fresh2_max.py:27`、`research/sweep_beat_h1_v4.py:35-54`）。
- 认错条件触发情况（原文见§6）：**T1触发**（异相位total 5连败+mdd 4/5更深），T2/T3/T4/T5/T6均未触发（T2有bf单调未测残留、T4绝对收益缩水293pp两项WARNING）。
- 报告文件：`team/audit/batch_017/audit_m07k3_review.md`（本文件）；脚本/产物：`team/audit/batch_017/work_audit_m07k3_gph.py`、`work_audit_m07k3_gbf07.py`、`part_gph.json`（13行）、`part_gbf07.json`（7行）。

## 1. 复核对象与证据链

| 项目 | 值 |
|---|---|
| K1 | `research/sweep_beat_m07_k1.py` → `results/r30_bt/sweep_beat_m07_k1.json`：30配（含base复现行），max nbeat=4（k05_by05、k25_cut78），beat_all=0 |
| K2 | `research/sweep_beat_m07_k2.py` → `results/r30_bt/sweep_beat_m07_k2.json`：9配（含base），max nbeat=4（a/b/c/d/e/f/g共7配），beat_all=0；最接近g_by05_cut78_bx15（nbeat4，mdd −22.87，1m/3m差−0.01/−0.03pp） |
| K3 | `research/sweep_beat_m07_k3.py` → `results/r30_bt/sweep_beat_m07_k3.json`：29配（含base），max nbeat=5（仅g_bf07），beat_all=0，win_all=0 |
| 候选g_bf07 | by0.05 + cutA/B 0.78 + bx0.15 + bf0.7，其余与M07逐字一致（K3 CFGS第95行）；K3行：total 2128.41，mdd −24.28，trades 184，cost 57657，mode B，3切换，六窗−4.10/17.29/39.30/164.90/1487.61/1875.48，对M07差−0.01/+0.01/+0.30/+0.85/+13.53/+197.95，nbeat=5，mdd_better=true，switch_same_m07=true |
| 本次复核脚本/产物 | `team/audit/batch_017/work_audit_m07k3_gph.py`（g多相位+滑点）→`part_gph.json`；`team/audit/batch_017/work_audit_m07k3_gbf07.py`（g_bf07 T1-T6）→`part_gbf07.json` |

口径核对（读K3脚本源码+复跑）：capital=50000、slip=0.002（T4另跑0.004）、lot=100、cost_one_way=None、RUN_START/EVAL_END/MB/legacy_grid/full_liquidate与`run_m07_final.py`一致；phase仅本复核多相位部分使用（K3全为ph0）；g_bf07与M07差异仅by 0.05/cut 0.78/bx 0.15/bf 0.7四个阈值。K3 base_M07行与`M07_final.json`六窗逐值一致（复核脚本独立确认）。

## 2. 独立复算（T1-复现性）

方法：自写脚本（仿`valid_m07_k3ph.py`结构，不import主引擎`_mdd/WINDOWS`之外的任何结果，公式自写），用K3同口径参数重跑g_bf07，与K3文件逐字段对比。

命令：`.venv/bin/python team/audit/batch_017/work_audit_m07k3_gbf07.py`（产物`part_gbf07.json`首行）。

| 指标 | 自跑 | K3文件 | 差 |
|---|---|---|---|
| total/mdd | 2128.41/−24.28 | 同 | 0.00 |
| trades/cost/mode/switches | 184/57657/B/3 | 同 | 0 |
| 1m/3m/6m | −4.10/17.29/39.30 | 同 | 0.00 |
| 1y/2y/3y | 164.90/1487.61/1875.48 | 同 | 0.00 |
| nbeat/mdd_better/switch_same | 5/true/true | 同 | 一致 |
| switch_log/brake_log | 逐字一致（含brake 3×ON/OFF，末次OFF 2024-08-16恢复6.15） | 同 | 一致 |

最大偏差**0.00pp** → K3数字可复现，通过复现性部分。另：M07@滑点0.004自跑（本脚本附带）与batch_016产物`part2_slip.json`8字段逐值一致（total 1595.72等），交叉确认T4基线可靠。

## 3. 证伪清单执行结果（g_bf07为主，g为佐证）

### (a) 多相位同口径对比（g_bf07 − M07，同相位；M07侧引自`part_gph.json`）

| 相位 | g_bf07 total | M07 total | 差(pp) | 同相位nbeat | mdd(g/m07) |
|---|---|---|---|---|---|
| ph0 | 2128.41 | 1863.27 | **+265.14** | 5/6 | −24.28/−27.05（浅2.77） |
| ph5 | 688.11 | 755.73 | **−67.62** | 4/6 | −35.71/−31.61（深） |
| ph7 | 1081.96 | 1127.52 | **−45.56** | 0/6 | −17.20/−17.20（平） |
| ph10 | 410.97 | 497.92 | **−86.95** | 1/6 | −29.73/−28.47（深） |
| ph14 | 354.84 | 480.64 | **−125.80** | 2/6 | −32.80/−30.23（深） |
| ph15 | 527.78 | 609.80 | **−82.02** | 2/6 | −29.19/−27.15（深） |

ph0的+265pp total优势在异相位下**全部反转**（5连败，−45~−126pp），mdd 4/5更深 → **T1触发**：ph0优势主要来自相位运气，不可跨相位推广。g（K2，bf0.6版本）同样total 5连败（−114.35/−45.56/−128.39/−108.90/−87.03），结论一致。

**1m端点结构墙论证**：ph0的1m缺口−0.01pp与舍入无关——文件值g_bf07 −4.10（真值∈[−4.105,−4.095)）vs M07 −4.09（真值∈[−4.095,−4.085)），区间不重叠，必败；滑点加倍后同成本1m仍为−4.46 vs −4.45（−0.01pp，同样区间不重叠）→ 该缺口不受成本缩放影响，是固定端点划分下的结构性落后，非相位运气可解释（异相位下g_bf07的1m对M07为4胜1平：−6.97>−9.34、−8.38<−8.08、−7.65>−7.76、−7.72>−7.78、−7.45>−7.47——短窗本身可胜，唯独ph0端点组合下必败）。

### (b) 邻域稳健性

- bf轴（by05+cut78+bx15固定）：bf0.5（g_bf05）nbeat1/total 1819.65/mdd −21.99 → bf0.6（g）nbeat4/2084.73/−22.87 → bf0.7（g_bf07）nbeat5/2128.41/−24.28：nbeat单调递增但mdd同步加深，**bf0.8未测**（残留风险，WARNING）。
- g系其余邻点最高nbeat=4（g_bx20、g_rs70、g_winA30、K2的a–g），无nbeat≥5者 → T2严格线未触发。
- 观察项（WARNING）：g_winA30以total **2400.08**（全场最高）、mdd **−22.95**双优于g_bf07，但nbeat仅4（1m −4.09持平非超、3m 17.25<17.28）——说明bf0.7点非total/mdd全局最优，后续若放宽“六窗全超”硬约束可优先考察该方向。

### (c) 剔除Top3

- g_bf07：top3_share **26.3%**，extop3_total **1545.93**；M07：26.4%/1351.75。去顶后仍盈利1545.93%且超M07去顶后**+194.18pp** → 非集中赌博，T3未触发。（g：26.3%/1512.95，+161.20pp，同通过。）
- 方法：同脚本以自写pandas代码从`res.trades["net_pnl"]`独立重算（`nlargest(3)`），未用主引擎集中度字段。

### (d) 成本压力（滑点加倍0.002→0.004）

- 非对称口径（g_bf07@0.004 vs 原M07@0.002）：total **1834.96**（−293.45pp），mdd −24.72，六窗−4.46/15.93/35.97/153.41/1343.08/1649.32，对原基线**0/6** → 绝对收益对成本敏感（WARNING，与batch_016的M07 −267pp同类）。
- 同成本基线（M07@0.004自跑，产物`part_gph.json:m07_slip04_ph0`，与batch_016 `part2_slip.json`逐值一致）：g_bf07六窗差−0.01/+0.06/+0.12/+0.41/+9.66/+176.61，**5/6**，total +239.24，mdd浅2.91pp → 相对edge具成本鲁棒性，T4未触发；但1m墙（−0.01pp）在双倍滑点下纹丝不动，见(a)论证。
- 命令：`.venv/bin/python team/audit/batch_017/work_audit_m07k3_gbf07.py`（`gbf07_slip04_ph0`行）+ `.venv/bin/python team/audit/batch_017/work_audit_m07k3_gph.py`（`m07_slip04_ph0`行）。

### (e) 切换/刹车节拍

- ph0切换日志g_bf07与M07**逐字相同**（3次：2023-06-21→B，2024-08-15→A，2026-09-08→B；复跑`switch_same_m07=true`）→ ph0增量来自选股/刹车参数（cut/bf），无择时运气，T5未触发。
- 刹车日志同日期、幅度漂移（ON：18.16/15.16/19.10 vs M07的18.16/19.70/22.82；OFF恢复：17.72/11.84/6.15 vs 15.23/10.04/18.53，末次OFF提前至2024-08-16）→ 持仓路径差异的自然结果（同batch_016 §3e措辞修正意见）。
- 跨相位切换次数：g_bf07为3/10/8/13/12/12（M07为3/9/7/13/12/10；g与g_bf07各相位switches逐值相同，bf不改切换节拍），终态ph5/7为A vs M07的B → 相位敏感互证，与(a)的T1触发一致。

## 4. 未来函数与口径审查（读码）

1. g_bf07相对M07仅改四个阈值：max_cut 0.80→0.78（`fresh2_max.py:27`当日截面分位截断，trailing）、by 0.08→0.05/bx 0.18→0.15/bf 0.6→0.7（`sweep_beat_h1_v4.py:35-54`同bar盯市刹车，contemporaneous）。代码路径与batch_016已审计的7项完全一致，无新增前视面。
2. 口径字段逐项核对（读`research/sweep_beat_m07_k3.py:41`与复跑KW）：capital 50000、slip、lot 100、cost_one_way=None、RUN_START/EVAL_END、legacy_grid=False、full_liquidate=True、MB排除集均与M07一致；phase仅本复核自用且同相位对比口径成立。
3. 已知caveat（非FAIL，与M07同口径故对比公平）：ffill盯市、静态快照伪市值、幸存者偏差、单样本（沿用batch_016 §4第7条）。

结论：未发现未来函数，未发现口径不一致，T6未触发。

## 5. 对K3文件的逐项核对

- 29配逐行独立重算nbeat（`mdd_better`/`switch_same`同步验算）：max nbeat=5（仅g_bf07），`beat_all=0`、`win_all=0`全文件成立，与agent-3同步的结论一致。
- g_bf07行15字段复跑0偏差（§2表）；K3 base_M07行与`M07_final.json`六窗逐值一致。
- K3与K1/K2的交叉一致性：g_bx20（K3，nbeat4）与K2的g系方向一致；s_rs70（nbeat4，switch_same=false）因改RS节拍被T5排除在晋级路径外（切换漂移）。
- 措辞修正：K3 docstring称g系为“brake on g”准确；但`g_winA30`（total全场最高2400.08）未被选为候选——按“六窗全超”硬目标正确（nbeat仅4），已在§3b记录为后续方向。

## 6. 认错条件（原文，沿用batch_016 §6并适配“超M07”目标）

- T1（相位运气）：若候选相对M07的total优势在异相位下反转（多数相位total落后），则认错“ph0优势主要来自相位运气”。当前：g_bf07异相位total **5连败**（−67.62/−45.56/−86.95/−125.80/−82.02），mdd 4/5更深 → **已触发**。
- T2（邻域过拟合）：若邻域内出现nbeat更高、或同nbeat但total/mdd双优的点，则认错“最优点为噪声峰”。当前：邻域最高nbeat=4（<5），未触发；但bf轴单调+bf0.8未测、g_winA30 total/mdd双优两项WARNING延续。
- T3（集中赌博）：若剔除Top3后候选total转负或落后M07 ex-top3，则认错“增量来自少数彩票股”。当前：1545.93 vs 1351.75（+194.18pp），未触发。
- T4（成本鲁棒）：若同成本基线（双边滑点加倍）候选对M07 nbeat<3或mdd不再更浅，则认错“edge不具成本鲁棒性”。当前：5/6且mdd浅2.91pp，未触发（绝对收益缩水293pp已证实成本敏感，实盘须按真实冲击成本重估）。
- T5（择时运气）：若复现switch_log与M07不一致，则认错“增量来自切换时点漂移”。当前：逐字一致，未触发。
- T6（前视/口径）：若发现任一未来函数或口径（本金/费率/整手/起止/网格）不一致，直接判FAIL。当前：7项检查通过，未触发。

## 7. verdict与建议

- verdict：**FAIL**（晋级视角：六窗6/6+mdd更浅的目标未达成；K1+K2+K3共68配beat_all=0/win_all=0；T1已触发，无FAIL项但目标落空故不判PASS_WITH_WARNINGS）。
- g_bf07处置：不晋级实盘；可作为“5/6观察项”纳入paper-track，但须先补测bf0.8邻点并解释1m墙（−0.01pp舍入无关必败）方可重新评估。
- 后续方向（按优先级）：① g_winA30系（total/mdd双优，差1窗）与winA×cut组合；② bf0.8及bx0.12/0.13细化1m墙是否可破；③ 任何新候选须先过本报告T1（异相位total≥4胜）再谈晋级。
- 约束遵守声明：本报告所有数字均来自所列命令/文件/参数的可复算产物；未审计数字（如K3其余27配的brake细节）未被用作达标依据。
