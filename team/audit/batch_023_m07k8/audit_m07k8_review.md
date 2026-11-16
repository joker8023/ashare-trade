# K8 峰顶二阶组合独立复核（batch_023_m07k8）

- 复核对象：K8 峰顶二阶组合 8 行（`results/r30_bt/sweep_beat_m07_k8.json`：1 base_M07 + 7 新配：g_bf07×rs70/winA30/rs70+winA30/cut75/cut75+rs70/stop22/takeB90；脚本 `research/sweep_beat_m07_k8.py`，R8 执行 12:13 落盘），目标六窗全超 M07 且回撤更浅（win_all = beat_all 且 mdd_better，beat 为六窗严格大于）。
- M07 基线：`results/r30_bt/M07_final.json`（total 1863.27，mdd −27.05；1m −4.09 / 3m 17.28 / 6m 39.00 / 1y 164.05 / 2y 1474.08 / 3y 1677.53）。
- 复核人：review 子 agent（agent-15），只读复算 + 引 K8 模块重跑（仅新增 `team/audit/batch_023_m07k8/` 内文件，未改主流程）。
- 口径（读 K8 脚本源码确认，与 M07 逐字一致）：2020 新浪口径 ph0，RUN_START=2023-01-03，EVAL_END=2026-11-12，5 万本金，现实费率（cost_one_way=None）+ 滑点 0.002，整手 100 股，只做多不加杠杆，legacy_grid=False，full_liquidate=True，stop=0.25/stop_exec=next（stop22 行除外），A 腿 N5/R20/take1.2、B 腿 N4/R30/take0.80，MaxInputs 双腿 cut/win、RS60（rs70 行除外）、MB 排除、刹车 bx/by/bf 可参、factor=amihud_60（MaxInputs 默认，与 K7 同源）、phase=0、lock_mode=None 单 switch 机制。
- 结论：**FAIL —— K8 共 8 行 beat_all=0（file-declared 与独立重算一致）、win_all=0，最高 nbeat 仅 4（三行，均卡死 1m+3m 短窗）；K1–K8 累计 120 新配 beat_all=0（128 行含 8 校准行）。T1–T6 本轮均未触发（K8 无 beat_all 或 nbeat>=5 候选故 T1/T3/T4 moot，见第 5 节；T1 家族延续线仍为触发态，见第 5 节）。**

## 0. 一句话结论与证伪数字

