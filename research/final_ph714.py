import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'team'/'audit')); sys.path.insert(0, str(ROOT/'research'))
import pandas as pd
from final_validation import run_one
from sweep_beat_h1_v4 import RUN_START
piv = pd.read_pickle(ROOT/'data'/'pivots_2020_clean.pkl')
dates = piv['close'].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
cfgs = [
    dict(tag='u08_ph7', phase=7, stop=0.25, b_n=5, b_take=0.80, bf=0.6),
    dict(tag='u08_ph14', phase=14, stop=0.25, b_n=5, b_take=0.80, bf=0.6),
    dict(tag='u09_ph7', phase=7, stop=0.25, b_n=5, b_take=0.80, bf=0.7),
    dict(tag='u09_ph14', phase=14, stop=0.25, b_n=5, b_take=0.80, bf=0.7),
]
rows = []
for cfg in cfgs:
    r = run_one(piv, first_sig, cfg)
    r['tag'] = cfg['tag']
    print(json.dumps({k: r[k] for k in ['tag','total','mdd','trades','cost','mode','switches','1m','3m','6m','1y','2y','3y','gap','nbeat','top3_share','extop3_total']}, ensure_ascii=False), flush=True)
    rows.append(r)
open(ROOT/'results'/'r30_bt'/'final_ph714.json', 'w').write(json.dumps(rows, ensure_ascii=False, indent=1))
print('saved', flush=True)