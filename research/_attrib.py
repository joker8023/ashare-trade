import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
from sweep_beat_h1_v2 import run_one, WINDOWS
import pickle
piv = pd.read_pickle(ROOT/"data"/"pivots_2020_clean.pkl")
dates = piv["close"].index
grid_dates = [dates[i] for i in range(300, len(dates), 30)]
first_sig = next(d for d in grid_dates if d >= pd.Timestamp("2023-01-03"))
# re-run key cfgs but capture equity: monkeypatch by re-running run_one internals is complex; instead re-run switch here with equity return
from design_r30_grid8 import X3Inputs
import prior_check as pc
from sweep_beat_h1_v2 import build_ns, _mdd
MB = ("688","689","300","301","8","4"); STAR = ("300","301","8","4")
def eq_of(cfg):
    excl_a = STAR if cfg.get("star_a", cfg.get("star", False)) else MB
    excl_b = STAR if cfg.get("star_b", cfg.get("star", False)) else MB
    stop = cfg.get("stop"); a_take = cfg.get("a_take", 1.2)
    b_exp = cfg.get("b_exp", 0.9); b_take = cfg.get("b_take", 0.45)
    inp_a = X3Inputs(piv, gate60=cfg.get("gate", -0.15)); inp_b = pc.Inputs(piv)
    CA = dict(factor="amihud_60", stop=stop, stop_exec="next", exclude=excl_a, capital=50_000.0, lot=100, cost_one_way=None, slip=0.002, run_start="2023-01-03", eval_start=first_sig, eval_end=pd.Timestamp("2026-11-12"), legacy_grid=False, full_liquidate=True)
    CB = dict(CA); CB["exclude"] = excl_b
    CFG_B = dict(n=cfg.get("b_n", 4), rebal=30, take=b_take, exposure=b_exp)
    ra = pc.run_strategy(inp_a, n=cfg.get("a_n", 5), rebal=cfg.get("a_r", 20), take=a_take, exposure=cfg.get("a_exp", 1.0), phase=0, **CA)
    rb = pc.run_strategy(inp_b, phase=0, **{**CB, **CFG_B})
    KW = dict(n=cfg.get("a_n", 5), rebal=cfg.get("a_r", 20), take=a_take, exposure=cfg.get("a_exp", 1.0), phase=0, inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, exclude_a=excl_a, exclude_b=excl_b, **{k: v for k, v in CA.items() if k != "exclude"})
    ns = build_ns(cfg.get("bx", 0.18), cfg.get("by", 0.08), cfg.get("bf", 0.5))
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    return eq.dropna()
cfgs = [{"tag": "TB18"}, {"tag": "stop25", "stop": 0.25}, {"tag": "Bstar", "star_b": True}]
eqs = {}
for c in cfgs:
    eqs[c["tag"]] = eq_of(c)
    print(c["tag"], "n=", len(eqs[c["tag"]]), flush=True)
pickle.dump(eqs, open(ROOT/"results"/"r30_bt"/"_attrib_eqs.pkl", "wb"))
for tag, eq in eqs.items():
    print("="*20, tag)
    yr = eq.resample("YE").last()
    prev = pd.Series([eq.iloc[0]], index=[eq.index[0]-pd.Timedelta(days=1)])
    base = pd.concat([prev, yr])
    for i in range(1, len(base)):
        print(f"  {base.index[i].year}: {base.iloc[i]/base.iloc[i-1]-1:+.2%}")
