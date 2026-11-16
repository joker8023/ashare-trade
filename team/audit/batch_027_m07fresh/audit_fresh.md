# M07 Evidence Freshness Audit (batch_027_m07fresh / audit_fresh)

- Audit time (UTC+8): 2026-11-16
- Workdir: /Users/joker/coding/ashare-trade ; Python: .venv/bin/python
- Goal: independently rerun two anchors and confirm the 120-line evidence has no data drift; deviation must be 0.00.
- Verdict first: BOTH anchors deviate 0.00 on every value; pivots fingerprint as expected; NO DRIFT.

## 1. Repro commands (verbatim)

    .venv/bin/python research/sweep_beat_m07_k8.py --only base_M07
    .venv/bin/python research/sweep_beat_m07_k8.py --only g_bf07_winA30
    # full fields (incl six-window mdds) via same-caliber run_one from research/sweep_beat_m07_k8.py CFGS
    # base_M07: default M07 params calibration row
    # g_bf07_winA30: win_a=30 + by 0.05 + cut 0.78 legs + bx 0.15 + bf 0.7
    # pivots fingerprint via pandas read_pickle close shape and index ends

Note: sweep_beat_m07_k8.py natively supports --only (same pattern as k3 main argparse), so no k3-style reimplementation was needed. --only mode prints rows only and does not rewrite the json (write-back happens only when --only is None). Full fields incl mdd windows and switch/brake logs were additionally fetched via same-caliber run_one.

## 2. Anchor 1: base_M07 vs results/r30_bt/M07_final.json (also matches K8 base_M07 row)

Raw stdout (--only base_M07):
    tag=base_M07 total=1863.27 mdd=-27.05 trades=184 cost=50990.0 switches=3 brakes=3
    1m=-4.09 3m=17.28 6m=39.0 1y=164.05 2y=1474.08 3y=1677.53
    BASE calibration OK

| metric | archived (M07_final.json) | rerun | diff |
| total | 1863.27 | 1863.27 | 0.00 |
| mdd | -27.05 | -27.05 | 0.00 |
| trades | 184 | 184 | 0 |
| cost | 50990.0 | 50990.0 | 0.0 |
| mode and switches | B and 3 | B and 3 | match |
| switch_log | 2023-06-21 B; 2024-08-15 A; 2026-09-08 B | identical | match |
| brake_log 6 entries | 2023-06-26 ON 18.16; 2023-09-18 OFF 15.23; 2024-01-31 ON 19.7; 2024-05-23 OFF 10.04; 2024-06-21 ON 22.82; 2024-09-13 OFF 18.53 | identical | match |
| 1m and 1m_mdd | -4.09 and -8.53 | -4.09 and -8.53 | 0.00 and 0.00 |
| 3m and 3m_mdd | 17.28 and -10.15 | 17.28 and -10.15 | 0.00 and 0.00 |
| 6m and 6m_mdd | 39.00 and -11.94 | 39.00 and -11.94 | 0.00 and 0.00 |
| 1y and 1y_mdd | 164.05 and -12.96 | 164.05 and -12.96 | 0.00 and 0.00 |
| 2y and 2y_mdd | 1474.08 and -15.44 | 1474.08 and -15.44 | 0.00 and 0.00 |
| 3y and 3y_mdd | 1677.53 and -27.05 | 1677.53 and -27.05 | 0.00 and 0.00 |

Result: anchor 1 PASS; total, mdd and six windows (incl mdd windows) all diff 0.00; logs item-identical.

## 3. Anchor 2: g_bf07_winA30 vs results/r30_bt/sweep_beat_m07_k8.json row

Raw stdout (--only g_bf07_winA30):
    tag=g_bf07_winA30 total=2400.29 mdd=-24.17 trades=184 cost=64607.0 switches=3 brakes=2
    1m=-4.09 3m=17.25 6m=39.26 1y=164.4 2y=1480.3 3y=1870.56

| metric | archived (K8 row) | rerun | diff |
| total | 2400.29 | 2400.29 | 0.00 |
| mdd | -24.17 | -24.17 | 0.00 |
| trades | 184 | 184 | 0 |
| cost | 64607.0 | 64607.0 | 0.0 |
| mode switches brakes | B 3 2 | B 3 2 | match |
| switch_log | 2023-06-21 B; 2024-08-15 A; 2026-09-08 B | identical | match |
| brake_log 4 entries | 2024-01-31 ON 15.09; 2024-05-23 OFF 11.83; 2024-06-21 ON 19.0; 2024-08-16 OFF 6.29 | identical | match |
| 1m and 1m_mdd | -4.09 and -8.54 | -4.09 and -8.54 | 0.00 and 0.00 |
| 3m and 3m_mdd | 17.25 and -10.14 | 17.25 and -10.14 | 0.00 and 0.00 |
| 6m and 6m_mdd | 39.26 and -11.91 | 39.26 and -11.91 | 0.00 and 0.00 |
| 1y and 1y_mdd | 164.40 and -13.06 | 164.40 and -13.06 | 0.00 and 0.00 |
| 2y and 2y_mdd | 1480.30 and -15.52 | 1480.30 and -15.52 | 0.00 and 0.00 |
| 3y and 3y_mdd | 1870.56 and -24.17 | 1870.56 and -24.17 | 0.00 and 0.00 |

Result: anchor 2 PASS; total, mdd and six windows (incl mdd windows) all diff 0.00; logs item-identical.

## 4. Data drift fingerprint

| check | expected | observed | verdict |
| pivots close shape | (1662, 5030) | (1662, 5030) | match |
| close index end | 2026-11-12 (= EVAL_END) | 2026-11-12 00:00:00 | match, no drift |
| close index start extra | 2020-01-02 | 2020-01-02 00:00:00 | match |
| in-script asserts | RUN_START 2023-01-03; EVAL_END 2026-11-12 | no assert fired on either rerun | pass |

## 5. Drift conclusion

1. base_M07 vs M07_final.json: total, mdd and six windows (incl six mdd windows) diff all 0.00; switch and brake logs identical.
2. g_bf07_winA30 vs K8 row: total, mdd and six windows (incl six mdd windows) diff all 0.00; switch and brake logs identical.
3. pivots fingerprint (1662, 5030) with index end 2026-11-12 = EVAL_END; no data drift.
4. Only new files in this directory were added; no existing file was modified; --only reruns did not rewrite result jsons.

FINAL: 120-line evidence stays fresh; no invalidation.
