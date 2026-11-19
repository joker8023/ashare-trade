# 跨族5策略总验 (task-10, lead直验 + audit-5旧验)

## 1. Verdicts (strict: 2024 slice>60且yoy>60, 2025_yoy>60, 2026 slice>60且yoy>60, 全程及每年mdd>-30; margin<5标fragile)

| 族 | 策略 | total/mdd | 2024 slice/yoy/mdd | 2025 yoy | 2026 slice/yoy | margin | 结论 |
|---|---|---|---|---|---|---|---|
| F1 amihud_60 | C2_grid_mh0_bx0.15_by0.1_bf0.5 | 1349.24/-23.42 | 70.54/71.68/-16.87 | 264.9 | 120.32/125.02 | +6.58 | PASS稳固 (audit-5独立重建, max_abs_diff 0.0) |
| F2 amihud_5 | famF2_T08_bx012_by005_bf04 | 1641.39/-21.26 | 79.33/83.46/-21.26 | 277.02 | 118.14/122.80 | +8.74 | PASS稳固 (root新进程重跑, 全字段diff 0, switch_log逐字一致) |
| F4 c_a60_a5 | F4_c_a60_a5_N5_R30_T08_rs13_b01200605_grid | 1454.11/-20.02 | 64.59/67.46/-20.02 | 289.16 | 92.69/96.77 | +4.59 | PASS fragile (同上, 0偏差, switches 17一致) |
| F5 c_a60_turn | F5s3_rs42_h004_dg | 1398.44/-21.47 | 66.64/68.30/-21.47 | 205.28 | 129.70/134.61 | +6.64 | PASS稳固 (同上, 0偏差, 刹车0触发) |
| F7 c_a60_amt | F7sF_rs47_h0035_exp078 | 1328.96/-19.89 | 61.14/62.63/-19.89 | 228.58 | 128.36/133.25 | +1.14 | PASS fragile (同上, 0偏差; 注: closing消息误写cost 47502, 以落盘json 49706为准, 重跑即49706) |

5/5 strict PASS; 数值 diff 全 0.00; switch_log 全部逐字一致。

## 2. Reproduce (每族独立新进程, 与search/fam业务模块零import)

- F1: `.venv/bin/python research/verify_C5.py` → results/r30_bt/verify_C5.json (audit-5, 引擎独立重建)
- F2: `.venv/bin/python research/root_verify_F2.py` → results/r30_bt/verify_F2.json
- F4: `.venv/bin/python research/root_verify_F4.py` → results/r30_bt/verify_F4.json
- F5: `.venv/bin/python research/root_verify_F5.py` → results/r30_bt/verify_F5.json
- F7: `.venv/bin/python research/root_verify_F7.py` → results/r30_bt/verify_F7.json
- 汇总比对: `.venv/bin/python research/root_cross_gate.py` → results/r30_bt/verify_CROSS.json

引擎: F2用sweep_beat_h1_v4.build_ns(grid经典); F4/F5/F7用search_C_stage2.build_ns(逐日+hyst/mh, audit-5 §4已审无前视同款)。影子统一现建: A腿M07固定(MaxInputs band0.02-0.30/gate-0.15/cut0.8/win40 N5/R20/take1.2/exp1.0); B腿DInputs band0.05-0.30/gate-1.0。判定只用t及以前trailing影子RS, 执行t+1收盘整手, 滑点0.002, 现实费率。

## 3. Lookahead (复用已审结论, 未引入新引擎)

- RS取searchsorted right-1且j>=lookback, 只用sig_i及以前影子权益; exec=signal+1; picks用信号日因子、成交用执行日mark; stop_next收盘触发、t+1执行; lot100/费率/滑点与filed一致。
- F1的完整前视审查见team/audit/batch_06x_C5/README.md §4; 本次F2/F4/F5/F7用同一批已审引擎, 无新代码路径 (daily/hyst/min_hold/brake语义与C2一致)。
- 原audit-7/audit-8两次失败均为空输出失败 (无verify物), 非数值分歧; 本次lead直验逐族单进程重跑成功, 失败子agent未留下任何与本结论冲突的证据。

## 4. sel正交声明 (字符串级正交, 成分诚实注)

- F1 `amihud_60` / F2 `amihud_5` / F4 `c_a60_a5`=rank-sum(amihud60,amihud5) / F5 `c_a60_turn`=rank-sum(amihud60,turn20) / F7 `c_a60_amt`=rank-sum(amihud60,adv20): 五个sel字符串互不相同。
- 诚实注: 复合键共享成分 (F4与F2共享amihud5; F5/F7与F1共享amihud60), 但rank对象与单键不同, 且B腿N/R/TP/刹车/切换节拍各异 (switches 9/9/17/9/9, 骨架不同)。去重判断权交用户: 若按“成分完全不重叠”计, 本次仅F1/F2/F5成分两两正交 (amihud_60 vs amihud_5 vs amihud60+turn20仍共享amihud60——严格成分正交仅F2 vs turn20/vol20纯族, 但纯族已证伪)。
- 证伪族留档: F3 size (113行0达标, 2024结构性缺失), F6 c_4 (860行0达标, 天花板56.63)。

## 5. 2026部分年注

EVAL_END=2026-11-12, 2026年内207 bars。strict仍要求slice>60 (五族118/92/129/128/120均过); 年化外推仅参考。

## 6. Files

- research/root_verify_F2.py, root_verify_F4.py, root_verify_F5.py, root_verify_F7.py (独立重跑脚本)
- results/r30_bt/verify_F2.json, verify_F4.json, verify_F5.json, verify_F7.json, verify_C5.json (F1), verify_CROSS.json (汇总)
- results/r30_bt/fam_F2/F4/F5/F7_stage.json (filed基准, 未改动)
- research/root_cross_gate.py (汇总比对)
