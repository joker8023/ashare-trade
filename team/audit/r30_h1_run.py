"""H1 执行批（冻结 specs batch_033_h1.json，需用户批准后执行）。
Tier矩阵：25 specs fresh + 5 gross + 5 stress08 + exTop3(5,需top3先出) + 闭环细节。
"""
import sys
sys.path.insert(0, "team")
import pandas as pd
from harness import normalize_spec, run_spec, simulate

SPECS = __import__("json").load(open("team/specs/batch_033_h1.json"))
assert len(SPECS) == 25, len(SPECS)
OUT = "team/runs/batch_034_h1_results.csv"

def gross_of(s):
    g = dict(s)
    g["id"] = s["id"] + "_GROSS"
    g["cost"] = dict(mode="fixed", one_way=0.0, capital=1.0, lot_size=1)
    return g

def stress_of(s):
    g = dict(s)
    g["id"] = s["id"] + "_STRESS08"
    g["cost"] = dict(mode="realistic", capital=50000, lot_size=100, slip=0.007)
    return g

rows = []
for s in SPECS:
    try:
        r = run_spec(s, variants=("fresh",))
    except Exception as ex:
        r = dict(id=s["id"], status="error", error=str(ex)[:200])
    r.update(family="H1", stress="base")
    rows.append(r)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print("%s fresh=%s mdd=%s wp=%s" % (s["id"], r.get("fresh_total"), r.get("fresh_mdd"), r.get("fresh_win_period")), flush=True)

# phase0: gross + stress + detail(top3)
p0 = [s for s in SPECS if s["phase"] == 0]
assert len(p0) == 5, len(p0)
for s in p0:
    for mk, tag in [(gross_of, "gross"), (stress_of, "slip007")]:
        g = mk(s)
        try:
            r = run_spec(g, variants=("fresh",))
        except Exception as ex:
            r = dict(id=g["id"], status="error", error=str(ex)[:200])
        r.update(family="H1", stress=tag)
        rows.append(r)
        pd.DataFrame(rows).to_csv(OUT, index=False)
        print("%s fresh=%s" % (g["id"], r.get("fresh_total")), flush=True)
for s in p0:
    sc = dict(s)
    sc["window"] = dict(warmup_start="2026-01-05", eval_start="2026-01-05", eval_end="2026-11-04")
    cfg = normalize_spec(sc)
    sim = simulate(cfg)
    tr = sim["trades"]
    ev = sim["ev_end"]
    top3 = []
    share = None
    if len(tr):
        gg = tr.groupby("code")["pnl"].sum().sort_values(ascending=False)
        top3 = gg.index[:3].tolist()
        share = float(gg.iloc[:3].sum() / gg.sum()) if float(gg.sum()) != 0 else None
    eq = float(sim["equity"].iloc[-1])
    expo = float(sim["expo_full"][ev])
    nh = float(sim["nhold_full"][ev])
    mv = eq * (expo if expo == expo else 0.0)
    liq = (max(mv * 50000 / max(nh, 1) * 0.00025, 5.0) * max(nh, 0) + mv * 50000 * 0.00251) / 50000
    print("DETAIL %s n=%d top3=%s share=%s forced=%.4f expo=%.3f" % (
        s["id"], len(tr), top3, round(share, 4) if share else None, eq - liq - 1, expo), flush=True)
    if top3:
        e = dict(s)
        e["id"] = s["id"] + "_exTOP3"
        e["selector"] = dict(e["selector"]); e["selector"]["exclude_codes"] = list(top3)
        try:
            r = run_spec(e, variants=("fresh",))
        except Exception as ex:
            r = dict(id=e["id"], status="error", error=str(ex)[:200])
        r.update(family="H1", stress="exTOP3")
        rows.append(r)
        pd.DataFrame(rows).to_csv(OUT, index=False)
        print("%s fresh=%s mdd=%s" % (e["id"], r.get("fresh_total"), r.get("fresh_mdd")), flush=True)
print("=== H1 DONE ===", flush=True)