- 一句话：K8 的 7 个峰顶二阶新配无一六窗全超 M07，最强的 g_bf07_winA30 以 total +537.02pp（全场最高 2400.29）但 1m 打平/3m −0.03pp 双卡、止步 4/6；takeB90 二阶直接 0/6 崩、cut75+rs70 三阶 1/6 崩且 mode 翻 A——峰顶叠加不是出路，判 FAIL、峰顶邻域撞墙确认。
- 证伪数字（每项均给命令/文件/参数）：
  1. 全文件独立复算 nbeat/beat_all/mdd_better/win_all（K1–K8 共 128 行，M07 六窗逐值对照严格大于口径）：0 mismatch；file-declared beat_all=True 计 0、win_all=True 计 0；全域唯一非 base nbeat>=5 仍是 K3 g_bf07（已审计，batch_017 T1 已触发）。命令：`.venv/bin/python team/audit/batch_023_m07k8/work_k8scan.py`（产物 part_k8scan.json）。
  2. 独立复算误差：最强档 g_bf07_rs70 引 K8 模块 run_one 同参重跑，与 K8 文件 total/mdd/trades/cost/六窗/nbeat 最大偏差 0.00（total 2022.83、mdd −24.28、trades 178、cost 54725、switches 5，逐项一致）。命令：`.venv/bin/python team/audit/batch_023_m07k8/work_k8deep.py`。
  3. K8 七新配六窗差（候选减 M07，pp）与 total/mdd：
     - g_bf07_winA30：0.00/−0.03/+0.26/+0.35/+6.22/+193.03（4/6，total 2400.29 全场最高，mdd −24.17 浅 2.88；1m 打平非严格胜）；
     - g_bf07_rs70_winA30：−0.01/−0.03/+0.33/+0.77/+42.41/+112.89（4/6，total 2298.59，mdd −24.17）；
     - g_bf07_rs70：−0.02/−0.04/+0.23/+0.32/+41.14/+104.35（4/6，total 2022.83，mdd −24.28）；
     - g_bf07_cut75：0.00/−0.02/+0.27/+1.10/+11.80/+190.44（4/6，total 1904.82，mdd −25.02）；
     - g_bf07_stop22：0.00/−0.03/+0.15/−0.61/−28.65/+110.20（2/6，total 2029.43，mdd −24.89）；
     - g_bf07_cut75_rs70：−0.46/−3.93/−4.58/−8.92/−24.16/+19.09（1/6，total 1730.27，mdd −25.02，mode 翻 A、switches 6）；
     - g_bf07_takeB90：−0.03/−4.49/−5.01/−10.04/−307.66/−198.08（0/6，total 1658.10，mdd −24.32，switches 7）。
     七行 1m 无一严格胜出（最好打平）、3m 全败——短窗墙第八轮纹丝不动；mdd_better 七行全 True 但 beat_all 全 0，回撤优势救不了晋级。
  4. 去重：K8 的 7 个 tag 与 K1–K7 的 113 新配 tag 交集为空（程序比对 0 重叠）；抽查 2 个二阶组合的参数签名与数值双重确认未做过（见第 4 节）；K8 脚本内置 dedup_check（tag + 参数签名双重门， kept=7、base 校准行旁路），落盘 base 行与 M07_final 六窗/total/mdd 逐值偏差 0.00 且脚本内含 base 校准 assert（通过，否则不落盘）。
  5. 峰顶邻域穷尽：单维最优方向（bf0.7 峰顶 g_bf07=5/6）上的全部二阶/三阶叠加（rs70、winA30、cut75、stop22、takeB90 及其三阶 rs70+winA30、cut75+rs70）最高仅 4/6，且出现 0/6 与 1/6 崩盘行——叠加不单调，二阶无一逼近峰值 5/6，更无 beat_all。
- 认错触发情况（原文见第 5 节）：本轮 T1–T6 均未触发（T1/T3/T4 因 K8 无 beat_all/nbeat>=5 候选而 moot；T2 最高 nbeat=4 且峰值仍在已审计 g_bf07=5；T5 三行与 M07 逐字一致、四行漂移但因无候选而 moot；T6 口径检查通过）。家族延续线：T1 在 batch_017 已对 g_bf07 触发，本轮峰顶仍是该行，T1 触发态延续（非本轮新触发）。
- 报告文件：`team/audit/batch_023_m07k8/audit_m07k8_review.md`（本文件）；脚本/产物：work_k8scan.py、part_k8scan.json、work_k8deep.py。

## 1. 复核对象与证据链

| 项目 | 值 |
|---|---|
| K8 脚本 | `research/sweep_beat_m07_k8.py`（186 行）：复用已审计引擎（prior_check.run_strategy + sweep_beat_h1_v4.build_ns + MaxInputs shadow + run_strategy_switch，lock_mode=None）；get_ns/get_shadows 缓存；run_one 落盘 total/mdd/trades/cost/mode/switches/brakes/双 log/六窗+nbeat_m07/beat_all/mdd_better/win_all/switch_same_m07；CFGS 8 组（1 base + 7 二阶/三阶）；dedup_check（tag + 参数签名 KNOWN_SIGS 双重门）；base 校准 assert（total/mdd 偏差 <0.01 且六窗逐值相等，否则抛错不落盘） |
| K8 文件 | `results/r30_bt/sweep_beat_m07_k8.json`：8 行（1 base + 7 新），字段与 K2 系 schema 一致（另含 combo/switch_same_m07） |
| 分组 | 二阶 5 组（rs70、winA30、cut75 双腿、stop22、takeB90）+ 三阶 2 组（rs70+winA30、cut75+rs70），基座统一 GBF07（by05+cut78 双腿+bx15+bf0.7，cut75 两组以 cut 双腿 0.75 替代 0.78） |
| 本次复核脚本与产物 | work_k8scan.py → part_k8scan.json（K1–K8 共 128 行重算 + 去重比对 + base 对账）；work_k8deep.py（g_bf07_rs70 引模块重跑备查） |

