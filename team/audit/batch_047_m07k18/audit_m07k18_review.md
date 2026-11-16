# M07-K18 排序加权持仓试点复核（batch_047）

- 复核对象：R35 K18 按排序加权持仓试点 —— 首个动腿内权重的 family，T 线从严。
- 基线：`results/r30_bt/M07_final.json`（M07 = J04 + B-MAX20(A40/B20) + B-N4；total +1863.27%，mdd −27.05%，trades 184，cost 50990，switches 3：2023-06-21→B / 2024-08-15→A / 2026-09-08→B；六窗 1m −4.09 / 3m +17.28 / 6m +39.0 / 1y +164.05 / 2y +1474.08 / 3y +1677.53；top3_share 26.4%，extop3_total +1351.75%）。
- M07 执行口径（`research/run_m07_final.py:16`，K18 必须逐字一致）：`lot=100` 整手，`slip=0.002`，`cost_one_way=None`（现实费率），`stop_exec="next"`（t+1 执行），30 日网格调仓，`legacy_grid=False`，`full_liquidate=True`，MB 排除，RUN_START=2023-01-03 / EVAL_END=2026-11-12，`prior_check.run_strategy` + `sweep_beat_h1_v4.build_ns(0.18,0.08,0.6)` 开关引擎。
- 一句话结论：**FAIL（R35-K18 未交付：`research/weight_k18.py` 与 `results/r30_bt/sweep_beat_m07_k18.json` 双缺失，前视不可排除，无候选可做 T 线）。**

## 1. weight_k18.py 逐行审计 —— FAIL（文件缺失，前视一票否决）

- `research/weight_k18.py`：**不存在**（全仓 `**/weight_k18*` / `**/weight*` 仅命中 `results/r30_bt/weight_frontier{,2}.json`（旧权重前沿，与 K18 无关）；`ls research/ | grep -i -E 'weight|k18'` 零命中；终查 glob `**/*k18*` 全仓零命中）。
- `results/r30_bt/sweep_beat_m07_k18.json`：**不存在**（`results/r30_bt/sweep_beat_m07_k*.json` 仅到 k17；终查确认）。
- git 工作树无相关未跟踪文件（`git status --short` 仅见 K17 以前旧文件，无 k18 条目）。
- 因此以下审计项**均不可验证**，按约束"权重前视一票 FAIL"直接判 FAIL：
  - (a) 权重是否只用 t 及以前排序（秩/Amihud 值有无前视；排序统计量必须闭合在 `eq[:t]` 内，影子波动率/回撤式单测缺失即 FAIL）；
  - (b) 权重归一化与整手取整逻辑（和为 1、lot=100 取整余量去向、余量是否产生非预期现金拖累）；
  - (c) 影子与实盘权重一致性（影子加权与开关后实盘加权同一函数、同一输入，t+1 执行链 `stop_exec="next"` 一致）；
  - (d) 费用/执行/口径与 M07 一致（`cost_one_way=None` / slip=0.002 / lot=100 / MB 排除 / RUN_START / EVAL_END / legacy_grid=False / full_liquidate=True）。
- 注：K18 是首个"腿内权重" family，前视面比 K17 更大（K17 只动开关比较标尺，持仓仍等权；K18 动持仓权重本身），T 线从严（见§4验收条件）。

## 2. K1–K17 前提复核（beat_all=0 确认）与候选 T 线

- 前提确认：17 个 sweep（k1–k17，`results/r30_bt/sweep_beat_m07_k{1..17}.json`）逐文件扫描，**beat_all=0 全文件成立**，与任务所述"170 新配 beat_all=0（全等权）"一致（行数 178 含各文件 base 校准行，新配量级相符）。
- K18 候选 T 线：候选数 **0**（sweep 缺失），beat_all / nbeat_m07≥4 名单为空 → 跨相位 / ex-top3 / 滑点加倍 / 独立复算**均 N/A，无 T 线可跑**。
- 往期 family 中 nbeat≥4 行归属说明（非本 batch 范围，不重复跑 T 线；beat_all=0 故冠军不受影响）：
  - k1：k05_by05（4）、k25_cut78（4）；k3：g_bf07（5，K3 行，后续 seat 用）、s_rs70（4）、g_bx20（4）；k5：nobrake_M07/gbf07（4）；k7：g_bf075/080/085（4）；k8：g_bf07_rs70/winA30 组合（4）。k17 最好行 k17_calmar_M07 仅 nbeat=2（batch_045 已全套 T 线三腿全败关闭）。
  - 未见 beat_all=true 行；mdd 更浅且六窗全超的策略不存在 → 本轮目标（六窗全超 M07 且回撤更浅）仍无候选。

