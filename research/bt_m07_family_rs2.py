import sys, json
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
from sweep_beat_m07_k21 import build_ns_k21
print("WINDOWS", WINDOWS, "RUN", RUN_START, EVAL_END, flush=True)
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
print("first_sig", first_sig, "n_dates", len(dates), flush=True)
_cache={}
def shadows(cut_a, win_a, cut_b, win_b, stop=0.25, a_take=1.2, b_take=0.80, a_n=5, b_n=4, b_exp=0.9):
    key=(cut_a,win_a,cut_b,win_b,stop,a_take,b_take,a_n,b_n,b_exp)
    if key in _cache: return _cache[key]
    inp_a = MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=cut_a, max_win=win_a)
    inp_b = MaxInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=cut_b, max_win=win_b)
    CA = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=b_n, rebal=30, take=b_take, exposure=b_exp)
    ra = pc.run_strategy(inp_a, n=a_n, rebal=20, take=a_take, exposure=1.0, phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
    _cache[key]=(inp_a,inp_b,ra,rb,CA,CFG_B)
    return _cache[key]
def run_grid(tag, cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, stop=0.25, a_take=1.2, b_take=0.80, rs=60, bx=0.18, by_=0.08, bf=0.6):
    inp_a,inp_b,ra,rb,CA,CFG_B = shadows(cut_a,win_a,cut_b,win_b,stop,a_take,b_take)
    KW = dict(n=5, rebal=20, take=a_take, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB, **{k:v for k,v in CA.items() if k!="exclude"})
    ns = build_ns(bx,by_,bf)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq,pd.DataFrame) else res.eq
    eq = eq.dropna()
    out={"tag":tag,"total":round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2),"mdd":round(_mdd(eq)*100,2),"trades":len(res.trades),"cost":round(float(res.meta["total_cost"]),0),"mode":res.meta["final_mode"],"switches":len(res.meta["switch_log"]),"switch_log":[list(x) for x in res.meta["switch_log"]]}
    for w,d in WINDOWS.items():
        sub=eq.tail(d+1)
        out[w]=round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
        out[w+"_mdd"]=round(_mdd(sub)*100,2)
    return out
def run_k21(tag, cut_a, cut_b, bx, by_, bf, hyst, rs):
    inp_a,inp_b,ra,rb,CA,CFG_B = shadows(cut_a,40,cut_b,20)
    KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB, evalfreq="daily", brake_daily=False, **{k:v for k,v in CA.items() if k!="exclude"})
    ns = build_ns_k21(bx,by_,bf,hyst)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq,pd.DataFrame) else res.eq
    eq = eq.dropna()
    out={"tag":tag,"total":round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2),"mdd":round(_mdd(eq)*100,2),"trades":len(res.trades),"cost":round(float(res.meta["total_cost"]),0),"mode":res.meta["final_mode"],"switches":len(res.meta["switch_log"]),"switch_log":[list(x) for x in res.meta["switch_log"]]}
    for w,d in WINDOWS.items():
        sub=eq.tail(d+1)
        out[w]=round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
        out[w+"_mdd"]=round(_mdd(sub)*100,2)
    return out
rows=[]
rows.append(run_grid("M07"))
print("done M07", flush=True)
rows.append(run_grid("K3(g_bf07)", cut_a=0.78, cut_b=0.78, bx=0.15, by_=0.05, bf=0.7))
print("done K3", flush=True)
rows.append(run_grid("K8(g_bf07_winA30)", cut_a=0.78, win_a=30, cut_b=0.78, bx=0.15, by_=0.05, bf=0.7))
print("done K8", flush=True)
rows.append(run_k21("K21(k21_daily_hyst003_gbf07)", cut_a=0.78, cut_b=0.78, bx=0.15, by_=0.05, bf=0.7, hyst=0.03, rs=60))
print("done K21", flush=True)
print(json.dumps(rows, ensure_ascii=False, indent=1))
open("results/r30_bt/backtest_M07_K3_K8_K21_realshares_v2.json", "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
