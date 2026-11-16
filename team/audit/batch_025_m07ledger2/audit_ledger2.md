# batch_025_m07ledger2：BEAT_M07_SUMMARY 本轮新增三处复核（ledger2）

- 复核对象：根目录 BEAT_M07_SUMMARY.md 本轮新增——标题 K1–K8、§2 R9 深挖段落、§3 报告链接 batch_023/batch_024、§4 累计数 120 与“短窗墙双重钉死”。
- 方法：只读复算，仅新增本目录文件。命令均用 `.venv/bin/python`。
- 结论先行：**逐项 PASS，无偏差；BEAT 三处新增数字与源文件一致。**

## (a) R9 数字 vs deep_tail_k9.json 与 batch_024（含 §7bis 更正）

| BEAT §2 断言 | 源文件值 |  verdict |
|---|---|---|
| 持仓身份相同、7 票/11 票、差集为空 | `tails.1m.held` base/g 各 7 票、`inter` 7 票、`only_base/only_g` 均空、`identical=true`；`tails.3m` 各 11 票、`inter` 11 票、差集均空、`identical=true` | PASS |
| 1m“打平”实为 −0.0018318954pp | `attrib.1m.ret_full.gap_g_minus_b=−0.0018318954048028857`，舍入即 −0.0018318954pp；`ret_r2` 双 −4.09 与“打平”表述一致 | PASS |
| 3m 差 −0.0355pp | `attrib.3m.gap=−0.03550555986744186` → −0.0355pp；`ret_r2` 17.28/17.25 | PASS |
| g 侧绝对多赚 +39240 元 | `attrib.3m.abs_gain_yuan` g 183878.16490919702 − base 144637.6975209599 = **+39240.467** | PASS |
| 基数大 +27.4% | g 3m `start_eq` 1066265.1464063353 / base 836995.8611012499 = 1.273919 → **+27.3919%** | PASS |
| 窗内刹车事件为空 | `attrib.1m/3m.brake_events_in_win` base/g 四组全空；3m 窗内 switch 双方同为 2026-09-08→B（身份一致的佐证） | PASS |
| batch_024 独立重算 10 位一致 | batch_024 §7bis：R9 gap 与 `part_k9deep.json` 1m/3m 十位一致；亲验 `part_k9deep.windows_full` diff 1m −0.0018318954048028857、3m −0.03550555986744186，与 R9 逐位相同；四组 `ret_full`（base 1m −4.0926396171 / g 1m −4.0944715125 / base 3m 17.280575 / g 3m 17.2450694397）一致 | PASS |

无偏差。§7bis 系“首查时点竞态误判存在性、后已亲验互证”的更正，与 BEAT 引用的互证结论一致。

## (b) 累计 128 行 / 120 新配 vs k1–k8 json 独立重算

独立重算（`results/r30_bt/sweep_beat_m07_k{1..8}.json`，逐文件 keys 计数 + tag 去重 + `beat_all/nbeat_m07` 字段统计）：

| 轮 | BEAT 表（行/新配/beat_all/最高nbeat） | 独立重算 | verdict |
|---|---|---|---|
| K1 | 30/29/0/4（k05_by05、k25_cut78 并列） | 30 行、base_M07×1、新配 29；max `nbeat_m07`=4 并列 k05_by05（total 2022.84）/k25_cut78（mdd −25.35）；`beat_all` 全 0 | PASS |
| K2 | 9/8/0/4（g_by05_cut78_bx15） | 9 行、新配 8；max nbeat=4；nbeat=4 行中 g_by05_cut78_bx15 total 2084.73 最高（h_…_bf07 total 2090.82 但 nbeat=3，按 nbeat→total 规则不入选，与 batch_023 tie-break 规则一致）；mdd −22.87、total 2084.73 | PASS |
| K3 | 29/28/0/5（g_bf07） | 29 行、新配 28；max nbeat=5 唯一 g_bf07（total 2128.41、mdd −24.28、1m −4.10/3m 17.29） | PASS |
| K4 | 18/17/0/2（r_A15B30） | 18 行、新配 17；max nbeat=2 唯一 r_A15B30（mdd −29.73） | PASS |
| K5 | 20/19/0/4（nobrake_gbf07） | 20 行、新配 19；max nbeat=4 并列两行，nobrake_gbf07 total 2243.52 > nobrake_M07 2182.6；mdd −28.40 | PASS |
| K6 | 8/7/0/2（cut75_both） | 8 行、新配 7；max nbeat=2 唯一 cut75_both（3y 1628.18，即 3y 差约 −49.35pp） | PASS |
| K7 | 6/5/0/4（g_bf085） | 6 行、新配 5；max nbeat=4 三行，g_bf085 total 2182.70 最高（g_bf080 2177.90 次之） | PASS |
| K8 | 8/7/0/4（g_bf07_winA30） | 8 行、新配 7；max nbeat=4 四行，winA30 total 2400.29 最高且为八轮全局最高；1m −4.09 打平/3m 17.25（−0.03pp）、mdd −24.17 | PASS |
| 合计 | 128/120/0 | 128 行、base_M07 校准行×8、新配 tag 去重 120 unique（跨文件零重名）；`beat_all=True` 全域 0；8 个 base 行 total/mdd/六窗与 M07_final（1863.27/−27.05/−4.09/17.28/39.00/164.05/1474.08/1677.53）逐值相等 | PASS |

无偏差。备注：BEAT 表格“最强行”在并列时取 total 高者（K2/K5/K7/K8 均有并列），与 batch_023 §2 明示的 tie-break 规则一致，不属偏差。

## (c) §3 报告链接 batch_023 / batch_024

- `team/audit/batch_023_m07k8/audit_m07k8_review.md` 存在；结论为 **FAIL**（§7 verdict：“K8 的 7 新配 beat_all=0、win_all=0；K1–K8 累计 120 新配 beat_all=0”），与 BEAT §3“（K8）”标注及 §4 裁决引用一致。PASS。
- `team/audit/batch_024_m07k9/audit_m07k9_review.md` 存在；结论为 FAIL 延续（§7 verdict），§7bis 更正 R9 文件存在性并与 R9 全精度互证，与 BEAT §2“复核 batch_024 独立重算 10 位一致”引用一致。PASS。

## §4 “累计 120 新配 beat_all=0”与“短窗墙双重钉死”

- 120 新配 beat_all=0：见 (b) 全域重算，PASS。
- “双重钉死”（持仓身份 + 分母效应）：见 (a)，身份逐字相同（差集空）与分母效应（+39240 元绝对多赚 / +27.4% 基数摊薄反输）两链均有源文件值支撑，PASS。

## 总 verdict

- **BEAT_M07_SUMMARY 本轮新增三处：逐项 PASS，零偏差。**
- 产物清单（仅本目录）：`audit_ledger2.md`（本文件）。
