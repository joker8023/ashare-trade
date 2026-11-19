import json
fp="results/r30_bt/search_C_stage2.json"
d=json.load(open(fp))
rows=d if isinstance(d,list) else d.get("rows",[])
# show PASS rows full
def get(r,k):
    return r.get(k)
for r in rows:
    y24=r.get("2024_yoy", r.get("y2024_yoy")); y25=r.get("2025_yoy", r.get("y2025_yoy")); y26=r.get("2026_yoy", r.get("y2026_yoy"))
    m=r.get("mdd"); m24=r.get("2024_mdd", r.get("y2024_mdd"))
    if y24 and y25 and y26 and m and m24 and y24>60 and y25>60 and y26>60 and m>-30 and m24>-30:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        print("---")
