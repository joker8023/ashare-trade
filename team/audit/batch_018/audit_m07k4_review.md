# M07“六窗全超自己”K4独立复核（batch_018）

- 复核对象：K4家族变量18配（`results/r30_bt/sweep_beat_m07_k4.json`：1 base + 11双/三相位袖 + 6 R网格），目标：六窗全超M07且回撤更浅（`win_all = beat_all && mdd_better`，beat_all为六窗严格>）。
- M07基线：`results/r30_bt/M07_final.json`（total 1863.27，mdd −27.05，1m −4.09/3m 17.28/6m 39.00/1y 164.05/2y 1474.08/3y 1677.53）。
- 复核人：review子agent（agent-6），只读复算 + 自写引擎复跑（仿 `research/valid_m07_k3ph.py` 结构，只新增 `team/audit/batch_018/` 内文件，未改主流程）。
- 基准口径（与M07逐字一致，读码确认）：2020新浪口径，RUN_START=2023-01-03，EVAL_END=2026-11-12，5万本金，现实费率+滑点0.002，整手100股，只做多，不加杠杆，legacy_grid=False，full_liquidate=True；K4仅动 phase（袖）与 a/b_rebal（R网格）。
- 结论：**FAIL** —— 18配 `beat_all=0`、`win_all=0`，最高nbeat仅2（r_A15B30）；双袖合成方法独立复算逐值一致（J04袖 maxdiff 0.0，K4最强袖15字段0偏差），方法无误但家族变量同样撞墙：袖换phase对total腰斩，R网格节拍全漂移。

## 0. 一句话结论与证伪数字

- 一句话：K4共18配无一六窗全超M07，最接近的r_A15B30仅2/6且长窗崩−1000pp级，最强袖sleeve_gbf07_p0_p15为0/6（total落后523pp），判FAIL、不晋级。
- 证伪数字（详见§3，每项均给命令/文件/参数）：
  1. 独立复算误差：K4最强袖（sleeve_gbf07_p0_p15）自跑与文件15字段（total/mdd/trades/cost/switches/六窗/nbeat/beat_all/mdd_better/win_all/switch_same）**最大偏差0.00**，双腿（2128.41/527.78）逐值一致，ph0腿与K3 g_bf07一致、ph15腿527.78与batch_017异相位值交叉一致；J04双袖（`results/r30_bt/dual_phase.json`）自算 `(eq0+eq15)/2` 与存档净值 **maxdiff 0.0**，total/mdd六值逐值一致。命令：`.venv/bin/python team/audit/batch_018/work_k4repro.py`（产物`part_k4repro.json`）、`.venv/bin/python team/audit/batch_018/work_audit_m07k4_sleeve.py`（产物`part_sleeve.json`）。
  2. 袖跨phase对坍塌（同参数换phase对，total）：M07系 p0_p15 **1247.64** → pm8_pp8 **625.25** → pm5_pp5 **696.67**；gbf07系 **1339.96** → **625.37** → **660.75**；gbx15系 **1315.41** → **611.86** → **616.13**；三袖 **1065.22/1155.58**。腿spread 1253~1601pp（p0_p15组）vs 16~111pp（pm组）：袖收益完全由phase对选择决定。
  3. R网格（phase0，仅rebal差异）：最高nbeat=2（r_A15B30，赢1m +0.03/3m +0.67，6m −23.37、1y −95.94、2y −962.52、3y −1068.13）；total最高r_A20B20仅1480.90（落后M07 **382.37pp**，0/6）；6配switches为13/11/5/9/13/10（M07为3，`switch_same`全false），cost 14892~48908。R nbeat≥4零个 → 脚本R+sleeve分支正确SKIPPED（18行=1+11+6吻合）。
  4. 最强袖六窗差（sleeve_gbf07_p0_p15 − M07，pp）：1m **−0.77**、3m **−2.49**、6m **−3.19**、1y **−27.54**、2y **−425.08**、3y **−432.10**，0/6；mdd −26.35 vs −27.05（浅0.70，有mdd_better但无意义）。结构性上界：combo为腿净值均值，不可能系统性超越最强腿的六窗（ph0腿2128.41本身仅5/6，ph15腿527.78拖累全部窗口）。
  5. 费用与合成口径：每腿5万全尺寸实盘费率+滑点计入各自净值，combo取均值隐含费用均值（`cost`=腿均值，如42752=(57657+27846)/2），**无双计、无漏计**；trades/switches取和（393=184+209）仅为周转计数。caveat：无再平衡（权重随业绩漂移）、inner对齐截掉非重叠头部（J04袖起点49588.03非50000，naive均值1204.71与存档1215.55差10.84pp即源于此），袖为诊断性混合、不可直接实盘。
  6. 口径与前视：`run_leg`内shadow与switch用同一phase（K4脚本64~66行），brake同bar盯市（沿用batch_017结论），仅phase/rebal两处差异；base_M07行total/mdd与`M07_final.json`逐值一致（脚本163行assert通过）。T6未触发。
