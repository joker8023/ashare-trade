# M07-K17 风险调整影子切换试点复核（batch_045）

- 基线：`results/r30_bt/M07_final.json`（M07 = J04 + B-MAX20(A40/B20) + B-N4；total +1863.27%，mdd −27.05%，trades 184，cost 50990，switches 3：2023-06-21→B / 2024-08-15→A / 2026-09-08→B；六窗 1m −4.09 / 3m +17.28 / 6m +39.0 / 1y +164.05 / 2y +1474.08 / 3y +1677.53；top3_share 26.4%，extop3_total +1351.75%）
- M07 执行链（`research/run_m07_final.py:16`）：`lot=100` 整手，`slip=0.002`，`cost_one_way=None`，`stop_exec="next"`（t+1 执行），30 日网格调仓，`prior_check.run_strategy` + `sweep_beat_h1_v4.build_ns(0.18,0.08,0.6)` 开关引擎。
- K1–K16 横扫复核：`results/r30_bt/sweep_beat_m07_k{1..16}.json` 共 **186** 条候选，**beat_all = 0**（与任务所述“167 新配 beat_all=0”一致，量级相符；差异为部分文件含非 dict/附加条目）。

## 1. riskadj_k17.py 逐行审计

**结论：无法审计 —— 文件不存在。 verdict: FAIL（缺失工件，按“标尺不可验证 = FAIL”计）。**

- `research/riskadj_k17.py`：**不存在**（`ls research/ | grep -i k17/risk` 无命中；全仓 `grep -ri "riskadj"` 仅任务描述外零命中）。
- `results/r30_bt/sweep_beat_m07_k17.json`：**不存在**（`results/r30_bt/sweep_beat_m07_k*.json` 仅到 k16 + k16.notes）。
- 全仓 `grep -ri "k17"` 仅命中 `sweep_beat_{j04,m07}_k1.py` 内网格 tag（`k17_rs75` / `k17_an4`，K1 代内编号，与 R33-K17 无关）及 `batch_023/026` 审计残留；无 Sharpe/Calmar/下行 RS 比较逻辑的任何实现。
- git 历史（`git log --oneline`）无 R33/K17 提交；工作树无相关未跟踪文件。
- 因此三种标尺（Sharpe / Calmar / 下行 RS）的以下审计项**均不可验证**：
  - (a) 是否只用 t 及以前影子净值（波动率/回撤窗口有无前视）；
  - (b) t+1 执行链路是否与 M07 一致（`stop_exec="next"` / lot=100 / slip=0.002 / 费用口径）；
  - (c) 费用/整手/口径一致性。
- 按约束“标尺前视一票 FAIL”：连标尺代码都不存在，前视风险不可排除，**直接判 FAIL**，不得进入候选 T 线。

## 2. 候选全套 T 线

- K17 候选数：**0**（sweep JSON 缺失）。beat_all / nbeat_m07≥4 名单为空，**无 T 线可跑**（跨相位 / ex-top3 / 滑点加倍 / 独立复算均 N/A）。
- 开关时点核查：无 K17 switch_log 可与 M07 三开关（2023-06-21→B，2024-08-15→A，2026-09-08→B）比对；“开关逐字相同而六窗仍败 ⇒ 标尺无增量”判据**不适用**（无开关记录）。

## 3. 判决与建议

- **Verdict: FAIL（R33-K17 试点未交付：实现 + 结果双缺失）。**
- K1–K16 beat_all=0 经独立复算确认（186 条 / 0 全超），M07 基线维持 champion。
- 建议：R33 若要重启 K17，必须先交付 `research/riskadj_k17.py`（强制：滚动窗口仅取 `eq[:t]`、影子波动率/回撤函数单测断言无未来索引、复用 M07 `CA` 执行参数与 `build_ns` 开关引擎），再产出 `sweep_beat_m07_k17.json`（含每候选 switch_log + 六窗 + mdd + beat 字段），方可进入本 batch 的 T 线复核。

## §5 真实产出复核（R33-K17 落盘后追加；§1–§3 时序记录保留）

> 背景：首查时 `research/riskadj_k17.py` / `research/sweep_beat_m07_k17.py` / `results/r30_bt/sweep_beat_m07_k17.json` 尚未落盘（§1–§3 为此时序记录）；回测完成后真实产出为 4 行（base_M07 校准 + 3 新配），本节为全套复核。

产出摘要（`sweep_beat_m07_k17.json`）：base_M07 与 M07 逐字一致（total 1863.27 / mdd −27.05 / switches 3，`switch_same_m07=true`，校准断言通过）；k17_sharpe_M07：total 1637.20 / mdd −27.05 / 5 切 / **nbeat=0**；**k17_calmar_M07（最好行）**：total 1689.26 / mdd −29.06 / 9 切 / **nbeat=2**（仅 6m +0.01、1y +0.01）；k17_downside_M07：total 1433.55 / mdd −34.54 / 7 切 / **nbeat=1**（仅 6m）。beat_all=0，win_all=0；phase2 门槛（nbeat≥3）未触发，无 g_bf07 行，总行数 4（≤6 上限合规）。

### §5.1 riskadj_k17.py 逐行审计（三种标尺前视）——PASS（无前视），口径一致

