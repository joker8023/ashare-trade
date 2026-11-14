"""Final validation: champion candidates x phases + concentration + yearly."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'team'/'audit')); sys.path.insert(0, str(ROOT/'research'))
import pandas as pd
import prior_check as pc
from design_r30_grid8 import X3Inputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB, BASE_W

def run_one(piv, first_sig, cfg):
    PH = cfg.get('phase', 0)
    stop = cfg.get('stop', 0.25)
    inp_a = X3Inputs(piv, gate60=-0.15)
    inp_b = pc.Inputs(piv)
    CA = dict(factor='amihud_60', stop=stop, stop_exec='next', exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=cfg.get('b_n', 5), rebal=30, take=cfg.get('b_take', 0.80), exposure=0.9)
    ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=PH, **CA)
    rb = pc.run_strategy(inp_b, phase=PH, **{**CA, **CFG_B})
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=PH, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, exclude_a=MB, exclude_b=MB, **{k: v for k, v in CA.items() if k != 'exclude'})
    ns = build_ns(cfg.get('bx', 0.18), cfg.get('by', 0.08), cfg.get('bf', 0.5))
    res = ns['run_strategy_switch'](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    eq = eq.dropna()
    out = {'total': round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), 'mdd': round(_mdd(eq)*100,2), 'trades': len(res.trades), 'cost': round(float(res.meta['total_cost']),0), 'mode': res.meta['final_mode'], 'switches': len(res.meta['switch_log'])}
    for w, d in WINDOWS.items():
        sub = eq.tail(d+1)
        out[w] = round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
    out['gap'] = round(out['3y']-out['2y'],2)
    out['nbeat'] = sum(1 for w in WINDOWS if out[w] > BASE_W[w])
    tr = res.trades
    if len(tr) > 0:
        pnl = tr['net_pnl'].fillna(0)
        top3 = pnl.nlargest(3).sum()
        out['top3_share'] = round(float(top3 / pnl.sum())*100, 1) if pnl.sum() != 0 else None
        out['extop3_total'] = round(float((eq.iloc[0] + pnl.sum() - top3)/eq.iloc[0]-1)*100, 2)
    yrs = {}
    for y in [2023, 2024, 2025, 2026]:
        m = eq[eq.index.year == y]
        if len(m) > 1:
            yrs[str(y)] = round(float(m.iloc[-1]/m.iloc[0]-1)*100, 2)
    out['years'] = yrs
    return out

def main():
    piv = pd.read_pickle(ROOT/'data'/'pivots_2020_clean.pkl')
    dates = piv['close'].index
    grid_dates = [dates[i] for i in range(300, len(dates), 30)]
    first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
    base_u08 = dict(stop=0.25, b_n=5, b_take=0.80, bf=0.6)
    base_u09 = dict(stop=0.25, b_n=5, b_take=0.80, bf=0.7)
    base_u01 = dict(stop=0.25, b_n=5, b_take=0.80, bf=0.5)
    base_tb = dict()
    configs = []
    for ph in [0, 10]:
        configs.append(dict(base_u08, tag='u08_ph%d' % ph, phase=ph))
        configs.append(dict(base_u09, tag='u09_ph%d' % ph, phase=ph))
        configs.append(dict(base_u01, tag='u01_ph%d' % ph, phase=ph))
        tb = dict(tag='TB18_ph%d' % ph, phase=ph, stop=None, b_n=4, b_take=0.45, bf=0.5)
        configs.append(tb)
    rows = []
    for cfg in configs:
        try:
            r = run_one(piv, first_sig, cfg)
            r['tag'] = cfg['tag']
            print(json.dumps(r, ensure_ascii=False), flush=True)
            rows.append(r)
        except Exception as e:
            print('FAIL %s: %s' % (cfg['tag'], e), flush=True)
            import traceback; traceback.print_exc()
    open(ROOT/'results'/'r30_bt'/'final_validation.json', 'w').write(json.dumps(rows, ensure_ascii=False, indent=1))
    print('saved %d rows' % len(rows), flush=True)

if __name__ == '__main__':
    main()