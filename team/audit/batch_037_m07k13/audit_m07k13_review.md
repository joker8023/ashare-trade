# M07/K13 self-adaptive pilot review (batch_037_m07k13)

## 0. One-line verdict

FAIL: all 6 K13 new configs fail (beat_all=0, best nbeat=3 dynT10_both). Lookahead, caliber and independent recompute all pass, but no promotion. The only nbeat>=4 candidate universe-wide is the K3 legacy row g_bf07 (full-precision rerun nbeat=5, misses only 1m by 0.007pp). Full T-line on it: recompute zero-dev and ex-top3 pass, but cross-phase collapses (ph7 goes 0/6) and slip-doubling zeroes it vs standard M07. K13 pilot closed in tested 6-config space. Paper-track stays M07.

- Baseline: results/r30_bt/M07_final.json -- total 1863.27 / mdd -27.05 / switches 3 / windows 1m -4.09 / 3m 17.28 / 6m 39.00 / 1y 164.05 / 2y 1474.08 / 3y 1677.53 / top3 26.4pct / extop3 1351.75.
- K13 objects: results/r30_bt/sweep_beat_m07_k13.json (7 rows = base + 6 new; producer research/sweep_beat_m07_k13.py 242 lines; mechanism research/adaptive_k13.py 184 lines, new-file only). Note: research/gbf07_fullprec_k13.py (71 lines) is a full-precision rerun of K3 g_bf07 with NO adaptive code (repo-wide grep for dynamic/confirm/delay/adaptive: zero code hits; the single hold_days hit is a trade-record field in switch_engine, not a decision input).
- Universe recount (independent this round): K1-K13 = 169 rows (156 new = 150 from K1-K12 + 6 from K13) plus the g_bf07 full-precision row. beat_all=True count = 0. File-declared vs recomputed nbeat/beat_all mismatches: none.

## 1. K13 verdict (6 new configs, all fail)

- k13_dynT05_B (dynN T=0.05, B leg): total 1797.36 (-65.91), mdd -26.02, nbeat 0.
- k13_dynT05_both (dynN T=0.05, both legs): total 1727.11 (-136.16), mdd -25.98, nbeat 1 (only 3m).
- k13_dynT10_B (dynN T=0.10, B leg): total 1897.93 (+34.66), mdd -25.72, nbeat 1 (only 3y).
- k13_dynT10_both (dynN T=0.10, both legs): total 1990.79 (+127.52), mdd -25.72, nbeat 3 (3m/2y/3y; loses 1m/6m/1y).
- k13_dly_enterB (delay A->B): total 1851.58 (-11.69), mdd -27.03, nbeat 0.
- k13_dly_exitB (delay B->A): total 1850.66 (-12.61), mdd -27.05, nbeat 2 (6m/1y).

Best row dynT10_both still loses three windows. All mdd values are shallower-or-equal vs M07 (-25.72 to -27.05 vs -27.05; exitB ties so mdd_better=False), but shallow mdd alone is not promotion (task needs all six windows plus shallower drawdown). Trigger set (beat_all or nbeat>=4) contains zero K13 new configs, so the T-line suite is moot for K13 proper.

## 2. Lookahead line-by-line (adaptive_k13.py, all 184 lines: PASS)

Patch construction: string-patch of switch_engine.py source then exec, same engine family as K11 (batch_033 audited). All anchors (AA/BB/CC/DD/EE/FF/GG/SIG/PICKLINE/DESIRED/STATE_BLK/BRAKE_EVAL/SKIP_BLOCK) asserted count==1 (fail-closed).

