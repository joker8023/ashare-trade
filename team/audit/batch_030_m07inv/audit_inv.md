# batch_030 M07 库存复核：inventory_k16.json vs BEAT_M07_SUMMARY.md §1（2026-11-16，复核子agent）

口径：M07 基准 results/r30_bt/M07_final.json 六窗 1m −4.09 / 3m 17.28 / 6m 39.00 / 1y 164.05 / 2y 1474.08 / 3y 1677.53，严格 \> 为胜；beat_all = 六窗全胜。数据源为 9 个 k-json（results/r30_bt/sweep_beat_m07_k1–k9.json），Python 独立重算（.venv/bin/python，不复用原脚本逻辑，只读 json 数值做计数/去重/比较）。

“最强行”约定：§1 表格的“最强行”=“nbeat 最高者（total 次之）”，非“total 最高者”。K3（g_winA30 total 2400.08 但 4/6 < g_bf07 5/6）、K9（k9_amihud_5_B_on/off total 1496.03 但 0/6 < both_on/off 3/6）、K4（r_A20B40 total 1504.38 但 0/6 < r_A15B30 2/6）三处均按此约定取值，与表格一致。

## 逐项结论

| # | 核查项 | 预期 | 独立重算 | 结论 |
|---|---|---|---|---|
| A | 9 个 k-json 行数 | 30/9/29/18/20/8/6/8/13=141 | len 实测 30/9/29/18/20/8/6/8/13，求和 141 | PASS |
| B1 | 每轮新配（tag≠base_M07） | 29/8/28/17/19/7/5/7/12=132 | 实测 29/8/28/17/19/7/5/7/12，求和 132 | PASS |
| B2 | 新配跨轮零重名 | 去重后 132 | 132 个新 tag 全不同（Counter 无复现；base_M07 未混入新配） | PASS |
| B3 | 每文件内零重名 | — | 9 文件内 tag 计数全为 1，无文件内复现 | PASS |
| C1 | 文件自带 beat_all | 全 0 | 9 文件中 beat_all=true 的行均为 none | PASS |
| C2 | 按 M07 六窗严格 \> 重算 beat_all | 全 0 | 逐行重算 nbeat=6 的行数为 0/轮（共 0 行） | PASS |
| C3 | 文件 nbeat_m07 与重算一致 | — | 全部 141 行 stored nbeat_m07 == 重算 nbeat，无一偏差 | PASS |
| D | 每轮 max nbeat | 4/4/5/2/4/2/4/4/3 | 重算 max 4/4/5/2/4/2/4/4/3 | PASS |
| E1 | K3 最强行 g_bf07 total | 2128.41 | g_bf07 total 2128.41（5/6 唯一，1m −4.10 仅输 1m 一窗） | PASS |
| E2 | K8 最强行 g_bf07_winA30 total | 2400.29 | total 2400.29（4/6 并列中 total 最高；1m −4.09 打平非 \>、3m 17.25<17.28） | PASS |
| E3 | K9 最强行 amihud_5_both total | 1338.14 | k9_amihud_5_both_on/off total 均为 1338.14（3/6 并列最高；MAX 开/关数值逐字相同） | PASS |
| F | inventory_k16.json 自洽 | totalrows 141/distinct 132/beat 0/maxnb 4/4/5/2/4/2/4/4/3 | 与 A–D 独立重算逐项相等 | PASS |
| G | 每轮 base_M07 逐字复现 | total 1863.27/mdd −27.05/六窗与 M07 一致 | 9 文件 base 行 total/mdd/六窗与 M07_final.json 全等 | PASS |

## 明细证据（重算值）

- K1：max 4/6 并列 k05_by05（total 2022.84，表格“前者 total 更高”成立）/ k25_cut78（mdd −25.35，表格“后者 mdd 更浅”成立）；次高 total 为 k04_bx20 2022.94（3/6，非最强）。
- K2：max 4/6 共 7 行，最强 g_by05_cut78_bx15（total 2084.73，mdd −22.87）；最高 total 为 h_by05_cut78_bf07 2090.82（3/6）。与表格一致。
- K3：唯一 5/6 g_bf07（total 2128.41，mdd −24.28）；4/6 中 total 最高 g_winA30 2400.08。表格取 5/6 者，正确。
- K4：max 2/6 唯一 r_A15B30（total 772.91，mdd −29.73）；最高 total r_A20B40 1504.38（0/6）。与表格一致。
- K5：max 4/6 nobrake_gbf07（total 2243.52，mdd −28.40）> nobrake_M07（2182.60）。与表格一致。
- K6：max 2/6 唯一 cut75_both（total 1630.77，3y 1628.18，3y 缺口 −49.35pp）。与表格一致。
- K7：max 4/6 三行 g_bf085（2182.70）> g_bf080（2177.90）> g_bf075（2141.87）。与表格一致。
- K8：max 4/6 四行之首 g_bf07_winA30（2400.29，全场最高 total，mdd −24.17）。与表格一致。
- K9：max 3/6 k9_amihud_5_both_on/off（total 均为 1338.14，mdd −34.87）；size/amount 双腿 total 115.48/280.12 崩塌（表格“115–280”成立）；最高 total k9_amihud_5_B_on/off 1496.03（0/6）。与表格一致。
- M07_final.json 六窗 −4.09/17.28/39.00/164.05/1474.08/1677.53 与 §0 基准逐字相等；total 1863.27/mdd −27.05。
- inventory_k16.json：{"totalrows":141,"distinct":132,"beat":0,"maxnb":{1:4,2:4,3:5,4:2,5:4,6:2,7:4,8:4,9:3}}，与重算全等。

## 总判

**全部 PASS：§1 表格 9 轮行数/新配/beat_all/max nbeat/最强行 total 与 k-json 独立重算一致，inventory_k16.json 与之一致。**
