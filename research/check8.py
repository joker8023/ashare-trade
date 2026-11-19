import json
for fp in ["results/r30_bt/search_B_stage2.json","results/r30_bt/search_D_stage3.json"]:
    try:
        d=json.load(open(fp))
        rows=d if isinstance(d,list) else d.get("rows",[])
        print(f"== {fp} n={len(rows)}")
        passes=[]
        for r in rows:
            # unify keys
            s24=r.get("2024", r.get("y2024_slice")); y24=r.get("2024_yoy", r.get("y2024_yoy")); m24=r.get("2024_mdd", r.get("y2024_mdd"))
            y25=r.get("2025_yoy", r.get("y2025_yoy")); m25=r.get("2025_mdd", r.get("y2025_mdd"))
            s26=r.get("2026", r.get("y2026_slice")); y26=r.get("2026_yoy", r.get("y2026_yoy")); m26=r.get("2026_mdd", r.get("y2026_mdd"))
            m=r.get("mdd")
            if s24 and y24 and y25 and y26 and s26 and m is not None and m24 is not None:
                if s24>60 and y24>60 and y25>60 and s26>60 and y26>60 and m>-30 and m24>-30 and (m25 is None or m25>-30) and (m26 is None or m26>-30):
                    passes.append(r)
        print(f" STRICT passes: {len(passes)}")
        for r in sorted(passes, key=lambda x: x.get("margin",0))[:10]:
            tag=r.get("tag")
            print(f"  {tag} margin={r.get('margin')} 24={r.get('2024',r.get('y2024_slice'))}/{r.get('2024_yoy',r.get('y2024_yoy'))}/{r.get('2024_mdd',r.get('y2024_mdd'))} 25={r.get('2025_yoy',r.get('y2025_yoy'))} 26={r.get('2026',r.get('y2026_slice'))}/{r.get('2026_yoy',r.get('y2026_yoy'))} mdd={r.get('mdd')}")
        # closest
        def score(r):
            try:
                y24=r.get("2024_yoy",r.get("y2024_yoy") or -999); y25=r.get("2025_yoy",r.get("y2025_yoy") or -999); y26=r.get("2026_yoy",r.get("y2026_yoy") or -999)
                return min(y24,y25,y26)
            except: return -999
        cands=[r for r in rows if (r.get("mdd") or -99)>-30]
        print(" closest mdd>-30:")
        for r in sorted(cands, key=score, reverse=True)[:3]:
            print(f"   {r.get('tag')} min_yoy={score(r):.2f} mdd={r.get('mdd')} 24={r.get('2024',r.get('y2024_slice'))}/{r.get('2024_yoy',r.get('y2024_yoy'))}")
    except Exception as e:
        print(fp, "ERR", e)
