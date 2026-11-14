"""U8 champion official record: stop25 + B-N5 + Btake80 + bf06 + RS60 + brakeX18/Y08.
Reproduces u08 (sweep v12): total +1623.00 / -27.75, 195 trades, cost 47480.
"""
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
cfg = dict(tag='U8', phase=0, stop=0.25, b_n=5, b_take=0.80, bf=0.6)
r = run_one(piv, first_sig, cfg)
print(json.dumps(r, ensure_ascii=False, indent=1))
open(ROOT/'results'/'r30_bt'/'U8_final.json', 'w').write(json.dumps(r, ensure_ascii=False, indent=1))
print('saved U8_final.json')
