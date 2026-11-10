# R7小时线数据说明 (dataeng)

## 备选池
- 日线源: `data/pivots_long_clean.pkl` (4088交易日 2010-01-04~2026-11-05, 5028只).
- 复现 `team/harness.py` 网格: `normalize_spec(selector=amihud_60/n=4/size_range=[0.05,0.30]/min_adv=5e6/exclude_star=True/exclude_bj=True/exclude_chinext=True(主板), rebalance_days=7, phase=0, anchor=full300, window warmup 2024-01-01/eval 2026-11-04)` + `picks_at` 逐信号日取Top4, 只取名单不做收益.
- 信号日: 2024-01-02~2026-10-27 共98个; 392人次去重得 **57只** (远<1500, 无需截断). Top: 603838x36, 002951x33, 603559x28, 002586x25, 603813x19.
- 清单: `team/dataeng/pool_list.csv`(code,count) + `team/dataeng/pool_by_date.csv`(signal_date,picks).

## 60分钟线下载
- 脚本: `team/dataeng/dl_hourly60.py`; 日志: `team/dataeng/dl_hourly60.log`.
- 数据源优先级: Baostock `query_history_k_data_plus(frequency="60", adjustflag="2")` 逐票按年(2024/2025/2026至2026-11-04)拉取; Baostock为空才试 Tushare `stk_mins(freq=60min)` 补缺, 仍无则记manifest缺失原因跳过.
- 代码映射: 6开头->sh.前辍, 其余->sz.前缀.
- 列: `datetime,open,high,low,close,volume,amount`; datetime由Baostock time(%Y%m%d%H%M%S%f)解析, 日内4根(10:30/11:30/14:00/15:00).
- 断点续跑: `data/hourly_60m/progress.json` 逐票落盘; 已done+csv存在则跳过; `manifest.csv` 完工重写.

## 指数小时线
- 脚本: `team/dataeng/make_index_hourly.py`; 由 `data/minute_etf/*_5m.csv` 按日内桶(<=10:30/<=11:30/<=14:00/其余15:00)聚合OHLC(首开/最高/最低/末收, 量额求和), 不另下载.
- 覆盖: 159915 2023-08-09~2026-11-04(1884 bars); 510300/510500 仅2026-01-05~2026-11-04(各804 bars, 因源5m文件仅含2026).
- 文件与股票同目录: `data/hourly_60m/510300.csv,510500.csv,159915.csv`, manifest中source=resample-5m.

## 约束遵守
- 仅写 `data/hourly_60m/**` 与 `team/dataeng/**`; 未碰他人目录.
