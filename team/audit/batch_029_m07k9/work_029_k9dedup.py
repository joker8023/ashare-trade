import json,glob
seen={}
dup=[]
for f in sorted(glob.glob('results/r30_bt/sweep_beat_m07_k*.json')):
  d=json.load(open(f))
  for x in d:
    t=x['tag']
    seen.setdefault(t,[]).append(f.split('/')[-1])
d9=json.load(open('results/r30_bt/sweep_beat_m07_k9.json'))
k9tags=[x['tag'] for x in d9]
print('k9 tags:',k9tags)
print('cross-file dup tags:',{t:v for t,v in seen.items() if len(v)>1})
print('k9-vs-K1K8 overlap:',[t for t in k9tags if len(seen.get(t,[]))>1])
b9=next(x for x in d9 if x['tag']=='base_M07')
m=json.load(open('results/r30_bt/M07_final.json'))
print('base dev:',{k:b9[k]-m[k] for k in ['total','mdd','1m','3m','6m','1y','2y','3y','trades']})
print('base swlog==M07:',b9['switch_log']==m['switch_log'])
print('switch_same flags:',{x['tag']:x['switch_same_m07'] for x in d9})
print('mdd_better flags:',{x['tag']:x['mdd_better'] for x in d9})
