import sys, json
from pathlib import Path
ROOT=Path('.').resolve()
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'team'/'audit')); sys.path.insert(0,str(ROOT/'research'))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, RUN_START, EVAL_END, MB
import search_C_stage2 as S
print('loaded, running best tag...', flush=True)
o, eq = S.run_one('ROOT_check_grid_by01_bf05', rs=60, bx=0.15, by_=0.1, bf=0.5, hyst=0.0, mh=0, cf=1, evalfreq='grid', brake_daily=False)
print(json.dumps({k:o.get(k) for k in ['tag','total','mdd','2024','2024_yoy','2024_mdd','2025_yoy','2025_mdd','2026','2026_yoy','2026_mdd','trades','cost','switches','brakes','mode','margin','pass']}, ensure_ascii=False, indent=1))
# compare to filed row
filed=json.load(open('results/r30_bt/search_C_stage2.json'))
for r in filed:
    if r['tag']=='C2_grid_mh0_bx0.15_by0.1_bf0.5':
        print('FILED:', json.dumps({k:r.get(k) for k in ['total','mdd','2024','2024_yoy','2024_mdd','2025_yoy','2026_yoy','trades','cost','switches']}, ensure_ascii=False))
        break
print('ROOT check done')
