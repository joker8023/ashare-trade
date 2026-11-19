import pathlib, re
root=pathlib.Path("research")
for p in sorted(root.glob("*.py")):
    try:
        t=p.read_text()
    except: continue
    if re.search(r"combo_w|w50|ME_equity|QE_equity|_equity\.pkl", t):
        print(p.name)
        # print snippet
        for i,line in enumerate(t.splitlines(),1):
            if re.search(r"combo_w|ME_equity|QE_equity|equity\.pkl|blend|weight", line):
                print(f"  {i}: {line[:200]}")
        print()
print("done scan")
# also check t40 trail
for p in sorted(pathlib.Path("results/r30_bt").glob("T40*")):
    print(p.name)
for p in sorted(pathlib.Path("results/r30_bt").glob("combo*")):
    print(p.name)
