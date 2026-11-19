# C2 Five-Candidate Independent Audit (audit-5, task-5)

## 1. Verdicts (strict)

strict: 2024 slice>60 and yoy>60, 2025_yoy>60, 2026 slice>60 and yoy>60
(2026 ends 11-12, partial year; slice must still exceed 60, annualized is reference),
full mdd>-30 and 2024/2025/2026 yearly mdd>-30. margin<5 flagged fragile.

- C2_grid_mh0_bx0.15_by0.1_bf0.5 : PASS, margin 6.58, solid. total 1349.24 mdd -23.42.
- C2_daily_h0.03_mh0_bx0.15_by0.05_bf0.5_bd : PASS fragile, margin 2.90. total 1233.45 mdd -27.10.
- C2_daily_h0.03_mh10_bx0.15_by0.05_bf0.5_bd : PASS fragile, margin 2.90. total 1239.65 mdd -27.10.
- C2_daily_h0.02_mh10_bx0.15_by0.1_bf0.5_bg : PASS fragile, margin 1.10. total 1190.57 mdd -25.17.
- C2_grid_mh0_bx0.15_by0.1_bf0.7 : PASS fragile, margin 0.04. total 1300.89 mdd -29.14.
  2024 slice 60.04 / 2024_mdd -26.66 / full mdd -29.14, three near-the-line metrics.

All five PASS; max per-value deviation vs filed rows is 0.00
(numeric fields, switch_log and brake_log all identical).
Root independently reran the strongest item with 0 deviation, consistent.

## 2. Reproduce

    .venv/bin/python research/verify_C5.py

Output: results/r30_bt/verify_C5.json
(each row: tag/total/mdd/2024/2024_yoy/2024_mdd/2025_yoy/2025_mdd/2026/2026_yoy/2026_mdd/
switches/trades/cost/switch_log/brake_log + diff vs search_C_stage2.json,
strict verdict, fragile flag, 2026 annualization).

Caliber (per research/search_C_stage2.py comments):
realshares data/pivots_2020_clean_realshares_v2.pkl, RUN_START 2023-01-03,
EVAL_END 2026-11-12, capital 50000, real fees (cost_one_way None) + slip 0.002,
lot 100, full_liquidate True, exposure<=1, stop 0.25 stop_exec next.
Shadow A (M07-A): MaxInputs band 0.02-0.30 gate60 -0.15 cut 0.80 win 40,
N5/R20/take1.2/exp1.0. Shadow B (B_R15_N5): MaxInputs same band/gate cut0.80 win20,
N5/R15/take0.45/exp1.0. first_sig 2023-02-09, n_dates 1664.
Independent shadow rebuild: A trades 230, B trades 305.

Independence: research/verify_C5.py does not import search_C_combo/search_C_stage2
(grep no match); engine rebuilt from research/switch_engine.py source anchors
with independently written patch code (build_ns idea).

## 3. Value-by-value diff (verify minus filed search_C_stage2.json)

All 13 numeric fields diff 0.0; switch_log_match true; brake_log_match true.

- C2_grid_mh0_bx0.15_by0.1_bf0.5 : max_abs_diff 0.0, switches 8, trades 280, cost 51018.
- C2_daily_h0.03_mh0_bx0.15_by0.05_bf0.5_bd : max_abs_diff 0.0, switches 14, trades 330, cost 52383.
- C2_daily_h0.03_mh10_bx0.15_by0.05_bf0.5_bd : max_abs_diff 0.0, switches 12, trades 325, cost 54371.
- C2_daily_h0.02_mh10_bx0.15_by0.1_bf0.5_bg : max_abs_diff 0.0, switches 14, trades 330, cost 52679.
- C2_grid_mh0_bx0.15_by0.1_bf0.7 : max_abs_diff 0.0, switches 8, trades 280, cost 50604.
(YoY/MDD detail per row is in results/r30_bt/verify_C5.json verify/ref blocks.)

## 4. Lookahead review (research/switch_engine.py, unpatched source)

- RS signal (lines 93-99): _rs locates shadow equity with
  eq.index.searchsorted(dates[sig_i], side=right)-1 and requires j>=rs_lookback(60).
  Only trailing RS up to and including sig_i is used. No future.
- Exec mapping (lines 61-66): exec day = signal day + 1 + sig_lag, sig_lag=0,
  i.e. signal t-close / execution t+1-close. Picks use signal-day factors
  (line 190 picks(sig_day)); fills use exec-day mark prices (line 219).
- Daily patch: evaluates every day but exec_map.setdefault keeps grid entries;
  daily signal sig_i=i-1, i.e. decides on t-1 and earlier, executes at t close:
  strictly more conservative than grid caliber. No lookahead.
- min_hold counts signal-index distance: mh=10 means 10 trading days in daily
  mode; in grid mode any two grid evals are >=10 apart so mh never binds.
- confirm=1: a single trigger switches (subject to min_hold); the counter
  resets whenever raw==mode. hyst=0 degenerates to ra>=rb->A, identical to the
  original EVAL_OLD expression.
- Brake: evaluated only on rebalance days (brake_daily False) or daily
  (brake_daily True), using same-day holdings mark-to-market; scales only new-buy
  alloc; bf>0 avoids the full-liquidate deadlock. Only current/past prices used.
- stop/take with stop_exec=next: triggered at t close, executed t+1 close via
  pending_stop (lines 269-277, 296-304). Lot 100, real fees, slip 0.002 as filed.

Conclusion: no lookahead in evalfreq/daily/min_hold/confirm/brake paths.

## 5. Engine-equivalence evidence

- Independent REF check inside verify_C5.py: lockB no-brake rebuild gives
  total 841.36 / mdd -32.65 / trades 295, identical to the filed
  REF_lockB_R15_nobrake row (841.36 / -32.65 / 295). Engine rebuild is exact.
- The gap vs direct single-leg B (858.64 / -32.31 / 305) is a filed-engine
  property: the switch engine skips no-change rebalances
  (if not switching and set(picks)==set(pos): return False), saving 10 churn
  round-trips. Same gap exists in filed data, not a verify artifact.
- Audit catch during rebuild: the brake total-MV accumulation line must sit
  inside the holdings loop (12 spaces, stage2 line 77). An 8-space variant
  crashes on empty positions and mis-scales; it was fixed before the final run.
  Filed results use the correct 12-space version (proven by 0.00 diffs).

## 6. 2026 partial-year note

2026 covers 01-01~11-12 only (EVAL_END 2026-11-12). Strict still requires slice>60;
annualized extrapolation (1+slice)^(365/days)-1 is reference only:
151.96 / 161.15 / 156.89 / 157.02 / 151.21 for the five rows respectively.

## 7. Files

- research/verify_C5.py : independent rerun script.
- results/r30_bt/verify_C5.json : meta + lookahead + parity + 5 rows.
- results/r30_bt/search_C_stage2.json : filed reference (114 rows, not modified).
