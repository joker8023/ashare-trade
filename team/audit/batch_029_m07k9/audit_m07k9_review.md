# M07K9 复核（batch_029_m07k9）

## 0. 一句话结论与关键数字

一句话：任务所指的 K9 新选股器试点实际不存在——`research/inputs_k9.py` 与 `results/r30_bt/sweep_beat_m07_k9.json` 均无此文件（`part_029_verify.json` premise 四项：false/false/true/true），真实 K9 只有 `research/deep_tail_k9.py` + `results/r30_bt/deep_tail_k9.json`（K8 最强行 g_bf07_winA30 vs base_M07 的双配置深挖，选股器仍是 amihud_60，无 size/amount_level/amihud_5 新因子）；可审计范围内 beat_all=0、最高 nbeat=4、深尾短窗双负，判 FAIL，K9 试点全灭（且是“未产出即全灭”，不是“新因子被证伪”）。

关键数字（本轮独立复算，`part_029_verify.json`）：
1. K8 共 8 行：beat_all 独立重算 =0，文件声明 mismatch=0；新配最高 nbeat=4（g_bf07_rs70 / g_bf07_winA30 / g_bf07_rs70_winA30 / g_bf07_cut75），无 nbeat>=5、无 beat_all。
2. base 校准行 vs `M07_final.json`：total/mdd/六窗偏差全部 0.00（M07：total 1863.27 / mdd −27.05；六窗 −4.09 / 17.28 / 39.00 / 164.05 / 1474.08 / 1677.53）。
3. K9 深尾全精度差值（g−base）：1m −0.001832pp / 3m −0.035506pp / 6m +0.255293pp / 1y +0.350860pp / 2y +6.217112pp / 3y +193.037064pp；尾部持仓 identical：1m=true、3m=true。
4. 深尾文件自洽：ret_full = end/start−1 复算最大偏差 0.0；deep round2 vs K8 同名行 8 值偏差 0.0；`shift(-` 全库零命中。

## 1. 前提更正（任务描述与落盘事实不符）

- 任务称“见 research/inputs_k9.py 与 results/r30_bt/sweep_beat_m07_k9.json”——两文件都不存在（glob + exists 双证，见 premise 项）。实际 K9 产物仅为深挖对（deep_tail_k9.py/json，R9 12:28 落盘），其 docstring 与代码逐行确认：factor=amihud_60（第 50/110 行写死），CFGS 仅 base_M07 与 g_bf07_winA30 两配置，无新选股器、无 size/amount_level/amihud_5 引用（grep 新因子名在 sweep_beat_m07_k*.py 与 deep_tail_k9.py 中零命中）。
- 后果：任务第 1 条要求的“逐行审查 inputs_k9.py 窗口定义”无法执行——本报告不对不存在的文件做前视结论，不把未审计数字说成达标（见 §5 T6）。

## 2. T 线执行情况（无新 selector 候选，触发条件空集）

- 触发门：beat_all 或 nbeat_m07>=4 的新 selector 候选。K1–K8 累计 120 新配 beat_all=0；K8 四个 nbeat=4 行均为同 selector（amihud_60）阈值/刹车/RS 微调（K8 脚本第 1–12 行口径声明 + 第 67–69 行 CA 写死 factor），非新 selector。故全套 T 线对新 selector 的触发集为空集——不是“通过”，是 moot。
- 仍执行的普适核查（part_029_verify.json + 源码阅读）：
  (a) 前视：实际使用的 X3Inputs.picks（research/design_r30_grid8.py 第 30–47 行）只做 `.loc[t]` 切片；ret60/ret10 用 shift(60/10)，MaxInputs.maxret 用 rolling(max_win) trailing（research/fresh2_max.py 第 18 行）；全库 `shift(-` 零命中；成交为信号 t 执行 t+1（deep_tail 第 99 行 sig+1 映射、stop_exec=next）；RS 用 trailing shadow searchsorted。——对已用代码判通过；对不存在的 inputs_k9.py 不判。
  (b) 口径：K8/K9/M07 同为 ph0 / RUN_START=2023-01-03 / EVAL_END=2026-11-12 / 5 万 / 现实费率 cost_one_way=None / slip=0.002 / lot=100 / legacy_grid=False / full_liquidate=True / stop_next / amihud_60 / MB 排除（K8 脚本 assert + deep_tail meta caliber + 文件对账 0 偏差三重互证）。
  (c) 跨相位：K8/K9 仅跑 ph0；换相位成绩未知。T1 家族线（ph0 峰值含相位运气，batch_017 已触发）延续触发态，不因本轮改变。
  (d) ex-top3：M07 extop3_total=1351.75（top3 占比 26.4%）；无晋级候选，ex-top3 重跑 moot，未做、不宣称。
  (e) 滑点加倍：无候选可跑，moot，未做、不宣称。
  (f) 独立复算：本轮 JSON 级独立重算 0 偏差（§0 第 4 项）；引擎级已有 R9 与 batch_024 两套独立实现 10 位小数互证（batch_024 §7bis），本轮引用、不重复烧机。

