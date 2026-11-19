import json
fp="results/r30_bt/search_C_stage2.json"
d=json.load(open(fp))
rows=d if isinstance(d,list) else d.get("rows",[])
print(f"total {len(rows)}")
# strict: 2024 slice>60 and yoy>60, 2025_yoy>60, 2026 slice>60? and yoy>60, mdd>-30 all years
passes=[]
for r in rows:
    if r.get("2024") and r["2024"]>60 and r.get("2024_yoy",0)>60 and r.get("2025_yoy",0)>60 and r.get("2026_yoy",0)>60 and r.get("2026",0)>60 and r.get("mdd",-99)>-30 and r.get("2024_mdd",-99)>-30 and r.get("2025_mdd",-99)>-30 and r.get("2026_mdd",-99)>-30:
        passes.append(r)
print(f"STRICT slice+yoy passes: {len(passes)}")
for r in sorted(passes, key=lambda x: x["2024"]):
    print(f"{r['tag']}: 24 slice {r['2024']}/yoy {r['2024_yoy']}/mdd {r['2024_mdd']} | 25 yoy {r['2025_yoy']}/mdd {r['2025_mdd']} | 26 slice {r['2026']}/yoy {r['2026_yoy']}/mdd {r['2026_mdd']} | total {r['total']}/mdd {r['mdd']} trades {r['trades']} cost {r['cost']} switches {r['switches']} brakes {r['brakes']} margin {r.get('margin')}")
