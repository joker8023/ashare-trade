# M07 inv10 复核：inventory_k40.json vs BEAT_M07_SUMMARY.md §1（batch_053）

日期：2026-11-16；复核人：agent-60（子agent独立重算）；工具：.venv/bin/python 系文本重算（node 读取 JSON，逐行独立统计）。
对象：results/r30_bt/sweep_beat_m07_k{1..21}.json（21 文件）→ results/r30_bt/inventory_k40.json ↔ BEAT_M07_SUMMARY.md §1 表格。

## 独立重算基线（新配口径 = tag ∉ {base_M07, base_gbf07}）

| 轮 | 行数 | 新配 | 新配max nbeat | 全量max nbeat |
|---|---|---|---|---|
| K1 | 30 | 29 | 4 | 4 |
| K2 | 9 | 8 | 4 | 4 |
| K3 | 29 | 28 | 5 | 5 |
| K4 | 18 | 17 | 2 | 2 |
| K5 | 20 | 19 | 4 | 4 |
| K6 | 8 | 7 | 2 | 2 |
| K7 | 6 | 5 | 4 | 4 |
| K8 | 8 | 7 | 4 | 4 |
| K9 | 13 | 12 | 3 | 3 |
| K10 | 7 | 6 | 1 | 1 |
| K11 | 7 | 6 | 0 | 0 |
| K12 | 7 | 6 | 2 | 2 |
| K13 | 7 | 6 | 3 | 3 |
| K14 | 6 | 4 | 3 | 5（base_gbf07 校准行） |
| K15 | 5 | 3 | 1 | 5（base_gbf07 校准行） |
| K16 | 6 | 4 | 2 | 5（base_gbf07 校准行） |
| K17 | 4 | 3 | 2 | 2 |
| K18 | 6 | 4 | 1 | 5（base_gbf07 校准行） |
| K19 | 7 | 6 | 1 | 1 |
| K20 | 6 | 5 | 4 | 4 |
| K21 | 6 | 5 | 5 | 5 |
| 合计 | 215 | 190 | — | — |

K1–K20 新配 = 185，K21 新配 = 5，合计 190；非 base tag 跨 21 文件零重名（185+5=190，dup=0）。
beat_all=true 行数 = 0（215 行全为 false）。
base_M07 行 21 文件逐字一致（total 1863.27 / mdd −27.05 / 1m −4.09 / 3m 17.28 / 6m 39.00 / 1y 164.05 / 2y 1474.08 / 3y 1677.53）。
base_gbf07 校准行仅 K14/K15/K16/K18 含（六窗/total/mdd/nbeat=5 一致，total 2128.41 / mdd −24.28；K18 行多 weight 键，属 schema 差异，数值一致）；K21 仅 base_M07（1 base + 5 新 = 6 行，无 base_gbf07）。

## 逐项结论

1. 21 文件齐全（K1–K21 各一）——PASS（21/21 存在且为数组）。
2. 行数 = 215（30/9/29/18/20/8/6/8/13/7/7/7/7/6/5/6/4/6/7/6/6）——PASS（与 §1 表格 K1–K21 行数逐轮一致；求和 215 = inventory totalrows）。
   注：任务 briefing 括号内行数字串（…/8/7/13/…/6/7/…）求和为 217 且 K9/K10 顺位互换、K15 误作 7，系 briefing 转述笔误，§1 表格正文无此问题。
3. 新配 185+5=190、零重名——PASS（独立去重 190，重复 0）。
4. K21 结构（1×base_M07 + 5 新配 = 6 行，无 base_gbf07 校准行）——PASS。
   注：briefing“6行base+5新配”系笔误（6 行总数不可能容纳 6 base + 5 新）；实际 tags = base_M07 + k21_daily_hyst003_M07/hyst008_M07/rs120_M07/rs252_M07/hyst003_gbf07。
5. beat 全 0——PASS（beat_all=true 计 0；inventory beat=0 一致）。
6. maxnbeat（新配口径）4/4/5/2/4/2/4/4/3/1/0/2/3/3/1/2/2/1/1/4/5——PASS（与 §1 表格逐轮一致；inventory maxnb 21 键逐键一致）。
   注：briefing 串中 K19 误作 2，实际新配 max = 1（r_B90_A90）；全量口径下 K14/K15/K16/K18 的 5 来自 base_gbf07 校准行，§1/inventory 取新配口径（3/1/2/1），口径一致即 PASS。
   并列说明（代表行命名均为并列之一）：K1 k05_by05/k25_cut78 并列 4；K2 七行并列 4（含 g_by05_cut78_bx15）；K5 nobrake_M07/nobrake_gbf07 并列 4；K7 g_bf075/080/085 并列 4；K8 四行并列 4（含 g_bf07_winA30）；K9 on/off 并列 3；K12 四行并列 2；K14 三行并列 3；K15 k15_dynT10_B/dly_enterB 并列 1；K18 四行并列 1；K20 daily_M07/daily_gbf07/daily_M07_brakeD 并列 4。
7. 最强行并列 K3 g_bf07 与 K21 k21_daily_hyst003_gbf07（nbeat=5）——PASS（两行 nbeat_m07=5；K3 唯一 5，K21 唯一 5；K3 仅 1m 差 −0.01pp：−4.10 vs −4.09）。
8. K21 短窗增量 +1.48/+5.27/+6.53/+12.46——PASS（−2.61+4.09=1.48；22.55−17.28=5.27；45.53−39=6.53；176.51−164.05=12.46；另 2y −106.20、3y +55.95、mdd −24.28 更浅、switches=11）。
9. inventory_k40.json 一致性——PASS（totalrows 215、distinct 190、beat 0、maxnb 21 键全对、cal 映射 K14/15/16/18 双 base 其余单 base_M07 全对）。
10. K20 备注“刹车逐日对照行与 daily 逐字相同不计新配”——词语 FAIL、数字 PASS：daily_M07_brakeD vs daily_M07 六窗+total/mdd/trades/cost/switches 全同，但 brake_daily（false/true）与 brake_log 时间戳不同，非逐字相同；且 190 系含 brakeD 按独立 tag 计得（若真剔除则为 189），故“不计新配”与 190 自洽 only 按“方向不双计”理解。建议改为“指标相同（brake_log 时间戳除外），190 按独立 tag 计含该行”。

## 总判

数字口径（215 行 / 190 新配零重名 / beat 全 0 / 新配 maxnbeat / 并列最强 5 / K21 短窗增量 / inventory 三值与两映射）全部 PASS；仅两处文字瑕疵（briefing 转述串笔误系传达层、非文件错；§1 K20“逐字相同”措辞过实）。§1 与 inventory_k40.json 一致。
