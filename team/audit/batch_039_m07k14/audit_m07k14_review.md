# M07/K14 peak-times-adaptive review (batch_039_m07k14)

## 0. One-line verdict

FAIL: K14 all out (beat_all=0, best new nbeat=3, three-way tie). Dual calibration passes at 0.00 deviation on all 16 values, file flags recompute with zero mismatch, and the independent rerun of the best overlay row is zero-dev -- but no overlay candidate meets the T-line gate (beat_all or nbeat>=4), so the full T-line suite is moot and nothing promotes. Synergy conclusion: antagonistic -- the same adaptive mechanisms that are neutral on the M07 base destroy windows on the g_bf07 peak (5/6 -> 3/6 max). Paper-track stays M07.

- Baseline: results/r30_bt/M07_final.json -- total 1863.27 / mdd -27.05 / windows 1m -4.09 / 3m 17.28 / 6m 39.00 / 1y 164.05 / 2y 1474.08 / 3y 1677.53.
- K14 objects: results/r30_bt/sweep_beat_m07_k14.json (6 rows = 2 calib + 4 new; producer research/sweep_beat_m07_k14.py 316 lines, reuses research/adaptive_k13.py audited in batch_037; lock_mode=None throughout).
- Machine record: team/audit/batch_039_m07k14/part_039_k14verify.json (dual-calib table + per-row flag recompute + independent rerun values).

## 1. Dual calibration (gate <= 0.01, both PASS at 0.00)

- base_M07 vs M07_final: total/mdd/six windows deviation 0.00 on all 8 values (1863.27 / -27.05 / -4.09 / 17.28 / 39.00 / 164.05 / 1474.08 / 1677.53). Producer script carries the same assert (L263 total/mdd <= 0.01) plus RUN_START/EVAL_END/WINDOWS asserts (L57-59).
- base_gbf07 vs K3 g_bf07 row (results/r30_bt/sweep_beat_m07_k3.json): deviation 0.00 on all 8 values (2128.41 / -24.28 / -4.10 / 17.29 / 39.30 / 164.90 / 1487.61 / 1875.48, nbeat=5). Peak base reproduces verbatim (by05+cut78both+bx15+bf0.7).

## 2. K14 verdict (4 new overlays on the g_bf07 peak, all fail)

- k14_dynT10_both (peak x dynN T=0.10 both-legs): total 2242.86 (+114.45 vs peak), mdd -23.65, nbeat 3 (wins 3m/2y/3y; loses 1m/6m/1y). Highest total and shallowest mdd in file, yet loses three windows (6m -13.4pp, 1y -37pp vs peak).
- k14_dynT05_both (peak x dynN T=0.05 both-legs): total 1786.87 (-341.54), mdd -26.47, nbeat 1 (wins only 3m). Extra 4th brake vs peak.
- k14_dly_exitB (peak x confirm-delay exitB): total 1969.11 (-159.30), mdd -24.28, nbeat 3 (wins 6m/2y/3y; loses 1m/3m/1y).
- k14_triple_T10xB (peak x dynN(T10,both)+exitB): total 2108.48 (-19.93 vs peak), mdd -23.65, nbeat 3 (wins 3m/2y/3y). No compounding over the single mechanism (-134.38 total vs dynT10 alone, identical window pattern).
- beat_all=True count = 0 (all 6 rows). File-declared vs recomputed nbeat/beat_all/mdd_better mismatches: none (6/6 MATCH).
- Behavior: both dyn rows keep switch_log item-identical to the peak (06-21 B / 08-15 A / 09-08 B) -- N resizes positions but never changes switch timing, same as K13 on the M07 base. Both delay-involved rows shift the middle cut 08-15 -> 09-12 (same one-grid delay signature as K13 exitB).

## 3. T-line trigger set and execution

- Gate (beat_all or nbeat>=4) over the 4 new overlays: trigger set is EMPTY (best = 3). Full T-line legs (cross-phase, ex-top3, slip doubling, independent recompute) test promotion-candidate robustness and are moot for non-qualifiers -- no T-line executed, same moot rule as batch_023/033/035/037.
- The only nbeat>=4 row in the file is base_gbf07 (nbeat=5, calibration row, not an overlay candidate). Its full 4-leg T-line was already executed in batch_037 (cross-phase FAIL, absolute-slip FAIL, 1m miss -0.007pp) -- no rerun, conclusion stands.
- Lookahead spot check: grep over research/sweep_beat_m07_k14.py finds no shift(- futures and no new searchsorted/iloc future indexing (the two iloc hits are L218/234 trailing-window return math, t-and-before); mechanism code is the batch_037-audited adaptive_k13.py reused verbatim. No new temporal code from K14.
- Independent recompute spot check (reviewer-executed): .venv/bin/python research/sweep_beat_m07_k14.py --only k14_dynT10_both -> total 2242.86 / mdd -23.65 / six windows item-identical to file (dev 0.0), nbeat=3 confirmed. File peak row is genuinely computed, not hand-filled.

## 4. Synergy conclusion (peak x adaptive)

One sentence: ANTAGONISTIC -- the K13-best mechanism (dynT10_both, 3/6 on the M07 base) stacked on the g_bf07 peak (5/6, misses only 1m) stays at 3/6 while destroying two of the peak existing wins (6m 39.30->25.60, 1y 164.90->127.05); the delay mechanism likewise converts the peak 5/6 into 3/6; the triple stack adds nothing over the single mechanism -- on peak legs already at a local optimum, timing/sizing perturbations subtract windows even as they inflate total, so there is no orthogonal gain to harvest in this direction.

## 5. Verdict

- FAIL: K14 0/4 (beat_all=0, best nbeat=3 x3, win_all=0). Universe beat_all stays 0. No overlay row and no triple-stack variant may go live.
- T1 (beat_all) not triggered. T2 (nbeat>=4) not triggered by any new overlay. Paper-track stays M07.
- Deliverables (this directory only): this report + part_039_k14verify.json. Compliance: no files added outside this directory; no engine/caliber/result files touched; the K14 artifact (landed 16:36 from the parallel R38 run, after this review started) was read and recomputed solely by independent reviewer execution.
