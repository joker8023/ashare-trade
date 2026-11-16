# M07K11 联合重构试点复核（batch_033_m07k11）

## 0. 一句话结论与关键数字

一句话：K11 新家族（hysteresis 带宽切换×刹车冻结联动 × K10 a60_a5 复合选股器）6 新配全灭——beat_all=0、最高 nbeat_m07=0（六行全 0 窗胜出）、mdd_better=0、win_all=0，触发集（beat_all 或 nbeat>=4）为空集，全套 T 线对候选 moot；切换引擎前视逐行通过（10 锚点唯一、除切换判据外与 M07 build_ns 逐字一致、零未来引用）、口径 PASS、base 校准零偏差、独立复算 0 偏差（含截断对照 ALL OK＋最佳行内存重跑 17 键零偏差），判 **FAIL**，联合重构第一试点在已测 6 配空间内关闭。

关键数字（本轮独立复算，`part_033_verify.json`／`part_033_repro.json`）：

1. 7 行 = base_M07 + 6 新配（hyst∈{0.02,0.05,0.10} × legs∈{B,both}，sel=a60_a5，MAX on，brake_freeze on）；beat_all=0；新配 nbeat 全 0；mdd_better=0（新配 mdd 区间 −29.74 ~ −39.53，M07 −27.05）。
2. 最好行 k11_h05_B：total 1680.98（M07 1863.27，差 −182.29pp）、mdd −29.74（差 −2.69pp）、switches 5、六窗全输（1m −5.73/3m 15.66/6m 36.93/1y 159.63/2y 1292.04/3y 1350.71）。
3. 双腿变体崩：k11_h05_both total 959.42（全场最低）、k11_h10_both mdd −39.53（全场最深）；单腿B（1412–1681）系统性好于双腿（959–1070），与 K10 同构。
4. 1m 墙加厚：K11 最好 1m −5.68（h10_B）vs M07 −4.09，缺口 −1.59pp（K1–K10 最窄缺口仅 −0.01pp）——a60_a5 选择器把短窗基数整体下移，切换机制未补回。
5. 迟滞机械有效但无收益：switches 随 h 增大 7→5→4/3（whipsaw 下降），但无一窗转正；brakes 1–2（M07 为 3）。
6. 引擎：10 锚点在 switch_engine.py 中计数全 1、9 个 patch 常量与 M07 build_ns 逐字相等、brake_eval 归一化 608 字相等、skip_block 相等、build_ns_k11() exec 成功；新判据 token 仅 {mode,ra,rb,_brake,_BRAKE_FREEZE,_HYST,desired}，禁 token（dates/mark/searchsorted/iloc/loc/picks/pos/cash/grid/sig_i/shadow）零命中；code 区 dates[ 出现 1 次（= CC 锚常量本身）。
7. 口径/base/去重/重算：sweep 三 assert 通过、CA 与 M07 逐字一致、影子腿与实盘腿一致；base_M07 行 12 键＋switch/brake 双 log 与 M07_final.json 零偏差；k11_ 6 tag 与 K1–K10 零重名（全库 dup 仅 base_M07 校准行）；JSON 六窗→nbeat/beat_all/mdd_better/win_all 独立重算 6/6 一致。

## 1. 复核对象

- `research/family_k11.py`（107 行：K11 切换引擎构造器，hysteresis＋brake_freeze，14:11 落盘）
- `research/sweep_beat_m07_k11.py`（208 行：6 新配＋base 校准，14:12 落盘）
- `results/r30_bt/sweep_beat_m07_k11.json`（7 行，14:13 落盘）
- M07 基线：`results/r30_bt/M07_final.json`（total 1863.27 / mdd −27.05；六窗 −4.09 / 17.28 / 39.00 / 164.05 / 1474.08 / 1677.53；switches 3）
- 参照：switch_engine.py（355 行）、sweep_beat_h1_v4.py（build_ns，M07 机制母版）、inputs_k10.py（batch_031 已审 PASS）

## 2. 前视逐行审查（family_k11.py 全 107 行：PASS，有条件）

- 构造方式：读 switch_engine.py 源码做字符串 patch 后 exec，与 M07 build_ns 同机制（非新回测循环）。10 锚点在母版中计数全 1（anchors_all_unique=true），任一锚点漂移即 assert 炸（fail-closed）；9 个沿用 patch 常量与 v4 逐字相等（anchors_match_v4=true）。
- 切换信号（第 89-95 行新判据）：仅读 ra/rb（影子 trailing-60d 收益，母版 _rs 经 searchsorted right-1 取 sig_i 及以前影子值，母版第 93-99 行，既往已审）、mode、_brake、_HYST/_BRAKE_FREEZE。判据块禁 token（dates/mark/searchsorted/iloc/loc/picks/pos/cash/grid/sig_i/shadow）零命中；code 区未来引用扫描（shift(-、sig_i 加偏、searchsorted、iloc、loc、exec_map 重定义、px_ffill_or_nan 新增调用）全 False；dates[ 出现 1 次且为 CC 锚常量本身。外层 gate（仅 A 网格信号日评估，母版第 171 行）未被 patch 触及。
- 影子比较：h=0.02/0.05/0.10 为收益率单位阈值（ra/rb 为 60d trailing 收益分数，单位一致）；mode 为 A 时 rb-ra>=h 才切 B，反之亦然；等值边界与 M07（ra>=rb 切 A）差一 ULP 翻转——hyst=0 加 freeze 关也不是 M07 比特复刻，回归门须按近似而非全等立（见 6）。
- 刹车联动：brake_eval 插入点（CC 之后、切换评估之前）与顺序和 build_ns 逐字一致（归一化 608 字相等；初版 false 系提取引理把 K11 多行括号写法与 v4 单行转义写法直接比所致 artifact，check3 已正）；刹车口径 bx/by/bf=0.18/0.08/0.6 与 M07 一致；冻结仅抑制 desired（desired=mode），brake_eval 本身仍每信号日更新，brake_log 可比（K11 brakes 1-2 对 M07 的 3，系持仓路径不同所致，非口径差）。执行时点：exec_map（信号 t 到执行 t+1，母版第 62-66 行）、stop_exec、sig_lag 均无 patch——信号与执行仍差一 bar，picks 用 sig_day、成交用执行日价，与 M07 同。
- 费用/整手：K11 未碰 capital/lot/cost_one_way/slip/full_liquidate 任一行；口径一致性由 sweep 脚本保证（见 3）。
- 选择器装配：sel=a60_a5 的 K10Inputs（batch_031 已审 trailing 与 t-only，MAX on）；本轮独立复跑 sweep 自带 trailing_check：2 日期全量对截断实例 picks 逐字一致加 amihud5 手工 1e-9 一致（ALL OK，见 4）；A_P 参数化的 K10Inputs 实例（both 腿 A 侧）未被 trailing_check 直接覆盖，但走同一 picks 代码路径（机制已审），记观察项不记 fail。
- 背景断言核验：docstring 称 K9 amihud5 系 sw=7、K10 a60_a5_B sw=11、a60_adv_both sw=11、M07=3——实测 k9_amihud_5_both_on/off sw=7（注：为 _on/_off 双行，非裸 tag，双行一致）、k10_a60_a5_B sw=11、k10_a60_adv_both sw=11、M07 sw=3，实质成立。
- 条件：前视 PASS 以影子曲线与实盘腿同实例（sweep 第 89-90 行已满足，见 3）为前提；任何换腿换 sel 的后续 sweep 须重跑本节。切换机制前视一票：本节无否决项。

## 3. 口径（PASS）与去重（干净）

- sweep 第 44-46 行三 assert：RUN_START=2023-01-03、EVAL_END=2026-11-12、WINDOWS 六窗格与 M07/K1-K10 一致；grid/first_sig 推导逐字同 K1。
- 腿参数 A_P/B_P（band/gate/cut/win）、A(5/20/1.2/1.0) 与 B(4/30/0.80/0.9) 腿格、rs_lookback=60、phase=0，与 run_m07_final.py 及 K1 一致（sweep 第 51-52、89-91、95 行）。
- 费用执行 CA：factor 按腿切换（M07 腿 amihud_60，K10 腿 a60_a5 但 K10Inputs 构造期绑定 sel 而忽略传入 factor，与 batch_031 第 28 行实例绑定结论一致）、stop=0.25、stop_exec=next、exclude=MB、capital=50000、lot=100、cost_one_way=None（现实费率）、slip=0.002、legacy_grid=False、full_liquidate=True（第 80 行），逐字 M07。base 行走 NS_M07（v4 build_ns 0.18/0.08/0.6），K11 行 brake 参数同值。
- 影子与实盘腿一致：B 腿配置 A 腿用 M07 MaxInputs、K11 腿用 K10Inputs(a60_a5)，影子（第 89-90 行）与实盘腿（第 97 行同 inp_a/inp_b）同实例；both 配置双腿同切 K10。无影子实盘错配。
- 新配严格 6（第 117 行 assert），预算 8 以内；tag 全 k11_ 前缀；全库 tag 去重：k11_ 6 个零重名，dup 仅 base_M07 校准行（每轮一条，预期内）。
- base 校准行：total/mdd/trades/cost/mode/switches/六窗 12 键零偏差（BASE_MISMATCH 空），switch_log 3 段与 brake_log 6 段逐项相等（双 True）。

## 4. T 线执行情况（触发集空集，moot；普适核查全过）

- 触发门：beat_all 或 nbeat_m07>=4 的新家族候选。K11 结果：beat_all=0，最高 nbeat=0（六行全 0）——触发集为空集，全套 T 线（跨相位、ex-top3、滑点加倍）对候选 moot，不是通过，不做、不宣称（与 batch_031 K10 同例）。
- 仍执行的普适核查：(a) 前视 PASS（2，有条件）；(b) 口径 PASS（3）；(c) 跨相位：无候选可跑，moot（未跑、不宣称；M07 自身 T1 家族线延续态不变）；(d) ex-top3：moot；(e) 滑点加倍：moot；(f) 独立复算：JSON 六窗到四旗重算 6/6 一致（RECOMP 全 match=True）；base 校准 0 偏差（见 3）；最佳行 k11_h05_B 内存重跑 17 键零偏差＋switch/brake 双 log 逐项相等（part_033_repro.json repro_all_zero=true）；trailing_check 独立复跑 ALL OK（2 日期 picks 逐字一致、amihud5 手工 1e-9）。
- 唯一 mdd 相对最浅行 k11_h05_B（-29.74）：仍差 M07 -2.69pp 且六窗全输——单回撤浅而无一窗胜出不构成晋级理由（任务要求六窗全超且回撤更浅，缺一不可），不触发任何重跑。

## 5. K11 失败归因与方向判定

- 现象：3 h 值乘 2 腿型全灭；双腿（959-1070）系统性差于单腿 B（1412-1681），复刻 K10 双腿惩罚；迟滞把 switches 从 7 压到 3-5，但六窗恢复数为 0——whipsaw 不是瓶颈，瓶颈在选择器腿的收益基数本身（a60_a5 在 K10 已证六窗近全输，换切换机制未改变腿收益）。
- 1m 墙从缺口 -0.01pp 级加厚到 -1.59pp：a60_a5 把短窗整体下移（六行 1m 全在 -5.7 附近），切换机制只能改持仓归属、改不了尾部持仓身份与分母效应（与 batch_024 短窗归因同构）。
- 判定：联合重构第一试点（hysteresis 加 brake-freeze 乘 a60_a5）在已测 6 配空间内关闭。关闭范围 = {h 0.02/0.05/0.10} 乘 {单腿B/双腿} 乘 MAX 开。不关闭：其余 h 值、freeze 关变体、其余选择器、MAX 关——但须重立全套 T 线，且先过切换前视门。

## 6. verdict

- FAIL：K11 试点 6 新配全灭（beat_all=0、最高 nbeat=0、win_all=0）；前视/口径通过但无晋级候选；联合重构第一试点在已测空间内关闭。
- 认错触发：本轮 T1-T6 均未新触发（无候选，T1/T3/T4 moot；T2 最高 nbeat=0；T6 口径通过）。延续态不变。paper-track 维持 M07，K11 任何行不得实盘。
- 回归门建议（下轮若续测）：K11(hyst=0, freeze=False) 对 M07 应近似相等（等值边界一 ULP 翻转除外），建议立为必跑回归；冻结语义（刹车 ON 期不换路）须保留 brake_log 可比性审计。
- 产物清单（仅本目录）：work_033_verify.py、part_033_verify.json、work_033_check2.py、work_033_check3.py、work_033_repro.py、part_033_repro.json、本文件。约束遵守：未新增本目录外任何文件；未改动引擎/口径/结果文件；未把任何未审计数字说成达标。