## 3. K9 失败归因：是“短窗身份墙”，与新因子无关

- 深尾结论（batch_024 已立、本轮文件级复核一致）：1m/3m 窗内两策略持仓代码集合逐字相同（identical=true），g 只是等比放大（≈1.274×）配更大分母——1m 微负 −0.001832pp、3m 反输 −0.035506pp 是分母效应；刹车尾部全程 OFF、win_a/cut_a 作用 A 腿而尾部 mode=B，可调旋钮在尾部全部失效。
- 该结论解释的是同 selector 峰顶叠加为何撞墙，不能外推到新选股器：因子本身弱 vs MAX/切换不兼容——无任何新因子实盘数据，本轮无法区分，也不做判断。

## 4. 新 selector 方向状态：未关闭、未开启（仍是未探明方向）

- 关闭条件（新因子被证伪）未满足：没有任何新因子回测落盘。开启条件（新因子通过 T 线）同样未满足。
- 第二轮是否需要：需要——但前提是先有真实 Inputs 实现落盘（size/amount_level/amihud_5 等），且立项时必须重立全套 T1–T6（含 size×MAX 交互这个 batch_020 遗留 moot 项）；在该文件出现之前，任何“新 selector 已验证/已证伪”的说法均为违规宣称。

## 5. 认错触发情况

- 本轮 T1–T6 均未新触发（无 beat_all / 无 nbeat>=5 候选，T1/T3/T4 moot；T2 最高 nbeat=4；T5 无候选 moot；T6 对已用代码通过、对不存在的新因子文件明确不判）。
- 延续态：T1 在 batch_017 已对 g_bf07 触发，本轮峰顶仍是同族行，触发态延续（非本轮新触发）。
- 无达标宣称：K1–K8 累计 120 新配 beat_all=0；K9 未产出新 selector；paper-track 维持 M07，K8/K9 任何行不得实盘。


## 5. 真实产出复核（R15 落盘后补审，§0–§4 的时序误判保留）

说明：§0–§4 写于 R15 回测落盘前（`research/inputs_k9.py` 与 `results/r30_bt/sweep_beat_m07_k9.json` 当时确无此文件，`part_029_verify.json` premise 留证），结论“未产出即全灭”系时序误判、特此保留审计链。本节对真实产出做全套 T 线复核，取代 §0–§4 的空集结论，verdict 仍为 FAIL（见 §6 更新）。

### 5.1 复核对象与去重

- `research/inputs_k9.py`（K9Inputs：size/amount/amihud_5 三种 trailing 排序键）+ `research/sweep_beat_m07_k9.py`（12 配：3 selector × 单腿B/双腿 × MAX开/关）+ `results/r30_bt/sweep_beat_m07_k9.json`（13 行 = base + 12）。
- 去重：k9_ 前缀 12 tag 与 K1–K8 tags 交集为空（程序比对，仅 base_M07 为各文件共有校准行）；base 行 vs M07_final total/mdd/六窗/trades/switch_log 偏差全 0.00。
- 全文件独立重算 nbeat/beat_all（严格大于口径）：mismatch=0；beat_all=0（13 行）；新配最高 nbeat=3（k9_amihud_5_both_on/off）；mdd_better=0（12 新配 mdd 全差于 −27.05，最好 −27.36）。