- 认错条件触发情况（原文见§6）：**家族T1类失败**（袖换phase对total腰斩、腿spread超1200pp，确认撞墙）；T2/T3/T4/T5/T6均未触发（T3/T4/T5无候选故moot，见§6说明）。
- 报告文件：`team/audit/batch_018/audit_m07k4_review.md`（本文件）；脚本/产物：`work_audit_m07k4_sleeve.py`→`part_sleeve.json`、`work_k4repro.py`→`part_k4repro.json`、`work_k4scan.py`、`work_k4detail.py`、`work_k3schema.py`。

## 1. 复核对象与证据链

| 项目 | 值 |
|---|---|
| K4脚本 | `research/sweep_beat_m07_k4.py`（201行，11:20产出，R3 agent-5执行）：`run_leg`单腿（与M07逐字一致，仅phase可变）+ `sleeve_row`（`pd.concat(eqs,axis=1,join=inner).mean(axis=1)`）+ `single_row`（R网格，仅a/b_rebal差异）+ base校准assert |
| K4文件 | `results/r30_bt/sweep_beat_m07_k4.json`：18行（1 base_M07 + 11 sleeve/sleeve3 + 6 r_），字段含tag/kind/phases/params/legs/leg_total_spread/leg_nbeat_ge4/total/mdd/六窗/nbeat_m07/beat_all/mdd_better/win_all/trades/cost/switches/brakes/switch_log/brake_log/switch_same_m07 |
| 袖分组 | M07/gbf07/gbx15 × {p0_p15, pm8_pp8, pm5_pp5} 共9双袖 + sleeve3_m07/gbf07_m8_0_p8共2三袖 |
| R网格 | r_A15B30 / r_A25B30 / r_A20B20 / r_A20B40 / r_A15B20 / r_A25B40（a_rebal ∈ {15,20,25} × b_rebal ∈ {20,30,40}，phase=0） |
| 方法参照 | `research/dual_phase.py`（J04双袖，ph0/ph15等权均值，`results/r30_bt/dual_phase.json` + 三条pkl） |
| 本次复核脚本/产物 | `team/audit/batch_018/work_audit_m07k4_sleeve.py`→`part_sleeve.json`（J04袖交叉验证）；`work_k4repro.py`→`part_k4repro.json`（最强袖双腿+combo全字段复跑）；`work_k4scan.py`（18行总表）；`work_k4detail.py`（腿明细+R六窗差） |

口径核对（读K4脚本源码）：capital=50000、slip=0.002、lot=100、cost_one_way=None、RUN_START/EVAL_END、legacy_grid=False、full_liquidate=True、MB排除集、brake rs=60默认，均与`run_m07_final.py`一致；base行assert（163行）通过即校准成立。M07/G_BF07/G_BX15参数见脚本34~38行（G_BF07=K3 g_bf07：by0.05+双腿cut0.78+bx0.15+bf0.7；G_BX15=K2 g：bf保持0.6）。

## 2. 独立复算

### (a) J04双袖合成方法交叉验证（任务2）

