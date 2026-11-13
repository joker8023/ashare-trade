# X3 研究脚本

2026-11-10 ~ 11 的 R30 / X3 研究脚本，2026-11-13 从 `~/workspace/tools/` 入库。
定版策略 X3 的定义在 `design_r30_grid8.py` 的 `X3Inputs`（调用时传 `gate60=-0.15`）：
主板、N4、市值带 2–30%、Amihud60 排序、精修门（ret60<-15% 且 ret10<0 才剔除）、TP+100%、仓位 1.0、R30。

## 索引

- 数据：`download_ashare_3y.py`（三年版 2023-11-10 起）、`download_ashare_2020.py`（长窗版 2020-01-02 起），新浪 / AKShare 前复权
- 定版路径：`backtest_r30.py`、`backtest_n4_tp45.py`（基线复现）→ `design_r30_grid{,2,3,4,5}.py`（D1→X2 迭代）→ `diag_x1_3m.py`（3 个月窗口诊断）→ `design_r30_grid7.py`（精修门）→ `design_r30_grid8.py`（X3 定义）→ `design_r30_grid10.py`（30 相位审计）
- 月度网格：`design_monthly{,2,3}.py`（月末污染诊断、滞后信号、第 8 交易日锚）
- 新策略批次：`fresh5.py` / `fresh5b.py` / `fresh5c.py`（15 个全新策略，无一胜 X3）、`win_hunt.py`（四窗口占优搜寻，W1/W2）
- 其他形态：`event_engine.py`（事件驱动 E1–E6 + 阈值再平衡 R1）
- 长窗：`backtest_x3_2020.py`（2021-03-31 起 +1565.77% / -38.51%；股票池为今日幸存者名单，长窗收益偏高估）
- 跟踪与展示：`paper_track.py`（基准 vs X3 双篮子模拟盘）、`export_x3_web.py`、`build_x3_web.py`（跟踪页生成）

## 运行

仓库根目录下：`.venv/bin/python research/<脚本>.py`
脚本自带 `sys.path` 设置（引用仓库 `team/audit` 模拟器与同目录脚本）；数据在 `data/`（git 忽略，需先跑下载脚本）。
回撤优化、环境门、防御混合等约 40 个变体多为一次性命令，未全部留存为文件，结论见各脚本头注释与提交历史。

## 本地复现（X3 vs N4 对比，2020 长窗口径）

环境：Python 3 + pandas / akshare（仓库根目录 `python3 -m venv .venv && .venv/bin/pip install pandas akshare`）。
下面这条链的脚本已做路径可移植（按脚本自身位置推导仓库根），clone 到任意目录可跑：

1. 拉数据（新浪前复权，约 45 分钟）：`END_DATE=20261112 .venv/bin/python research/download_ashare_2020.py`
   → `data/ashare_daily_long_2020.pkl`（7,408,288 行，2020-01-02 ~ 2026-11-12）+ `data/universe_2020.pkl`。数据不在仓库里（git 忽略），必须本地拉。
2. 建 pivots：`.venv/bin/python research/rebuild_pivots_2020.py` → `data/pivots_2020_clean.pkl`（1662 交易日，末日有价 5025 只）。
3. 跑对比：`.venv/bin/python research/compare_x3_n4_2020cal.py` → `results/r30_bt/compare_x3_n4_2020cal_1112.json`。
   对照值（截至 2026-11-12）：X3 全程 **+547.86% / MDD -38.19%**（92 笔，成本 ¥17,505）；N4 全程 **+309.70% / MDD -41.40%**（92 笔，成本 ¥10,198）；1/3/6m、1/2y 窗口见 JSON。

另：`backtest_x3_2020.py` 是 X3 单独的长窗全程回测（run_start 2020-01-01，首信号 2021-03-31；数据到 2026-11-10 时为 +1565.77% / -38.51%，数据更新后数字随之变化）。
未可移植：`paper_track.py` 及三年数据链仍写死沙箱路径（`~/workspace/tools/...`），暂只能在沙箱跑。

## 双引擎切换（R20_N5 × N4）

- `build_switch_engine.py`：从 `team/audit/prior_check.py` 源码派生切换引擎（外科式替换，基础设施与审计引擎共用）。重跑它生成的 `switch_engine.py` 与仓库内版本逐字节一致。
- `switch_engine.py`：持仓层切换引擎。A=R20_N5（带 2–30%、精修门、Amihud60 前 5、R20、TP+100%、敞口 1.0），B=均衡型 N4（带 5–30%、前 4、R30、TP+45%、敞口 0.9）。两引擎独立影子曲线在 A 网格信号日比较 trailing-60 交易日收益，高者当权（平局维持，两影子均满 60 天才开始评估）；翻转时次日收盘全清（真实费率+滑点）按新引擎重建仓，止盈随当前引擎；不翻转时仅当前引擎自身网格日调仓。
- `run_switch_backtest.py`：先过双回归门（lock A/B 与独立运行在共同索引上逐值一致、成本一致，切换版多出的前置点为平坦资本），再给 ph0 正式结果与六窗表，JSON 落 `results/r30_bt/switch_backtest_ph0.json`。
- ph0 结果（2020 口径，数据至 2026-11-12）：全程 **+1336.06% / -43.01%**，六窗（1m/3m/6m/1y/2y/3y）全部超过 R20_N5 ph0，5 次切换（2023-06-21→B、2024-02-21→A、2024-05-22→B、2024-08-15→A、2026-09-08→B），总成本 ¥43,310，期末模式 B。
- 口径警告：20 相位中只有 ph0 一个相位六窗全胜，相位中位数 +710.34% / -33.08%——ph0 是最顺的网格锚，不要把 ph0 数字当期望表现。后续两轮优化（滞回/长回望/三引擎/避险 C/加密评估/元切换）均未在 ph0 全窗超过本版，此线已关闭。

## 日8锚（X3 规则 × 每月第 8 交易日网格）

- `run_day8_anchor.py`：自包含 runner（MInputs 类逐字内嵌自 `design_monthly.py`，因原文件仍带沙箱路径）。选股与 X3 完全相同（带 2–30%、精修门、Amihud60 前 4、主板），网格改为自然月锚：每月第 8 个交易日执行（信号为其前一交易日，grid 注入审计引擎），全清重选、TP+100%、敞口 1.0。月末锚污染的诊断与修复见月度线（`design_monthly{,2,3}.py`）。
- ph0 长口径结果（数据至 2026-11-12，runner 内含复现断言）：全程 **+1352.68% / -39.15%**，184 笔，成本 ¥48,181。全程收益与 3y 窗（+1248.75%）超过双引擎切换（+1336.06% / +1215.03%），回撤更浅；但 1m/3m/1y/2y 不及切换版，未过全窗判据。两个冠军分工：长窗与总账归日8锚，近窗与中窗归切换版。
- 注意口径：此处为长口径（曲线 2023 年初起）；月度线当年的 +741.48% 为三年口径，不可混用。
