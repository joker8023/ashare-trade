"""R30 Round-4 冻结spec预建 + 零回测schema校验（不调用simulate/run_spec，只做normalize_spec）。
输出：team/specs/batch_033_h1.json（25）+ team/specs/batch_034_h2.json（35）。
"""
import sys
sys.path.insert(0, "team")
import json
from harness import normalize_spec

POOL = dict(type="amihud_60", n=4, size_range=[0.05, 0.30], min_adv=5000000,
            exclude_star=True, exclude_bj=True, exclude_chinext=True)
COST = dict(mode="realistic", capital=50000, lot_size=100, slip=0.002)
WIN = dict(warmup_start="2024-01-01", eval_start="2026-01-05", eval_end="2026-11-04")
PHASES = [-10, -5, 0, 5, 10]

def base(id_, R, phase=0, gate=None, mw=None, exit_extra=None):
    sel = dict(POOL)
    if mw is not None:
        sel["max_weight"] = mw
    ex = dict(take_profit=0.45)
    if exit_extra:
        ex.update(exit_extra)
    return dict(id=id_, selector=sel, rebalance_days=R, exit=ex,
                timing=dict(type="none"), cost=dict(COST),
                portfolio=dict(exposure=1.0), window=dict(WIN),
                rebalance_anchor="full300", phase=phase,
                rebalance_gate=gate, notes="R30 Round-4 frozen")

h1, h2 = [], []
for R in [20, 25, 30, 35, 40]:
    for ph in PHASES:
        h1.append(base("H1_R%d_ph%+d" % (R, ph), R, phase=ph))
h2cfg = [
    ("H2_R30sym", 30, None, None),
    ("H2_R30x45", 30, {"type": "asymmetric", "entry_R": 30, "exit_R": 45}, None),
    ("H2_R45sym", 45, None, None),
    ("H2_R30x60", 30, {"type": "asymmetric", "entry_R": 30, "exit_R": 60}, None),
    ("H2_R60sym", 60, None, None),
    ("H2_R30sigK8", 30, {"type": "asymmetric", "entry_R": 30, "exit_rank": 8}, 90),
    ("H2_R30sigK12", 30, {"type": "asymmetric", "entry_R": 30, "exit_rank": 12}, 90),
]
for sid, R, gate, mh in h2cfg:
    for ph in PHASES:
        ex = dict(max_hold_days=mh) if mh else None
        h2.append(base("%s_ph%+d" % (sid, ph), R, phase=ph, gate=gate, exit_extra=ex))

# 零回测校验：仅 normalize（会触发全部参数校验 + gate互斥校验），不 simulate
for s in h1 + h2:
    cfg = normalize_spec(s)
    assert cfg["id"] == s["id"]
    if s["rebalance_gate"] and s["rebalance_gate"].get("type") == "asymmetric":
        assert cfg["rebalance_gate"]["entry_R"] == cfg["rebalance_days"], s["id"]

json.dump(h1, open("team/specs/batch_033_h1.json", "w"), ensure_ascii=False, indent=1)
json.dump(h2, open("team/specs/batch_034_h2.json", "w"), ensure_ascii=False, indent=1)
print("H1 specs:", len(h1), "H2 specs:", len(h2), "all normalize OK; zero simulations run", flush=True)