方法：自写脚本仅用pandas重算，不import主引擎统计函数，验证 `dual_sleeve_equity.pkl == (dual_ph0_equity.pkl + dual_ph15_equity.pkl)/2` 逐点一致。命令：`.venv/bin/python team/audit/batch_018/work_audit_m07k4_sleeve.py`。

| 检查项 | 结果 |
|---|---|
| 长度 | ph0 922 / ph15 927 / sleeve 922（ph15早5天启动2023-01-12，ph0始2023-01-19） |
| 存档sleeve vs 手算均值dropna | **maxdiff 0.0**（逐点相等） |
| total/mdd重算 vs 文件 | ph0 1765.84/−27.63、ph15 643.58/−26.22、sleeve 1215.55/−26.18，**三组0偏差** |
| naive均值 (1765.84+643.58)/2=1204.71 vs 存档1215.55 | 差10.84pp，归因：对齐后起点为2023-01-19且值为49588.03（ph15腿此时已漂至49176.06），非50000；纯起点效应，无算术错误 |
| J04袖六窗 vs M07 | −5.60/12.94/36.96/131.51/980.93/1073.67 vs −4.09/17.28/39.00/164.05/1474.08/1677.53，**0/6**，total落后647.72pp |

结论：双袖合成算术无误（等权均值、无未来函数：仅用已实现净值逐点平均）；但J04袖本身0/6大败于M07，家族变量在此口径下不构成晋级路径（撞墙佐证一）。

### (b) K4最强袖全字段复跑

方法：`import sweep_beat_m07_k4`（__main__守卫外仅加载数据与函数）后调用 `sleeve_row` 重跑双腿+combo，与文件行逐字段对比。命令：`.venv/bin/python team/audit/batch_018/work_k4repro.py`（约1分钟，产物`part_k4repro.json`）。

15字段（total/mdd/trades/cost/switches/六窗/nbeat/beat_all/mdd_better/win_all/switch_same）**全部0偏差**：total 1339.96、mdd −26.35、trades 393、cost 42752、switches 15、六窗−4.86/14.79/35.81/136.51/1049.0/1245.43、nbeat 0、mdd_better true、win_all false。双腿复跑 2128.41/−24.28/184/57657 与 527.78/−29.19/209/27846，与文件`legs[]`逐值一致；且ph0腿= K3 g_bf07、ph15腿527.78 = batch_017异相位独立值，三文件交叉一致。

### (c) base校准

K4文件base_M07行：total 1863.27、mdd −27.05、trades 184、cost 50990、switches 3、六窗与`M07_final.json`逐值一致；脚本163行 `assert total/mdd差<0.01` 通过才落盘 → K4引擎口径与M07一致，比较基准成立。

## 3. 证伪清单执行结果

### (a) 袖合成方法正确性（等权/再平衡/费用）

- 等权：`pd.concat(eqs, axis=1, join=inner).mean(axis=1)`（K4脚本120行），与`dual_phase.py`的 `(eq0+eq15)/2` 在连续日频下等价（§2a已逐点验证）；inner对齐截掉非重叠头部，无前视（只用t时刻已实现净值）。
- 再平衡：**无**。权重随业绩漂移（ equity加权 ），且起点按对齐日净值隐式归一（§2a起点49588.03实例）；袖为诊断性混合策略，不可直接实盘（无再平衡规则、无组合执行口径）。判为caveat，不判FAIL（与dual_phase同口径，比较公平）。
- 费用：每腿5万全尺寸、现实费率+滑点0.002独立计入各自净值；combo取均值即费用取均值（42752=(57657+27846)/2，四舍五入内一致），经济含义=每腿半仓，**无双计、无漏计**；`trades`/`switches`取和（393=184+209、15=3+12）为周转/计数口径，与成本口径不冲突。
- 结构性上界（为何袖注定难赢）：combo为腿净值均值，其任一窗口收益率被夹在两腿之间；p0_p15组一腿为ph0强腿（本身nbeat≤5）另一腿ph15弱腿（全线落后），均值不可能六窗全超M07 ph0；pm组两腿皆弱（leg_nbeat_ge4全0），均值更无机会。11袖nbeat全0与此一致，非偶然。

