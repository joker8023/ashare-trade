# audit_inv6 — inventory_k28.json vs BEAT_M07_SUMMARY.md §1 独立重算复核

日期： 2026-11-16；复核人： agent-40（复核子 agent）；工作目录： /Users/joker/coding/ashare-trade；Python： .venv/bin/python。
对象： results/r30_bt/inventory_k28.json 对 BEAT_M07_SUMMARY.md §1（K1–K14）逐项声明。
方法： 独立脚本 team/audit/batch_040_m07inv6/recompute_inv6.py（+ check_k11k14.py）直读
  results/r30_bt/sweep_beat_m07_k{1..14}.json 全行重算：行数、新配数（tag 非 base_ 开头）、
  新配 tag 跨轮去重、beat_all / win_all 计数、每轮 max(nbeat_m07)、K8 最强行、K14 校准行、
  base_M07 行与 results/r30_bt/M07_final.json 关键字段比对；再与 inventory_k28.json 逐值核对。

## 结论先行

**全部逐项 PASS（共 8 大项），附两条口径备注（N1、N2，不影响 PASS）。**
inventory_k28.json（totalrows 175 / distinct 160 / beat 0 / maxnb 14 轮映射）与独立重算逐值一致；
§1 表格中 K1–K14 行数、新配数、beat 全 0、maxnbeat、K8 最强行 g_bf07_winA30 total 2400.29 全部复现。

## 逐项 verdict

| # | 核查项 | §1 / inventory 声明 | 独立重算 | verdict |
|---|---|---|---|---|
| 1 | K1–K14 每轮行数 | 30/9/29/18/20/8/6/8/13/7/7/7/7/6（K1→K14，合计 175） | K1=30,K2=9,K3=29,K4=18,K5=20,K6=8,K7=6,K8=8,K9=13,K10=7,K11=7,K12=7,K13=7,K14=6，合计 175 | PASS |
| 2 | 每轮新配数 | 29/8/28/17/19/7/5/7/12/6/6/6/6/4（K1–K13 合计 156，K14 追加 4，合计 160） | 同左；K1–K13 求和=156，+K14 的 4=160 | PASS |
| 3 | 160 新配零重名 | distinct=160、无重名 | 160 个新配 tag 去重后=160，跨轮重名：无；轮内重名：14 轮均为无 | PASS |
| 4 | beat 全 0 | beat_all=0（inventory beat=0；§1 每轮 beat_all=0） | 175 行（含校准行）中 beat_all=true 共 0；win_all=true 共 0 | PASS |
| 5 | 每轮 maxnbeat | 4/4/5/2/4/2/4/4/3/1/0/2/3/3（K1→K14） | 新配口径下逐轮一致（K14=3 见 N1） | PASS |
| 6 | 最强行 K8 | g_bf07_winA30，total 2400.29 | K8 按 (nbeat,total) 取顶：g_bf07_winA30，nbeat=4，total=2400.29 | PASS |
| 7 | K14 含 base_gbf07 第二校准行 | K14=6 行=2 校准行+4 新配 | K14 tags=[base_M07, base_gbf07, k14_dynT10_both, k14_dynT05_both, k14_dly_exitB, k14_triple_T10xB]；base_gbf07 与 K3 g_bf07 在 total/mdd/六窗/trades/cost/mode/switches/brakes 逐键相等 | PASS |
| 8 | inventory_k28.json 文件值 | totalrows=175, distinct=160, beat=0, maxnb={k1:4,k2:4,k3:5,k4:2,k5:4,k6:2,k7:4,k8:4,k9:3,k10:1,k11:0,k12:2,k13:3,k14:3} | 与重算逐值一致（maxnb 为新配口径，见 N1） | PASS |

## 口径备注

- N1（maxnbeat 口径）： §1 表格与 inventory 的 maxnb 均为“新配口径”（排除 base_* 校准行）。
  若按全行口径，K14 max=5（来自第二校准行 base_gbf07 自身 nbeat_m07=5），其余 13 轮不受影响
  （base_M07 行 nbeat=0，K11 新配口径 max=0 也已单列验证：6 个新配 nbeat 全 0）。
  K14 新配 4 行：k14_dynT10_both(3/2242.86)、k14_triple_T10xB(3/2108.48)、k14_dly_exitB(3/1969.11)、
  k14_dynT05_both(1/1786.87)——三行并列 nbeat=3，与 §1“K14 三行并列 nbeat=3”一致。故 N1 为预期内口径事项，非数据错误。
- N2（任务串行数顺序）： 任务描述串“30/9/29/18/20/8/6/8/7/13/7/7/7/6”若按 K1→K14 顺序解读，
  K9/K10 会被读作 7/13；实际文件与 §1 表格均为 K9=13 行、K10=7 行（总和同为 175）。本复核以文件与 §1 表格为准，判 PASS。

## 附：关键重算证据（摘录）

- K1 顶： k05_by05 nbeat=4 total=2022.84；K2 顶： g_by05_cut78_bx15 nbeat=4 total=2084.73；
  K3 顶： g_bf07 nbeat=5 total=2128.41；K5 顶： nobrake_gbf07 nbeat=4 total=2243.52；
  K7 顶： g_bf085 nbeat=4 total=2182.7；K13 顶： k13_dynT10_both nbeat=3 total=1990.79。
- base_M07 校准行： K1–K14 每轮各 1 行；与 M07_final.json（total 1863.27 / mdd −27.05）比对，
  total/mdd/六窗/trades/cost/mode/switches 全等，唯一差异键为 brakes（sweep 行 brakes=3，M07_final.json 无此键，
  为 schema 差异非数值矛盾——§1“逐字复现”指策略口径复现；本项不影响本次 8 项 verdict，记为观察项）。
- K14 base_gbf07 行： total=2128.41, mdd=−24.28, 1m=−4.10/3m=17.29/6m=39.30/1y=164.90/2y=1487.61/3y=1875.48，nbeat_m07=5。

## 文件清单（本次新增，仅限本目录）

- team/audit/batch_040_m07inv6/audit_inv6.md（本报告）
- team/audit/batch_040_m07inv6/recompute_inv6.py（独立重算脚本）
- team/audit/batch_040_m07inv6/check_k11k14.py（K11/K14 新配口径复查脚本）
