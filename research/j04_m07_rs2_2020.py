import sys, json, gc
from pathlib import Path
ROOT = Path('.').resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'team' / 'audit'))
sys.path.insert(0, str(ROOT / 'research'))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, EVAL_END, MB
piv = pd.read_pickle(ROOT / 'data' / 'pivots_2020_clean_realshares_v2.pkl')
dates = piv['close'].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
RUN_START = str(dates[0].date())
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
print(f'RUN_START={RUN_START} first_sig={first_sig.date()} EVAL_END={EVAL_END}', flush=True)
CA = dict(factor='amihud_60', stop=0.25, stop_exec='next', exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
def run_cfg(tag, a_win, b_win, b_n):
    inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=a_win)
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=0.80, max_win=b_win)
    CFG_B = dict(n=b_n, rebal=30, take=0.80, exposure=0.9)
    ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
    print(f'{tag} shadows done atr={len(ra.trades)} btr={len(rb.trades)}', flush=True)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, exclude_a=MB, exclude_b=MB, **{k: v for k, v in CA.items() if k != 'exclude'})
    ns = build_ns(0.18, 0.08, 0.6)
    res = ns['run_strategy_switch'](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    eq.to_pickle(ROOT / 'results' / 'r30_bt' / (tag + '_rs2_2020_equity.pkl'))
    print(f'{tag} eq {eq.index[0].date()} -> {eq.index[-1].date()} n={len(eq)}', flush=True)
    del ra, rb, ns
    gc.collect()
    return eq, res
def yearly(eq):
    d = {}
    for y in [2021, 2022, 2023, 2024, 2025, 2026]:
        sub = eq[eq.index.year == y]
        if len(sub) > 1:
            d[str(y)] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
            d[str(y) + '_mdd'] = round(float(_mdd(sub)) * 100, 2)
            d[str(y) + '_bars'] = int(len(sub))
    return d
def trailing(eq):
    d = {}
    for w, b in WINDOWS.items():
        sub = eq.tail(b + 1)
        d[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
        d[w + '_mdd'] = round(float(_mdd(sub)) * 100, 2)
        d[w + '_start'] = str(sub.index[0].date())
        d[w + '_bars'] = int(len(sub))
    return d
rows = []
for tag, a_win, b_win, b_n in [('J04', 40, 40, 5), ('M07', 40, 20, 4)]:
    eq, res = run_cfg(tag, a_win, b_win, b_n)
    out = dict(tag=tag, start=str(eq.index[0].date()), end=str(eq.index[-1].date()), nbars=int(len(eq)))
    out['total'] = round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2)
    out['full_mdd'] = round(float(_mdd(eq)) * 100, 2)
    out['trades'] = int(len(res.trades))
    out['cost'] = round(float(res.meta['total_cost']), 0)
    out['mode'] = res.meta['final_mode']
    out['switches'] = len(res.meta['switch_log'])
    out.update(yearly(eq))
    out.update(trailing(eq))
    print(json.dumps(out, ensure_ascii=False, indent=1), flush=True)
    rows.append(out)
    del eq, res
    gc.collect()
open(ROOT / 'results' / 'r30_bt' / 'j04_m07_rs2_2020.json', 'w').write(json.dumps(rows, ensure_ascii=False, indent=1))
print('saved j04_m07_rs2_2020.json', flush=True)