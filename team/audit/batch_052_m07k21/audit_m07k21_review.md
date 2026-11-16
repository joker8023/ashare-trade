# M07-K21 约束逐日复核（batch_052）

- 复核对象：R40 K21 约束逐日（逐日 × hysteresis / 长 RS，目标“保住长窗的短窗机制”）。
- 基线：`results/r30_bt/M07_final.json`（total +1863.27%，mdd −27.05%，trades 184，cost 50990，switches 3：2023-06-21→B / 2024-08-15→A / 2026-09-08→B；六窗 1m −4.09 / 3m +17.28 / 6m +39.00 / 1y +164.05 / 2y +1474.08 / 3y +1677.53）。
- K20 前情（本复核 JSON 级独立重验，见 §2）：逐日评估首破短窗——daily_M07 / daily_gbf07 / brakeD 均 nbeat=4（1m/3m/6m/1y 全超），但 2y/3y 崩（daily_M07 差值 −121.28/−92.17），switches 33 对 3，cost 97391 对 50990（+91%）。beat_all 全 0，目标未达成。
- 一句话结论：**FAIL（R40 交付物缺失：`research/sweep_beat_m07_k21.py` 与 `results/r30_bt/sweep_beat_m07_k21.json` 均不存在，逐行审计与 T 线无从执行；按“前视一票 FAIL”约束直接判 FAIL）。**

## 0. 输入核验 —— FAIL（阻塞项）

- `research/sweep_beat_m07_k21.py`：**不存在**（`ls` 报 No such file；`grep -ril k21` 在 research/results/team 下仅命中 k1 误报与 batch_022 ledger，无 K21 实现痕迹；research 最新文件止于 20:46 的 K20）。
- `results/r30_bt/sweep_beat_m07_k21.json`：**不存在**（该目录最新 sweep 止于 k20；inventory 止于 k38）。
- `team/audit/batch_052_m07k21/`：本报告创建前不存在。
- 后果：任务 1（逐行审计）与任务 2（K21 候选 T 线）**均无审计对象**，以下 §1 为 K21 交付后重审用的针对性清单（hysteresis/长 RS/拼接三项前视点），§2 触发集按 moot 规则记空，§3 先立 K21 判决标尺（K20 实测数）。

## 1. 逐行审计 —— 未执行（文件缺失）；R40 交付后必须逐项核查

K21 在 K20 逐日机制上加约束（hysteresis 阈值 / 长 RS 窗口），以下四项有一项不满足即一票 FAIL。行号指 K20 已审计实现（`research/evalfreq_k20.py`）与母引擎（`research/switch_engine.py`）的对应位置，K21 补丁必须能逐行映射回它们：

1. hysteresis 阈值只用 t 及以前：阈值比较的 ra/rb 必须来自 `_rs(shadow, ≤t)`（`switch_engine.py:93-99`：`searchsorted(dates[sig_i],right)-1` trailing 比值，`j<rs_lookback→None` 守卫；K20 逐日调用点 `evalfreq_k20.py:54-71`，`sig_i=_t`=执行日−1）。**严禁**阈值本身含未来统计（如用全样本 RS 差分位数定阈值即前视，必须是常数或纯 trailing 自适应）；“差距<阈值则维持 mode”的维持分支必须证明其计数器/状态初值不窥视未来（首个信号日前瞻 None 期只许维持，不得回填）。
2. 长 RS 窗口只用 t 及以前：若 `rs_lookback` 从 60 加长（如 120/250），`_rs` 的 `j<rs_lookback` 守卫必须同步加长（不得沿用 60 守卫配长窗口分母）；长窗口在样本早期的 None 期处理（维持 mode）不得回退到短窗口“事后选择”（同一 t 只许一个窗口出 desired，禁止“长窗 None 则用短窗”的回退逻辑——那是隐性多重比较）。
3. 与 `evalfreq_k20.py` 的拼接无时序漏洞：翻转执行仍须 `_ei=_t+1+sig_lag`（`evalfreq_k20.py:72-76`，`setdefault` 不覆盖网格映射）；选股仍用信号日 `sig_day=dates[_t]` 因子数据（引擎 `:168-190`）、执行价取 t+1 日 ffill 收盘；hysteresis 状态（上次 desired/连续计数）不得跨 phase、跨候选泄漏（`get_shadows`/`get_ns` 类缓存键必须含全部新参数——K20 已有 `_shadow_cache` 键遗漏 phase 的前车之鉴，batch_051 verify 脚本被迫自建 `_sh_cache` 补 phase 键）；`switch_log` 打标 `sig_day`（t）与 M07 网格版同形，不得把执行日记成信号日。
4. 口径恒等项：保留网格评估对照臂（同参数仅评估频率不同）+ `base_M07` 校准断言（total/mdd/六窗/trades/cost/`switch_log` 与 M07_final 逐字一致，K20 为 1863.27/−27.05/184/50990/3 切）；费用 `cost_one_way=None` 现实费率 + slip=0.002 + lot=100 + 5 万 + `stop_exec="next"` + `legacy_grid=False` + `full_liquidate=True` 不得顺带改动；EVAL 窗/WINDOWS/RUN_START/EVAL_END 与 M07 同口径。

