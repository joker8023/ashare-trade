import sys
sys.path.insert(0, "team")
import pandas as pd
from harness import normalize_spec, run_spec, simulate

def mk(id_, R, gate=None, mh=None, phase=0):
    ex = dict(take_profit=0.45)
    if mh:
        ex["max_hold_days"] = mh
    return dict(
        id=id_,
        selector=dict(type="amihud_60", n=4, size_range=[0.05, 0.30], min_adv=5000000,
                      exclude_star=True, exclude_bj=True, exclude_chinext=True),
        rebalance_days=R, exit=ex, timing=dict(type="none"),
        cost=dict(mode="realistic", capital=50000, lot_size=100, slip=0.002),
        portfolio=dict(exposure=1.0),
        window=dict(warmup_start="2024-01-01", eval_start="2026-01-05", eval_end="2026-11-04"),
        rebalance_anchor="full300", phase=phase, rebalance_gate=gate, notes="R7-D sup",
    )

rows = []
for ph in [-10, -5, 0, 5, 10]:
    r = run_spec(mk("R14sym_ph%+d" % ph, 14, phase=ph), variants=("fresh",))
    r.update(family="R7-D", spec="R14sym", phase=ph, stress="base")
    rows.append(r)
    print("R14sym ph%+d fresh=%s mdd=%s wp=%s" % (ph, r.get("fresh_total"), r.get("fresh_mdd"), r.get("fresh_win_period")), flush=True)
pd.DataFrame(rows).to_csv("team/runs/batch_028_r7d_sup.csv", index=False)
g = mk("R14sym_GROSS", 14)
g["cost"] = dict(mode="fixed", one_way=0.0, capital=1.0, lot_size=1)
gr = run_spec(g, variants=("fresh",))
print("R14sym GROSS fresh=%s" % gr.get("fresh_total"), flush=True)
gr.update(family="R7-D", spec="R14sym", phase=0, stress="gross")
rows.append(gr)
pd.DataFrame(rows).to_csv("team/runs/batch_028_r7d_sup.csv", index=False)

specs = [
    ("R7D_D1_exitR7", 7, {"type": "asymmetric", "entry_R": 7, "exit_R": 7}, None),
    ("R7D_D2_exitR14", 7, {"type": "asymmetric", "entry_R": 7, "exit_R": 14}, 42),
    ("R7D_D3_exitR21", 7, {"type": "asymmetric", "entry_R": 7, "exit_R": 21}, 42),
    ("R7D_D4a_sigK8", 7, {"type": "asymmetric", "entry_R": 7, "exit_rank": 8}, 42),
    ("R7D_D4b_sigK12", 7, {"type": "asymmetric", "entry_R": 7, "exit_rank": 12}, 42),
    ("R7D_R21sym", 21, None, None),
]
for sid, R, gate, mh in specs:
    s = mk(sid + "_freshdet", R, gate, mh)
    s["window"] = dict(warmup_start="2026-01-05", eval_start="2026-01-05", eval_end="2026-11-04")
    cfg = normalize_spec(s)
    sim = simulate(cfg)
    tr = sim["trades"]
    ev = sim["ev_end"]
    tp = len(tr[tr["reason"] == "take_profit"]) if len(tr) else 0
    sd = len(tr[tr["reason"] == "signal_death"]) if len(tr) else 0
    rb_ = len(tr[tr["reason"] == "rebalance"]) if len(tr) else 0
    eq = float(sim["equity"].iloc[-1])
    expo = float(sim["expo_full"][ev])
    nh = float(sim["nhold_full"][ev])
    mv = eq * (expo if expo == expo else 0.0)
    liq = (max(mv * 50000 / max(nh, 1) * 0.00025, 5.0) * max(nh, 0) + mv * 50000 * (0.0005 + 0.00001 + 0.002)) / 50000
    print("%s: n=%d TP=%d(%d%%) death=%d rebal=%d forced=%.4f expo=%.3f nh=%.0f" % (
        sid, len(tr), tp, round(tp / max(len(tr), 1) * 100), sd, rb_, eq - liq - 1, expo, nh), flush=True)
print("=== DONE ===", flush=True)
