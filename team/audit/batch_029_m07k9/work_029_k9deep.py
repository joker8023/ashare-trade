import sys, json
sys.path.insert(0,'.'), sys.path.insert(0,'team/audit'), sys.path.insert(0,'research')
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from inputs_k9 import K9Inputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
M07W={'1m':-4.09,'3m':17.28,'6m':39.0,'1y':164.05,'2y':1474.08,'3y':1677.53}
piv=pd.read_pickle('data/pivots_2020_clean.pkl')
dates=piv['close'].index
grid_dates=[dates[i] for i in range(300,len(dates),30)]
first_sig=next(d for d in grid_dates if d>=pd.Timestamp(RUN_START))
A_P=dict(band=(0.02,0.30),gate60=-0.15,max_cut=0.80,max_win=40)
B_P=dict(band=(0.05,0.30),gate60=-1.0,max_cut=0.80,max_win=20)
NS=build_ns(0.18,0.08,0.6)
_ic={}; _sc={}
def get_inp(kind,leg,max_on):
  k=(kind,leg,max_on)
  P=A_P if leg=='A' else B_P
  return _ic.setdefault(k, MaxInputs(piv,**P) if kind=='M07' else K9Inputs(piv,use_max=max_on,sel=kind,**P))
def get_shadow(kind,leg,max_on,n,rebal,take,exposure,phase,slip):
  k=(kind,leg,max_on,n,rebal,take,exposure,phase,slip)
  if k not in _sc:
    inp=get_inp(kind,leg,max_on)
    factor='amihud_60' if kind=='M07' else kind
    CA=dict(factor=factor,stop=0.25,stop_exec='next',exclude=MB,capital=50000.0,lot=100,cost_one_way=None,slip=slip,run_start=RUN_START,eval_start=first_sig,eval_end=EVAL_END,legacy_grid=False,full_liquidate=True)
    _sc[k]=(inp,pc.run_strategy(inp,n=n,rebal=rebal,take=take,exposure=exposure,phase=phase,**CA),CA)
  return _sc[k]
def run_variant(tag,selector,legs,max_on,phase,slip):
  a_kind='M07' if legs=='B' else selector
  ia,ra,CA=get_shadow(a_kind,'A',max_on,5,20,1.2,1.0,phase,slip)
  ib,rb,_=get_shadow(selector,'B',max_on,4,30,0.80,0.9,phase,slip)
  CFG_B=dict(n=4,rebal=30,take=0.80,exposure=0.9)
  kwf='amihud_60' if legs=='B' else selector
  KW=dict(n=5,rebal=20,take=1.2,exposure=1.0,phase=phase,inp_b=ib,cfg_b=CFG_B,shadow_a=ra.eq,shadow_b=rb.eq,rs_lookback=60,exclude_a=MB,exclude_b=MB,factor=kwf,**{k:v for k,v in CA.items() if k not in ('exclude','factor')})
  res=NS['run_strategy_switch'](ia,lock_mode=None,**KW)
  eq=res.eq.iloc[:,0] if isinstance(res.eq,pd.DataFrame) else res.eq
  eq=eq.dropna()
  o={'tag':tag,'phase':phase,'slip':slip,'total_f':(eq.iloc[-1]/eq.iloc[0]-1)*100,'mdd_f':_mdd(eq)*100,'trades':len(res.trades),'mode':res.meta['final_mode'],'switches':len(res.meta['switch_log']),'swlog':[list(x) for x in res.meta['switch_log']]}
  for w,d in WINDOWS.items():
    s=eq.tail(d+1); o[w+'_f']=float(s.iloc[-1]/s.iloc[0]-1)*100; o[w]=round(o[w+'_f'],2)
  o['total']=round(o['total_f'],2); o['mdd']=round(o['mdd_f'],2)
  o['nbeat']=sum(1 for w in WINDOWS if o[w]>M07W[w]); o['beat']=all(o[w]>M07W[w] for w in WINDOWS)
  return o,res,eq
TAGS=[('k9_amihud_5_both_on','amihud_5','both',True),('k9_amihud_5_B_on','amihud_5','B',True)]
out={}
for tag,sel,legs,mon in TAGS:
  out[tag]={}
  for vn,ph,sl in [('cal',0,0.002),('ph5',5,0.002),('ph15',15,0.002),('slip2x',0,0.004)]:
    o,res,eq=run_variant(tag,sel,legs,mon,ph,sl)
    slim={k:o[k] for k in ('total','mdd','trades','mode','switches','1m','3m','6m','1y','2y','3y','nbeat','beat')}
    slim['swlog']=o['swlog']
    out[tag][vn]=slim
    print(tag,vn,json.dumps(slim,ensure_ascii=False),flush=True)
  o,res,eq=run_variant(tag,sel,legs,mon,0,0.002)
  tr=res.trades
  g=tr.groupby('code')['net_pnl'].sum().sort_values(ascending=False)
  top3=list(g.head(3).items())
  s0=float(eq.iloc[0]); ex=(float(eq.iloc[-1])-s0-sum(v for _,v in top3))/s0*100
  out[tag]['extop3']={'top3':[[c,round(float(v),2)] for c,v in top3],'extop3_total':round(ex,2)}
  print(tag,'extop3',json.dumps(out[tag]['extop3'],ensure_ascii=False),flush=True)
open('team/audit/batch_029_m07k9/part_029_k9deep.json','w').write(json.dumps(out,ensure_ascii=False,indent=1))
print('saved',flush=True)
