"""R7-D 第一批：D1/D2/D3/D4a/D4b + R21sym对称对照 x 5相位 + Gross + 细节归因。
R7-049 起编号（注册表登记）。
"""
import json, sys, time
sys.path.insert(0, "team")
import pandas as pd
from harness import normalize_spec, run_spec, simulate

PHASES = [-10, -5, 0, 5, 10]

def mk(id_, R, gate, mh=None):
    ex = dict(take_profit=0.45)
    if mh: ex["max_hold_days"] = mh
    return dict(
        id=id_,
        selector=dict(type="amihud_60", n=4, size_range=[0.05, 0.30], min_adv=5000000,
                      exclude_star=True, exclude_bj=True, exclude_chinext=True),
        rebalance_days=R,
        exit=ex,
        timing=dict(type="none"),
        cost=dict(mode="realistic", capital=50000, lot_size=100, slip=0.002),
        portfolio=dict(exposure=1.0),
        window=dict(warmup_start="2024-01-01", eval_start="2026-01-05", eval_end="2026-11-04"),
        rebalance_anchor="full300", phase=0,
        rebalance_gate=gate,
        notes="R7-D round1",
    )

G = lambda t, **k: dict(type=t, entry_R=7, **k)
SPECS = [
    ("R7D_D1_exitR7", 7, G("asymmetric", exit_R=7), None),
    ("R7D_D2_exitR14", 7, G("asymmetric", exit_R=14), 42),
    ("R7D_D3_exitR21", 7, G("asymmetric", exit_R=21), 42),
    ("R7D_D4a_sigK8", 7, G("asymmetric", exit_rank=8), 42),
    ("R7D_D4b_sigK12", 7, G("asymmetric", exit_rank=12), 42),
    ("R7D_R21sym", 21, None, None),
]

rows = []
n = 0
for sid, R, gate, mh in SPECS:
    for ph in PHASES:
        n += 1
        s = mk(f"{sid}_ph{ph:+d}", R, gate, mh); s["phase"] = ph
        t0 = time.time()
        try:
            row = run_spec(s, variants=("fresh",))
        except Exception as e:
            row = dict(id=s["id"], status="error", error=str(e)[:200])
        row.update(family="R7-D", spec=sid, phase=ph, stress="base")
        rows.append(row)
        pd.DataFrame(rows).to_csv("team/runs/batch_028_r7d_results.csv", index=False)
        print(f"[{n}/30] {sid} ph{ph:+d} fresh={row.get('fresh_total')} mdd={row.get('fresh_mdd')} wp={row.get('fresh_win_period')} {time.time()-t0:.1f}s", flush=True)
    # phase0: gross + 细节
    s0 = mk(sid + "_ph+0", R, gate, mh)
    g = dict(s0); g["id"] = sid + "_GROSS"; g["cost"] = dict(mode="fixed", one_way=0.0, capital=1.0, lot_size=1)
    try:
        grow = run_spec(g, variants=("fresh",))
    except Exception as e:
        grow = dict(id=g["id"], status="error", error=str(e)[:200])
    grow.update(family="R7-D", spec=sid, phase=0, stress="gross")
    rows.append(grow)
    pd.DataFrame(rows).to_csv("team/runs/batch_028_r7d_results.csv", index=False)
    print(f"  GROSS {sid} fresh={grow.get('fresh_total')}", flush=True)
    try:
        cfg = normalize_spec(s0); sim = simulate(cfg)
        tr = sim["trades"]
        rb = sim["rebal"]
        tp = len(tr[tr["reason"] == "take_profit"]) if len(tr) else 0
        sd = len(tr[tr["reason"] == "signal_death"]) if len(tr) else 0
        ev = sim["ev_end"]
        eq_end = float(sim["equity"].iloc[-1])
        expo = float(sim["expo_full"][ev])
        mv = eq_end * (expo if expo == expo else 0.0)
        cap = 50000.0
        liq = (max(mv*cap/max(float(sim["nhold_full"][ev]),1)*0.00025, 5.0)*max(float(sim["nhold_full"][ev]),0) + mv*cap*(0.0005+0.00001+0.002))/cap
        print(f"  DETAIL {sid}: n_tr={len(tr)} TP={tp} deathsell={sd} forced={round(eq_end-liq-1,4)} expo_end={round(expo,3)}", flush=True)
    except Exception as e:
        print(f"  DETAIL {sid} ERR {str(e)[:150]}", flush=True)

print("=== DONE ===", flush=True)
