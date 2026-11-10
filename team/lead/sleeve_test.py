import sys, copy, json
sys.path.insert(0,'.')
import pandas as pd, numpy as np
from team.harness import normalize_spec, simulate

def spec(N=5, tp=0.5, mainboard=True, phase=0, mode="realistic", capital=10000, exit_extra=None):
    sp={"id":f"sleeve_N{N}_tp{tp}_ph{phase}","selector":{"type":"amihud_60","n":N,"size_range":[0.05,0.3],
        "min_adv":5000000,"exclude_star":True,"exclude_bj":True,"exclude_chinext":mainboard,"params":{}},
        "rebalance_days":30,"exit":{"trailing_stop":None,"fixed_stop":None,"take_profit":tp,
        "trailing_take":None,"max_hold_days":None,"stop_exec":"next"},
        "timing":{"type":"none"},"cost":{"mode":mode,"one_way":0.005,"capital":capital,"lot_size":100},
        "window":{"warmup_start":"2024-01-01","eval_start":"2026-01-05","eval_end":"2026-11-04"},
        "rebalance_anchor":"full300","phase":phase,"notes":""}
    if exit_extra: sp['exit'].update(exit_extra)
    return sp

def eq_of(sp):
    cfg=normalize_spec(sp); sim=simulate(cfg); return sim['equity']

def combine(eqs):
    df=pd.concat(eqs,axis=1).ffill().dropna()
    return df.mean(axis=1)

def metrics(eq):
    base=eq[eq.index<=pd.Timestamp('2025-12-31')].iloc[-1]
    s=eq[eq.index>=pd.Timestamp('2026-01-05')]
    tot=s.iloc[-1]/base-1; mdd=(s/s.cummax()-1).min()
    m=s.resample('ME').last().pct_change().dropna()
    first=s[s.index.month==1]
    if len(first): m.iloc[0]=first.iloc[-1]/base-1
    idx=list(s.index); blocks=[]
    for k in range(0,len(idx),30):
        b=s.iloc[k:min(k+30,len(idx))]
        if len(b)>=20: blocks.append(b.iloc[-1]/b.iloc[0]-1)
    roll=(s.shift(-30)/s-1).dropna()
    return dict(total=tot,mdd=mdd,win_month=(m>0).mean(),n_month=len(m),
                block_wr=np.mean([x>0 for x in blocks]),n_block=len(blocks),
                roll_wr=(roll>0).mean(),months=(m*100).round(1).to_dict())

if __name__=="__main__":
    for N in [5,6]:
        for tp in [0.5]:
            for offsets in ([-12,-6,0,6,12],[-10,0,10]):
                eqs=[eq_of(spec(N=N,tp=tp,phase=o)) for o in offsets]
                m=metrics(combine(eqs))
                print(f"N{N} tp{tp} sleeves{len(offsets)} offs{offsets}: total {m['total']:+.1%} mdd {m['mdd']:.1%} mon {m['win_month']:.0%} block {m['block_wr']:.0%}({m['n_block']}) roll30 {m['roll_wr']:.0%}")
                print("   months",m['months'])
