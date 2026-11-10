import sys
sys.path.insert(0, "team")
import pandas as pd
from harness import run_spec
from r7f_tier0 import mk
rows = []
for o in [0, -2, -4, -6, -3, -1, 1, 3]:
    g = mk("F_single_ph%+d_GROSS" % o, phase=o)
    g["cost"] = dict(mode="fixed", one_way=0.0, capital=1.0, lot_size=1)
    try:
        r = run_spec(g, variants=("fresh",))
    except Exception as ex:
        r = dict(id=g["id"], status="error", error=str(ex)[:200])
    r.update(family="R7-F", spec="F_single_gross", phase=o, stress="gross")
    rows.append(r)
    print("%s GROSS fresh=%s" % (g["id"], r.get("fresh_total")), flush=True)
df = pd.read_csv("team/runs/batch_031_r7f_tier0.csv")
df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
df.to_csv("team/runs/batch_031_r7f_tier0.csv", index=False)
print("=== DONE ===", flush=True)