### 5.2 前视逐行审查（inputs_k9.py，全 96 行，PASS）

- 池子：复用 MaxInputs（MAX开）/ X3Inputs（MAX关）`picks(t, 9999, ...)` 全池，seasoned/adv20/close/amihud60/gate/band/exclude 全套 M07 条件（第 82–91 行），无新增过滤、无 ST 过滤（与 M07 一致，如实声明第 13–14 行）。
- 新排序键（第 64–74 行 `_rank` + 第 95 行 `mat.loc[t, base]`）：size→`cap.loc[t]` ascending；amount→`adv20.loc[t]` ascending；amihud_5→`amihud5.loc[t]` descending。
- trailing 证明：`amihud5 = (|ret|/(amt/1e8)).rolling(5, min_periods=5).mean()`（第 59–62 行）只用 t 及以前；`cap = close×shares` 静态快照与 M07 同款伪市值（prior_check.py 第 67–68 行注释）；`adv20` rolling(20, min_periods=10) trailing；`maxret` rolling(max_win) trailing（fresh2_max.py 第 18 行）；全库 `shift(-` 零命中（`part_029_verify.json`）。
- 执行：`.loc[t]` 只读 t 切片；`cap` 截面分位用 t 日收盘、执行 t+1（`stop_exec=next` + 引擎 sig→exec+1 映射，与 M07 逐字一致）；RS trailing `searchsorted−1`（batch_024 已审计）。
- 实例绑定细节（第 28–31/76–80 行 + sweep 第 76–78 行）：switch 引擎双腿共用单一 factor（switch_engine.py L190），K9Inputs 忽略传入 factor、以构造期 sel 为准；单腿B传 amihud_60（A 腿 M07 生效、B 腿 K9 忽略）、双腿传 selector（两腿 K9 均按实例 sel）。行为与声明一致，无暗门。
- 结论：新因子前视门通过；shares 快照与 M07 一致（同为静态伪市值，非新增口径差）。

### 5.3 最好两行独立复算（0 偏差）

- 方法：`work_029_k9deep.py` 独立复现 sweep 口径（自建缓存、NS=build_ns(0.18,0.08,0.6)、同影子参数），重跑 k9_amihud_5_both_on 与 k9_amihud_5_B_on（phase0/slip0.002）。
- 结果：both_on 得 total 1338.14 / mdd −34.87 / trades 196 / switches 7 / 六窗 2.02/16.66/41.21/167.24/1058.99/987.98 / nbeat=3——与文件逐值一致；B_on 得 1496.03 / −30.93 / 209 / 15 / nbeat=0——逐值一致。独立复算 0 偏差。

### 5.4 跨相位（ph0/5/15，T1 触发）

- both_on：ph0 total 1338.14（nbeat 3）→ ph5 536.45（nbeat 1）→ ph15 381.34（nbeat 0）；switches 7→4→16，mode B→A→A。
- B_on：ph0 1496.03（nbeat 0）→ ph5 751.71（nbeat 1）→ ph15 886.13（nbeat 0）；switches 15→9→8。
- 判定：**T1 触发**——ph0 的相对优势（both_on 唯一的 nbeat=3）纯系相位运气，换相位即崩（−60%~−70% total），且 M07 自身 T1 家族线延续。任何“amihud_5 双腿接近晋级”的说法不成立。

### 5.5 ex-top3（T3 触发）

- 方法：校准重跑 trades 按 code 加总 net_pnl，取 top3，extop3_total = (end−start−top3pnl)/start×100。
- both_on：top3 = 603137（144835.60）/ 603580（78780.07）/ 002713（58553.23），extop3_total = **773.80**；B_on：top3 = 603580（106797.23）/ 003004（96607.11）/ 002713（72834.50），extop3_total = **943.56**。M07 extop3_total = 1351.75。
- 判定：**T3 触发**——两行 ex-top3 均大幅落后 M07，收益高度集中于 2–3 票，不具备分散鲁棒性。

