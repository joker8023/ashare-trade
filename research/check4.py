import json, glob, os
for fp in sorted(glob.glob("results/r30_bt/search_D*"))+sorted(glob.glob("results/r30_bt/search_B*"))+sorted(glob.glob("results/r30_bt/search_C*"))+sorted(glob.glob("results/r30_bt/search_A*")):
    try:
        sz=os.path.getsize(fp)
        if fp.endswith(".jsonl"):
            rows=[json.loads(l) for l in open(fp)]
            print(f"{fp} n={len(rows)} sz={sz}")
        else:
            d=json.load(open(fp))
            rows=d if isinstance(d,list) else d.get("rows",d)
            if isinstance(rows,list):
                print(f"{fp} n={len(rows)} sz={sz}")
            else:
                print(f"{fp} dict keys={list(rows.keys())[:5]}")
    except Exception as e:
        print(fp, "ERR", e)