## 3. M07 口径独立复算证据（本次实跑）

- 命令：`.venv/bin/python research/sweep_beat_m07_k17.py --only base_M07`（K17 引擎路径，truncation_check + base 校准同跑；exit 0）。
- 结果：`truncation_check PASS: 24 (seat,leg,metric,t) combos, full==truncated`；base_M07 输出 total **1863.27** / mdd **−27.05** / trades **184** / cost **50990.0** / switches **3** / 六窗 −4.09/17.28/39.00/164.05/1474.08/1677.53 / switch_same_m07=true —— 与 `M07_final.json` **零偏差**，M07 champion 地位维持。
- K18 落盘后，其 sweep 必须内含同等 base_M07 校准行（total/mdd/switch_log 逐字断言，仿 `sweep_beat_m07_k17.py:214-216`），否则口径项直接 FAIL。

## 4. 判决与 K18 落盘验收条件（T 线从严）

- **Verdict: FAIL（R35-K18 试点未交付，实现 + 结果双缺失；权重前视不可排除，按约束一票否决）。**
- R35 若重启 K18，必须先交付下述工件方可进入复核（缺一即 FAIL，不跑 T 线）：
  1. `research/weight_k18.py`：权重函数仅取 t 及以前数据（秩/Amihud 窗切片 `iloc[j-W:j+1]` 式、预热守卫、零方差守卫），附 t-截断 vs 全序列切片全等单测（仿 K17 truncation_check，覆盖全部决策日）；
  2. 归一化 + lot=100 取整规则书面化（权重和、余量处理、影子/实盘同一函数）；
  3. `results/r30_bt/sweep_beat_m07_k18.json`（K2 schema：tag/base/family/mechanism/selector/legs/total/mdd/trades/cost/switch_log/brake_log/六窗/nbeat_m07/beat_all/mdd_better/win_all/switch_same_m07），首行 base_M07 校准零偏差；
  4. 执行口径逐字 M07（§0 所列 8 项）。
- 落盘后对任一 beat_all 或 nbeat_m07≥4 候选执行全套 T 线：leg1 独立复算五项零偏差；leg2 跨相位 ph0/5/7/10/14/15 vs 同相位 M07（无一致 edge 即 FAIL）；leg3 ex-top3（extop3_total 落后 M07 1351.75 即 FAIL）；leg4 滑点加倍 0.002→0.004 全链（nbeat 归零或 mdd 反超即 FAIL）；leg5 权重前视全决策日复核（任一差值 ≠0 即 FAIL）。另加 K18 专属：影子加权 vs 实盘加权逐日持仓权重一致性抽查。
- Paper-track 保持 M07；K18 在 verdict 翻转前不得上线。

*复核子 agent agent-51；工作目录 `/Users/joker/coding/ashare-trade`；本目录新增唯一文件：本报告。其它目录零新增（复算复用既有 `research/sweep_beat_m07_k17.py`，未落盘）。*

## §5 真实产出复核（R35-K18 落盘后追加；§0–§4 为首查时序记录保留）

> 首查时 `research/weight_k18.py` / `research/sweep_beat_m07_k18.py` / `results/r30_bt/sweep_beat_m07_k18.json` 尚未落盘（§1–§4 为此时序记录）；回测完成后真实产出为 6 行（2 校准 + 4 新配），本节为全套复核。T 线脚本 `tline_k18_amiprop.py`，产物 `tline_k18_amiprop_out.json`（均在本目录）。

产出摘要（`sweep_beat_m07_k18.json`）：base_M07 / base_gbf07 双校准零偏差（见下）；4 新配 beat_all=0，最好的新配是 **k18_amiprop_gbf07**（total 1581.87 / mdd −25.82 / 7 切 / **nbeat=1**，唯一 mdd_better=true）：

| tag | total | mdd | trades | switches | nbeat | beat_all |
|---|---|---|---|---|---|---|
| base_M07 | 1863.27 | −27.05 | 184 | 3（=M07三切） | 0 | false |
| base_gbf07 | 2128.41 | −24.28 | 184 | 3（=M07三切） | 5 | false |
| k18_ranklin_gbf07 | 1511.82 | −31.85 | 183 | 11 | 1 | false |
| **k18_amiprop_gbf07** | **1581.87** | **−25.82** | 180 | 7 | **1** | false |
| k18_ranklin_B（单腿） | 740.84 | −32.67 | 120 | 0 | 1 | false |
| k18_amiprop_B（单腿） | 783.20 | −30.30 | 120 | 0 | 1 | false |

