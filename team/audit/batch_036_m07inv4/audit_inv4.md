# M07 inv4 复核 Batch 036 — inventory_k24.json vs BEAT_M07_SUMMARY.md §1 (K1–K12)

- 日期: 2026-11-16
- 复核人: 子agent (batch_036_m07inv4)
- 口径: M07 windows {1m:-4.09, 3m:17.28, 6m:39.00, 1y:164.05, 2y:1474.08, 3y:1677.53}, 严格 > 为胜; nbeat_m07=六窗胜数, beat_all=(nbeat==6)
- 方法: .venv/bin/python 独立重算 12 个 sweep 文件 (results/r30_bt/sweep_beat_m07_k{1..12}.json), 逐行比对存储的 nbeat_m07/beat_all, 统计行数/新配/重名/max-nbeat/最强行, 并与 inventory_k24.json {totalrows:162, distinct:150, beat:0} 对照
- 基础一致性: 12 文件各含 1 行 base_M07, total/mdd/六窗逐字一致 (1863.27/-27.05, [-4.09,17.28,39.0,164.05,1474.08,1677.53})

## 逐项结论

| # | 断言 (BEAT_M07_SUMMARY.md §1) | 独立重算 | 结论 |
|---|---|---|---|
| 1 | K1 行数 30 (新配 29) | k1.json n=30, nonbase=29 | PASS |
| 2 | K2 行数 9 (新配 8) | k2.json n=9, nonbase=8 | PASS |
| 3 | K3 行数 29 (新配 28) | k3.json n=29, nonbase=28 | PASS |
| 4 | K4 行数 18 (新配 17) | k4.json n=18, nonbase=17 | PASS |
| 5 | K5 行数 20 (新配 19) | k5.json n=20, nonbase=19 | PASS |
| 6 | K6 行数 8 (新配 7) | k6.json n=8, nonbase=7 | PASS |
| 7 | K7 行数 6 (新配 5) | k7.json n=6, nonbase=5 | PASS |
| 8 | K8 行数 8 (新配 7) | k8.json n=8, nonbase=7 | PASS |
| 9 | K9 行数 13 (新配 12) | k9.json n=13, nonbase=12 | PASS |
| 10 | K10 行数 7 (新配 6) | k10.json n=7, nonbase=6 | PASS |
| 11 | K11 行数 7 (新配 6) | k11.json n=7, nonbase=6 | PASS |
| 12 | K12 行数 7 (新配 6) | k12.json n=7, nonbase=6 | PASS |
| 13 | 合计 162 行 | 30+9+29+18+20+8+6+8+13+7+7+7=162 | PASS |
| 14 | 新配 144+6=150 (K1–K11 新配 144, K12 追加 6) | K1–K11 nonbase=29+8+28+17+19+7+5+7+12+6+6=144, +K12的6=150 | PASS |
| 15 | 零重名 (distinct=150) | 150 个非 base tag 去重后 150, 重复集为空 | PASS |
| 16 | beat 全 0 (beat_all=0, win_all=0) | 12 文件 beat_all 计数均为 0, 逐行重算 beat_all=(nbeat==6) 全部一致; inventory beat=0 一致 | PASS |
| 17 | max-nbeat K1–K12 = 4/4/5/2/4/2/4/4/3/1/0/2 | 重算非 base 最大值: K1=4,K2=4,K3=5,K4=2,K5=4,K6=2,K7=4,K8=4,K9=3,K10=1,K11=0,K12=2; 与存储值逐行一致, 无 MISMATCH | PASS |
| 18 | 最强行 K8 g_bf07_winA30 total 2400.29 (4/6, 全场最高) | k8 内排序第一: g_bf07_winA30 nbeat=4 total=2400.29 mdd=-24.17; 全局按 total 排序第一 (次席 K3 g_winA30 2400.08), 全局 max-nbeat=5 (K3 g_bf07) | PASS |
| 19 | inventory_k24.json {totalrows:162, distinct:150, beat:0} | 与重算三数完全一致 | PASS |

## 附带核对 (最强行/次强行抽查, 均一致)

- K1: k05_by05 (4/6, total 2022.84) 与 k25_cut78 (4/6, total 1908.74, mdd -25.35) 并列最高 nbeat — 与 §1 描述一致 (前者 total 更高, 后者 mdd 更浅)。
- K2: g_by05_cut78_bx15 (4/6, total 2084.73, mdd -22.87) 居首 — 一致。
- K3: g_bf07 (5/6, total 2128.41, mdd -24.28) 唯一 5 — 一致。
- K4: r_A15B30 (2/6, mdd -29.73, total 772.91) 居首 — 一致。
- K5: nobrake_gbf07 (4/6, mdd -28.40, total 2243.52) 居首 — 一致。
- K6: cut75_both (2/6, total 1630.77) 居首; 其 3y=1628.18, 差值 -49.35pp — 与 §1 表注 (3y差-49.35pp) 一致。
- K7: g_bf085 (4/6, total 2182.70) 居首, g_bf080 (total 2177.90) 次之 — 一致。
- K9: k9_amihud_5_both_on/off 并列 (3/6, total 1338.14, mdd -34.87) — 一致。
- K10: nbeat 居首 k10_a60_size_both (1/6, total 402.79); total 最高 k10_a60_a5_B (1437.72<M07) — 与 “唯一领先窗、最好total仅1437.72” 一致。
- K11: k11_h05_B (0/6, total 1680.98) 居首 — 一致。
- K12: k12_h02_B/h02_both/h05_B 三者并列 (2/6, total 1422.05, mdd -34.48) — 与 “h02/h05_B (尘埃胜)” 一致。

## 备注

- 委托任务串中的行数简写 “30/9/29/18/20/8/6/8/7/13/7/7” 把 K9/K10 写反了 (写成 K9=7/K10=13); 实际文件与 BEAT_M07_SUMMARY.md §1 表格均为 K9=13/K10=7, 总和同为 162, 不影响 §1 表格本身的正确性。本报告按文件实际 (K9=13, K10=7) 判定 PASS。
- 本次只新增本目录内文件, 未改动其他路径。
