#!/usr/bin/env python3
"""B3: outstanding(total-share) rerun of M07/K3/K8/K21 on frozen pivots.
Only change vs frozen: shares = mktcap/last_close (static total) instead of float_cap/last_close.
Caliber otherwise verbatim: ph0/RUN_START/EVAL_END/5w/cost_one_way=None+slip0.002/lot100.
Configs: M07, g_bf07(K3), g_bf07_winA30(K8), k21_daily_hyst003_gbf07(K21).
Output: results/r30_bt/rerun_outstanding_b3.json
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
assert RUN_START=="2023-01-03" and str(EVAL_END)[:10]=="2026-11-12"
import os as _os
MODE = _os.getenv("SHARE_MODE", "OUT")
piv0 = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
uni = pd.read_pickle(ROOT/"data"/"universe.pkl").set_index("code")
ratio = (uni["mktcap"]/uni["float_cap"]).replace([float("inf"),float("-inf")], float("nan")).dropna()
ratio = ratio.clip(lower=1.0)
print(f"universe.pkl ratio: n={len(ratio)} median={float(ratio.median()):.4f} p90={float(ratio.quantile(0.9)):.4f} max={float(ratio.max()):.3f}", flush=True)
print(f"universe_2020.pkl degenerate check: mkt==float for all={(pd.read_pickle(ROOT/'data'/'universe_2020.pkl')['mktcap']==pd.read_pickle(ROOT/'data'/'universe_2020.pkl')['float_cap']).all()}", flush=True)
piv = dict(piv0)
if MODE == "OUT":
    sfloat = piv0["shares"]
    if hasattr(sfloat, "columns"):
        r = ratio.reindex(sfloat.columns).fillna(1.0)
        sout = sfloat.mul(r, axis=1).astype("float32")
    else:
        r = ratio.reindex(sfloat.index).fillna(1.0)
        sout = (sfloat * r).astype("float32")
    piv["shares"] = sout
    print(f"MODE=OUT total-cap shares (float x mkt/float ratio)", flush=True)
else:
    print(f"MODE=FLOAT current-piv float shares (unchanged)", flush=True)
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
print("first_sig:", first_sig.date(), flush=True)
_shadow_cache={}; _ns_cache={}
def get_ns(bx,by,bf):
    k=(bx,by,bf)
    if k not in _ns_cache: _ns_cache[k]=build_ns(bx,by,bf)
    return _ns_cache[k]
def get_shadows(cut_a,win_a,cut_b,win_b,stop,a_take,b_take,a_n,b_n,b_exp,gate_a=-0.15,band_a_lo=0.02):
    key=(cut_a,win_a,cut_b,win_b,stop,a_take,b_take,a_n,b_n,b_exp,gate_a,band_a_lo)
    if key in _shadow_cache: return _shadow_cache[key]
    inp_a=MaxInputs(piv,band=(band_a_lo,0.30),gate60=gate_a,max_cut=cut_a,max_win=win_a)
    inp_b=MaxInputs(piv,band=(0.05,0.30),gate60=-1.0,max_cut=cut_b,max_win=win_b)
    CA=dict(factor="amihud_60",stop=stop,stop_exec="next",exclude=MB,capital=50000.0,lot=100,cost_one_way=None,slip=0.002,run_start=RUN_START,eval_start=first_sig,eval_end=EVAL_END,legacy_grid=False,full_liquidate=True)
    CFG_B=dict(n=b_n,rebal=30,take=b_take,exposure=b_exp)
    ra=pc.run_strategy(inp_a,n=a_n,rebal=20,take=a_take,exposure=1.0,phase=0,**CA)
    rb=pc.run_strategy(inp_b,phase=0,**{**CA,**CFG_B})
    _shadow_cache[key]=(inp_a,inp_b,ra,rb,CA,CFG_B)
    return _shadow_cache[key]
def run_one(tag,combo="",cut_a=0.80,win_a=40,cut_b=0.80,win_b=20,stop=0.25,a_take=1.2,b_take=0.80,a_n=5,b_n=4,b_exp=0.9,rs=60,bx=0.18,by_=0.08,bf=0.6,gate_a=-0.15,band_a_lo=0.02):
    inp_a,inp_b,ra,rb,CA,CFG_B=get_shadows(cut_a,win_a,cut_b,win_b,stop,a_take,b_take,a_n,b_n,b_exp,gate_a,band_a_lo)
    KW=dict(n=a_n,rebal=20,take=a_take,exposure=1.0,phase=0,inp_b=inp_b,cfg_b=CFG_B,shadow_a=ra.eq,shadow_b=rb.eq,rs_lookback=rs,exclude_a=MB,exclude_b=MB,**{k:v for k,v in CA.items() if k!="exclude"})
    ns=get_ns(bx,by_,bf)
    res=ns["run_strategy_switch"](inp_a,lock_mode=None,**KW)
    eq=res.eq.iloc[:,0] if isinstance(res.eq,pd.DataFrame) else res.eq
    eq=eq.dropna()
    out={"tag":tag,"combo":combo,"total":round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2),"mdd":round(_mdd(eq)*100,2),"trades":len(res.trades),"cost":round(float(res.meta["total_cost"]),0),"mode":res.meta["final_mode"],"switches":len(res.meta["switch_log"]),"switch_log":[list(x) for x in res.meta["switch_log"]]}
    for w,d in WINDOWS.items():
        sub=eq.tail(d+1)
        out[w]=round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
        out[w+"_mdd"]=round(_mdd(sub)*100,2)
    return out
from sweep_beat_m07_k21 import build_ns_k21 as _k21ns
def run_k21(tag,**kw):
    hyst=kw.pop("hyst",0.03); bx=kw.pop("bx",0.15); by_=kw.pop("by_",0.05); bf=kw.pop("bf",0.7)
    inp_a,inp_b,ra,rb,CA,CFG_B=get_shadows(0.78,40,0.78,20,0.25,1.2,0.80,5,4,0.9)
    KW=dict(n=5,rebal=20,take=1.2,exposure=1.0,phase=0,inp_b=inp_b,cfg_b=CFG_B,shadow_a=ra.eq,shadow_b=rb.eq,rs_lookback=60,exclude_a=MB,exclude_b=MB,evalfreq="daily",brake_daily=False,**{k:v for k,v in CA.items() if k!="exclude"})
    ns=_k21ns(bx,by_,bf,hyst)
    res=ns["run_strategy_switch"](inp_a,lock_mode=None,**KW)
    eq=res.eq.iloc[:,0] if isinstance(res.eq,pd.DataFrame) else res.eq
    eq=eq.dropna()
    out={"tag":tag,"total":round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2),"mdd":round(_mdd(eq)*100,2),"trades":len(res.trades),"cost":round(float(res.meta["total_cost"]),0),"mode":res.meta["final_mode"],"switches":len(res.meta["switch_log"]),"switch_log":[list(x) for x in res.meta["switch_log"]]}
    for w,d in WINDOWS.items():
        sub=eq.tail(d+1)
        out[w]=round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
        out[w+"_mdd"]=round(_mdd(sub)*100,2)
    return out
rows=[]
rows.append(run_one("M07_"+MODE,"M07 seat "+MODE))
rows.append(run_one("g_bf07_"+MODE,"K3 g_bf07 "+MODE,by_=0.05,cut_a=0.78,cut_b=0.78,bx=0.15,bf=0.7))
rows.append(run_one("g_bf07_winA30_"+MODE,"K8 "+MODE,by_=0.05,cut_a=0.78,cut_b=0.78,bx=0.15,bf=0.7,win_a=30))
rows.append(run_k21("k21_daily_hyst003_gbf07_"+MODE,hyst=0.03,bx=0.15,by_=0.05,bf=0.7))
for r in rows:
    print(json.dumps(r,ensure_ascii=False),flush=True)
open(ROOT/"results"/f"r30_bt/rerun_outstanding_b3_{MODE}.json","w").write(json.dumps(rows,ensure_ascii=False,indent=1))
print(f"saved {len(rows)} rows",flush=True)