加权 total 缺口：amiprop_gbf07 −281.40pp vs M07（1581.87−1863.27）；ranklin_gbf07 −616.59pp vs 同座等权（1511.82−2128.41）。与 lead 通报（最好 nbeat=1；switches 7/11/0/0；加权 total −281~−616pp）逐字相符。

### §5.1 weight_k18.py 逐行审计 —— PASS（无前视），口径一致

- 锚点（`weight_k18.py:70-86`）：`_SW_ALLOC_OLD` / `_SW_LOOP_A` / `_SW_LOOP_B` / `_SW_SNAP` / `_PC_ALLOC_OLD` / `_PC_SNAP` 在当前引擎中计数**均为 1**（独立复验通过；`sig_lag` 默认 0 ⇒ 执行日 = 信号日 +1，t+1 执行链成立）。
- t-only 读取（`_weight_block:94-95`）：`_w_vals = list(_w_facsrc.loc[sig_day, picks])` —— 信号日快照，与 `picks = inp.picks(sig_day, …)` 同一信息集；`sig_day = dates[sig_i]`，执行价取 `day = dates[i]`（t+1），读价与执行价分离正确。`factor` 在 K18 全链恒为 `"amihud_60"`，else 分支死代码。
- 因子面板无前视：`prior_check.py:63-64`，`amihud60 = (r/(amt/1e8)).rolling(60, min_periods=60).mean()` —— trailing 60 日均值，无 center，`.loc[sig_day]` 只用 t 及以前数据。rank_linear 的秩假设经实测成立（`fresh2_max.py:30` `sort_values(ascending=False)`，抽查一日 desc-sorted=true，权重 [0.4,0.3,0.2,0.1] 对齐）。
- 归一化/整手（`:116-119` + 替换后 loop）：`sum w = 1`，`alloc_i = equity×exposure×w_i`（exposure≤1 保持：A 1.0 / B 0.9；brake bf≤1 先乘在 _w_expo 上，与原生 `alloc×bf` 逐值等价）；lot 取整行与原生逐字一致（仅 alloc→_w_alloc），cash-fallback（`int(max(cash-fee,0)/px//lot)*lot`）逐字保留 —— fallback 与 alloc 无关，对大小权重码一视同仁，无隐性前视。边界：n=1→[1.0]，n=0→[]（调用前 `if not picks: return` 守卫），amihud 非正/NaN→0、全退化→等权（实测 nan-fallback=[0.5,0.5]）。long-only、无杠杆。
- 影子/实盘一致：影子经 `get_single_ns`（patched prior_check），实盘开关经 `run_switch_weighted` 内联组合（`_weight_block` 同一函数 + brake 缩放）；RS 比较保持原生 trailing-60 raw（OLD_RS 未动）。附带发现：`_patch_switch_source` / `get_switch_ns` 在 pilot 中是**死代码**（sweep 只 import `get_single_ns`），实盘走的是 sweep 内联组合 —— 两处权重逻辑经比对逐行等价（同一 `_weight_block` + 同 brake 缩放替换式），死代码不构成风险，但建议 R35 后续合并且只留一处实现。
- 口径：`CA_BASE`（`sweep_beat_m07_k18.py:81-84`）capital 50000 / lot 100 / cost_one_way=None / slip 0.002 / run/eval 日期 / legacy_grid=False / full_liquidate=True / stop 0.25 stop_exec next / MB 排除，与 M07 逐字一致；A/B 参数 gbf07 座（cut 0.78 / win 40/20）与 K3 g_bf07 行一致；brake GBX/GBY/GBF=(0.15,0.05,0.7)。`run_switch` 内 `assert weight is None` 保证校准行必走等权原生路径；`check_calib` 双基线断言通过（sweep 落盘即证明）。
- **权重前视：PASS。归一化/整手/影实一致/口径：PASS。**

### §5.2 k18_amiprop_gbf07 全套 T 线（nbeat=1，按规则执行；产物 `tline_k18_amiprop_out.json`）

