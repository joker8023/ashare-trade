"""R7-E Stage B: locked E1/a0.25 x 5相位 + stress08 + exTop3 + gross + 闭环。
只测锁定的一组（并列无）。OOS 选择见 batch_029（只读2024/2025列锁定）。
"""
import sys
sys.path.insert(0, "team")
import pandas as pd
from harness import normalize_spec, run_spec, simulate

S7, S7P, S30, S30P, A = "amihud_5", {}, "amihud_60", {}, 0.25

def mk(id_, alpha=A, s7=S7, s7p=S7P, s30=S30, s30p=S30P, R=7, phase=0, slip=0.002, excl=()):
    return dict(
        id=id_,
        selector=dict(type="dual_scale", n=4, size_range=[0.05, 0.30], min_adv=5000000,
                      exclude_star=True, exclude_bj=True, exclude_chinext=True,
                      exclude_codes=list(excl),
                      params=dict(alpha=alpha, s7=s7, s7_params=s7p, s30=s30, s30_params=s30p)),
        rebalance_days=R, exit=dict(take_profit=0.45), timing=dict(type="none"),
        cost=dict(mode="realistic", capital=50000, lot_size=100, slip=slip),
        portfolio=dict(exposure=1.0),
        window=dict(warmup_start="2024-01-01", eval_start="2026-01-05", eval_end="2026-11-04"),
        rebalance_anchor="full300", phase=phase, notes="R7-E locked",
    )

rows = []
for ph in [-10, -5, 0, 5, 10]:
    r = run_spec(mk("E1a025_ph%+d" % ph, phase=ph), variants=("fresh",))
    r.update(family="R7-E", spec="E1a025", phase=ph, stress="base")
    rows.append(r)
    pd.DataFrame(rows).to_csv("team/runs/batch_030_r7e_locked.csv", index=False)
    print("E1a025 ph%+d fresh=%s mdd=%s wp=%s wt=%s month=%s cost=%s turn=%s" % (
        ph, r.get("fresh_total"), r.get("fresh_mdd"), r.get("fresh_win_period"),
        r.get("fresh_win_trade"), r.get("fresh_win_month"),
        r.get("fresh_cost_paid_pct"), r.get("turnover")), flush=True)

# stress08
r = run_spec(mk("E1a025_STRESS08", slip=0.007), variants=("fresh",))
r.update(family="R7-E", spec="E1a025", phase=0, stress="slip007")
rows.append(r)
pd.DataFrame(rows).to_csv("team/runs/batch_030_r7e_locked.csv", index=False)
print("STRESS08 fresh=%s mdd=%s" % (r.get("fresh_total"), r.get("fresh_mdd")), flush=True)

# fresh detail -> top3 -> exTop3 + closure + TP share + complementarity arms gross
s0 = mk("E1a025_det")
s0["window"] = dict(warmup_start="2026-01-05", eval_start="2026-01-05", eval_end="2026-11-04")
cfg = normalize_spec(s0)
sim = simulate(cfg)
tr = sim["trades"]
ev = sim["ev_end"]
g = tr.groupby("code")["pnl"].sum().sort_values(ascending=False) if len(tr) else None
top3 = g.index[:3].tolist() if g is not None else []
share = float(g.iloc[:3].sum() / g.sum()) if g is not None and float(g.sum()) != 0 else None
eq = float(sim["equity"].iloc[-1])
expo = float(sim["expo_full"][ev])
nh = float(sim["nhold_full"][ev])
mv = eq * (expo if expo == expo else 0.0)
liq = (max(mv * 50000 / max(nh, 1) * 0.00025, 5.0) * max(nh, 0) + mv * 50000 * 0.00251) / 50000
tp = len(tr[tr["reason"] == "take_profit"]) if len(tr) else 0
print("DETAIL n=%d TP=%d top3=%s share=%s forced=%.4f expo=%.3f" % (
    len(tr), tp, top3, round(share, 4) if share else None, eq - liq - 1, expo), flush=True)

r = run_spec(mk("E1a025_exTOP3", excl=top3), variants=("fresh",))
r.update(family="R7-E", spec="E1a025", phase=0, stress="exTOP3")
rows.append(r)
pd.DataFrame(rows).to_csv("team/runs/batch_030_r7e_locked.csv", index=False)
print("exTOP3 fresh=%s mdd=%s wp=%s" % (r.get("fresh_total"), r.get("fresh_mdd"), r.get("fresh_win_period")), flush=True)

for gid, ga, gs7, gs7p, gs30, gs30p in [
    ("E1a025_GROSS", A, S7, S7P, S30, S30P),
    ("CTRL60_GROSS", 0.0, "amihud_5", {}, "amihud_60", {}),
    ("CTRL20_GROSS", 0.0, "amihud_5", {}, "amihud", {}),
]:
    gg = mk(gid, alpha=ga, s7=gs7, s7p=gs7p, s30=gs30, s30p=gs30p)
    gg["cost"] = dict(mode="fixed", one_way=0.0, capital=1.0, lot_size=1)
    gr = run_spec(gg, variants=("fresh",))
    gr.update(family="R7-E", spec=gid, phase=0, stress="gross")
    rows.append(gr)
    pd.DataFrame(rows).to_csv("team/runs/batch_030_r7e_locked.csv", index=False)
    print("%s GROSS fresh=%s" % (gid, gr.get("fresh_total")), flush=True)
print("=== DONE ===", flush=True)
