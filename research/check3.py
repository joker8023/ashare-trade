import json, glob
for fp in ["results/r30_bt/search_A_stage2_prog.jsonl"]:
    try:
        rows=[json.loads(l) for l in open(fp)]
        print(fp, len(rows))
        ok=[r for r in rows if (r.get("2024_yoy") or -999)>60 and (r.get("2025_yoy") or -999)>60 and (r.get("2026_yoy") or -999)>60 and (r.get("mdd") or -99)>-30 and (r.get("2024_mdd") or -99)>-30]
        print(" meet:", len(ok))
        for r in ok[:5]:
            print(r.get("tag"), r.get("2024_yoy"), r.get("2025_yoy"), r.get("2026_yoy"), r.get("mdd"), r.get("2024_mdd"))
        best=sorted(rows, key=lambda r: (r.get("2024_yoy") or -999), reverse=True)[:3]
        for r in best:
            print("best", r.get("tag"), r.get("2024_yoy"), r.get("2024_mdd"), r.get("2025_yoy"), r.get("2026_yoy"), r.get("mdd"))
    except Exception as e:
        print("err", e)
