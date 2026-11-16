import json, glob
M07={'total':1863.27,'mdd':-27.05,'1m':-4.09,'3m':17.28,'6m':39.0,'1y':164.05,'2y':1474.08,'3y':1677.53}
rows=[]
for f in sorted(glob.glob('results/r30_bt/sweep_beat_m07_k*.json')):
    for r in json.load(open(f)):
        if r['tag']=='base_M07': continue
        rows.append(r)
violA=[r['tag'] for r in rows if r['total']>M07['total'] and r['1m']>M07['1m']]
win1m=[{'tag':r['tag'],'total':r['total'],'d1m':round(r['1m']-M07['1m'],4),'d3m':round(r['3m']-M07['3m'],4),'mdd':r['mdd']} for r in rows if r['1m']>M07['1m']]
violC=[r['tag'] for r in rows if r['3m']>M07['3m'] and r['1m']>M07['1m']]
big=sorted([(r['total'],r['tag']) for r in rows if r['total']>M07['total']],reverse=True)
json.dump({'n':len(rows),'m07':M07,'violA':violA,'win1m':win1m,'violC':violC,'high_total':big},open('results/r30_bt/frontier_k11.json','w'),indent=1,ensure_ascii=False)
print('n=%d violA=%s n_win1m=%d violC=%s n_high_total=%d max=%s'%(len(rows),violA,len(win1m),violC,len(big),big[0] if big else None))
