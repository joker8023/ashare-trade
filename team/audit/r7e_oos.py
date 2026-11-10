"""R7-E OOS 选择 + 锁定单测。纪律：选择函数只读 total_2024/total_2025 列。
Stage A: 9 (S7xalpha) + 2 controls(alpha=0 纯S30 R7网格)。
Stage B: 锁定配置 x 5相位 + stress08 + exTop3 + gross + 闭环。
"""
import sys
sys.path.insert(0, "team")
import time
import pandas as pd
from harness import normalize_spec, run_spec, simulate

S7S = {
    "E1": dict(s7="amihud_5", s7_params={}, s30="amihud_60", s30_params={}),
    "E2": dict(s7="rev5", s7_params={}, s30="amihud_60", s30_params={}),
    "E3": dict(s7="low_vol", s7_params={"window": 5}, s30="amihud", s30_params={}),
}
ALPHAS = [0.25, 0.5, 0.75]

def mk(id_, s7, s7p, s30, s30p, alpha, R=7, extra_cost=None, excl=(), phase=0):
    cost = dict(mode="realistic", capital=50000, lot_size=100, slip=0.002)
    if extra_cost:
        cost.update(extra_cost)
    return dict(
        id=id_,
        selector=dict(type="dual_scale", n=4, size_range=[0.05, 0.30], min_adv=5000000,
                      exclude_star=True, exclude_bj=True, exclude_chinext=True,
                      exclude_codes=list(excl),
                      params=dict(alpha=alpha, s7=s7, s7_params=s7p, s30=s30, s30_params=s30p)),
        rebalance_days=R, exit=dict(take_profit=0.45), timing=dict(type="none"),
        cost=cost, portfolio=dict(exposure=1.0),
        window=dict(warmup_start="2024-01-01", eval_start="2026-01-05", eval_end="2026-11-04"),
        rebalance_anchor="full300", phase=phase, notes="R7-E OOS",
    )

print("=== Stage A: 9 + 2 controls ===", flush=True)
rows = []
specs = {}
for e, (s7, s7p, s30, s30p) in {
    "E1": ("amihud_5", {}, "amihud_60", {}),
    "E2": ("rev5", {}, "amihud_60", {}),
    "E3": ("low_vol", {"window": 5}, "amihud", {}),
}.items():
    for a in ALPHAS:
        sid = "%s_a%.2f" % (e, a)
        specs[sid] = mk(sid, s7, s7p, s30, s30p, a)
specs["CTRL_amihud60_a0"] = mk("CTRL_amihud60_a0", "amihud_5", {}, "amihud_60", {}, 0.0)
specs["CTRL_amihud_a0"] = mk("CTRL_amihud_a0", "amihud_5", {}, "amihud", {}, 0.0)

for sid, s in specs.items():
    t0 = time.time()
    try:
        row = run_spec(s, variants=("fresh",))
    except Exception as ex:
        row = dict(id=sid, status="error", error=str(ex)[:200])
    row.update(stage="A")
    rows.append(row)
    pd.DataFrame(rows).to_csv("team/runs/batch_029_r7e_oos.csv", index=False)
    print("%s 2024=%s 2025=%s [%ss]" % (sid, row.get("total_2024"), row.get("total_2025"), round(time.time() - t0, 1)), flush=True)

df = pd.DataFrame(rows)
# ---- 选择（只读 2024/2025 列） ----
df["t2024"] = pd.to_numeric(df["total_2024"], errors="coerce")
df["t2025"] = pd.to_numeric(df["total_2025"], errors="coerce")
rank = df[df["id"].str.contains("_a0.50")].sort_values("t2024", ascending=False)
print(rank[["id", "t2024", "t2025"]].to_string(), flush=True)
s7order = [i.split("_a")[0] for i in rank["id"].tolist()]
keep, drop = s7order[:2], s7order[2:]
print("KEEP S7:", keep, "DROP:", drop, flush=True)
best = None
for e in keep:
    sub = df[df["id"].str.startswith(e + "_a")].set_index("id")
    v = {a: float(sub.loc["%s_a%.2f" % (e, a), "t2025"]) for a in ALPHAS}
    v24 = {a: float(sub.loc["%s_a%.2f" % (e, a), "t2024"]) for a in ALPHAS}
    cand = 0.5
    b = max(v, key=v.get)
    if b in (0.25, 0.75) and v[b] >= v[0.5] + 0.05 and v24[b] > min(v24.values()):
        cand = b
    if v[0.5] < max(v.values()) - 0.03:
        print("%s SMOOTHNESS_WARNING: alpha=0.5 off best by >3pp" % e, flush=True)
    print("%s 2025 by alpha:" % e, {k: round(x, 4) for k, x in v.items()}, "-> lock alpha", cand, flush=True)
    if best is None or v[cand] > best[2]:
        best = (e, cand, v[cand])
print("LOCKED:", best, flush=True)
import json
json.dump(dict(locked=dict(E=best[0], alpha=best[1]), keep=keep, drop=drop),
          open("team/runs/batch_029_r7e_lock.json", "w"))
print("=== Stage A DONE ===", flush=True)
