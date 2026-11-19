import json
def get_yoy(r, y):
    for k in [f"{y}_yoy", f"y{y}_yoy", str(y)]:
        if k in r and r[k] is not None:
            return r[k]
    return None
def get_mdd(r, y=None):
    if y is None:
        return r.get("mdd")
    for k in [f"{y}_mdd", f"y{y}_mdd"]:
        if k in r:
            return r[k]
    return None
for fp in ["results/r30_bt/search_B_stage2a.json","results/r30_bt/search_C_stage2.json","results/r30_bt/search_A_stage2.json"]:
    try:
        d=json.load(open(fp))
        rows=d if isinstance(d,list) else d.get("rows",[])
        print(f"== {fp} n={len(rows)}")
        ok=[]
        for r in rows:
            try:
                y24=get_yoy(r,2024); y25=get_yoy(r,2025); y26=get_yoy(r,2026)
                m=get_mdd(r); m24=get_mdd(r,2024)
                if y24 and y25 and y26 and m and m24:
                    if y24>60 and y25>60 and y26>60 and m>-30 and m24>-30:
                        ok.append(r)
            except: pass
        print(f" strict PASS (yoy>60 x3, mdd>-30, 2024mdd>-30): {len(ok)}")
        for r in ok[:10]:
            print("  PASS", r.get("tag"), get_yoy(r,2024), get_yoy(r,2025), get_yoy(r,2026), get_mdd(r), get_mdd(r,2024))
        # closest: sort by min(y24,y25,y26) with mdd constraint
        def score(r):
            try:
                return min(get_yoy(r,2024) or -999, get_yoy(r,2025) or -999, get_yoy(r,2026) or -999)
            except: return -999
        cands=[r for r in rows if (get_mdd(r) or -99)>-30]
        cands_sorted=sorted(cands, key=score, reverse=True)[:3]
        print(" closest with mdd>-30:")
        for r in cands_sorted:
            print("  ", r.get("tag"), "24:", get_yoy(r,2024), get_mdd(r,2024), "25:", get_yoy(r,2025), "26:", get_yoy(r,2026), "mdd:", get_mdd(r))
        cands2=sorted(rows, key=score, reverse=True)[:3]
        print(" closest overall:")
        for r in cands2:
            print("  ", r.get("tag"), "24:", get_yoy(r,2024), get_mdd(r,2024), "25:", get_yoy(r,2025), "26:", get_yoy(r,2026), "mdd:", get_mdd(r))
    except Exception as e:
        print(fp, "ERR", e)
