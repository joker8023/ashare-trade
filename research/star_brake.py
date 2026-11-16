"""s02刹车网格: shadows只算一次, 切换跑bx/bf组合. s02 = A(MB)+B(STAR), RS90.
 目标: 保住近窗(1m/3m/6m/1y>=J04), 抬2y/3y, 压mdd.
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'team' / 'audit')); sys.path.insert(0, str(ROOT / 'research'))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
STAR = ('300', '301', '8', '4')

piv = pd.read_pickle(ROOT / 'data' / 'pivots_2020_clean.pkl')
dates = piv['close'].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))

inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=0.80, max_win=40)
CA = dict(factor='amihud_60', stop=0.25, stop_exec='next', exclude=MB, capital=50000.0,
          lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
          eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
CB = dict(CA); CB['exclude'] = STAR
CFG_B = dict(n=5, rebal=30, take=0.80, exposure=0.9)
ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
rb = pc.run_strategy(inp_b, phase=0, **{**CB, **CFG_B})
print('shadows done', flush=True)

def stats(eq):
    eq = eq.dropna()
    out = {'total': round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
           'mdd': round(float((eq / eq.cummax() - 1).min()) * 100, 2)}
    for w, d in WINDOWS.items():
        sub = eq.tail(d + 1)
        out[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
        out[w + '_mdd'] = round(float((sub / sub.cummax() - 1).min()) * 100, 2)
    return out

out = {}
for bx, bf in [(0.18, 0.6), (0.15, 0.6), (0.12, 0.6), (0.15, 0.5), (0.12, 0.5), (0.12, 0.3)]:
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B,
              shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=90, exclude_a=MB, exclude_b=STAR,
              **{k: v for k, v in CA.items() if k != 'exclude'})
    ns = build_ns(bx, 0.08, bf)
    res = ns['run_strategy_switch'](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    tag = f'bx{bx}_bf{bf}'
    eq.to_pickle(ROOT / f'results/r30_bt/star_brake_{tag}_equity.pkl')
    out[tag] = {**stats(eq), 'trades': len(res.trades),
                'cost': round(float(res.meta['total_cost']), 0),
                'switches': len(res.meta['switch_log']),
                'brakes': len(res.meta.get('brake_log', [])) // 2}
    print(tag, 'done', flush=True)
open(ROOT / 'results' / 'r30_bt' / 'star_brake.json', 'w').write(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out, ensure_ascii=False, indent=1))
print('saved star_brake', flush=True)
