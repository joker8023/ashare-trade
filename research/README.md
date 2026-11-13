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
