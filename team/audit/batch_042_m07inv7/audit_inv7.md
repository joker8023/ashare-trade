# M07 sweep 盘点复核 audit_inv7（batch_042_m07inv7）

- 审计对象：results/r30_bt/inventory_k30.json vs BEAT_M07_SUMMARY.md §1（K1-K15）
- 方法：独立重算，只读源文件，不改动源文件；计算环境 .venv/bin/python，逐文件解析 results/r30_bt/sweep_beat_m07_k1..15.json（数组长度、tag、nbeat_m07、beat_all、win_all、校准行签名、total/mdd）。
- 结论速览：逐项 PASS（7/7）；inventory 与 SUMMARY §1 表格完全一致。委派语中的行数字串有一处笔误（见项1备注），不影响源文件结论。

## 逐项判定

### 1. 每轮行数：30/9/29/18/20/8/6/8/13/7/7/7/7/6/5 = 180 —— PASS

重算（数组长度）：K1=30, K2=9, K3=29, K4=18, K5=20, K6=8, K7=6, K8=8, K9=13, K10=7, K11=7, K12=7, K13=7, K14=6, K15=5；求和 = 180。与 SUMMARY §1 表格逐轮一致，与 inventory totalrows=180 一致。

备注：委派语行数字串 30/9/29/18/20/8/6/8/7/13/7/7/7/7/5 按字面求和为 181（K9/K10 位置互换且 K14 写成 7），与源文件实际（K9=13、K10=7、K14=6）不符，判定为委派语笔误，源文件与 SUMMARY 表格无误。

### 2. 新配 163、零重名 —— PASS

- 非校准 tag（排除 base_M07、base_gbf07）去重计数 = 163，与 inventory distinct=163 一致。
- 非校准 tag 跨 15 文件零重复（Counter 无 base_M07/base_gbf07 之外的重复项）。
- 每轮新配 = 行数 - 校准行数：29/8/28/17/19/7/5/7/12/6/6/6/6/4/3，求和 163（= 180 - 17 校准行：K1-K13 各 1 行 + K14/K15 各 2 行）。

### 3. 校准行：K1-K13 为 base_M07 单行，K14/K15 为 base_M07+base_gbf07 双行 —— PASS

重算每轮校准 tag：K1-K13 均为 [base_M07]，K14/K15 均为 [base_M07, base_gbf07]，与 inventory cal 逐文件一致。

逐字复现校验：

- 15 个 base_M07 行按 total/mdd/1m/3m/6m/1y/2y/3y/trades/cost/mode/switches/brakes/switch_log/brake_log 签名唯一 1 种，且 total=1863.27/mdd=-27.05 与 M07_final.json 一致。
- K14/K15 的 base_gbf07 全行签名与 K3 g_bf07 完全相同（total=2128.41/mdd=-24.28/nbeat=5）。

### 4. beat 全 0 —— PASS

15 文件全部行的 beat_all=false（每轮 beat_all 行数均为 0，win_all 行数亦为 0），与 inventory beat=0 及 SUMMARY §1“beat_all=0”一致。

### 5. maxnbeat（非校准行最大值）：4/4/5/2/4/2/4/4/3/1/0/2/3/3/1 —— PASS

重算（排除校准行后每轮 nbeat_m07 最大值）：K1=4, K2=4, K3=5, K4=2, K5=4, K6=2, K7=4, K8=4, K9=3, K10=1, K11=0, K12=2, K13=3, K14=3, K15=1。与 inventory maxnb 15 个键及 SUMMARY §1“最高nbeat”列逐轮一致。

口径说明（重要）：K14/K15 若含校准行则最大值均为 5（来自 base_gbf07 的 nbeat=5）；inventory 与 SUMMARY 的 3/1 指非校准新配中的最大值（K14 k14_dynT10_both=3，K15 k15_dynT10_B=1），口径一致，予以通过。

### 6. 最强行 K8 g_bf07_winA30，total 2400.29 —— PASS

- K8 文件内按 total 排序第一为 g_bf07_winA30：total=2400.29/mdd=-24.17/nbeat=4/beat=false。
- 全 180 行全局最大 total 亦为该行（K8/g_bf07_winA30），“全场最高”成立。

### 7. inventory 字段自洽 —— PASS

totalrows=180（=分轮之和）、distinct=163（=180-17校准行=非校准去重数）、beat=0、maxnb 15 键全对、cal 15 键全对。未发现缺键、多键或数值漂移。

## 总判定

PASS 7/7：inventory_k30.json 与 BEAT_M07_SUMMARY.md §1 在行数、总数 180、新配 163、零重名、校准行构成（含逐字复现）、beat 全 0、maxnbeat 序列、最强行（K8 winA30 / 2400.29）上全部一致。唯一注记为委派语行数字串笔误（K9/K10 互换、K14 误写 7），源文件与 SUMMARY 表格均正确，无需改动源文件。