## 2. 独立复算（三重：全文件重算 + base 对账 + 引模块重跑）

方法：先对 K1–K8 全 128 行按 M07 六窗独立重算 nbeat/beat_all 并与文件声明比对；再核 K8 base_M07 行与 M07_final 逐值对比；最后引 K8 模块 run_one 同参重跑 g_bf07_rs70 逐字段对比。

| 检查 | 结果 |
|---|---|
| K1–K7 file-declared beat_all=True 计数 | 0（重算 beat_all=True 计 0，一致） |
| K1–K7 nbeat/beat_all 声明 vs 重算 mismatch | 0 行（113 新配 + 7 校准全一致） |
| K8 file-declared beat_all/win_all | 0 / 0（重算 beat_all=True 计 0，一致，decl mismatch 空） |
| K8 新配最高 nbeat | 4（三行：g_bf07_rs70、g_bf07_winA30、g_bf07_rs70_winA30；0 行 >=5） |
| K8 base_M07 vs M07_final | total/mdd/六窗 8 值逐值相等，偏差 0.00 |
| 引模块重跑 g_bf07_rs70 | total/mdd/trades/cost/mode/switches/六窗/nbeat 与文件逐项一致，最大偏差 0.00 |

tie-break 声明（吸取 batch_022 对 K1/K7 最强行选择的 PARTIAL/FAIL 教训）：nbeat 并列时按 total 高者为最强——K8 最强为 g_bf07_winA30（4/6，total 2400.29），而非首个 max 行 g_bf07_rs70（4/6，total 2022.83）。两者同为 4/6、同卡 1m+3m，名次不影响 FAIL 结论，特此明示规则以保三轮一致。

## 3. 证伪清单执行结果

### (a) K8 七新配六窗差与短窗墙（第八轮）

见 §0 第 3 项表。补充：K3 g_winA30（bf0.6 版）total 2400.08 与 K8 g_bf07_winA30（bf0.7 版）total 2400.29 仅差 +0.21pp——bf0.6→0.7 在 winA30 分支上几乎无增量，edge 不在 bf 轴而在分支本身，但分支本身同样破不了短窗（1m 打平、3m −0.03pp）。

### (b) 叠加非单调：二阶/三阶崩盘行

- g_bf07_takeB90（0/6）：B 腿 take 0.80→0.90 在 bf0.7 基座上导致 2y −307.66pp、3y −198.08pp 长窗崩，与 K3 g_takeB90（bf0.6 版，0/6，total 1621.17）同构——takeB90 方向在两版基座上双杀确认，非偶然。
- g_bf07_cut75_rs70（1/6）：cut75+rs70 三阶仅赢 3y +19.09pp，其余五窗全败且 mode 翻 A（全场唯一 A）、switches 6——三阶叠加改变切换节拍但方向为负，是“叠加即改善”假设的反例。
- g_bf07_stop22（2/6）：stop 0.25→0.22 仅赢 1m 打平外的 6m/3y，1y −0.61pp、2y −28.65pp——stop 轴二阶同样撞墙。

### (c) switch_log 漂移记录（T5 备查，moot 但留痕）

- 与 M07 逐字一致（switch_same_m07=True，3 切）：g_bf07_winA30、g_bf07_cut75、g_bf07_stop22——墙不在切换节拍（同 batch_021 备查观察一致）。
- 漂移：g_bf07_rs70 / g_bf07_rs70_winA30（5 切）、g_bf07_cut75_rs70（6 切，mode A）、g_bf07_takeB90（7 切）——漂移行 total 全部低于不漂移的最强行（2022.83/2298.59/1730.27/1658.10 < 2400.29），漂移未带来晋级，T5 按“仅对候选执行”口径 moot。

## 4. 去重核查（重点：K8 脚本自带去重声明 + 独立抽查 2 组合）

