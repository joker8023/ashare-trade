"""Fresh-6: (a) J04 phases ph5/ph15; (b) Donchian-breakout single-engine check.
Donchian cross-sectional: pool(X3 gate) + close>=trailing-20d high, rank Amihud.
Uses close-only (no high/low needed): breakout = close >= rolling(20).max().shift(1)."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'team'/'audit')); sys.path.insert(0, str(ROOT/'research'))
import pandas as pd
import prior_check as pc
from design_r30_grid8 import X3Inputs
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB, BASE_W
class DonchianInputs(X3Inputs):
    def __init__(self, piv, band=(0.05, 0.30), gate60=-0.15, min_adv=5e6, entry_n=20):
        super().__init__(piv, band=band, gate60=gate60, min_adv=min_adv)
        self.hi = self.close.rolling(entry_n, min_periods=entry_n).max().shift(1)
    def picks(self, t, n, size_range=None, min_adv=None, exclude=(), factor='amihud_60'):
        base = super().picks(t, 9999, size_range=size_range, min_adv=min_adv, exclude=exclude, factor=factor)
        if not base:
            return []
        c = self.close.loc[t, base]; h = self.hi.loc[t, base]
        brk = [x for x in base if pd.notna(c[x]) and pd.notna(h[x]) and c[x] >= h[x]]
        if len(brk) < n:
            return brk
        fac = self.amihud60 if factor == 'amihud_60' else self.amihud
        return list(fac.loc[t, brk].dropna().sort_values(ascending=False).head(n).index)
def run_switch(piv, first_sig, cfg):
    PH = cfg.get('phase', 0)
    inp_a = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
    inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=0.80, max_win=40)
    CA = dict(factor='amihud_60', stop=0.25, stop_exec='next', exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=5, rebal=30, take=0.80, exposure=0.9)
    ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=PH, **CA)
    rb = pc.run_strategy(inp_b, phase=PH, **{**CA, **CFG_B})
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=PH, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, exclude_a=MB, exclude_b=MB, **{k: v for k, v in CA.items() if k != 'exclude'})
    ns = build_ns(0.18, 0.08, 0.6)
    res = ns['run_strategy_switch'](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    return eq.dropna(), res
def run_single(piv, first_sig, cfg):
    inp = DonchianInputs(piv, entry_n=cfg.get('entry_n', 20))
    CA = dict(factor='amihud_60', stop=cfg.get('stop'), stop_exec='next', exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    res = pc.run_strategy(inp, n=cfg.get('n', 4), rebal=30, take=None, exposure=1.0, phase=0, **CA)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    return eq.dropna(), res
def metrics(eq, res, tag):
    out = {'tag': tag, 'total': round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), 'mdd': round(_mdd(eq)*100,2), 'trades': len(res.trades), 'cost': round(float(res.meta['total_cost']),0)}
    if 'final_mode' in res.meta:
        out['mode'] = res.meta['final_mode']; out['switches'] = len(res.meta['switch_log'])
    for w, d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
    out['gap'] = round(out['3y']-out['2y'],2)
    out['nbeat'] = sum(1 for w in WINDOWS if out[w] > BASE_W[w])
    return out
def main():
    piv = pd.read_pickle(ROOT/'data'/'pivots_2020_clean.pkl')
    dates = piv['close'].index
    grid_dates = [dates[i] for i in range(300, len(dates), 30)]
    first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
    rows = []
    for cfg in [dict(tag='j04_ph5', phase=5), dict(tag='j04_ph15', phase=15)]:
        eq, res = run_switch(piv, first_sig, cfg)
        r = metrics(eq, res, cfg['tag'])
        print(json.dumps(r, ensure_ascii=False), flush=True)
        rows.append(r)
    for cfg in [dict(tag='d01_donch20_N4', entry_n=20, n=4, stop=None), dict(tag='d02_donch20_N4_stop25', entry_n=20, n=4, stop=0.25), dict(tag='d03_donch55_N4_stop25', entry_n=55, n=4, stop=0.25)]:
        eq, res = run_single(piv, first_sig, cfg)
        r = metrics(eq, res, cfg['tag'])
        print(json.dumps(r, ensure_ascii=False), flush=True)
        rows.append(r)
    open(ROOT/'results'/'r30_bt'/'fresh6_mixed.json', 'w').write(json.dumps(rows, ensure_ascii=False, indent=1))
    print('saved %d rows' % len(rows), flush=True)
if __name__ == '__main__':
    main()