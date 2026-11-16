#!/usr/bin/env python3
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'team' / 'audit'))
sys.path.insert(0, str(ROOT / 'research'))
import sweep_beat_m07_k11 as S
out = {}
try:
    S.trailing_check()
    out['trailing_check'] = 'ALL OK'
except SystemExit as e:
    out['trailing_check'] = 'FAILED code=' + str(e.code)
except Exception as e:
    out['trailing_check'] = 'ERROR ' + type(e).__name__ + ': ' + str(e)
r = S.run_one('k11_h05_B', 'repro-audit', 'B', 0.05)
ref = [x for x in json.load(open(ROOT / 'results' / 'r30_bt' / 'sweep_beat_m07_k11.json')) if x['tag'] == 'k11_h05_B'][0]
keys = ['total', 'mdd', 'trades', 'cost', 'mode', 'switches', 'brakes', '1m', '3m', '6m', '1y', '2y', '3y', 'nbeat_m07', 'beat_all', 'mdd_better', 'win_all']
mis = {}
for k in keys:
    if r.get(k) != ref.get(k):
        mis[k] = [r.get(k), ref.get(k)]
out['repro_mismatch'] = mis
out['repro_switchlog_eq'] = (r.get('switch_log') == ref.get('switch_log'))
out['repro_brakelog_eq'] = (r.get('brake_log') == ref.get('brake_log'))
out['repro_all_zero'] = (len(mis) == 0 and out['repro_switchlog_eq'] and out['repro_brakelog_eq'])
open(ROOT / 'team' / 'audit' / 'batch_033_m07k11' / 'part_033_repro.json', 'w').write(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out, ensure_ascii=False, indent=1))
