# F4 amount/复合族搜索总结（中文）

## 1. 任务与口径

- 家族：B 腿 `DInputs`，`sel ∈ {amount, c_a60_size, c_a60_amt, c_a60_a5}`，与 F1/F2/F3/F5 选股器正交（见 §5）。
- A 腿冻结 M07：`MaxInputs band=(0.02,0.30) gate60=-0.15 cut=0.80 win=40`，N5/R20/take1.2/exp1.0/stop0.25。**F1=C2_grid 未动。**
- 统一口径（realshares_v2）：RUN_START=2023-01-03，EVAL_END=2026-11-12，本金 5 万，slip=0.002，整手 100，long-only，敞口≤1，`legacy_grid=False`，`full_liquidate=True`，信号 t 收盘 / 执行 t+1 收盘，切换判定只用 t 及以前影子收益（无前视）。
- 严格达标：2024 slice>60 且 2024_yoy>60，2025_yoy>60，2026 slice>60 且 2026_yoy>60（截至 11-12），全程 mdd>-30 且每年 mdd>-30。

## 2. 扫描规模（共 680 组切换 + 180 组单腿）

| 阶段 | 内容 | 数量 |
|---|---|---|
| phase1 | sel×N{4,5,6}×R{15,20,30}×TP{0.45,0.6,0.8,1.0,1.2}，默认刹车 grid | 180 |
| phase2 | 每 sel top3 锚点 × 刹车5 × 切换4(grid/daily+hyst/mh) + band/gate2 + cut/win4 + lockB | 316 |
| bsole | 4 sel 单腿全 N/R/TP（B 腿天花板摸底，无刹车）| 180 |
| phase3 | top2 锚点 × RS{30,45,90} × 刹车3 × 切换5 + lockA | 91 |
| phase4/4b/4c | RS{10-40} 微网 × 刹车微调（grid）| 95 |

脚本：`research/fam_F4.py`（`--phase phase1/phase2/phase3/phase4/bsole`，断点续跑 + 每 N 行落盘）。
中途修过一次 OOM：早期跨 run 缓存 `DInputs`（每个带 3 个全市场滚动矩阵）被 kill（exit 137），改为逐 run 现建现放后通过。

## 3. 结论：3 组严格达标（c_a60_a5 × N5/R30/T08 × 刹车 0.12/0.06/0.5 × grid）

| 配置 | 2024 slice/yoy | 2025_yoy | 2026 slice/yoy | 全程mdd | 年mdd | 总收益 | margin |
|---|---|---|---|---|---|---|---|
| **主推 rs13** | 64.59 / 67.46 | 289.16 | 92.69 / 96.77 | -20.02 | -20.02/-11.75/-12.63 | 1454% | **+4.59** |
| 备份 rs12 | 64.59 / 67.46 | 235.37 | 80.44 / 84.58 | -20.02 | -20.02/-12.30/-12.59 | 1156% | +4.59 |
| 备份 rs18 | 64.47 / 67.33 | 233.42 | 105.20 / 109.89 | -20.14 | -20.14/-12.34/-12.62 | 1463% | +4.47 |

- 开关 17–21 次、刹车 3 次（2024-01-31 ON→05-23 OFF，2024-06-21 ON→08-16 OFF，2025-02-06 ON→03-20 OFF），平均敞口 ~0.85，最大 <1.0，成本利润比 ~14。
- 新鲜进程独立重跑三组：total/mdd/年度 slice-yoy-mdd/trades/cost/switches/pass/margin **逐值一致（EXACT_MATCH）**。

## 4. 关键发现

1. **短 RS 是本族钥匙**：RS60 下本族 2024 天花板约 45（c_a60_a5），RS30→56.4，RS25→56.4，RS15→57.0，**RS12/13→64.6 达标**，RS10 则掉到 19。响应速度与噪音的甜点在 12–18 日。
2. **2024 是唯一瓶颈**：纯 A 腿 2024 仅 10.9（mdd -36.8），纯 B 腿天花板 51.0（c_a60_a5_N4_R30_T08），amount/size/amt 纯腿 2024 均 <5。切换择时把两者拼出 64.6（远超任一单腿）。
3. **grid 切换优于 daily**：本族 daily+hyst 在 2024 全面落后 grid 约 10–20 个点（与 C2 结论方向不同，是 B 腿特性所致）。
4. brake(0.12,0.06,0.5) 最优；band(0.05,0.30)/gate-1.0/cut0.70/win20 均为默认胜出，cut/win/band 灵敏度行基本与锚点同解。

## 5. 与各族的正交说明

- `amount`（adv20 最小）、`c_a60_size`（amihud60+市值）、`c_a60_amt`（amihud60+adv20）与 F2（纯 amihud_5）、F3（纯 size）、F5（turn/vol 系）**完全正交**。
- 达标的 `c_a60_a5` = rank-sum(amihud60, amihud5)：与 F2 共享 amihud5 输入，但**选股器不同**（双因子复合秩 vs 纯 amihud_5 单因子），且最优 B 参数（N5/R30/T08/cut0.70/win20/RS12）与 F2 锚点不同。供跨族审计（task-10）做去重判断。

## 6. 产出文件

- `results/r30_bt/fam_F4_stage.json`：680 行全量（含 cfg/switch_log/brake_log），3 行 `pass=true`。
- `results/r30_bt/fam_F4_bsole.json`：180 行纯 B 腿天花板（全部 `pass=false`，2024 最高 50.97）。
- `research/fam_F4.py`：复现脚本。`--phase all` 跑 phase1+2；再依次 `--phase phase3`、`--phase phase4` 即得全量；`bsole` 独立。`--only` 仅支持 phase1 的 `F4_*` tag（phase2/3/4 tag 会提示不支持而非 StopIteration）。
- 2026-11-18 维护：`build_ns` 收敛到 `research/switch_ns.py` 唯一实现（C2-fixed confirm 语义：min_hold 持有期内不累积确认）。旧 F4 内联版缺该保护，`daily + mh>0` 的 phase2/3 配置结果与新口径不一致，需重跑；`grid` 配置不受影响。F5/F6/F7 同源，不再有跨家族代码版本差。
- 本文件：中文总结。
