import pathlib, json
import pandas as pd, pickle
# list near_miss + r30_bt subdirs
import os
for d in ["results/near_miss","results/r30_bt"]:
    print("==",d)
    for p in sorted(pathlib.Path(d).iterdir())[:60]:
        print(" ",p.name)
# inspect combo_5y vs combo_w relation: check if combo_w equals blend of two equities?
# try to see if combo_w70 = w * A + (1-w)*B for some A,B in combo_5y? Need equities of combo legs - not saved.
# Check search_C blend json
import pathlib as pl
for f in ["results/r30_bt/search_C_blend_annual.json","results/r30_bt/combo4_monthly18.json"]:
    q=pl.Path(f)
    print("==",f,q.exists())
    if q.exists():
        j=json.loads(q.read_text())
        print(str(j)[:3000])
