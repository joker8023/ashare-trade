import sys
sys.path.insert(0,'.')
import pandas as pd, numpy as np
from team.harness import normalize_spec, simulate

def spec(N,tp,phase,mode,capital,extra=None):
    sp={"id":f"s{N}_{tp}_{phase}_{mode}","selector":{"type":"amihud_60","n":N,"size_range":[0.05,0.3],
        "min_adv":5000000,"exclude_star":True,"exclude_bj":True,"exclude_chinext":True,"params":{}},
        "rebalance_days":30,"exit":{"trailing_stop":None,"fixed_stop":None,"take_profit":tp,
        "trailing_take":None,"max_hold_days":None,"stop_exec":"next"},
        "timing":{"type":"none"},"cost":{"mode":mode,"one_way":0.005,"capital":capital,"lot_size":100},
        "window":{"warmup_start":"2024-01-01","eval_start":"2026-01-05","eval_end":"2026-11-04"},
        "rebalance_anchor":"full300","phase":phase,"notes":""}
    if extra: sp['exit'].update(extra)
    return sp

def met(eq):
    base=eq[eq.index<=pd.Timestamp('2025-12-31')].iloc[-1]
    s=eq[eq.index>=pd.Timestamp('2026-01-05')]
    tot=s.iloc[-1]/base-1; mdd=(s/s.cummax()-1).min()
    m=s.resample('ME').last().pct_change().dropna(); first=s[s.index.month==1]
    if len(first): m.iloc[0]=first.iloc[-1]/base-1
    idx=list(s.index); blocks=[]
    for k in range(0,len(idx),30):
        b=s.iloc[k:min(k+30,len(idx))]
        if len(b)>=20: blocks.append(b.iloc[-1]/b.iloc[0]-1)
    return tot,mdd,(m>0).sum(),len(m),np.mean([x>0 for x in blocks]),len(blocks),(m*100).round(0).tolist()

def run(N,tp,offs,extra=None,mode="realistic",total=50000):
    cap=total/len(offs)
    eqs=[]
    for o in offs:
        cfg=normalize_spec(spec(N,tp,o,mode,cap,extra)); eqs.append(simulate(cfg)['equity'])
    eq=pd.concat(eqs,axis=1).ffill().dropna().mean(axis=1)
    t,mdd,wm,nm,bw,nb,ms=met(eq)
    print(f"N{N} tp{tp} {mode} offs{offs} cap/sleeve {cap:.0f}: total {t:+.1%} mdd {mdd:.1%} mon {wm}/{nm} block {bw:.0%}({nb}) months {ms}")
for mode in ["fixed","realistic"]:
  print("=== ",mode)
  for N,tp,extra in [(5,0.5,None),(6,0.5,None),(6,0.5,{"trailing_stop":0.20}),(7,0.5,None),(6,0.6,None)]:
    for offs in [[-10,0,10],[-12,0,12],[-8,0,8]]:
        run(N,tp,offs,extra,mode)
    print()
