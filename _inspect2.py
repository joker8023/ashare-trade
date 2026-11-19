import json, pathlib, glob
import pandas as pd
# look at combo_5y, t40 etc jsons
for p in ["results/r30_bt/combo_5y.json","results/r30_bt/T40_trail6.json","results/r30_bt/three_leg20.json","results/r30_bt/t40e_24.json"]:
    import pathlib as pl
    q=pl.Path(p)
    print("="*60)
    print(p, q.exists(), q.stat().st_size if q.exists() else None)
    if q.exists():
        j=json.loads(q.read_text())
        print("keys:", list(j.keys())[:10])
        rows=j.get("rows", j.get("runs", []))
        print("nrows", len(rows))
        for r in rows[:8]:
            print(r)