### (b) 袖跨phase对稳定性（换一组phase对即坍塌）

| 参数系 | p0_p15 | pm8_pp8 | pm5_pp5 | 三袖m8_0_p8 |
|---|---|---|---|---|
| M07 | 1247.64（腿1863.27/609.80，spread 1253.47） | 625.25（637.75/621.37，spread 16.38） | 696.67（644.85/755.73，spread 110.88） | 1065.22 |
| gbf07 | 1339.96（2128.41/527.78，spread 1600.63） | 625.37（607.95/651.42，spread 43.47） | 660.75（640.29/688.11，spread 47.82） | 1155.58 |
| gbx15 | 1315.41（2084.73/522.77，spread 1561.96） | 611.86（583.64/648.55，spread 64.91） | 616.13（597.38/641.38，spread 44.00） | — |

同参数换phase对total腰斩（−622pp级，如gbf07的1339.96→625.37）；p0_p15的高combo完全依赖ph0强腿（leg_nbeat_ge4=1系中唯一≥4的腿即ph0腿），pm组两腿皆弱。袖收益由phase对选择主导 → **家族T1类失败**（见§6）。另：M07 ph5腿755.73、ph15腿609.80、gbf07 ph5腿688.11与batch_017 `part_gph.json` 独立值一致，跨报告互证。

### (c) R网格：switch节拍漂移与费用

| tag | nbeat | 六窗差vsM07（pp） | sw | cost |
|---|---|---|---|---|
| r_A15B30 | 2 | +0.03/+0.67/−23.37/−95.94/−962.52/−1068.13 | 13 | 33686 |
| r_A25B30 | 1 | −2.88/−7.04/+2.64/−61.36/−951.03/−1116.34 | 11 | 19758 |
| r_A20B20 | 0 | −1.56/−5.23/−5.98/−11.79/−80.56/−198.10 | 5 | 48908 |
| r_A20B40 | 0 | −1.13/−2.20/−2.55/−4.69/−161.40/−85.66 | 9 | 46483 |
| r_A15B20 | 0 | −0.71/−2.87/−7.85/−71.67/−948.89/−1210.64 | 13 | 25416 |
| r_A25B40 | 1 | −4.68/−9.12/+1.29/−44.41/−963.80/−1196.67 | 10 | 14892 |

6配 `switch_same_m07` 全false，切换5~13次 vs M07的3次：rebal一动即节拍全漂移，无一保持M07择时；仅赢短窗（1m/3m/6m偶发+0.03~+2.64），6m+长窗全部崩−20pp以上。费用14892~48908覆盖M07（50990）上下两端，无成本优势方向。R nbeat≥4零个 → 脚本184~199行R+sleeve分支正确SKIPPED（若强行组合亦受(a)上界约束，无意义）。

### (d) ex-top3与滑点加倍（moot说明）

- ex-top3：仅对beat_all或nbeat≥5候选执行；K4最高nbeat=2，无候选 → moot。最强袖/最强R连六窗都未全超，集中度分析不能改变晋级结论。
- 滑点加倍同成本基线：同上moot。且数量级论证：最强R total落后382.37pp、最强袖落后523.31pp，长窗差−80~−1068pp；r_A15B30仅有的两个+0.03/+0.67pp微弱短窗优势在双倍滑点下只会缩小（方向不变、数值更差），不可能反转出beat_all。故不执行0.004重跑（batch_017的M07@0.004基线total 1595.72仍远高于K4最强1480.90，旁证成本无法弥合差距）。

## 4. 未来函数与口径审查（读码）

1. `run_leg`（K4脚本49~72行）：shadow双腿与switch组合均用**同一phase**（61~66行 `phase=phase` 三处），与`dual_phase.py` 25~31行结构一致；无跨phase信息串扰。
2. 相对M07差异仅两处：袖分支的phase取值、R分支的a/b_rebal（脚本149~156行）；其余capital/slip/lot/cost_one_way/RUN_START/EVAL_END/legacy_grid/full_liquidate/MB/rs_lookback=60逐字一致。
3. brake为同bar盯市（`build_ns`，沿用batch_017 §4结论）；`judge`用严格>（85~86行）与batch_017一致；`win_all = beat_all and mdd > −27.05`（88行）。
4. 已知caveat（非FAIL，与M07同口径故比较公平）：ffill盯市、静态快照伪市值、幸存者偏差、单样本（沿用batch_016 §4第7条）；另新增袖特有caveat：无再平衡、inner对齐截头（见§3a）。