- Dynamic-N threshold compare (L114-127): _ra/_rb are the M07-native votes from _rs(shadow, sig_i) (searchsorted right-1 takes the last bar at-or-before signal day t; audited in batch_033/035). _margin=abs(ra-rb) is a pure function of t-and-before trailing-60 spreads. _newN = 3 if margin>T else 5 uses no future data. N only changes on A-grid signal evaluation days (patch sits after DESIRED, outside if-switching, so switch and non-switch signal days both update it; non-signal days never touch it -- matches the docstring).
- N switch timing (L129): state_n override is appended after STATE_BLK (engine L184-185, inside if-switching, after the mode flip, before L187 n_eff=state_n). So the N used by the t+1 execution rebuild is the new-mode leg N computed from the same signal t margin. Timing is correct: decision info set = t-and-before, execution = t+1 via the native exec_map (L280-281 untouched by any patch).
- Confirm-delay counter (L154-178): _pend is a single slot, init None (L149), read/written only on signal evaluation days. pending->confirmed needs two consecutive same-direction signal days (any raw==mode signal day cancels, L175-178; non-delayed direction executes immediately and clears pend, L171-174). No timeout expiry, but the consecutive-same-vote semantics is an implicit expiry -- any intervening opposite/at-mode signal clears it, so no months-stale pending can confirm (verified: 9 dly_log entries, zero bad transitions, see section 3).
- Forbidden-token scan: no shift(- anywhere repo-wide in research (part_037_tline.json gate F); no new searchsorted/iloc/loc future indexing in either K13 file; brake HELD verbatim (BRAKE_EVAL reused literally, bf=0.6, no freeze). Lookahead veto: none, PASS.
- Observation (not a fail): the dynamic B leg rests at N=5, not the M07-native B n=4 (script self-documents this as the mechanism under test), and the signal shadow rb is always n=4 -- so signal basis and executed leg differ by construction. Disclosed design property. The delay mechanism has no such mismatch (state_n untouched, native 5/4 kept).

## 3. Independent recompute and mechanism activity (all pass -- proves correct, not winning)

Reviewer-executed (work_037_k13verify.py -> part_037_k13verify.json):

1. Module-import rerun of all 7 rows: max deviation 0.00 across 15 numeric keys; trades/mode/switches/brakes identical; switch_log and dyn_log item-equal.
2. base_M07 vs M07_final: total/mdd/six windows deviation 0.00 on all 8 values (K13 producer has no base assert gate; this independent check closes it).
3. dyn margins recomputed from t-and-before shadow trailing-60 RS: 22 dyn_log entries, max deviation 4.9e-05 (round(4) dust), zero N-rule violations across legs scopes. Mechanism fires for real (T05: 12 toggles / 6 concentrated episodes; T10: 10 / 5).
4. Delay state machine: enterB (2023-06-21 pending -> 07-21 confirmed; 2026-09-08 pending -> 10-14 confirmed; 2024-08-15 immediate B->A) and exitB (2024-08-15 pending -> 09-12 confirmed, both ends immediate) validate clean. Producer --check-trailing rerun by reviewer: ALL OK (4/4 picks + amihud 1e-9).
5. Caliber: sweep L48-50 triple assert passes; CA (capital 50000 / lot 100 / cost_one_way=None real fee / slip 0.002 / stop 0.25 / stop_exec next / legacy_grid False / full_liquidate True / MB / ph0 / grid) literally M07; shadow legs share instances with live legs (L96-97 into L110); tags unique (k13_ prefix, dedup covers K1-K12+j04); exactly 6 new configs (L139 assert). Fees/lots PASS.
6. Behavior notes: all 4 dyn rows have switch_log item-identical to M07 (dynamic N resizes positions but never changes switch timing); both delay rows shift the delayed-direction switch by about one grid (enterB first cut 06-21 -> 07-21, last cut 09-08 -> 10-14; exitB middle cut 08-15 -> 09-12). Delay works as designed but buys no window.

## 4. T-line trigger set and execution

Under the task gate (beat_all or nbeat>=4) the trigger set has 23 seats: K3 g_bf07 (nbeat=5, the only >=5 universe-wide) plus 22 legacy nbeat=4 rows (K1 x2, K2 x7, K3 x3, K5 x2, K7 x3, K8 x4). All 22 lose exactly [1m, 3m] (independently recomputed from file values this round) -- the short-window wall stands for the 13th round, win_all is impossible for them, and their file flags recompute with zero mismatch (section 0). Prior batches (017/022/023/029/031/033/035) already dispositioned each; no reruns (same moot rule as batch_023/033/035: T-line legs test promotion-candidate robustness, moot for non-qualifiers).

Full 4-leg T-line on g_bf07 full-precision (total 2128.41 / mdd -24.28 / gaps vs M07: 1m -0.007 / 3m +0.01 / 6m +0.30 / 1y +0.85 / 2y +13.53 / 3y +197.95 / mdd edge +2.77). Reviewer-executed work_037_tline.py -> part_037_tline.json (14 full-precision backtest groups):

- Independent rerun: 15 keys deviate 0.0, trades/mode/switches identical, switch_log identical -- PASS. nbeat=5 confirmed with the 1m miss surviving at full precision (not a rounding artifact).
- Cross-phase vs phase-matched M07 (ph 0/5/7/10/14/15): nbeat = 5/4/0/1/2/2. At ph7 g loses all six windows (total 1081.96 vs phase-matched M07 1127.52). Edge is ph0-specific -- cross-phase FAIL.
- ex-top3: g top3 26.3pct vs M07 26.4pct; extop3_total 1545.93 vs 1351.75 (+194pp) -- no concentration deterioration, PASS.
- Slip doubling (0.004): slip-doubled gbf07 vs slip-doubled M07 keeps nbeat=5 (structure preserved); but vs standard M07 nbeat=0 (gbf07 total 2128 -> 1835, -293pp; M07 1863 -> 1596) -- not slip-robust in absolute promotion terms, FAIL.
- Static gates: RUN_START/EVAL_END/WINDOWS/MB match M07; no new temporal code.

## 5. Failure attribution

- dynN: 10-12 N toggles all land on signal days that do not change the switch path (switch_log identical to M07) -- N resizes positions but timing x leg returns decide windows. Even the best T=0.10 both-legs only reaches 3/6.
- confirm-delay: about one grid of delay takes effect as logged, but the M07 native three-cut timing is already at a local optimum -- postponing switches only translates, never adds (enterB 0/6, exitB 2/6 with total -12pp).
- Family level: old mechanism x native legs (K12) falsified + new mechanisms x native legs (K13) falsified. On native amihud_60 legs, the switch dimension (timing/sizing/delay, 12 configs) is exhausted with the passive K3 g_bf07 (5/6) still the peak. If retested: dyn rest-N control (rest at native 4, not 5, to remove the current confound) and pending-timeout variants -- but only with a fresh full T-line past the lookahead gate.

## 6. Verdict

- FAIL: K13 pilot 0/6 (beat_all=0, best nbeat=3, win_all=0). Universe beat_all stays 0 (169 rows independently recomputed). The sole nbeat>=4 fresh candidate (g_bf07 full-precision, 5/6 + shallower mdd) fails two T-line legs (cross-phase, absolute slip level) plus one hard window miss (1m -0.007pp) -- no promotion.
- T1 (beat_all) not triggered. T2 triggered on g_bf07 but not passed (cross-phase 5 -> 0-4, slip zeroes). Remaining T-line legs moot for the K13 trigger set. Paper-track stays M07. No K13 row and no g_bf07 variant may go live.
- Deliverables (this directory only): this report, work_037_tline.py + part_037_tline.json (g_bf07 full T-line), work_037_k13verify.py + part_037_k13verify.json (7-row rerun + margin recompute + state machine), tline_stdout.log. Compliance: no files added outside this directory; no engine/caliber/result files touched; the K13 artifacts (landed 16:22 from the parallel R25 run, after this review started) were read and recomputed solely by independent reviewer execution.