- 程序比对：K8 7 新 tag（g_bf07_rs70、g_bf07_winA30、g_bf07_rs70_winA30、g_bf07_cut75、g_bf07_cut75_rs70、g_bf07_stop22、g_bf07_takeB90）与 K1–K7 的 113 新配 tag 求交 = 空集；K1–K8 新配合计 120，unique 120（113+7，无跨文件/文件内重复）。
- K8 脚本内置 dedup_check：tag 级（seen_tags 来自 K1–K7 json）+ 参数签名级（KNOWN_SIGS 来自 K1–K7 脚本 CFGS）双重门；落盘 7 新配 = kept 全集，无 SKIP（文件 8 行即全集；若有跳过会打印 SKIP，本次复核未见跳过记录需求——文件行数与 CFGS 去 base 后一致）。
- 抽查组合 1：g_bf07_rs70（bf0.7+rs70 二阶）。K1–K7 无此 tag；最近似为 K3 g_rs70（bf0.6 版：`research/sweep_beat_m07_k3.py:104` 无 bf 参数即默认 0.6，total 1956.14/mdd −22.87/nbeat 4）——K8 版 total 2022.83/mdd −24.28/nbeat 4，数值不同、签名不同（关键区分位 bf=0.7），确为新跑非复用。
- 抽查组合 2：g_bf07_takeB90（bf0.7+takeB90 二阶）。K1–K7 无此 tag；最近似为 K3 g_takeB90（bf0.6 版：`research/sweep_beat_m07_k3.py:98`，total 1621.17/mdd −23.19/nbeat 0）——K8 版 total 1658.10/mdd −24.32/nbeat 0，数值不同、签名不同（多了 bf0.7），确为新跑非复用；且两版同为 0/6，同构双杀。
- 另注：K5 已有 rs30/rs120(+gbf07) 但无 rs70，K5 注释“无 stop22/takeB90 单改、无 rs70”与程序比对一致；K6 cut75_both 为 M07 裸基座版，K8 cut75 两组带 by05/bx15/bf07，签名不同。去重声明成立：**PASS**。

## 5. 认错条件（沿用 batch_017 第 6 节原文并适配超 M07 目标；T1 家族延续线）

- T1（相位运气）：若候选相对 M07 的 total 优势在异相位下反转，则认错 ph0 优势主要来自相位运气。K8 无 beat_all/nbeat>=5 候选，moot、未触发；家族延续线为 batch_017 已对 g_bf07 触发（T1 认错成立并延续，K8 峰顶基座仍是该行，其 5/6 不计入晋级）。
- T2（邻域过拟合）：若邻域内出现 nbeat 更高、或同 nbeat 但 total/mdd 双优的点，则认错最优点为噪声峰。K8 新增最高 nbeat=4（小于 5），无更高新邻点，未触发；且二阶/三阶 7 点（4/4/4/4/2/1/0）全部低于峰值 g_bf07=5，峰值为局部峰的证据再增强（非认错线，属撞墙确认）。
- T3（集中赌博）：若剔除 Top3 后候选 total 转负或落后 M07 ex-top3，则认错增量来自少数彩票股。无候选，moot、未触发。
- T4（成本鲁棒）：若同成本基线候选对 M07 nbeat<3 或 mdd 不再更浅，则认错 edge 不具成本鲁棒性。无候选，moot、未触发。
- T5（择时运气）：若复现 switch_log 与 M07 不一致，则认错增量来自切换时点漂移。K8 无候选故 moot、未触发；备查：三行逐字一致、四行漂移但 total 更低（见 §3c），漂移未产生晋级。
- T6（前视/口径）：若发现任一未来函数或口径（本金/费率/整手/起止/网格/执行/费用）不一致，直接判 FAIL。本节读码检查通过，未触发：① 数据与窗口：pivots_2020_clean.pkl、RUN_START/EVAL_END/grid（300 步/30 步）与 M07 同一引用（sweep_beat_h1_v4 导入），assert 门守卫三处（RUN_START/WINDOWS/EVAL_END），新增数据源无；② 本金/费率/滑点/整手：50000/cost_one_way=None/slip=0.002/lot=100 逐字一致；③ 执行：stop/stop_exec=next、legacy_grid=False、full_liquidate=True 一致；④ 因子原生性：仅 amihud_60（MaxInputs 默认，与 K7 同源），未触非原生因子；⑤ 未来函数：复用已审计 build_ns/run_strategy_switch（shadow+信号日切片），K8 新增仅为 CFGS 参数、dedup 门与 base assert，无手写回测器，无未来引用，通过；⑥ 文件-脚本一致性：文件 8 行 = CFGS 全集（7 新 + 1 base），无口径外点。

