#!/usr/bin/env python3
"""Route C stage2: 以B_R15_N5为B影子 + M07-A为A影子, 切换吃A腿2026红利、保住B腿2024.

影子定义(与search_B_stage1单腿口径一致, 真股本realshares_v2):
  A腿: MaxInputs(band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=40), N=5/R20/take=1.2/stop=0.25/exp=1.0
  B腿: MaxInputs(band=(0.02,0.30), gate60=-0.15, max_cut=0.80, max_win=20), N=5/R15/take=0.45/stop=0.25/exp=1.0
  公共: RUN_START=2023-01-03, EVAL_END=2026-11-12, 本金5万, 现实费率+slip=0.002, 整手100,
        long-only全清, 敞口<=1, 信号t收盘/执行t+1收盘, 判定只用t及以前影子RS.
切换: grid(A网格日, hyst=0) 或 daily(逐日, hyst带), rs_lookback=60, min_hold 0/10, confirm=1/2/3.
 确认语义: min_hold持有期内不累积确认, 确认只计持有期满后的连续信号(已修P0-1).
 switch_log记录的是切换后新mode(先mode=desired后append), 与parity口径一致.
刹车: 自身权益回撤bx触发 -> 新开仓降至bf; 反弹by解除. brake_daily逐日或仅调仓日评估.
注意: bf必须>0 (bf=0+全清会导致触发后永久空仓死锁, 已在stage1验证). 本sweep只用bf 0.5-0.7.
目标: 2024slice>60且2024_yoy>60, 2025_yoy>60, 2026_yoy>60(截至11-12注明), 全程与每年mdd>-30.
用法: .venv/bin/python research/search_C_stage2.py  (全sweep, 输出results/r30_bt/search_C_stage2.json)
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'team' / 'audit'))
sys.path.insert(0, str(ROOT / 'research'))
import pandas as pd
import numpy as np
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, RUN_START, EVAL_END, MB

from switch_ns import build_ns  # single implementation (was local copy)


piv = pd.read_pickle(ROOT / 'data' / 'pivots_2020_clean_realshares_v2.pkl')
dates = piv['close'].index
grid30 = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid30 if d >= pd.Timestamp(RUN_START))
print('RUN ' + str(RUN_START) + ' EVAL_END=' + str(EVAL_END) + ' first_sig=' + str(first_sig), flush=True)

inpA = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=40)
inpB = MaxInputs(piv, band=(0.02, 0.30), gate60=-0.15, max_cut=0.80, max_win=20)
CA = dict(factor='amihud_60', stop=0.25, stop_exec='next', exclude=MB, capital=50000.0,
          lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
          eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
CFG_B = dict(n=5, rebal=15, take=0.45, exposure=1.0)
print('building shadows A(R20/take1.2) + B(R15/take0.45)...', flush=True)
ra = pc.run_strategy(inpA, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
rb = pc.run_strategy(inpB, phase=0, **dict(CA, **CFG_B))
eqB0 = (rb.eq.iloc[:, 0] if isinstance(rb.eq, pd.DataFrame) else rb.eq).dropna()
print('shadows ready A trades=%d B trades=%d' % (len(ra.trades), len(rb.trades)), flush=True)

def annual_out(eq, res, tag, cfg):
    eq = eq.dropna()
    rets = eq.pct_change().dropna()
    shr = float(rets.mean() / rets.std() * (252 ** 0.5)) if float(rets.std()) > 0 else 0.0
    tot = float(eq.iloc[-1] / eq.iloc[0] - 1) * 100
    md = _mdd(eq) * 100
    out = {'tag': tag, 'cfg': cfg, 'eq_len': int(len(eq)),
           'eq_start': str(eq.index[0].date()), 'eq_end': str(eq.index[-1].date()),
           'total': round(tot, 2), 'mdd': round(md, 2),
           'calmar': round(tot / abs(md), 3) if md != 0 else None,
           'sharpe': round(shr, 3), 'trades': int(len(res.trades)),
           'cost': round(float(res.meta['total_cost']), 0),
           'mode': res.meta['final_mode'], 'switches': len(res.meta['switch_log']),
           'switch_log': [list(x) for x in res.meta['switch_log']],
           'brakes': len(res.meta.get('brake_log', [])) // 2,
           'brake_log': [list(x) for x in res.meta.get('brake_log', [])],
           'avg_exp': round(float(res.exposure.mean()), 4) if res.exposure is not None else None,
           'max_exp': round(float(res.exposure.max()), 4) if res.exposure is not None else None}
    prev_end = None
    yy = [2023, 2024, 2025, 2026]
    for y in yy:
        sub = eq[eq.index.year == y]
        if len(sub) == 0:
            out[str(y)] = None
            continue
        sret = float(sub.iloc[-1] / sub.iloc[0] - 1) * 100
        out[str(y)] = round(sret, 2)
        out[str(y) + '_mdd'] = round(_mdd(sub) * 100, 2)
        out[str(y) + '_bars'] = int(len(sub))
        out[str(y) + '_thin'] = bool(len(sub) < 20)  # 数据缺失年份标脏, yoy可能跨年错位(2023_yoy为年内口径, 仅参考)
        out[str(y) + '_yoy'] = round((float(sub.iloc[-1] / prev_end - 1) * 100) if prev_end is not None else sret, 2)
        prev_end = float(sub.iloc[-1])
    okpass = out['2024'] is not None and out['2024'] > 60 and out['2024_yoy'] > 60
    okpass = okpass and out['2025_yoy'] > 60 and out['2026_yoy'] > 60
    okpass = okpass and out['mdd'] > -30 and out['2024_mdd'] > -30
    okpass = okpass and out['2025_mdd'] > -30 and out['2026_mdd'] > -30
    out['pass'] = bool(okpass)
    out['margin'] = round(min(out['2024'] - 60, out['2024_yoy'] - 60, out['2025_yoy'] - 60, out['2026_yoy'] - 60, out['mdd'] + 30, out['2024_mdd'] + 30, out['2025_mdd'] + 30, out['2026_mdd'] + 30), 2)
    pe = float(eq.iloc[-1] - eq.iloc[0])
    out['cost_eff'] = round(pe / float(res.meta['total_cost']), 2) if float(res.meta['total_cost']) > 0 else None
    return out

SLIM = ('tag', 'total', 'mdd', 'calmar', 'sharpe', '2024', '2024_yoy', '2024_mdd',
        '2025_yoy', '2025_mdd', '2026_yoy', '2026_mdd', 'trades', 'cost', 'cost_eff',
        'switches', 'brakes', 'mode', 'avg_exp', 'max_exp', 'pass', 'margin')

_ns = {}
def get_ns(bx, by_, bf, hyst, mh, cf):
    k = (bx, by_, bf, hyst, mh, cf)
    if k not in _ns:
        _ns[k] = build_ns(bx, by_, bf, hyst, mh, cf)
    return _ns[k]

def run_one(tag, rs=60, bx=0.18, by_=0.08, bf=0.6, hyst=0.0, mh=0, cf=1, evalfreq='grid', brake_daily=False, lock=None):
    # P2-2: exclude_a/b 要么都设要么都不设, 否则未设的一腿等于不过滤, 口径不对称
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inpB, cfg_b=CFG_B,
              shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB,
              evalfreq=evalfreq, brake_daily=brake_daily)
    assert (KW['exclude_a'] is None) == (KW['exclude_b'] is None), 'exclude_a/b must be both set or both None'
    for k, v in CA.items():
        if k != 'exclude':
            KW[k] = v
    ns = get_ns(bx, by_, bf, hyst, mh, cf)
    res = ns['run_strategy_switch'](inpA, lock_mode=lock, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    cfg = dict(rs=rs, bx=bx, by_=by_, bf=bf, hyst=hyst, min_hold=mh, confirm=cf, evalfreq=evalfreq, brake_daily=brake_daily, lock=lock)
    return annual_out(eq, res, tag, cfg), eq

def main():
    rows = []
    refB, eB = run_one('REF_lockB_R15_nobrake', bx=0.90, by_=0.50, bf=1.0, evalfreq='grid', lock='B')
    direct_tot = float(eqB0.iloc[-1] / eqB0.iloc[0] - 1) * 100
    print('PARITY lockB-nobrake total %.2f vs direct %.2f | mdd %.2f vs %.2f | trades %d vs %d' % (refB['total'], direct_tot, refB['mdd'], _mdd(eqB0) * 100, refB['trades'], len(rb.trades)), flush=True)
    print(json.dumps({k: refB[k] for k in SLIM}, ensure_ascii=False), flush=True)
    rows.append(refB)
    refB2, eB2 = run_one('REF_lockB_R15_bx015_by005_bf06', bx=0.15, by_=0.05, bf=0.6, evalfreq='grid', lock='B')
    print(json.dumps({k: refB2[k] for k in SLIM}, ensure_ascii=False), flush=True)
    rows.append(refB2)
    brakes = [(0.15, 0.05, 0.5), (0.15, 0.05, 0.7), (0.15, 0.10, 0.5), (0.15, 0.10, 0.7), (0.22, 0.05, 0.5), (0.22, 0.05, 0.7), (0.22, 0.10, 0.5), (0.22, 0.10, 0.7)]
    for b in brakes:
        bx, by_, bf = b
        for mh in [0, 10]:
            tag = 'C2_grid_mh%d_bx%s_by%s_bf%s' % (mh, bx, by_, bf)
            o, e = run_one(tag, bx=bx, by_=by_, bf=bf, mh=mh, evalfreq='grid', brake_daily=False)
            print(json.dumps({k: o[k] for k in SLIM}, ensure_ascii=False), flush=True)
            rows.append(o)
        for h in [0.02, 0.03, 0.05]:
            for mh in [0, 10]:
                for bd in [False, True]:
                    for cf in [1, 2, 3]:
                        tag = 'C2_daily_h%s_mh%d_cf%d_bx%s_by%s_bf%s_%s' % (h, mh, cf, bx, by_, bf, 'bd' if bd else 'bg')
                        o, e = run_one(tag, bx=bx, by_=by_, bf=bf, hyst=h, mh=mh, cf=cf, evalfreq='daily', brake_daily=bd)
                        print(json.dumps({k: o[k] for k in SLIM}, ensure_ascii=False), flush=True)
                        rows.append(o)
    rs = sorted(rows, key=lambda r: (r['pass'], r['margin'], r['total']), reverse=True)
    print('=== STAGE2 TOP10 ===', flush=True)
    for b in rs[:10]:
        print(json.dumps({k: b[k] for k in SLIM}, ensure_ascii=False), flush=True)
    for b in rs[:3]:
        print(json.dumps({'tag': b['tag'], 'switch_log': b['switch_log'], 'brake_log': b['brake_log'][:12]}, ensure_ascii=False), flush=True)
    open(ROOT / 'results' / 'r30_bt' / 'search_C_stage2.json', 'w').write(json.dumps(rows, ensure_ascii=False, indent=1))
    print('saved rows=' + str(len(rows)), flush=True)

if __name__ == '__main__':
    main()