## 2. T 线触发集 —— K21 空（moot）；K20 nbeat≥4 行触发态复验

- K21 触发集（beat_all 或 nbeat_m07≥4）：**空（moot）**—— sweep 文件不存在，无候选可评估；跨相位 / ex-top3 / 滑点加倍 / 独立复算全套 T 线按 moot 规则跳过，不跑。
- K20 触发态 JSON 级独立重验（本复核实跑 `.venv/bin/python`，逐行 `nbeat/beat_all` 由六窗数值重算）：base_M07 0/false；daily_M07 **4**/false（beats 1m/3m/6m/1y，d2y −121.28，d3y −92.17）；daily1_M07 3/false；daily_gbf07 **4**/false（d2y −117.03，d3y −100.13）；daily1_gbf07 3/false；brakeD **4**/false（与 daily_M07 数值逐字一致）。重算与 JSON 自带字段全部一致（`ALL NBEAT/BEAT_ALL RECALC OK`）。
- K20 两个 nbeat=4 候选的全套 T 线已在 batch_051 §5.2 由引擎级独立复算完成（`work_051_k20verify.py` → `part_051_k20.json`），结论引用不再重跑：独立复算 exact（含 switch_log/brake_log 逐字一致）；跨相位 ph5/10/15 nbeat 0/0/0（total 676.45/282.81/688.17，edge 全失）；ex-top3 不救（daily_M07 extop3 1441.42 vs M07 1351.75，但 2y/3y 照败）；滑点加倍（0.004）daily_M07 total 跌至 1509.70（cost +46951）、nbeat 归零。K21 若出现 nbeat≥4 候选，必须在 K21 自身参数上重跑同款全套 T 线（不得沿用 K20 数）。

## 3. switches/cost 是否真被压住 —— K21 无数可验；K20 实测为判决标尺

- M07 参照：switches 3，trades 184，cost 50990。
- K20 实测（未压住）：daily_M07 switches **33**（2024-03 单月 8 翻，2024-10/11、2025-08、2026-10 三簇密集翻转），trades 317，cost **97391（+91%）**；daily_gbf07 switches 25 / cost 88489；daily1 确认版把 switches 压到 17/15 但 total 反跌至 1625.43/1755.11（确认滞后、两头挨打）——**压 switches 本身不难，难的是不丢短窗 edge**。
- K21 判决线（交付后执行）：任一候选若 switches 回落，必须同时满足 (a) 短窗 nbeat≥4 不丢（1m/3m/6m/1y 仍全超），(b) 长窗差值收敛（d2y/d3y 负缺口相对 daily_M07 的 −121/−92 显著收窄，而非 daily1 式的 −211/−203 扩大），(c) 滑点加倍后 nbeat 不归零。否则只是 daily1 翻版，判 FAIL。

## 4. 判决

- **Verdict: FAIL（输入缺失：无实现可审、无结果可验；前视一票 FAIL。六窗全超 M07 且回撤更浅的策略在 K1–K20 落盘证据中仍不存在——K20 最好行 nbeat=4 但 beat_all=0、长窗崩、跨相位归零、滑点加倍归零。）**
- Paper-track 保持 M07；K20（含 brakeD 对照）不 provision、不上线；K21 待交付。
- 重启条件：R40 落盘 `research/sweep_beat_m07_k21.py` + `results/r30_bt/sweep_beat_m07_k21.json` 后，按 §1 四项清单逐行重审，任一 beat_all / nbeat≥4 候选跑全套 T 线（跨相位、ex-top3、滑点加倍、独立复算；核查 switches/cost/switch_log/brake_log diff）后方可改判。

