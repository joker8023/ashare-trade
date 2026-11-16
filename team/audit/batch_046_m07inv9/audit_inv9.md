# batch_046_m07inv9 审计报告：inventory_k34.json vs BEAT_M07_SUMMARY.md §1（K1–K17）

- 审计人：复核子 agent agent-49；日期 2026-11-16；工作目录 /Users/joker/coding/ashare-trade；Python .venv/bin/python。
- 审计对象：
  - A: results/r30_bt/inventory_k34.json（totalrows=190, distinct=170, beat=0, maxnb 17 键）。
  - B: BEAT_M07_SUMMARY.md §1（标题"十七轮 sweep（Lead 独立复验：190 行、170 独立新配、零重名、beat_all=0）"+ K1–K17 表格 + 脚本/结果清单行）。
- 方法：独立重算，不信任现成合计。直读 results/r30_bt/sweep_beat_m07_k{1..17}.json（数组长度、tag、base_ 校准行、beat_all/win_all、nbeat_m07 新配口径与全口径双算、跨文件 tag 去重、base_M07 与 M07_final.json 签名比对、base_gbf07 与 K3 g_bf07 比对、全局 total 最大值）。脚本：team/audit/batch_046_m07inv9/recompute_inv9.py。
- 口径：新配 = tag 不以 base_ 开头；新配口径 maxnbeat = 排除 base_ 行后每轮 max(nbeat_m07)。

## 独立重算结果（.venv/bin/python 输出摘录）

- 行数：[30,9,29,18,20,8,6,8,13,7,7,7,7,6,5,6,4]，和=190。
- 新配：[29,8,28,17,19,7,5,7,12,6,6,6,6,4,3,4,3]，和=170；去重后 170，跨文件重复 []。
- 校准行：K1–K13=[base_M07]（各 1）；K14/K15/K16=[base_M07, base_gbf07]（各 2）；K17=[base_M07]（1）。
- beat_all=true 全 17 文件共 0；win_all=true 共 0。
- maxnbeat（新配口径）：K1–K17 = 4/4/5/2/4/2/4/4/3/1/0/2/3/3/1/2/2；全口径下 K14/K15/K16 max=5（来自校准行 base_gbf07 自身 nbeat=5）。
- base_M07 签名：17 行 total/mdd/六窗/trades/cost/mode/switches 去重仅 1 种，且与 M07_final.json（total 1863.27/mdd −27.05）一致。
- base_gbf07（K14/K15/K16）与 K3 g_bf07 在 total/mdd/六窗/trades/cost/mode/switches/nbeat 全键相等（total 2128.41/mdd −24.28/nbeat 5）。
- 全局 total 最大：sweep_beat_m07_k8.json/g_bf07_winA30 = 2400.29（mdd −24.17, nbeat 4, beat false）。

## 逐项 verdict

| # | 核对项 | 预期 | 独立重算 | verdict |
|---|---|---|---|---|
| 1 | 每轮行数，和=190 | 30/9/29/18/20/8/6/8/13/7/7/7/7/6/5/6/4=190（§1 表格口径） | 实测 [30,9,29,18,20,8,6,8,13,7,7,7,7,6,5,6,4]=190，与 §1 表格（K9 13/12、K10 7/6、K15 5/3）及 inventory totalrows=190 一字不差 | PASS（注：委派语行数字串"30/9/29/18/20/8/6/8/7/13/7/7/7/6/7/6/4"把 K9/K10 写反为 7/13、K15 写成 7，字面求和 192≠190，为委派语笔误，源文件与 §1 表格正确） |
| 2 | 新配 167+3=170、零重名 | distinct=170，无重复 | 非 base_ tag 去重=170，跨文件重复=[]，轮内无重复；分轮和 170 = 190−20 校准行（K1–K13 各1=13，K14–K16 各2=6，K17 1） | PASS |
| 3 | 校准行 K1–K13 单行、K14–K17 双行 | K1–K13=[base_M07]；K14–K17=[base_M07, base_gbf07] | K1–K13 单行 PASS；K14–K16 双行 PASS（含 base_gbf07≡K3 g_bf07）；但 K17 实际仅 [base_M07] 单行（4 行=1 校准+3 新配），"K17 双行"不成立 | FAIL（仅 K17 一处：委派语"K14–K17 双行"与 K17 文件不符；§1 表格本身未断言 K17 双行，且 K17 行数/新配 4/3 与文件一致） |
| 4 | beat 全 0 | 17 轮 beat_all=0 | 17 文件 beat_all=true 共 0（逐文件 0），win_all=true 共 0；与 inventory beat=0、§1 全 0 一致 | PASS |
| 5 | maxnbeat 4/4/5/2/4/2/4/4/3/1/0/2/3/3/1/2/2 | 新配口径序列 | 新配口径重算一字不差；与 inventory maxnb 17 键逐键一致 | PASS（附口径注：全口径 K14–K16 max=5 系校准行 base_gbf07 所致，非新配） |
| 6 | 最强行 K8 g_bf07_winA30 total 2400.29 | total=2400.29 | K8 该 tag total=2400.29/mdd=−24.17/nbeat=4；为 190 行全局 total 最大，"全场最高"成立 | PASS |
| 7 | inventory_k34.json 字段自洽 | totalrows/distinct/beat/maxnb 与源文件一致 | totalrows=190 ✓、distinct=170 ✓、beat=0 ✓、maxnb 17 键 ✓；注：本版 inventory 无 cal 字段（前版 k30 有），未断言校准构成，故项3 FAIL 不牵连本文件字段 | PASS |

## 总判定

**源数据与 §1 表格实质一致（6/7 PASS），inventory_k34.json 现有 4 字段全部正确；唯一 FAIL 是委派语两处文字笔误：(a) 行数字串 K9/K10 互换且 K15 误写 7（字面和 192≠190）；(b) "K14–K17 双行"中 K17 实际为单校准行。§1 表格与 inventory 文件本身无误，无需改动源文件。**

## 本目录新增文件（仅此两项，未碰他处）

- team/audit/batch_046_m07inv9/recompute_inv9.py（独立重算脚本）
- team/audit/batch_046_m07inv9/audit_inv9.md（本报告）
