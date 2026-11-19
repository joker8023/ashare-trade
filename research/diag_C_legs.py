
import sys, json
sys.path.insert(0, "."); sys.path.insert(0, "team/audit"); sys.path.insert(0, "research")
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, RUN_START, EVAL_END, MB
piv = pd.read_pickle("data/pivots_2020_clean_realshares_v2.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp(RUN_START))
print("first_sig " + str(first_sig) + " n_dates " + str(len(dates)), flush=True)
def annual(eq, label):
    eq = eq.dropna()
    out = {"tag": label, "total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100,2), "mdd": round(_mdd(eq)*100,2)}
    prev = None
    for y in [2023,2024,2025,2026]:
        sub = eq[eq.index.year==y]
        sret = float(sub.iloc[-1]/sub.iloc[0]-1)*100
        yoy = float(sub.iloc[-1]/prev-1)*100 if prev is not None else sret
        out[str(y)] = round(sret,2); out[str(y)+"_yoy"] = round(yoy,2); out[str(y)+"_mdd"] = round(_mdd(sub)*100,2)
        prev = float(sub.iloc[-1])
    print(json.dumps(out, ensure_ascii=False), flush=True)
    return out
for tup in [(0.80,40,0.80,20,"M07seat"),(0.78,40,0.78,20,"gbf07seat")]:
    cut_a,win_a,cut_b,win_b,tag = tup
    inp_a = MaxInputs(piv, band=(0.02,0.30), gate60=-0.15, max_cut=cut_a, max_win=win_a)
    inp_b = MaxInputs(piv, band=(0.05,0.30), gate60=-1.0, max_cut=cut_b, max_win=win_b)
    CA = dict(factor="amihud_60", stop=0.25, stop_exec="next", exclude=MB, capital=50000.0, lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START, eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
    CFG_B = dict(n=4, rebal=30, take=0.80, exposure=0.9)
    ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
    eqa = ra.eq.iloc[:,0] if isinstance(ra.eq, pd.DataFrame) else ra.eq
    eqb = rb.eq.iloc[:,0] if isinstance(rb.eq, pd.DataFrame) else rb.eq
    annual(eqa.dropna(), tag+"_Aonly")
    annual(eqb.dropna(), tag+"_Bonly")
    for w in [0.5,0.6,0.7]:
        ea = eqa.dropna(); eb = eqb.dropna()
        idx = ea.index.intersection(eb.index)
        bl = (ea.loc[idx]/ea.loc[idx[0]]*w + eb.loc[idx]/eb.loc[idx[0]]*(1-w))
        bl = bl*ea.loc[idx[0]]
        annual(bl, tag+"_blend%02d"%(int(w*100)))