*复核子 agent agent-59；工作目录 /Users/joker/coding/ashare-trade；§0–§4 为首查时序记录（当时 K21 未落盘）。其它目录零新增。*

## 5. 真实产出复核（R40 落盘后；§0–§4 时序保留）

- 落盘确认：`research/sweep_beat_m07_k21.py`（321 行，`build_ns_k21` 内联本文件，未动 `switch_engine.py`/`evalfreq_k20.py`）+ `results/r30_bt/sweep_beat_m07_k21.json`（6 行 = base + 4 phase-1 + 1 phase-2）。Phase-2 门控自洽：phase-1 最高 nbeat=4（hyst003_M07）≥4 开门，次席 hyst008/rs120/rs252 均 nbeat=0 故仅 best 进 gbf07 座位（`k21_daily_hyst003_gbf07`）。
- 六行摘要：base_M07 校准零偏差；hyst003_M07 nbeat=4/total 1708.17/mdd −27.11/sw 11/cost 56374；hyst008_M07 nbeat=0/total 1592.21/sw 5（过约束，反例）；rs120 nbeat=0/total 1368.30/sw 4；rs252 nbeat=0/total 1273.59/sw 2（长 RS 单用杀死 edge）；**hyst003_gbf07 nbeat=5/total 1934.29/mdd −24.28/sw 11/cost 63201**，六窗差值 +1.48/+5.27/+6.53/+12.46/−106.20/+55.95——首个“短窗大胜 + 仅差 2y + 回撤更浅（−24.28 vs −27.05）”候选，beat_all 仍为 0。

### 5.1 逐行审计 —— PASS（前视一票项通过；§1 四项清单逐项关闭）

- Hysteresis 只用 t 及以前（`sweep_beat_m07_k21.py:81-92`）：`ra/_rs(shadow, sig_i)`（`sig_i=_t`= 执行日 −1）经 `switch_engine.py:93-99`（`searchsorted(dates[sig_i],right-1)` trailing 比值，`j<rs_lookback→None` 守卫）纯过去；`_HYST` 为字面常数（0.0/0.03/0.08，`:109` 注入源码），非样本统计量；`desired` 初值恒为 `mode`，None 期只许维持，无计数器/隐藏状态。无未来函数。
- 长 RS 窗口只用 t 及以前：`rs_lookback` 经 KW 运行时传入（`:191`），`_rs` 内 `j<rs_lookback` 守卫随窗口同步加长；长窗早期 None 期维持 mode，**无“长窗 None 则回退短窗”逻辑**（单窗口出 desired）。rs120/rs252 把 total 砍到 1368/1274 证明长窗是真约束而非摆设。
- 逐日拼接/t+1 链路无时序漏洞：`EXECMAP_ADD`（`:93-97`）与 K20 同形（`_ei=_t+1+sig_lag`，`sig_lag=0`，`setdefault` 不覆盖网格映射）；选股 `sig_day=dates[_t]`、执行价 t+1 ffill 收盘（母引擎 `:168-199` 未动）；`get_ns` 缓存键含 hyst（`:158-162`），`rs` 走运行时 kwarg 而非源码 baked-in，无跨候选泄漏；`assert evalfreq in ("grid","daily")`（`:186`）封死 daily1 误用。注：`hyst=0.0` 网格分支在 `ra==rb` 精确相等且 `mode==A` 时与 M07 差一分支（浮点测度零事件），base 校准（total/mdd/六窗/trades/cost/`switch_log` 与 M07_final 逐字一致）实证无分歧。
- 刹车口径：补丁与 K20 逐字同形（`:107-141`，trailing peak/trough + `brake_daily=False` 硬编码 `:192`，调仓日门控 `_brake_gate`）。`brake_log` 日期实质一致：hyst003_M07 六个 ON/OFF 日期与 M07 逐字相同（仅深度 pct 随组合路径小幅漂移，如首 ON 18.93 vs 18.16——机制 verbatim 下的合法路径依赖）；gbf07 座位参数本就不同（bx0.15/by0.05）故日期可异；rs252 剩 2 对亦为路径依赖（2023-11-07 OFF 替代 09-18 OFF 等）。母引擎刹车评估只用当日及以前组合市值，无前视。
- 网格对照臂 + 费用整手：base_M07 行保留；5 万 / `cost_one_way=None` / slip=0.002 / lot=100 / `stop_next` / `legacy_grid=False` / `full_liquidate=True` / MB 与 M07 逐字一致（base 零偏差为证）。