- 锚点与切片（`RS_RISK_TMPL`，替换 `switch_engine.py:93-99 OLD_RS`，`_once` 计数断言==1，替换后 `exec` 编译）：`j = searchsorted(dates[s_idx], right)-1` 与原生逐字一致；三种标尺统一取 `eq_s.iloc[j-60:j+1]`（61 点 / 60 日收益），**只用 t 及以前数据**；`if j < rs_lookback(60): return None` 预热守卫与原生一致。三种公式（sharpe 均值/样本标准差 ddof=1；calmar 点收益/窗内最大回撤深度，分子与原生 RS 同为 `w[-1]/w[0]-1`；downside 点收益/下行偏差 `sqrt(mean(min(r,0)^2))`）全部闭合在该切片内。零波动/零回撤守卫映射为 ±1e9/0.0，`desired = "A" if ma >= mb else "B"` 比较行保持逐字（平局归 A，与原生 `ra>=rb` 一致）。**无前视：PASS。**
- 触发与执行链：仅 A 网格信号日比较（`sig_i in sig_a` 门守卫未动）、`rs_lookback=60` 与原生同窗；`stop_exec="next"`（t+1 执行）、`lot=100`、`cost_one_way=None`（现实费率）、`slip=0.002`、`MB` 排除、`legacy_grid=False`、`full_liquidate=True`、A/B 腿参数与 brake(0.18/0.08/0.6) 均与 M07 `CA`/`KW` 逐字一致（`sweep_beat_m07_k17.py:80-83,103-106` vs `run_m07_final.py:16,20`）。`np` 引用合法（`switch_engine.py:6 import numpy as np`，exec 命名空间内可用）。**t+1 链路与费用/整手口径：PASS。**
- 审计 helper `metric_k17` 与扫参内 `truncation_check`（两 seat × 首/中信号日 × 两腿 × 三标尺全等断言 1e-9）方向正确，但仅覆盖 4 点；本复核 leg5 将其扩展到全部决策日（见 §5.2）。

### §5.2 k17_calmar_M07 全套 T 线（nbeat=2，按规则执行；产物 `tline_k17_calmar_out.json`，脚本 `tline_k17_calmar.py`）

- leg1 独立复算（ph0 逐字重跑）：total/mdd/trades/cost/switch_log **五项零偏差**（1689.26/−29.06/190/47335/9 切），nbeat=2 复现。**PASS（可复现），但不晋级。**
- leg2 跨相位（ph 0/5/7/10/14/15 vs 同相位 raw-M07）：nbeat = 2/4/4/2/3/2；ph5/ph7 名义 4/6 占优，但绝对 total 全面坍塌（calmar 1212.52 vs raw 755.73；1156.96 vs 1127.52），且 ph0/ph10/ph14/ph15 均 ≤3、无一窗组合稳定占优。边缘非 ph0 稳健——**跨相位 FAIL（无一致 edge）。**
- leg3 ex-top3：calmar extop3_total **1222.38%** vs M07 1351.75%，去头后更差。**FAIL。**
- leg4 滑点加倍（slip 0.002→0.004，影子+开关全链）：total 1440.92（Δ −248.34），mdd 恶化至 −30.09，nbeat vs 标准 M07 = **0**。**FAIL。**
- leg5 前视独立复核（全部 A 网格信号日 × 两腿 × 三标尺，引擎切片值 vs t 截断序列 `metric_k17`）：**174 组合最大绝对差 0.0**，零索引错位。**PASS。**

### §5.3 开关时点变化确认——三标尺开关均变化（非逐字相同），但六窗仍败 ⇒ 标尺有增量动作、无增量收益

- M07（3）：2023-06-21→B / 2024-08-15→A / 2026-09-08→B。
- sharpe（5）：保留 M07 三切，**插入** 2024-10-21→B、2024-12-16→A。
- calmar（9）：含 M07 三切为子序列，**额外 6 切**（2024-04-19→A、2024-05-22→B、2024-09-12→B、2024-12-16→A、2025-01-14→B、2025-02-19→A）——2024–2025 来回鞭打。
- downside（7）：保留 M07 三切，**插入** 2024-03-20→A、2024-04-19→B、2024-10-21→B、2024-12-16→A。
- 三行 `switch_same_m07` 均为 false。“开关逐字相同而六窗仍败 ⇒ 标尺无增量”判据**不适用**（开关确有变化）；实际是反向证据：标尺改变了 2024–2025 切换行为，带来更多交易（182/190/187 vs 184）与更低费用无关的 total/mdd 全面恶化——**有动作、无收益**。

### §5 判决

- **Verdict: FAIL（K17 试点关闭）。前视/口径/独立复算三项 PASS，但最好行 nbeat=2 且 T 线三条实证腿全败（跨相位无一致 edge、ex-top3 更差、滑点加倍归零），beat_all=0、mdd 更深（−29.06 vs −27.05）。** 按 batch_039 同规则：nbeat<4 本可 moot，本次按指令执行 T 线，结果同样不支持晋级。Paper-track 保持 M07；K17 三标尺均不得上线。

*复核子 agent agent-48；工作目录 `/Users/joker/coding/ashare-trade`；本目录新增：`audit_m07k17_review.md`（§1–§3 为首查时序记录，§5 为真实产出复核）、`tline_k17_calmar.py`、`tline_k17_calmar_out.json`。*