- leg1 独立复算：模块重跑（`K18.run_one`）与本地重组（tline 内重写 composition，返回 res 对象）**双路** total/mdd/trades/cost/switch_log 与 JSON **五项零偏差**（1581.87/−25.82/180/44712/7 切），nbeat=1 复现。**PASS（可复现），但不晋级。**
- leg2 跨相位（加权 vs 同相位等权 gbf07 座，ph 0/5/7/10/14/15）：

| ph | 加权 total | 加权 nbeat | 加权切 | 等权 total | 等权 nbeat | 等权切 |
|---|---|---|---|---|---|---|
| 0 | 1581.87 | 1 | 7 | 2128.41 | 5 | 3 |
| 5 | 923.10 | 0 | 10 | 688.11 | 0 | 10 |
| 7 | 943.06 | 0 | 9 | 1081.96 | 1 | 8 |
| 10 | 280.57 | 0 | 13 | 410.97 | 0 | 13 |
| 14 | 277.96 | 0 | 12 | 354.84 | 0 | 12 |
| 15 | 269.49 | 0 | 10 | 527.78 | 0 | 12 |

加权仅 ph5 以 total 胜等权（923.10 vs 688.11，但双双远低于 M07，nbeat 0/0，无意义的矮子胜）；ph0 外加权 nbeat 全 0，等权座除 ph0 外最高 nbeat=1。切换数全面膨胀（9–13 切）。无一相位组合稳定占优 —— **跨相位 FAIL（无一致 edge）。**
- leg3 ex-top3：加权 extop3_total **1171.01%** vs M07 1351.75%，去头后落后 180.74pp（top3 占 PnL 24.85%，与 M07 26.4% 相近 —— 非集中赌博，纯粹水平损失）。**FAIL。**
- leg4 滑点加倍（slip 0.002→0.004，影子+开关全链）：total **1315.35**（Δ −266.52），mdd −26.60，切数 7 不变，nbeat vs 标准 M07 = **1**。绝对缩水 266pp 且仍只赢一窗 —— **FAIL。**
- leg5 权重全快照等价（t-only 独立重算 `compute_weights(fac.loc[sig_day, codes])` vs 快照 `weights` 归一化）：live 40 快照、shadowA 47、shadowB 31，**最大绝对差 1.9e-9，mismatch 0**。执行日→信号日按 sig_lag=0 回推（exec idx −1），全部对齐 —— 影子与实盘逐笔权重可证明只用 t 及以前排序。**PASS。**
- 一致性抽查：加权 B 影子终值 783.2 == k18_amiprop_B 单腿 total 783.2（影子=实盘 sizing 的闭环证据）。

### §5.3 “加权推高切换”机制确认 —— 成立

- 影子同加权是因：`run_switch_weighted:233-234` 开关读入的 `shadow_a/b` 即加权影子（非等权影子），RS 输入被加权改写是构造性的。
- RS 漂移量化（ph0，A 网格信号日 29 个有 60 日历史）：等权影子 vs 加权影子 desired 分歧 **3 天**（2024-08-01 eq=B/w=A；2024-12-16 eq=A/w=B；2025-03-19 eq=A/w=B），分歧日均落在实盘新增切换附近（amiprop 新增 2024-10-21→B、2025-01-14→A、2025-03-19→B、2025-04-17→A，均含在 §2 JSON switch_log 中）。
- 影子终值漂移：A 腿 1270.62→1053.73（−217pp），B 腿 592.56→783.20（+191pp）—— 加权同时压低 A、抬高 B 的 trailing-60 收益，RS 比较被系统性扰动；开关 3→7（ranklin 更是 3→11，total −616pp vs 同座），呈现"权重越集中→切换越多→total 越差"的单调恶化。
- 结论：**机制确认 —— 腿内加权通过改写影子 trailing-60 收益漂移 RS 判定，推高切换频率（+4 切），total −281pp 且回撤无改善（−25.82 vs M07 −27.05 虽浅 1.23pp，但六窗仅赢 3m 一窗 +2.05pp，远不构成晋级）。**

### §5 判决

- **Verdict: FAIL（K18 试点关闭）。前视/口径/独立复算/权重等价四项 PASS，最好行 nbeat=1 且 T 线四条实证腿（跨相位无一致 edge、ex-top3 落后 181pp、滑点加倍归零到 1 窗且绝对 −267pp）全败，beat_all=0，机制上确认加权有害（+4 切/−281pp）。** 按 batch_039 同规则：nbeat<4 本可 moot，本次按指令执行 T 线，结果同样不支持晋级。Paper-track 保持 M07；rank_linear / amihud_prop 两种腿内加权均不得上线。

