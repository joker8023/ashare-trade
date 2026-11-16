# M07K10 复核（batch_031_m07k10）

## 0. 一句话结论与关键数字

一句话：K10 复合秩和键 6 新配全灭——beat_all=0、最高 nbeat=1（k10_a60_size_both 仅 1m 存活）、win_all=0，触发集（beat_all 或 nbeat>=4）为空集，全套 T 线对候选 moot；文件级独立复算 0 偏差、base 校准 0 偏差、前视截断对照 ALL OK，判 **FAIL**，复合方向在已测空间内关闭。

关键数字（本轮独立复算，`part_031_verify.json`）：
1. 7 行 = base + 6 新配；beat_all=0；新配最高 nbeat=1（a60_size_both：1m −0.54 > −4.09，其余五窗全输）；mdd_better 仅 1 行（a60_adv_B −25.83 vs −27.05，但 nbeat=0、total 1244.63）。
2. 新配 total 区间 307.22–1437.72（M07 1863.27）；最好行 a60_a5_B 1437.72 仍低于 K9 最好纯键 amihud_5_B（1496.03），更远低于 M07。
3. base_M07 vs `M07_final.json`：total/mdd/六窗/trades/switch_log/brake_log 偏差全部 0（`base_all_zero=true`）。
4. 去重：k10_ 6 tag 与 K1–K9 tags 交集为空（overlap=0）；独立重算 nbeat/beat_all/mdd_better/win_all mismatch=0。
5. 前视：`--check-trailing` 3 键×2 日期截断对照逐字一致 + amihud5 手工点查 1e-9 通过；全库 `shift(-` 零命中。

## 1. 复核对象

- `research/inputs_k10.py`（K10Inputs：amihud60 秩 + size/adv20/amihud5 秩，秩和取小者优先）
- `research/sweep_beat_m07_k10.py`（3 复合键 × 单腿B/双腿 = 6 新配 + base_M07，全部 MAX 开）
- `results/r30_bt/sweep_beat_m07_k10.json`（7 行，2026-11-16 13:54 落盘）
- M07 基线：`results/r30_bt/M07_final.json`（total 1863.27 / mdd −27.05；六窗 −4.09 / 17.28 / 39.00 / 164.05 / 1474.08 / 1677.53）

## 2. 前视逐行审查（inputs_k10.py，全 100 行，PASS）

- 池子：复用 `MaxInputs.picks(t, 9999)`（MAX 开）/ `X3Inputs.picks`（MAX 关分支，K10 未启用），seasoned/adv20/close/amihud60/gate/band/exclude 全套 M07 条件（第 88–97 行）。
- 复合排序（第 71–80 行 `composite_order`）：`amihud60.loc[t, base]` 与第二键 `.loc[t, base]` 只读 t 切片截面；`rank`（默认 average 平分并列）+ 秩和 `sort_values`，无 t+1 数据；`dropna` 任一键缺值即剔除（与 K9 同口径，第 24–25 行声明）。
- trailing 证明：`amihud5` rolling(5, min_periods=5) 只用 t 及以前（第 60–61 行，与 K9 同构）；`cap` 静态快照伪市值与 M07 同款（如实声明）；`maxret` trailing（fresh2_max 第 18 行，既往已审）；执行 t+1（`stop_exec=next` + 引擎 sig→exec+1）；RS trailing `searchsorted−1`（既往已审）。
- 截断对照（producer 自带 `--check-trailing`，本轮复跑验证）：3 键 × 2 日期（2024-06-03 / 2025-09-01）全量 vs 截断实例 `picks(T,4)` 逐字一致；amihud5 手工重算（6 行窗 pct_change 后 5 值均值）1e-9 一致。结论：ALL OK。
- 全库 `shift(-` 零命中（research + team/audit，grep 实证）。
- 实例绑定（第 28–30/82–87 行 + sweep 第 80–82 行）：switch 引擎双腿共用单一 factor，K10Inputs 忽略传入 factor、以构造期 sel 为准；单腿B传 amihud_60、双腿传 selector。行为与声明一致。
- 结论：新复合键前视门通过；未发现未来函数。

## 3. 口径（PASS）与去重（干净）

- sweep 第 35–40 行 assert：RUN_START=2023-01-03、EVAL_END=2026-11-12、WINDOWS={1m:21,3m:63,6m:126,1y:252,2y:504,3y:756}；与 M07/K9 同口径（ph0 / 5 万 / 现实费率 / slip=0.002 / lot=100 / legacy_grid=False / full_liquidate=True / stop_next / MB 排除 / RS60 / 刹车 0.18/0.08/0.6；A/B 腿 band/gate/cut/win/take/n/rebal 与 M07 逐字一致，第 46–47 行）。
- base 校准行逐字复现 M07（含 trades=184、switch_log 3 段、brake_log 6 段，偏差全 0）。
- 去重：k10_ 6 tag 与 K1–K9 json tags 无交集；新配严格=6（第 106 行 assert），不超配。

## 4. T 线执行情况（触发集空集）

- 触发门：beat_all 或 nbeat_m07>=4 的复合候选。K10 结果：beat_all=0，最高 nbeat=1 → 触发集为空集，全套 T 线（跨相位 / ex-top3 / 滑点加倍）对候选 moot——不是“通过”，不做、不宣称。
- 仍执行的普适核查：(a) 前视 PASS（§2）；(b) 口径 PASS（§3）；(c) 跨相位：无候选可跑，moot（未跑、不宣称；M07 自身 T1 家族线延续态不变）；(d) ex-top3：moot；（e) 滑点加倍：moot；(f) 独立复算：JSON 级严格>重算 0 偏差（§0 第 4 项）。
- 唯一 mdd 更浅行 a60_adv_B（−25.83）：nbeat=0、六窗全输、total 1244.63——单回撤浅而无一窗胜出，不构成晋级理由，不触发任何重跑（任务要求六窗全超且回撤更浅，缺一不可）。

## 5. K10 失败归因与复合方向判定

- 现象：3 复合键 × 2 腿全灭；双腿变体（total 307–1261）系统性差于对应单腿B（1244–1438）；最好复合 a60_a5_B（1437.72）低于其纯键成分 amihud_5_B（K9：1496.03）——秩和稀释而非增强。
- 结合 K9 三纯键全崩（batch_029：12 配 beat_all=0、最高 nbeat=3、mdd 全差；size/amount 两族 total 最低至 115.48/280.12，方向性落后）：成分键本身无一成立，复合亦无一成立，且复合 < 最优成分。
- 判定：**复合方向在已测空间内关闭**——关闭范围 = {a60_size, a60_adv, a60_a5} × {单腿B, 双腿} × MAX 开。关闭理由是“成分+复合双重落盘证伪”（不是空集式未探明）。
- 未测空间（明确列出，不关闭、亦不开启）：MAX 关复合、非等权秩和/其他复合算子、新成分键、新框架（腿结构/切换机制）。第二轮如需重启，须换键或换框架并重立全套 T 线。

## 6. verdict

- **FAIL**：K10 试点 6 新配全灭（beat_all=0、最高 nbeat=1、win_all=0）；前视/口径通过但无晋级候选；复合方向已测空间关闭。
- 认错触发：本轮 T1–T6 均未新触发（无候选，T1/T3/T4 moot；T2 最高 nbeat=1；T6 口径通过）。延续态不变。paper-track 维持 M07，K10 任何行不得实盘。
- 产物清单（仅本目录）：`work_031_verify.py`、`part_031_verify.json`、本文件。约束遵守：未新增本目录外任何文件；未改动引擎/口径/结果文件。
