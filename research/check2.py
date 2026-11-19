import json, glob, os
for fp in sorted(glob.glob("results/r30_bt/search_*")):
    print(fp, os.path.getsize(fp))
print("---research---")
import glob as g
for fp in sorted(g.glob("research/search_*")):
    print(fp, os.path.getsize(fp))
# check C combo output
try:
    import pathlib
    txt=open("research/search_C_combo.py").read()
    print(txt[:3000])
except Exception as e:
    print(e)
