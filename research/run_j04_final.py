"""J04 champion official record: U8 + MAX40-cut80 on both legs. Reproduces fresh4 j04."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'team'/'audit')); sys.path.insert(0, str(ROOT/'research'))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
piv = pd.read_pickle(ROOT/'data'/'pivots_2020_clean.pkl')
dates = piv['close'].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=0.80, max_win=40)
CA = dict(factor='amihud_60', stop=0.25, stop_exec='next', exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
CFG_B = dict(n=5, rebal=30, take=0.80, exposure=0.9)
ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, exclude_a=MB, exclude_b=MB, **{k: v for k, v in CA.items() if k != 'exclude'})
ns = build_ns(0.18, 0.08, 0.6)
res = ns['run_strategy_switch'](inp_a, lock_mode=None, **KW)
eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
eq = eq.dropna()
eq.to_pickle(ROOT/'results'/'r30_bt'/'J04_equity.pkl')
out = {'strategy': 'J04 = U8 + MAX40-cut80 both legs', 'total': round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), 'mdd': round(_mdd(eq)*100,2), 'trades': len(res.trades), 'cost': round(float(res.meta['total_cost']),0), 'mode': res.meta['final_mode'], 'switches': len(res.meta['switch_log']), 'switch_log': [list(x) for x in res.meta['switch_log']], 'brake_log': [list(x) for x in res.meta.get('brake_log', [])]}
for w, d in WINDOWS.items():
    sub = eq.tail(d+1)
    out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
    out[w+'_mdd'] = round(_mdd(sub)*100,2)
tr = res.trades
pnl = tr['net_pnl'].fillna(0)
top3 = pnl.nlargest(3).sum()
out['top3_share'] = round(float(top3/pnl.sum())*100, 1)
out['extop3_total'] = round(float((eq.iloc[0]+pnl.sum()-top3)/eq.iloc[0]-1)*100, 2)
print(json.dumps(out, ensure_ascii=False, indent=1))
open(ROOT/'results'/'r30_bt'/'J04_final.json', 'w').write(json.dumps(out, ensure_ascii=False, indent=1))
print('saved J04_final.json + J04_equity.pkl')