"""R7-A/B/C 三关验证批：固定 N4/TP45/主板/fresh5万/realistic整手。
基线: BASE_R30 (N4 R30 TP45 e1.0, 目标 +102.07%) / BASE_R7 (N4 R7 TP45)。
实验: R7-A1 overlap(3) / R7-A2 cost_aware(3,lam1.0) / R7-B rank_hold(8) / R7-C dynamic(8,ft1)。
输出: team/runs/batch_026_r7abc_results.csv + attribution 明细。
窗口: 2026 fresh主判定 + 2025/2024 OOS (run_spec variants 自带); gross 用 fixed-zero 重跑作参考。
"""
import json, sys
sys.path.insert(0, "team")
import pandas as pd
from harness import normalize_spec, run_spec, simulate

def mk(id_, R, gate, expo=1.0):
    return dict(
        id=id_,
        selector=dict(type="amihud_60", n=4, size_range=[0.05, 0.30], min_adv=5000000,
                      exclude_star=True, exclude_bj=True, exclude_chinext=True),
        rebalance_days=R,
        exit=dict(take_profit=0.45),
        timing=dict(type="none"),
        cost=dict(mode="realistic", capital=50000, lot_size=100, slip=0.002),
        portfolio=dict(exposure=expo),
        window=dict(warmup_start="2024-01-01", eval_start="2026-01-05", eval_end="2026-11-04"),
        rebalance_anchor="full300", phase=0,
        rebalance_gate=gate,
        notes="R7-ABC batch026",
    )

SPECS = [
    mk("BASE_R30_N4TP45_e100", 30, None),
    mk("BASE_R7_N4TP45_e100", 7, None),
    mk("R7A1_overlap3", 7, {"type": "overlap", "min_overlap": 3}),
    mk("R7A2_costaware3_lam10", 7, {"type": "cost_aware", "min_overlap": 3, "lam": 1.0}),
    mk("R7B_rankhold8", 7, {"type": "rank_hold", "keep_rank": 8}),
    mk("R7C_dynamic8_ft1", 7, {"type": "dynamic", "keep_rank": 8, "full_threshold": 1}),
]

rows = []
for s in SPECS:
    print(f"=== {s['id']} ===", flush=True)
    row = run_spec(s)
    # gross 参考：fixed 零成本重跑（门控决策：overlap/rank/dynamic 与成本无关，决策一致；
    # cost_aware 在零成本下 C=0 会少跳过，此处仅作上限参考，见 gate 备注）
    g = dict(s); g["id"] = s["id"] + "_GROSS"; g["cost"] = dict(mode="fixed", one_way=0.0, capital=1.0, lot_size=1)
    grow = run_spec(g)
    # detail 拿 trades/rebal 做归因
    cfg = normalize_spec(s)
    sim = simulate(cfg)
    rb = sim["rebal"]
    nskip = sum(1 for r in rb if r.get("gate_skip"))
    npartial = sum(1 for r in rb if r.get("gate_mode") == "partial")
    tr = sim["trades"]
    n_tr = len(tr)
    row["gross_total_2026"] = grow.get("total_2026")
    row["gross_fresh_2026"] = grow.get("fresh_total")
    row["n_skip"] = nskip
    row["n_partial"] = npartial
    row["n_trades_sim"] = n_tr
    rows.append(row)
    print(f"  fresh_net={row.get('fresh_total')} mdd={row.get('fresh_mdd')} wp={row.get('win_period')} wt={row.get('win_trade')} cost={row.get('fresh_cost_paid_pct')} turn={row.get('turnover')} | gross_fresh={grow.get('fresh_total')} skips={nskip} partial={npartial} trades={n_tr}", flush=True)

df = pd.DataFrame(rows)
df.to_csv("team/runs/batch_026_r7abc_results.csv", index=False)
print(df[["id", "fresh_total", "fresh_mdd", "win_period", "win_trade", "win_month", "fresh_cost_paid_pct", "turnover", "gross_fresh_2026", "n_skip", "n_partial"]].to_string())