结论：未发现未来函数，未发现口径不一致，未发现费用双计/漏计，T6未触发。

## 5. 对K4文件的逐项核对

- 18行 = 1 base + 11 sleeve/sleeve3 + 6 r_，与脚本SLEEVE_GROUPS（11组，135~147行）+ R_GRID（6组）+ base逐一对应，无缺行、无FAIL行（脚本try/except若有异常会打印FAIL且不落盘，本次无）。
- `beat_all`全false、`win_all`全false；nbeat_m07分布：0×15、1×2（r_A25B30/r_A25B40）、2×1（r_A15B30）；max nbeat=2， beat_all=0成立。
- base_M07行与`M07_final.json`六窗/total/mdd逐值一致；`switch_same_m07`：仅base为true，其余全false。
- 与K1~K3交叉一致性：gbf07 ph0腿2128.41 = K3 g_bf07行；gbx15 ph0腿2084.73 = K2 g行（bf0.6版本）；M07 ph15/ph5腿609.80/755.73 = batch_017异相位值；新phase（±8/±5）腿走同一`run_leg`代码路径。
- 措辞修正：K4脚本docstring称袖`起点5万`（11行）不精确——inner/对齐后combo起点为对齐日均值（如J04袖49588.03），与名义5万有小偏差；属文档瑕疵，不影响数字（combo统计恒以自身起点为分母，口径自洽）。

## 6. 认错条件（沿用batch_017 §6并适配家族变量）

- T1（相位运气）：若候选相对M07的total优势在异相位下反转，则认错ph0优势主要来自相位运气。K4无候选，严格线不适用；但**家族层面触发T1类失败**：同参数袖换phase对total腰斩（gbf07系1339.96→625.37，M07系1247.64→625.25），腿spread超1200pp → 双袖收益完全由phase对选择决定，家族变量本身即相位运气载体，确认撞墙。
- T2（邻域过拟合）：若邻域出现nbeat更高者则认错。K4最高nbeat=2，R网格内无更高点，袖全0 → 未触发。
- T3（集中赌博）：仅对候选执行ex-top3；无候选 → moot（未触发）。
- T4（成本鲁棒）：仅对候选执行同成本滑点加倍；无候选 → moot（未触发；§3d数量级论证滑点无法弥合382pp+差距）。
- T5（择时运气）：若复现switch_log与M07不一致则认错增量来自切换漂移。无候选 → moot；R行节拍全漂移（5~13次 vs 3次）佐证rebal维度无稳定择时edge。
- T6（前视/口径）：若发现任一未来函数或口径（本金/费率/整手/起止/网格）不一致、或费用双计/漏计，直接判FAIL。§4四项检查通过 → 未触发。

## 7. verdict与建议

- verdict：**FAIL**（K4 18配 beat_all=0、win_all=0；双袖方法复算无误，家族变量同样撞墙；家族T1类失败）。
- 建议：① 终结双/三相位袖方向（结构性上界+phase对坍塌双重死刑，除非引入再平衡/动量加权等新机制并重立T线）；② 终结纯R（rebal）网格方向（节拍全漂移+长窗全崩）；③ 后续若重启家族变量，须先立可实盘组合规则（再平衡/权重/双倍资金或半仓声明）再谈beat_all，否则复核仍判口径不可比。
- 本报告产物清单（仅`team/audit/batch_018/`）：`audit_m07k4_review.md`、`work_audit_m07k4_sleeve.py`、`part_sleeve.json`、`work_k4repro.py`、`part_k4repro.json`、`work_k4scan.py`、`work_k4detail.py`、`work_k3schema.py`。