### 5.2 独立复算 + T 线（`work_052_k21verify.py` 输出 `part_052_k21.json`，本目录）

- 独立复算（自建影子 + 自建口径，`build_ns_k21` 仅复用引擎构造）：base_M07 exact（含 `switch_log`/`brake_log` 逐字）且 `base_matches_M07_final=true`；**hyst003_gbf07 与 hyst003_M07 全部数值 + `switch_log` + `brake_log` 逐字一致（`recompute_exact=true`×2）**。
- 跨相位（ph 5/10/15 vs M07 ph0 窗）：best nbeat **0/0/0**（total 1068.35/427.80/519.25，mdd −30.59/−30.19/−26.04，switches 15/19/14）；runner 同样 0/0/0（934.53/333.87/680.10）。相位一动 edge 全失。跨相位 FAIL。
- ex-top3（交易 `net_pnl` 口径，batch_051 同法）：best top3_share **25.2**（M07 为 26.4——集中度不恶化）/ extop3_total **1424.64**（M07 为 1351.75）；runner 25.4/1254.97。集中度不是败因，但 ex-top3 不改变 beat_all=0（2y 仍缺）。ex-top3 不救。
- 滑点加倍（slip 0.004）：best total 1934.29→**1597.58**（cost +35360），nbeat 5→**3**（1y 162.44<164.05 失守）；runner nbeat 4→3。11 切仍对成本敏感。滑点 FAIL。
- T 线小结：最好行过“独立复算”，不过跨相位 / 滑点加倍（ex-top3 中性）——按“六窗全超且回撤更浅”目标仍判 FAIL，但它是首个把 3y 翻正（+55.95）且回撤更浅的逐日约束变体。

### 5.3 约束效果确认 —— switches 33→11 达成，早切入保留，cost 未压到 M07 线

- Switches：K20-daily 33 → hyst003 系 **11**（两座位 `switch_log` 逐字相同：2023-06-07→B / 2024-08-15→A / 2024-10-31→B / 2024-11-12→A / 11-13→B / 11-18→A / 11-27→B / 12-13→A / 2026-08-26→B / 2026-10-26→A / 10-28→B）。hysteresis 砍掉了 2024-03 单月 8 翻簇与 2025-08 簇，残留 2024-11（11-12→A/11-13→B 隔日翻）与 2026-10 簇——死区 0.03 压住了高频鞭梭但未根除事件簇。
- 早切入保留：首切 **2023-06-07→B**（M07 为 06-21，K20-daily 为 06-06），短窗领先来源不断；第二切 2024-08-15→A 与 M07 同日。
- Cost：63201（best）/ 56374（runner）vs K20-daily 97391（**−35%/−42%**，churn 税大降）vs M07 50990（仍 +24%/+11%）；trades 218 vs 317 vs 184。约束降本显著，但 11 切的换仓量仍高于 3 切的 M07——cost 未压到 M07 线是 2y 未能翻正的原因之一。
- 反例对照：hyst008（0.08）过约束 total 1592.21 nbeat=0；rs120/rs252 单用长窗 total 1368/1274 nbeat=0——“保住长窗”不能靠单纯拉长 RS 或加宽死区，0.03 是当前唯一有效点。

### 5.4 判决（维持 FAIL，目标未达成）

- Verdict: **FAIL**（K21 实现审计 PASS：无前视、t+1 链路完整、刹车机制 verbatim、base 校准零偏差；但目标未达成——最好行 nbeat=5（达 T 线门槛，已跑全套 T 线）beat_all=0，仅差 2y（−106.20），且跨相位归零、滑点加倍 nbeat 归 3）。
- Paper-track 保持 M07；K21（含 hyst003_gbf07）不 provision、不上线。
- 后续方向（非重启条件，仅记录）：2y 缺口 −106 是唯一短板；在 hyst003 附近做死区微网格须配相位/滑点双门控，否则重蹈 daily1“压住切数、丢掉 edge”覆辙。

*第 5 节复核子 agent agent-59；本目录新增文件：work_052_k21verify.py、part_052_k21.json、tline_stdout.log、tline_stderr.log。其它目录零新增。*