### 5.6 滑点加倍（T4 触发）

- both_on slip 0.002→0.004：total 1338.14→1137.90（−200.24pp），nbeat 3→1（仅 1m 存活），trades/switches 不变（196/7）。
- B_on：1496.03→1175.27（−320.76pp），nbeat 0→0。
- 判定：**T4 触发**——成本敏感、加倍即再掉一档，无成本鲁棒性可言。

### 5.7 MAX 开/关 6 对逐位相同（claim 核验：通过，非 bug）

- 文件级：6 对（同 sel×同 legs，on vs off）total/mdd/六窗/trades/switches 逐值相等。
- 机制核验：`use_max` 透传无误（K9Inputs(piv, use_max=max_on, sel=kind)，`_inp_cache`/`_shadow_cache` 键均含 max_on，无缓存串扰）；抽查 amihud_5×B 腿 46 个调仓日 `picks`：on/off 逐字相等（diff=0，`work_029_maxpair.py`）。
- 解释：MAX cut（maxret 上 20% 分位剔除）作用于 9999 全池，而 K9 排序键的 head-N（4/5 票）在 6 组配置下均未命中被剔除名单——过滤真实生效但不改变头部选择，故整条成交路径相同。这是“ Across 全部 6 对”的强证据，非舍入假象。结论：claim 成立；副作用是 MAX 与新 selector 零交互（batch_020 遗留的 size×MAX 交互问题仍无数据，继续 moot）。

### 5.8 其余家族与 T2/T5/T6

- T2（邻域过拟合）：最高 nbeat=3 < 5，无候选，moot；且 amihud_5 双腿是孤立单点（单腿B同族 nbeat=0），峰形不支持。
- T5（择时运气）：12 新配 switch_same_m07 全 False，切换路径全漂移；跨相位下 switches 4–16 剧烈变化——择时不稳定，佐证 T1。
- T6（口径）：§5.2 通过 + base 校准 0 偏差 + 去重干净；ST 不过滤与 M07 一致（已声明）。
- size/amount 两族：total 115–1311、mdd −27.36~−40.84，全面落后 M07（1863.27/−27.05），双腿 size_total 仅 115.48——方向性证伪（不是噪声，是系统性落后）。

## 6. verdict（更新，取代 §0–§4 的空集结论）

- **FAIL**：K9 真实产出 12 新配 beat_all=0、最高 nbeat=3、mdd 全差；最好行三重 T 线触发（T1 相位运气 / T3 集中 / T4 成本敏感），ex-top3 与跨相位双杀；size/amount 两族系统性落后。
- 新 selector 方向判定：**首轮试点关闭**——amihud_5/size/amount 在当前池+MAX+switch 框架下无晋级路径；但关闭范围仅限“已测三键 × 单腿B/双腿 × MAX开/关”组合空间，不扩展到未测的新键或新框架。第二轮如需重启，须换键或换框架并重立全套 T 线。
- 认错触发：T1/T3/T4 本轮新触发（对象：k9_amihud_5_both 行）；T2/T5/T6 moot 或通过；T1 家族延续线不变。
- 产物清单（仅本目录）：`work_029_verify.json` 系旧版（`part_029_verify.json`）保留；新增 `work_029_k9sum.py`、`work_029_maxpair.py`、`work_029_k9deep.py`、`part_029_k9deep.json`、`work_029_k9dedup.py`、本文件。

## 6. verdict(旧版保留)

- **FAIL**：K9 试点全灭（空集式全灭——未产出任何新 selector，而非新因子被证伪）；新 selector 方向保持未探明，需真实 Inputs 落盘后第二轮重审。
- 产物清单（仅本目录）：`work_029_verify.py`、`part_029_verify.json`、`audit_m07k9_review.md`（本文件）。