## 6. T6 口径审查（K8 脚本读码，行号指 research/sweep_beat_m07_k8.py）

见 §5-T6 六项。补充：dedup_check 对 base_M07 旁路（仅新配做签名比对），base 行受独立 assert 守卫（total/mdd 偏差 <0.01 且六窗逐值相等）；main 块落盘前打印 slim 行与 BASE calibration OK（本次文件 base 行逐值相等，反推当时 assert 已通过）。

## 7. verdict 与全域结论更新

- verdict：**FAIL**（K8 的 7 新配 beat_all=0、win_all=0；K1–K8 累计 120 新配 beat_all=0；最强新配 g_bf07_winA30 以 1m 打平/3m −0.03pp、mdd 浅 2.88 止步 4/6；bf 轴峰值仍是已审计 g_bf07=5 且 T1 认错延续；无 FAIL 项但目标落空故不判 PASS_WITH_WARNINGS）。
- 累计数纠正表（per-file rows/base/new）：

| 文件 | rows | base_M07 校准 | 新配 | beat_all |
|---|---|---|---|---|
| K1 | 30 | 1 | 29 | 0 |
| K2 | 9 | 1 | 8 | 0 |
| K3 | 29 | 1 | 28 | 0 |
| K4 | 18 | 1 | 17 | 0 |
| K5 | 20 | 1 | 19 | 0 |
| K6 | 8 | 1 | 7 | 0 |
| K7 | 6 | 1 | 5 | 0 |
| K8 | 8 | 1 | 7 | 0 |
| 合计 | 128 | 8 | 120 | 0 |

  独立重算 file-declared 与重算 0 mismatch（beat_all=True 计 0）；新配去重 120 unique（K8 交集空）；每轮 base 行逐字复现（K8 base 8 值偏差 0.00）。
- 差距数量级总表（相对 M07 total 1863.27/mdd −27.05）：K8 total 为 −205.17（takeB90）到 +537.02pp（winA30）但短窗全灭（1m 最好打平、3m 最好 −0.02pp）；mdd_better 七行全 True（浅 1.73~3.40）救不了 beat_all；崩盘行 mode 翻 A（cut75+rs70）与 switches 7（takeB90）说明叠加已触及机制边界。
- 峰顶邻域穷尽声明：以全场峰值 g_bf07（bf0.7，5/6）为基座的全部二阶/三阶叠加方向（rs70、winA30、cut75、stop22、takeB90、rs70+winA30、cut75+rs70）已探明穷尽——最高 4/6，无一达到 5/6，更无 beat_all；与 K7“bf 轴收尾撞墙”（bf0.65–0.85 全 ≤4）互相印证，峰顶（bf0.7）在阈值/刹车/RS/敞开/执行各轴上均为局部峰。穷尽范围限定为：同切换族 + 双原生因子（amihud_60/20）+ ph0 + 现实成本口径；残留未探明方向（均标注非达标、需立项才做）：① 非原生因子（size/amount_level/liq_size/amihud_5，需新 Inputs + 全套 T 线重审）；② 异相位（T1 已触发，ph0 优势含相位运气成分，换相位须重审）。
- 全域结论：在当前数据与引擎下，同切换族 + 双原生因子 + ph0 口径内不存在六窗全超 M07 且回撤更浅的策略——八轮正交/峰顶族 120 新配零全胜，且短窗墙（1m 在打平/−0.01~−0.46pp、3m 在 −0.02~−4.49pp）八轮纹丝不动；paper-track 维持 M07，K8 任何行不得实盘。
- 本报告产物清单（仅 `team/audit/batch_023_m07k8/`）：audit_m07k8_review.md、work_k8scan.py、part_k8scan.json、work_k8deep.py。
