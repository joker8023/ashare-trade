"""STAR×MAX第二曲线: s02复现(rs60/90/120) + 与J04的50/50组合.
 s02 = A腿MB + B腿STAR, 双腿MAX80, 其余同J04.
 组合: 月度再平衡到50/50 vs 静态平均, 对比J04六窗.
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

def run_s02(rs):
    inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=0.80, max_win=40)
    CA = dict(factor='amihud_60', stop=0.25, stop_exec='next', exclude=MB, capital=50000.0,
              lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
              eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CB = dict(CA); CB['exclude'] = STAR
    CFG_B = dict(n=5, rebal=30, take=0.80, exposure=0.9)
    ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CB, **CFG_B})
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B,
              shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=STAR,
              **{k: v for k, v in CA.items() if k != 'exclude'})
    ns = build_ns(0.18, 0.08, 0.6)
    res = ns['run_strategy_switch'](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    return eq.dropna(), res

def stats(eq):
    eq = eq.dropna()
    out = {'total': round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
           'mdd': round(float((eq / eq.cummax() - 1).min()) * 100, 2)}
    for w, d in WINDOWS.items():
        sub = eq.tail(d + 1)
        out[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
        out[w + '_mdd'] = round(float((sub / sub.cummax() - 1).min()) * 100, 2)
    return out

eq_j04 = pd.read_pickle(ROOT / 'results' / 'r30_bt' / 'J04_equity.pkl').dropna()
out = {'J04': stats(eq_j04)}
eqs = {}
for rs in (60, 90, 120):
    eq, res = run_s02(rs)
    eqs[rs] = eq
    eq.to_pickle(ROOT / f'results/r30_bt/star_s02_rs{rs}_equity.pkl')
    out[f's02_rs{rs}'] = {**stats(eq), 'trades': len(res.trades),
                          'cost': round(float(res.meta['total_cost']), 0),
                          'switches': len(res.meta['switch_log']),
                          'mode': res.meta['final_mode']}
    print(f'rs={rs} done', flush=True)

# 组合: 静态平均 + 月度再平衡50/50 (用rs60)
eq_s = eqs[60].reindex(eq_j04.index).ffill().dropna()
eq_j = eq_j04.loc[eq_s.index]
static = (eq_j / eq_j.iloc[0] + eq_s / eq_s.iloc[0]) / 2 * 50000
out['combo_static'] = stats(static)
# 月度再平衡: 每月末重置权重50/50
rej = eq_j.resample('ME').last(); res_ = eq_s.resample('ME').last()
months = rej.index.intersection(res_.index)
w = pd.Series(0.5, index=eq_j.index)
combo = pd.Series(index=eq_j.index, dtype=float)
cap = 50000.0; sj = eq_j.iloc[0]; ss = eq_s.iloc[0]; nj = cap / 2 / sj; ns_ = cap / 2 / ss
cur_m = None
for i, d in enumerate(eq_j.index):
    combo.loc[d] = nj * eq_j.loc[d] + ns_ * eq_s.loc[d]
    m = d.strftime('%Y-%m')
    if cur_m is None:
        cur_m = m
    if m != cur_m or i == len(eq_j) - 1:
        tot = combo.loc[d]; nj = tot / 2 / eq_j.loc[d]; ns_ = tot / 2 / eq_s.loc[d]
        cur_m = m
out['combo_monthly'] = stats(combo)
combo.to_pickle(ROOT / 'results' / 'r30_bt' / 'combo_j04_s02_equity.pkl')
open(ROOT / 'results' / 'r30_bt' / 'star_combo.json', 'w').write(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out, ensure_ascii=False, indent=1))
print('saved star_combo', flush=True)
