import sys, copy
sys.path.insert(0,'.')
import numpy as np, pandas as pd
from team.harness import normalize_spec, simulate, run_spec

def base_spec(N, tp, mainboard, phase, exit_extra=None):
    sp={"id":f"exp_N{N}_tp{tp}_ph{phase}","selector":{"type":"amihud_60","n":N,"size_range":[0.05,0.3],
        "min_adv":5000000,"exclude_star":True,"exclude_bj":True,"exclude_chinext":mainboard,"params":{}},
        "rebalance_days":30,"exit":{"trailing_stop":None,"fixed_stop":None,"take_profit":tp,
        "trailing_take":None,"max_hold_days":None,"stop_exec":"next"},
        "timing":{"type":"none"},"cost":{"mode":"fixed","one_way":0.005,"capital":50000,"lot_size":100},
        "window":{"warmup_start":"2024-01-01","eval_start":"2026-01-05","eval_end":"2026-11-04"},
        "rebalance_anchor":"full300","phase":phase,"notes":""}
    if exit_extra: sp['exit'].update(exit_extra)
    return sp

def scaled_metrics(eq, expo):
    r=eq.pct_change().fillna(0.0)*expo
    e=(1+r).cumprod()
    base=e[e.index<=pd.Timestamp('2025-12-31')].iloc[-1]
    s=e[e.index>=pd.Timestamp('2026-01-05')]/base
    tot=s.iloc[-1]-1; mdd=(s/s.cummax()-1).min()
    m=s.resample('ME').last().pct_change().dropna()
    first=s[s.index.month==1]
    if len(first): m.iloc[0]=first.iloc[-1]-1
    return tot,mdd,(m>0).sum()/len(m)

print("strategy N tp pool phase | expo total mdd winp winm pass")
for N,tp,mb,label in [(5,None,False,"C1 N5 none retail"),(5,0.5,True,"C2 N5 tp50 main"),(6,0.5,True,"C3 N6 tp50 main"),(7,0.5,True,"C4 N7 tp50 main")]:
    for ph in [-10,-5,0,5,10]:
        sp=base_spec(N,tp,mb,ph); r=run_spec(sp, variants=())
        cfg=normalize_spec(sp); eq=simulate(cfg)['equity']
        for expo in [0.80,0.825,0.85,0.875,0.90]:
            tot,mdd,wm=scaled_metrics(eq,expo)
            ok=tot>=.6 and mdd>=-.15 and r['win_period']>=.8
            if expo in (0.85,) or ok:
                print(f"{label:22s} ph{ph:+3d} expo{expo:.3f}: {tot:+.1%} {mdd:.1%} wp{r['win_period']:.0%} mon{wm:.0%} {'PASS' if ok else ''}")
    print()
