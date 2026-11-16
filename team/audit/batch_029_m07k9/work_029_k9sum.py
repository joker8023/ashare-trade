import json
d=json.load(open('results/r30_bt/sweep_beat_m07_k9.json'))
print('rows=',len(d))
W=['1m','3m','6m','1y','2y','3y']
M={'1m':-4.09,'3m':17.28,'6m':39.0,'1y':164.05,'2y':1474.08,'3y':1677.53}
mis=[]
pairs={}
for x in d:
  nb=sum(1 for w in W if x[w]>M[w]); ba=all(x[w]>M[w] for w in W)
  if nb!=x.get('nbeat_m07') or ba!=x.get('beat_all'): mis.append(x['tag'])
  print(x['tag'],x.get('selector'),x.get('legs'),x.get('max_filter'),'| total=',x['total'],'mdd=',x['mdd'],'| wins=',[x[w] for w in W],'| nbeat=',x['nbeat_m07'],'re=',nb,'beat=',x['beat_all'],'trades=',x.get('trades'),'switches=',x.get('switches'),'same=',x.get('switch_same_m07'))
print('MISMATCH:',mis)
