# M07 inv10 独立复核（agent-61）：inventory_k40.json vs BEAT_M07_SUMMARY.md §1

日期：2026-11-16；工具：.venv/bin/python 独立重算（键：tag / nbeat_m07 / beat_all / win_all；新配口径 = tag ∉ {base_M07, base_gbf07}）；方法脚本见同目录 verify61.py。
对象：results/r30_bt/sweep_beat_m07_k{1..21}.json（21 文件）→ results/r30_bt/inventory_k40.json ↔ BEAT_M07_SUMMARY.md §1。

## 独立重算结果（实际文件值）

- 行数 K1–K21：30/9/29/18/20/8/6/8/13/7/7/7/7/6/5/6/4/6/7/6/6，合计 215。
- 新配（非 base tag）：K1–K20 计 185，K21 计 5，合计 190；跨 21 文件独立 tag 去重 = 190，重复 0。base 行共 25（K14/K15/K16/K18 各含 base_M07+base_gbf07 双校准行，其余 17 文件各 1 个 base_M07）。
- beat_all=true：0 行；win_all=true：0 行；inventory beat=0。
- maxnbeat（新配口径）K1–K21：4/4/5/2/4/2/4/4/3/1/0/2/3/3/1/2/2/1/1/4/5（全量口径下 K14/K15/K16/K18 另见 base_gbf07 校准行 nbeat=5；§1 与 inventory 均取新配口径）。
- K21：6 行 = 1×base_M07 + 5 新配（k21_daily_hyst003_M07/hyst008_M07/rs120_M07/rs252_M07/hyst003_gbf07），无 base_gbf07；最强行 k21_daily_hyst003_gbf07 nbeat=5，短窗增量 +1.48/+5.27/+6.53/+12.46（2y −106.20、mdd −24.28 更浅、switches=11）。
- 最强行：K8 g_bf07_winA30（nbeat=4，total 2400.29，mdd −24.17）为 215 行全场 total 最高；K3 g_bf07（nbeat=5，total 2128.41，仅 1m 差 −0.01pp）为并列峰值代表。
- base_M07 行 21 文件六窗/total/mdd 签名唯一（1863.27/−27.05/−4.09/17.28/39.00/164.05/1474.08/1677.53）；base_gbf07 四文件签名唯一（2128.41/−24.28/nbeat=5）。
- K20 对照行：daily_M07_brakeD 与 daily_M07 六窗+total/mdd/trades/cost/switches 全同，仅 brake_log 时间戳不同（switch_log 相同）；190 系按独立 tag 含该行计得。
- §3 复核报告链含 batch_052_m07k21（K21 约束逐日）——文本 grep 确认。

## 逐项结论（以 briefing 所列断言为准）

1. K1–K21 共 21 文件 —— PASS（21/21 存在且为数组）。
2. 行数串 30/9/29/18/20/8/6/8/7/13/7/7/7/6/7/6/4/6/7/6/6=215 —— briefing 转述 FAIL（该串求和 217≠215；K9/K10 顺位互换：实际 K9=13、K10=7；K15 误作 7：实际 5）；§1 表格行数（K9=13、K10=7、K15=5）与实际文件逐轮一致 —— PASS；inventory totalrows=215 —— PASS。
3. 新配 185+5=190、零重名 —— PASS（185=K1–K20 新配，5=K21 新配；去重 190，dup=0）。
4. K21 结构 —— PASS（6 行 = 1 base + 5 新；注：briefing“6行base+5新”按字面为 11 行系笔误，应读作“6 行含 base + 5 新”）。
5. beat 全 0 —— PASS（beat_all/win_all 真值行均为 0；inventory beat=0；§1 beat_all 列全 0）。
6. maxnbeat 串 4/4/5/2/4/2/4/4/3/1/0/2/3/3/1/2/2/1/2/4/5 —— briefing 转述 FAIL（K19 位误作 2，实际新配 max=1，r_B90_A90 唯一赢 1m）；§1 表格该列（K19=1）与实际一致 —— PASS；inventory maxnb 21 键逐键一致 —— PASS。
7. 最强行 K8 g_bf07_winA30 total 2400.29 —— PASS（nbeat=4；为 215 行全场 total 最高，“全场最高”成立）。
8. 报告链含 batch_052_m07k21 —— PASS。
9. inventory_k40.json（totalrows 215 / distinct 190 / beat 0 / maxnb 21 键 / cal 双-base 映射 K14·K15·K16·K18 其余单 base_M07）—— PASS。

## 总判

文件层（21 sweep 文件 → inventory_k40.json → §1 表格/§3 报告链）数字口径全部 PASS；briefing 转述串中 3 处笔误（行数串 K9/K10 互换且 K15 误 7 求和 217、maxnbeat 串 K19 误 2、“6行base+5新”措辞）系传达层问题，§1 正文与 inventory 文件无此问题。§1 与 inventory_k40.json 一致。

（同目录 audit_inv10.md 为 agent-60 报告，本文件为 agent-61 独立重算复核；结论互相印证，未改动其文件。）
