# 复核审计 audit_inv2：inventory_k19 vs BEAT_M07_SUMMARY §1（K1–K10）

- 审计对象：`results/r30_bt/inventory_k19.json`（{totalrows:148, distinct:138, beat:0}）vs `BEAT_M07_SUMMARY.md` §1 表格（K1–K10）+ 第26行累计口径。
- 独立重算源：`results/r30_bt/sweep_beat_m07_k1..k10.json` 十文件逐行重算（.venv/bin/python；判定口径 §0：六窗严格 > M07 且 mdd 更浅；M07 基准 total 1863.27 / mdd −27.05 / 1m −4.09 / 3m 17.28 / 6m 39.00 / 1y 164.05 / 2y 1474.08 / 3y 1677.53）。
- base_M07 校准行十轮逐字一致（total/mdd/六窗全同上）。

## 逐项结论

| # | 断言 | 重算值 | 结论 |
|---|---|---|---|
| 1 | 每轮行数 30/9/29/18/20/8/6/8/13/7=148 | K1..K10 实测 30,9,29,18,20,8,6,8,13,7，求和 148 | PASS（注：任务转述串“/8/7/13”把 K9/K10 写反，实际 K9=13、K10=7，Summary 表格本身正确；总数不受影响） |
| 2 | 新配 132+6=138（每轮新配 29/8/28/17/19/7/5/7/12/6） | 实测与断言逐轮一致；K1–K9 新配之和 132，+K10 的 6 = 138；每轮恰含 1 行 base_M07 | PASS |
| 3 | 零重名（distinct 新配 138） | 新配 tag 全局去重 138，无跨轮重名；全量去重 139（含 10 次复现的 base_M07，唯一重复 tag） | PASS |
| 4 | beat 全 0（beat_all/win_all） | 存储字段 beat_all 合计 0、win_all 合计 0；独立按 §0 口径重算 beat=0，无 nbeat=6 行，mismatch 0 行 | PASS |
| 5 | maxnbeat 4/4/5/2/4/4/2…即 4,4,5,2,4,2,4,4,3,1 | 实测存储值与独立重算（严格 > 六窗计数）十轮全一致：4,4,5,2,4,2,4,4,3,1 | PASS |
| 6 | 最强行 K8 g_bf07_winA30（4/6, total 2400.29 全场最高, mdd −24.17） | K8 内按 nbeat 并列领先 4 行中其 total 最高 2400.29；全局十轮新配最高即该行（次高 K3 g_winA30 2400.08）；1m −4.09 打平、3m 17.25 差 −0.03pp、mdd −24.17 全吻合 | PASS |
| 7 | 其余轮最强行点名（K1 并列/k2 g_bx15/K3 g_bf07/K4 r_A15B30/K5 nobrake_gbf07/K6 cut75_both/K7 g_bf085/K9 amihud_5_both/K10 a60_size_both） | 逐轮 nbeat 领先集合与点名一致：K1 k05_by05/k25_cut78 并列 nb4（2022.84/1908.74）；K2 g_by05_cut78_bx15 nb4 total 2084.73 mdd −22.87（该轮 total 最高）；K3 g_bf07 唯一 nb5（1m −4.10 差 −0.01pp, mdd −24.28, total 2128.41）；K4 r_A15B30 nb2 mdd −29.73；K5 nobrake_gbf07 nb4（与 nobrake_M07 并列，total 更高 2243.52，mdd −28.40）；K6 cut75_both nb2（3y 1628.18 差 −49.35pp）；K7 g_bf085 nb4 total 2182.70（g_bf080 2177.90 次之，并列还有 g_bf075）；K9 k9_amihud_5_both_**on/off 并列 nb3 mdd −34.87（Summary 省后缀，可接受）；K10 k10_a60_size_both 唯一 nb1（1m −0.54, +3.55pp；轮内 total 最高为 k10_a60_a5_B 1437.72 < M07，与“最好 total 仅 1437.72”吻合） | PASS |
| 8 | inventory 三数 totalrows 148 / distinct 138 / beat 0 | 与重算 148 / 138（新配去重）/ 0 全一致 | PASS |

## 附注（非 FAIL）

- §1 小标题“八轮 sweep（…128 行、120 独立新配…）”指 K1–K8 小计（30+9+29+18+20+8+6+8=128；新配 120），与第 26 行“累计 148 行/138 独立新配”衔接一致，非矛盾。
- inventory_k19.json 仅存三项聚合数，无分轮明细；分轮断言的核对基准是十个 sweep 源文件（本审计已逐行重算，零 mismatch）。
- K10 最强行 k10_a60_size_both 自身 total 402.79；Summary “最好 total 仅 1437.72”指该轮新配最高（k10_a60_a5_B），表述有歧义但数值可验。

## 总 verdict

**8/8 PASS** — inventory_k19 与 Summary §1 一致，独立重算零偏差。
