"""Fresh-3: U8 switch + MAX lottery filter on A/B legs."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'team'/'audit')); sys.path.insert(0, str(ROOT/'research'))
import pandas as pd
import prior_check as pc
from design_r30_grid8 import X3Inputs
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB, BASE_W
def run_one(piv, first_sig, cfg):
    cls_a = MaxInputs if cfg.get('max_a') else X3Inputs
    kw_a = dict(band=(0.02, 0.30), gate60=-0.15, max_cut=cfg.get('cut', 0.90)) if cfg.get('max_a') else dict()
    if cfg.get('max_b'):
        inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=cfg.get('cut', 0.90))
    else:
        inp_b = pc.Inputs(piv)
    inp_a = cls_a(piv, **kw_a) if cfg.get('max_a') else X3Inputs(piv, gate60=-0.15)
    CA = dict(factor='amihud_60', stop=0.25, stop_exec='next', exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=5, rebal=30, take=0.80, exposure=0.9)
    ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, exclude_a=MB, exclude_b=MB, **{k: v for k, v in CA.items() if k != 'exclude'})
    ns = build_ns(0.18, 0.08, 0.6)
    res = ns['run_strategy_switch'](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {'tag': cfg['tag'], 'total': round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), 'mdd': round(_mdd(eq)*100,2), 'trades': len(res.trades), 'cost': round(float(res.meta['total_cost']),0), 'mode': res.meta['final_mode'], 'switches': len(res.meta['switch_log'])}
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
    cfgs = [
        dict(tag='h01_MAX_Aonly', max_a=True),
        dict(tag='h02_MAX_Bonly', max_b=True),
        dict(tag='h03_MAX_both', max_a=True, max_b=True),
        dict(tag='h04_MAX20_both', max_a=True, max_b=True, cut=0.80),
    ]
    rows = []
    for cfg in cfgs:
        try:
            r = run_one(piv, first_sig, cfg)
            print(json.dumps(r, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print('FAIL %s: %s' % (cfg['tag'], e), flush=True)
            import traceback; traceback.print_exc()
    open(ROOT/'results'/'r30_bt'/'fresh3_uswitch.json', 'w').write(json.dumps(rows, ensure_ascii=False, indent=1))
    print('saved %d rows' % len(rows), flush=True)
if __name__ == '__main__':
    main()