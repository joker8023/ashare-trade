# batch_048_m07inv10 审计报告：inventory_k36.json vs BEAT_M07_SUMMARY.md §1（K1–K18）

- 审计人：复核子 agent agent-52；日期 2026-11-16；工作目录 /Users/joker/coding/ashare-trade；Python .venv/bin/python。
- 审计对象：
  - A: results/r30_bt/inventory_k36.json（totalrows=196, distinct=174, beat=0, maxnb 18 键）。
  - B: BEAT_M07_SUMMARY.md §1（标题"十八轮 sweep（Lead 独立复验：196 行、174 独立新配、零重名、beat_all=0）"+ K1–K18 表格 + 脚本/结果清单行）。
- 方法：独立重算，不信任现成合计。直读 results/r30_bt/sweep_beat_m07_k{1..18}.json（数组长度、tag、base_ 校准行、beat_all/win_all、nbeat_m07 新配口径与全口径双算、跨文件 tag 去重、base_M07 与 M07_final.json 签名比对、base_gbf07 与 K3 g_bf07 比对、全局 total 最大值、K18 行明细）。脚本：team/audit/batch_048_m07inv10/recompute_inv10.py。
- 口径：新配 = tag 不以 base_ 开头；新配口径 maxnbeat = 排除 base_ 行后每轮 max(nbeat_m07)。

## 独立重算结果（.venv/bin/python 输出摘录）

- 行数：[30,9,29,18,20,8,6,8,13,7,7,7,7,6,5,6,4,6]，和=196。
- 新配：[29,8,28,17,19,7,5,7,12,6,6,6,6,4,3,4,3,4]，和=174；去重后 174，跨文件重复 []。
- 校准行：K1–K13=[base_M07]（各 1）；K14/K15/K16=[base_M07, base_gbf07]（各 2）；K17=[base_M07]（1）；K18=[base_M07, base_gbf07]（2）。
- beat_all=true 全 18 文件共 0；win_all=true 共 0。
- maxnbeat（新配口径）：K1–K18 = 4/4/5/2/4/2/4/4/3/1/0/2/3/3/1/2/2/1；全口径下 K14/K15/K16/K18 max=5（来自校准行 base_gbf07 自身 nbeat=5）。
- base_M07 签名：18 行 total/mdd/六窗/trades/cost/mode/switches 去重仅 1 种，且与 M07_final.json（total 1863.27/mdd −27.05）一致。
- base_gbf07（K14/K15/K16/K18）与 K3 g_bf07 在 total/mdd/六窗/trades/cost/mode/switches/nbeat 全键相等（total 2128.41/mdd −24.28/nbeat 5）。
- 全局 total 最大：sweep_beat_m07_k8.json/g_bf07_winA30 = 2400.29（mdd −24.17, nbeat 4, beat false）。
- K18 明细（6 行=2 校准+4 新配）：k18_amiprop_gbf07 total 1581.87（1863.27−1581.87=281.4，即表内"total−281pp"）、k18_ranklin_gbf07 1511.82、k18_amiprop_B 783.2、k18_ranklin_B 740.84；四新配 nbeat 均为 1。

## 逐项 verdict

| # | 核对项 | 预期 | 独立重算 | verdict |
|---|---|---|---|---|
| 1 | K1–K18 共 18 文件 | sweep_beat_m07_k1..k18.json 齐全 | 18 文件逐个读出，均为数组，无缺失 | PASS |
| 2 | 每轮行数，和=196 | 30/9/29/18/20/8/6/8/13/7/7/7/7/6/5/6/4/6=196（§1 表格：K9 13、K10 7、K15 5、K18 6） | 实测 [30,9,29,18,20,8,6,8,13,7,7,7,7,6,5,6,4,6]=196，与 §1 表格及 inventory totalrows=196 一字不差 | PASS（注：委派语字串"…/8/7/13/…/6/7/6/…"把 K9/K10 写反为 7/13、K15 写成 7，字面求和 198≠196，为委派语笔误，与 batch_046 同类笔误；源文件与 §1 表格正确） |
| 3 | 新配 170+4=174、零重名 | distinct=174，无重复；K18 新增 4 | 非 base_ tag 去重=174，跨文件重复=[]，轮内无重复；分轮和 174 = 196−22 校准行（K1–K13 各1=13，K14–K16 各2=6，K17 1，K18 2）；K1–K17 新配沿用 170，K18 新配 4（k18_amiprop_B/gbf07、k18_ranklin_B/gbf07） | PASS |
| 4 | 校准行 K1–K13/K17 单行、K14–K16/K18 双行 | K1–K13=[base_M07]；K14–K16/K18=[base_M07, base_gbf07]；K17=[base_M07] | K1–K13 单行 PASS；K14–K16 双行 PASS；K17 单行 PASS；K18 双行 PASS；base_gbf07 四处均≡K3 g_bf07 | PASS（本轮委派语校准构成表述已修正，上轮"K17 双行"笔误不再出现） |
| 5 | beat 全 0 | 18 轮 beat_all=0 | 18 文件 beat_all=true 共 0（逐文件 0），win_all=true 共 0；与 inventory beat=0、§1 全 0 一致 | PASS |
| 6 | maxnbeat 4/4/5/2/4/2/4/4/3/1/0/2/3/3/1/2/2/1 | 新配口径序列 | 新配口径重算一字不差；与 inventory maxnb 18 键逐键一致（K1–K18 顺序） | PASS（附口径注：全口径 K14/K15/K16/K18 max=5 系校准行 base_gbf07 所致，非新配） |
| 7 | 最强行 K8 g_bf07_winA30 total 2400.29 | total=2400.29 | K8 该 tag total=2400.29/mdd=−24.17/nbeat=4/beat=false；为 196 行全局 total 最大，"全场最高"成立 | PASS |
| 8 | inventory_k36.json 字段自洽 | totalrows/distinct/beat/maxnb 与源文件一致 | totalrows=196 ✓、distinct=174 ✓、beat=0 ✓、maxnb 18 键 ✓（逐键等于新配口径 maxnbeat）；§1"K18追加4配，最高nbeat=1"与 K18 新配 4、maxnew 1 一致 | PASS |

## 总判定

**8/8 PASS：源数据、§1 表格、inventory_k36.json 三方实质一致，inventory_k36.json 现有 4 字段全部正确。唯一瑕疵是委派语行数字串两处笔误：(a) K9/K10 互换写成 7/13（实际 13/7）；(b) K15 误写 7（实际 5），字串字面和 198≠196；但"=196"的结论、§1 表格与 inventory 文件本身无误，无需改动源文件。**

## 本目录新增文件（仅此两项，未碰他处）

- team/audit/batch_048_m07inv10/recompute_inv10.py（独立重算脚本）
- team/audit/batch_048_m07inv10/audit_inv10.md（本报告）
