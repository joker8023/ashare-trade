# frontier_k11 独立复核审计（batch_026_m07k11）

- 脚本：research/frontier_check_k11.py（11 行；M07 基准 total=1863.27 / 1m=-4.09 / 3m=17.28；tag==base_M07 跳过；violA=total>M07 且 1m>M07；win1m=1m>M07；violC=3m>M07 且 1m>M07；high_total=total>M07 倒序）
- 产物：results/r30_bt/frontier_k11.json
- 源：results/r30_bt/sweep_beat_m07_k1..k8.json（8 文件），Python=.venv/bin/python
- 方法：独立重算（Node 全量重跑 glob 去 base 过滤逻辑，不复用脚本输出），逐项比对。

## (a) 新配行数=120（排除 8 个 base_M07 校准行）— PASS

- 8 文件原始行数：k1=30, k2=9, k3=29, k4=18, k5=20, k6=8, k7=6, k8=8，合计 raw=128。
- 每文件恰含 1 行 tag=base_M07，合计 base=8。
- 新配行 = 128-8 = 120，与 frontier_k11.json n=120 一致；无重复 tag（dups=[]）。

## (b) violA 为空（31 个 total>M07 者 1m 全不超）— PASS

- 重算 total>1863.27 行数 = 31，与 high_total 长度 31 一致。
- violA（total>M07 且 1m>-4.09）重算 = []，与产物一致。
- 31 行 1m 最大值 = -4.09（等于 M07，严格大于不成立），全部满足 1m<=-4.09（例 g_bf07_winA30 2400.29/-4.09、g_winA30 2400.08/-4.09、s_rs70 1904.57/-4.09 等，其余更低）。
- 附带：high_total 集合与重算集合完全相等（31/31）；仅同分并列（1961.01x5、1917.97x2）内部稳定排序顺序与 Python sorted 稳定序有 6 处位次差，属语言排序稳定性差异，不影响实质（set equal=true）。

## (c) win1m 共 10 行且其中仅 r_A15B30/legB_only 兼赢 3m、两者 total 为 772.91/567.08 — PASS

- 重算 1m>-4.09 行数 = 10，与产物 win1m 长度一致，tag 全集一致：
  k08_stop28, k17_an4, k28_btake90_bf07, a_bandA_lo003, b_stop30, s_rs50, r_A15B30, legB_only, pair_hi, Aleg_amihud。
- 10 行中 3m>17.28 者仅 2 行：r_A15B30（3m=17.95, d3m=+0.67, total=772.91）、legB_only（3m=17.92, d3m=+0.64, total=567.08）；其余 8 行 d3m 均为负（-0.06 ~ -5.39）。
- 两行 total 与源一致：r_A15B30=772.91（k4）、legB_only=567.08（k5）。

## (d) violC 恰为该两行 — PASS

- 重算 violC（3m>17.28 且 1m>-4.09）= [r_A15B30, legB_only]，与产物 violC 完全一致（顺序一致，长度 2）。

## 抽查：2 个 win1m 行的 1m/3m/total 与源 k-json 一致 — PASS

- k08_stop28 源 sweep_beat_m07_k1.json：1m=-4.08 / 3m=17.22 / total=1402.8 / mdd=-34.81（d1m=+0.01, d3m=-0.06）；产物 win1m 条目 total=1402.8, d1m=0.01, d3m=-0.06, mdd=-34.81 — PASS。
- s_rs50 源 sweep_beat_m07_k3.json：1m=-4.08 / 3m=16.45 / total=1630.18 / mdd=-34.39（d1m=+0.01, d3m=-0.83）；产物 win1m 条目 total=1630.18, d1m=0.01, d3m=-0.83, mdd=-34.39 — PASS。
- 另全量核对 10 个 win1m 条目的 total/d1m/d3m/mdd 与源逐行一致（10/10 match=true）。

## 结论

- (a) PASS｜(b) PASS｜(c) PASS｜(d) PASS｜抽查 PASS。
- 产物 frontier_k11.json 四项断言全部成立；唯一非实质差异为 high_total 同分并列内部顺序（JS vs Python 稳定排序），集合一致。
