import json
rows = json.load(open("results/r30_bt/sweep_beat_m07_k5.json"))
for r in rows:
    if "nobrake" in r["tag"] or "lock" in r["tag"]:
        print(r["tag"], "brakes=", r["brakes"], "brake_log=", r["brake_log"], "mode=", r["mode"], "switches=", r["switches"], "same=", r["switch_same_m07"])
