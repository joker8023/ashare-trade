# Route-D stage3/stage4 说明（冻结版）

## 口径（与 M07 家族逐字一致，真股本口径）
- 数据: `data/pivots_2020_clean_realshares_v2.pkl`; RUN_START=2023-01-03, EVAL_END=2026-11-12
- 5万本金 / 滑点0.002 / 整手lot=100 / 现实费率 / stop_exec=next / legacy_grid=False /
  full_liquidate=True / long-only / 敞口<=1 / MB=("688","689","300","301","8","4")双腿排除
- A腿: MaxInputs band=(0.02,0.30) gate60=-0.15 cut=0.80 win=40, n=5/R20/TP1.2/exp1.0
- B腿: DInputs(`research/inputs_d27.py`) sel=amihud_5, band=(0.05,0.30) gate60=-1.0(门控关闭)
- Switch: trailing-60影子RS + build_ns刹车; lock="B" = 纯B腿+刹车

## 选股器定义与分位逻辑（无前视）
- amihud_5 = trailing-5日 mean(|ret|/(amount/1e8))，越大越不流动，取最大N只
- MAX彩票过滤复用 MaxInputs.maxret（trailing max_win日最大单日涨幅，剔除分位>=cut）
- 池: 上市>=250天 & adv20>5e6 & t日close非空 & amihud60非空 & 市值截面分位 & MB排除
- 所有矩阵 trailing rolling(min_periods)，信号日只读 t及以前；排序为 t日池内截面分位，
  逐调仓日现算，无全样本分位

## 网格与产出
- stage3(`research/search_D_stage3.py` -> `results/r30_bt/search_D_stage3.json`, 84行):
  BatchA N{4,5,6}xR{15,20,30}xTP{0.45,0.6,0.8,1.0,1.2}(cut0.7/win20) + MAX敏感cut{0.6,0.7,0.8}xwin{10,20,40}
  (2锚点) + BatchB top3锚点x4刹车 + BatchC lockB(3单腿优胜x5刹车)
- stage4(`research/search_D_stage4.py` -> `results/r30_bt/search_D_stage4.json`, 19行):
  amihud_5_R15基座 x C路刹车(0.15,0.10,0.5)+邻域 x lock{B,switch} x TP x rs{60,90} x N5: 0通过
  （switch把2026拉到~96%但2024掉到~43%，R15基座在switch下保不住2024>60）
- schema: 每行含 total/mdd/trades/cost/mode/switches/switch_log/y2024_slice/y2024_yoy/
  y2024_mdd/y2025_yoy/y2025_mdd/y2026_yoy/y2026_mdd/y2023_yoy/pass_all/margin;
  注意: stage3.json 只有 y2024_slice（y2026_slice未补，冻结保持原样；yoy≈slice，
  仅差新年首日gap，2026_yoy~123%对应的slice必>60）

## 最佳3行（stage3, margin排序）
1. s3_N4_R30_T08_b01200605: total 1644.68 / mdd -22.66 / 2024 slice78.94 yoy83.05 mdd-22.66 /
   2025 yoy276.79 mdd-11.81 / 2026 yoy123.15 mdd-16.52 / margin 7.34 / switches 9, final B
2. s3_N4_R30_T06_b01200605: total 1594.48 / mdd -22.66 / 2024 slice73.67 yoy77.66 /
   2025 yoy277.40 / 2026 yoy122.95 / margin 7.34 / final B
3. s3_lockB_a5R30T10_b01200605: total 599.77 / mdd -22.71 / 2024 slice66.63 yoy70.48 /
   2025 yoy96.69 / 2026 yoy66.56 / margin 6.56 / 纯B腿+刹车(0.12,0.06,0.5)
- 共同点: B腿 amihud_5/N4/R30 + 刹车(0.12,0.06,0.5,偏紧触发+半仓)
- MAX cut/win在N=4时对头部 picks 非绑定（多组结果逐字相同），属实记录
- 承担回撤主体为2024年内-22.6%（2024 slice/yoy仍>60/78%+）
