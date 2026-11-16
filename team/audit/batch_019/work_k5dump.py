import json
rows = json.load(open("results/r30_bt/sweep_beat_m07_k5.json"))
W = ["1m", "3m", "6m", "1y", "2y", "3y"]
for r in rows:
    print(r.get("tag"), "|", r.get("kind"), "|", r.get("mechanism"), "| nbeat=", r.get("nbeat_m07"), "beat=", r.get("beat_all"), "win=", r.get("win_all"), "total=", r.get("total"), "mdd=", r.get("mdd"), "tr=", r.get("trades"), "cost=", r.get("cost"), "sw=", r.get("switches"), "same=", r.get("switch_same_m07"))
    print("   six:", {w: r.get(w) for w in W})
    print("   params:", json.dumps(r.get("params", {}), ensure_ascii=False)[:500])
