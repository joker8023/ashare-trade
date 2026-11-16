import json
M = json.load(open("results/r30_bt/M07_final.json")) if __import__("os").path.exists("results/r30_bt/M07_final.json") else {}
print("M07 keys:", sorted(M.keys())[:20] if isinstance(M, dict) else type(M))
d21 = json.load(open("results/r30_bt/sweep_beat_m07_k21.json"))
base = [r for r in d21 if r["tag"] == "base_M07"][0]
top = [r for r in d21 if r["tag"] == "k21_daily_hyst003_gbf07"][0]
for w in ["1m", "3m", "6m", "1y", "2y", "3y"]:
    print(w, "k21:", top[w], "base:", base[w], "delta:", round(top[w]-base[w], 2))
print("k21 mdd:", top["mdd"], "base mdd:", base["mdd"], "switches:", top.get("switches"))
d3 = json.load(open("results/r30_bt/sweep_beat_m07_k3.json"))
g = [r for r in d3 if r["tag"] == "g_bf07"][0]
print("K3 g_bf07 nbeat:", g["nbeat_m07"], "total:", g["total"], "mdd:", g["mdd"], "1m:", g["1m"])
d8 = json.load(open("results/r30_bt/sweep_beat_m07_k8.json"))
w = [r for r in d8 if r["tag"] == "g_bf07_winA30"][0]
print("K8 winA30 nbeat:", w["nbeat_m07"], "total:", w["total"], "mdd:", w["mdd"], "1m:", w["1m"], "3m:", w["3m"])
