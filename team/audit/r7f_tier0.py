"""R7-F Tier-0 诊断批：主集[0,-2,-4,-6]+备集[-3,-1,+1,+3] sleeves + 4 singles各集 + SCALE125 + gross。
合成 turnover/win_period 手工重算（不直接用合成行）。exposure floor 0.70 熔断。
"""
import sys
sys.path.insert(0, "team")
import pandas as pd
from harness import normalize_spec, run_spec, simulate

def mk(id_, phase=0, sleeves=None, capital=50000):
    pf = dict(exposure=1.0)
    if sleeves:
        pf["sleeves"] = dict(count=len(sleeves), offsets=list(sleeves), alloc="equal")
    return dict(
        id=id_,
        selector=dict(type="amihud_60", n=4, size_range=[0.05, 0.30], min_adv=5000000,
                      exclude_star=True, exclude_bj=True, exclude_chinext=True),
        rebalance_days=7, exit=dict(take_profit=0.45), timing=dict(type="none"),
        cost=dict(mode="realistic", capital=capital, lot_size=100, slip=0.002),
        portfolio=pf,
        window=dict(warmup_start="2024-01-01", eval_start="2026-01-05", eval_end="2026-11-04"),
        rebalance_anchor="full300", phase=phase, notes="R7-F Tier0",
    )

rows = []
def run(s, fam="R7-F", spec="F", phase=0, stress="base"):
    try:
        r = run_spec(s, variants=("fresh",))
    except Exception as ex:
        r = dict(id=s["id"], status="error", error=str(ex)[:200])
    r.update(family=fam, spec=spec, phase=phase, stress=stress)
    rows.append(r)
    pd.DataFrame(rows).to_csv("team/runs/batch_031_r7f_tier0.csv", index=False)
    print("%s fresh=%s mdd=%s expo=%s turn=%s" % (
        s["id"], r.get("fresh_total"), r.get("fresh_mdd"),
        r.get("fresh_exposure"), r.get("turnover")), flush=True)
    return r

MAIN, BACKUP = [0, -2, -4, -6], [-3, -1, 1, 3]
for name, offs in [("main", MAIN), ("backup", BACKUP)]:
    for o in offs:
        run(mk("F_%s_single_ph%+d" % (name, o), phase=o), spec="F_%s_single" % name, phase=o)
    run(mk("F_%s_composite" % name, phase=0, sleeves=offs), spec="F_%s_comp" % name, phase=0)
run(mk("F_SCALE125", phase=-3, capital=12500), spec="F_SCALE125", phase=-3)
# gross 版：两合成 + SCALE125
for gid, kw in [("F_main_comp_GROSS", dict(phase=0, sleeves=MAIN)),
                 ("F_backup_comp_GROSS", dict(phase=0, sleeves=BACKUP)),
                 ("F_SCALE125_GROSS", dict(phase=-3, capital=12500))]:
    g = mk(gid, **kw)
    g["cost"] = dict(mode="fixed", one_way=0.0, capital=1.0, lot_size=1)
    if "sleeves" not in kw:
        pass
    try:
        r = run_spec(g, variants=("fresh",))
    except Exception as ex:
        r = dict(id=gid, status="error", error=str(ex)[:200])
    r.update(family="R7-F", spec=gid, phase=kw.get("phase", 0), stress="gross")
    rows.append(r)
    pd.DataFrame(rows).to_csv("team/runs/batch_031_r7f_tier0.csv", index=False)
    print("%s GROSS fresh=%s" % (gid, r.get("fresh_total")), flush=True)

# 手工合成口径：turnover 取 singles 均值；win_period 在合成 equity 上按7日块重算
import numpy as np
df = pd.DataFrame(rows)
for name, comp_id, single_pat in [("main", "F_main_composite", "F_main_single"), ("backup", "F_backup_composite", "F_backup_single")]:
    sgl = df[df["spec"] == single_pat]
    turn_mean = float(pd.to_numeric(sgl["turnover"], errors="coerce").mean())
    print("%s manual composite turnover(mean of singles)=%.4f" % (name, turn_mean), flush=True)
    cfg = normalize_spec(mk("tmp", phase=0, sleeves=MAIN if name == "main" else BACKUP))
    sim = simulate(cfg)
    eq = sim["equity"]
    rets = eq.values[7:] / eq.values[:-7] - 1.0
    rets = rets[np.isfinite(rets)]
    wp = float((rets > 0).mean()) if len(rets) else None
    print("%s manual composite 7d-block win_period=%.4f (n=%d)" % (name, wp, len(rets)), flush=True)
print("=== DONE ===", flush=True)
