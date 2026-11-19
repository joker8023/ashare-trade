import sys, json
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, _mdd, WINDOWS, RUN_START, EVAL_END, MB
from sweep_beat_m07_k21 import build_ns_k21
WINDOWS2 = dict(WINDOWS); WINDOWS2["4y"] = 1008
print("RUN", RUN_START, EVAL_END, flush=True)
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
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
def run_one(tag, mode, cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, bx=0.18, by_=0.08, bf=0.6, hyst=None, rs=60):
    inp_a,inp_b,ra,rb,CA,CFG_B = shadows(cut_a,win_a,cut_b,win_b)
    if mode=="grid":
        KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB, **{k:v for k,v in CA.items() if k!="exclude"})
        ns = build_ns(bx,by_,bf)
    else:
        KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs, exclude_a=MB, exclude_b=MB, evalfreq="daily", brake_daily=False, **{k:v for k,v in CA.items() if k!="exclude"})
        ns = build_ns_k21(bx,by_,bf,hyst)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:,0] if isinstance(res.eq,pd.DataFrame) else res.eq
    eq = eq.dropna()
    out={"tag":tag,"eq_len":int(len(eq)),"eq_start":str(eq.index[0].date()),"eq_end":str(eq.index[-1].date()),"total":round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2),"mdd":round(_mdd(eq)*100,2),"trades":len(res.trades),"cost":round(float(res.meta["total_cost"]),0),"mode":res.meta["final_mode"],"switches":len(res.meta["switch_log"])}
    for w,d in WINDOWS2.items():
        sub=eq.tail(d+1)
        out[w]=round(float(sub.iloc[-1]/sub.iloc[0]-1)*100,2)
        out[w+"_mdd"]=round(_mdd(sub)*100,2)
    # calendar years, two definitions:
    # A) slice ret = last/first-1 within year; B) yoy = year_end/prev_year_end-1
    prev_end = None
    for y in [2023,2024,2025,2026]:
        sub = eq[eq.index.year==y]
        if len(sub)==0:
            out[str(y)]=None; out[str(y)+"_mdd"]=None; out[str(y)+"_yoy"]=None; continue
        sret = float(sub.iloc[-1]/sub.iloc[0]-1)*100
        out[str(y)]=round(sret,2)
        out[str(y)+"_mdd"]=round(_mdd(sub)*100,2)
        out[str(y)+"_bars"]=int(len(sub))
        out[str(y)+"_start"]=str(sub.index[0].date())
        out[str(y)+"_end"]=str(sub.index[-1].date())
        if prev_end is not None:
            out[str(y)+"_yoy"]=round(float(sub.iloc[-1]/prev_end-1)*100,2)
        else:
            out[str(y)+"_yoy"]=round(sret,2)
        prev_end = float(sub.iloc[-1])
    return out, eq
rows=[]; eqs={}
for tag, mode, kw in [
  ("M07","grid",dict()),
  ("K3(g_bf07)","grid",dict(cut_a=0.78,cut_b=0.78,bx=0.15,by_=0.05,bf=0.7)),
  ("K8(g_bf07_winA30)","grid",dict(cut_a=0.78,win_a=30,cut_b=0.78,bx=0.15,by_=0.05,bf=0.7)),
  ("K21(k21_daily_hyst003_gbf07)","k21",dict(cut_a=0.78,cut_b=0.78,bx=0.15,by_=0.05,bf=0.7,hyst=0.03)),
]:
    o, e = run_one(tag, mode, **kw)
    rows.append(o); eqs[tag]=e
    print("done", tag, o["eq_len"], o["total"], o["mdd"], flush=True)
print(json.dumps(rows, ensure_ascii=False, indent=1))
open("results/r30_bt/backtest_M07_K3_K8_K21_realshares_v2_annual.json","w").write(json.dumps(rows, ensure_ascii=False, indent=1))
pd.to_pickle(eqs, "results/r30_bt/rs2_equities_4y.pkl")
print("saved annual json + equities pkl", flush=True)
