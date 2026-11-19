import json, glob
for fp in sorted(glob.glob("results/r30_bt/search_*.json"))+["results/r30_bt/search_A_spark_prog.jsonl"]:
    print("==",fp)
    try:
        if fp.endswith(".jsonl"):
            rows=[json.loads(l) for l in open(fp)]
        else:
            d=json.load(open(fp))
            rows=d if isinstance(d,list) else d.get("rows",d.get("results",[]))
            if isinstance(rows,dict):
                print(" dict keys",list(rows.keys())[:5])
                continue
        print(f" n={len(rows)}")
        # find best 2024_yoy with mdd>-30
        def get(r,k):
            return r.get(k, r.get(k+"_yoy", -999))
        cand=[r for r in rows if r.get("2024_yoy",r.get("2024",-999)) is not None]
        cand_sorted=sorted(cand, key=lambda r: r.get("2024_yoy",r.get("2024",-999) or -999), reverse=True)
        for r in cand_sorted[:3]:
            print(json.dumps({k:r.get(k) for k in ["tag","total","mdd","2024","2024_yoy","2024_mdd","2025_yoy","2026_yoy","2025","2026"] if k in r}, ensure_ascii=False))
        # count meeting 60/60/60 and mdd
        ok=[r for r in rows if (r.get("2024_yoy",-999) or -999)>60 and (r.get("2025_yoy",-999) or -999)>60 and (r.get("2026_yoy",-999) or -999)>60 and (r.get("mdd",-99)>-30) and (r.get("2024_mdd",0)>-30)]
        print(f" MEET 60/60/60 & mdd>-30: {len(ok)}")
        for r in ok[:10]:
            print(" OK",r.get("tag"),r.get("2024_yoy"),r.get("2025_yoy"),r.get("2026_yoy"),r.get("mdd"))
    except Exception as e:
        print(" ERR",e)
