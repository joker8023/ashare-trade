import sys
sys.path.insert(0, 'research')
import sweep_beat_m07_k8 as K
import json
r = K.run_one('g_bf07_rs70', 'check', rs=70, by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.7)
keys = ('tag','total','mdd','trades','cost','mode','switches','1m','3m','6m','1y','2y','3y','nbeat_m07','beat_all','mdd_better','win_all')
print(json.dumps({k: r[k] for k in keys}, ensure_ascii=False))
