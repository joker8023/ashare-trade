# M07 §1 × inventory_k26.json 一致性复核（batch_038_m07inv5）

- 方法：用 `.venv/bin/python` 独立重算 `results/r30_bt/sweep_beat_m07_k{1..13}.json`（13 个文件，全为 list 结构，含 `tag/base_M07` 校准行 + `nbeat_m07/beat_all/win_all/total/mdd` 字段），逐项对照 `BEAT_M07_SUMMARY.md` §1 与 `results/r30_bt/inventory_k26.json`。
- 基准行：13 轮 `base_M07` 行各 1 行，`total=1863.27/mdd=-27.05` 与 M07 基准一致。

## 逐项结论

| # | 断言 | 重算值 | 结论 |
|---|---|---|---|
| 1 | K1–K13 行数 30/9/29/18/20/8/6/8/7/13/7/7/7，合计 169 | 30/9/29/18/20/8/6/8/7/13/7/7/7，合计 169 | PASS |
| 2 | 新配 150+6=156（每轮各 1 行 base，169−13=156；K1–K12 新配 29+8+28+17+19+7+5+7+12+6+6+6=150，K13 新配 6） | 新配合计 156，去重后 156 | PASS |
| 3 | 零重名（156 新配 tag 无重复） | 新配 tag 去重=156，重复 0 组 | PASS |
| 4 | inventory `totalrows=169/distinct=156/beat=0` | 与重算 169/156/全轮 `beat_all` 计数 0 一致 | PASS |
| 5 | beat 全 0（13 轮 `beat_all=true` 计数均为 0，`win_all` 亦全 0） | 13 轮 `beat_all_n=0`，`win_all_n=0` | PASS |
| 6 | maxnbeat 4/4/5/2/4/2/4/4/3/1/0/2/3（K1→K13） | 重算 max `nbeat_m07`：K1=4,K2=4,K3=5,K4=2,K5=4,K6=2,K7=4,K8=4,K9=3,K10=1,K11=0,K12=2,K13=3；与 inventory `maxnb` 13 键逐键一致 | PASS |
| 7 | K1 最强 `k05_by05/k25_cut78` 并列 4/6（前者 total 2022.84 更高，后者 mdd −25.35 更浅） | `k05_by05`: nb=4/total=2022.84/mdd=−27.05；`k25_cut78`: nb=4/total=1908.74/mdd=−25.35；确为仅有的两个 nb=4 行 | PASS |
| 8 | K2 最强 `g_by05_cut78_bx15`（4/6, mdd −22.87, total 2084.73） | 一致（1m−0.01/3m−0.03，其余四窗胜） | PASS |
| 9 | K3 最强 `g_bf07`（5/6，仅 1m 差 −0.01pp，mdd −24.28，total 2128.41） | 一致（1m 差 −0.01，其余五窗胜） | PASS |
| 10 | K4 最强 `r_A15B30`（2/6, mdd −29.73） | 唯一的 nb=2 行，total=772.91, mdd=−29.73 | PASS |
| 11 | K5 最强 `nobrake_gbf07`（4/6, mdd −28.40） | 一致（total=2243.52） | PASS |
| 12 | K6 最强 `cut75_both`（2/6，3y 差 −49.35pp） | `cut75_both` total=1630.77/3y=1628.18，1628.18−1677.53=−49.35 | PASS |
| 13 | K7 最强 `g_bf085`（4/6, total 2182.70；`g_bf080` 2177.90 次之） | 一致（nb=4 行按 total：2182.70 > 2177.90 > 2141.87） | PASS |
| 14 | K8 最强 `g_bf07_winA30`（4/6，1m 打平/3m −0.03pp，total 2400.29 全场最高，mdd −24.17） | 一致：1m=−4.09（差 0.0）、3m=17.25（差 −0.03）；2400.29 为 169 行全局最高 total | PASS |
| 15 | K9 最强 `k9_amihud_5_both_on/off` 并列（3/6, mdd −34.87；MAX 开/关逐位相同；size/amount 双腿 total 崩至 115–280） | on/off 行逐字段相同（total=1338.14/mdd=−34.87/nb=3）；`k9_size_both`=115.48、`k9_amount_both`=280.12 | PASS |
| 16 | K10 最强 `k10_a60_size_both`（唯一领先窗 1m +3.55pp；最好 total 仅 1437.72 < M07） | 唯一的 nb=1 行（1m=−0.54 vs −4.09，差 +3.55）；新配中最高 total 为 `k10_a60_a5_B`=1437.72 < 1863.27 | PASS（注：“最好 total”指新配中最高 total，非最强行本身 total=402.79） |
| 17 | K11 最强 `k11_h05_B`（六窗全败，total 1680.98；双腿崩至 959 / mdd −39.53） | `k11_h05_B` total=1680.98，六窗差值全负（0/6）；新配最低 total `k11_h05_both`=959.42；最差 mdd `k11_h10_both`=−39.53（注：最低 total 与最差 mdd 分属不同行，原文合并表述） | PASS（带注） |
| 18 | K12 最强 `k12_h02/h05_B`（1m +0.01 / 1y +0.05 尘埃胜；total −441pp / mdd −34.48；h10 零切换锁死 A） | `k12_h02_B/h02_both/h05_B` 三行 nb=2/total=1422.05/mdd=−34.48（1422.05−1863.27=−441.22）；1m=−4.08（差 +0.01）、1y=164.10（差 +0.05） | PASS |
| 19 | K13 最强 `k13_dynT10_both`（3/6 赢 3m/2y/3y，total 1990.79 / mdd −25.72） | 一致（胜窗恰为 3m +2.90 / 2y +46.16 / 3y +122.21） | PASS |

## 总结论

**19/19 PASS**：§1 表格数值（行数、新配数、beat、maxnbeat、最强行标识与关键数字）与源文件重算完全一致；`inventory_k26.json` 四字段与重算一致。仅两处表述口径注记（#16 最好 total 指新配最高、#17 最低 total 与最差 mdd 分属不同行），数值本身无误，不影响“beat 全 0、不提供策略”裁决。
