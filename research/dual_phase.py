"""双相位袖验证: J04配置分别跑phase0/phase15, 各半仓合并, 对比J04 ph0六窗.
 配置与run_j04_final逐字一致, 仅phase不同.
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'team' / 'audit')); sys.path.insert(0, str(ROOT / 'research'))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, WINDOWS, RUN_START, EVAL_END, MB

piv = pd.read_pickle(ROOT / 'data' / 'pivots_2020_clean.pkl')
dates = piv['close'].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))

def run_phase(ph):
    inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=0.80, max_win=40)
    CA = dict(factor='amihud_60', stop=0.25, stop_exec='next', exclude=MB, capital=50000.0,
              lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
              eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=5, rebal=30, take=0.80, exposure=0.9)
    ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=ph, **CA)
    rb = pc.run_strategy(inp_b, phase=ph, **{**CA, **CFG_B})
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=ph, inp_b=inp_b, cfg_b=CFG_B,
              shadow_a=ra.eq, shadow_b=rb.eq, exclude_a=MB, exclude_b=MB,
              **{k: v for k, v in CA.items() if k != 'exclude'})
    ns = build_ns(0.18, 0.08, 0.6)
    res = ns['run_strategy_switch'](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    return eq.dropna(), res

def stats(eq):
    eq = eq.dropna()
    out = {'total': round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
           'mdd': round(float((eq / eq.cummax() - 1).min()) * 100, 2),
           'start': str(eq.index[0].date()), 'end': str(eq.index[-1].date())}
    for w, d in WINDOWS.items():
        sub = eq.tail(d + 1)
        out[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
        out[w + '_mdd'] = round(float((sub / sub.cummax() - 1).min()) * 100, 2)
    return out

eq0, r0 = run_phase(0)
print('ph0 done', flush=True)
eq15, r15 = run_phase(15)
print('ph15 done', flush=True)
sleeve = (eq0 + eq15) / 2
eq0.to_pickle(ROOT / 'results' / 'r30_bt' / 'dual_ph0_equity.pkl')
eq15.to_pickle(ROOT / 'results' / 'r30_bt' / 'dual_ph15_equity.pkl')
sleeve.to_pickle(ROOT / 'results' / 'r30_bt' / 'dual_sleeve_equity.pkl')
res = {'ph0': stats(eq0), 'ph15': stats(eq15), 'sleeve': stats(sleeve),
       'trades_ph0': len(r0.trades), 'trades_ph15': len(r15.trades)}
open(ROOT / 'results' / 'r30_bt' / 'dual_phase.json', 'w').write(json.dumps(res, ensure_ascii=False, indent=1))
print(json.dumps(res, ensure_ascii=False, indent=1))
print('saved dual_phase', flush=True)
