import sys, json
sys.path.insert(0, '.'); sys.path.insert(0, './team/audit'); sys.path.insert(0, './research')
import sweep_beat_m07_k4 as k4
r = k4.sleeve_row('repro_gbf07_p0_p15', k4.G_BF07, [0, 15])
f = json.load(open('results/r30_bt/sweep_beat_m07_k4.json'))
row = [x for x in f if x.get('tag') == 'sleeve_gbf07_p0_p15'][0]
keys = ['total', 'mdd', 'trades', 'cost', 'switches', '1m', '3m', '6m', '1y', '2y', '3y', 'nbeat_m07', 'beat_all', 'mdd_better', 'win_all']
rep = {k: [row.get(k), r.get(k)] for k in keys}
rep['leg_totals'] = [[l.get('total'), l.get('mdd'), l.get('trades'), l.get('cost')] for l in row.get('legs', [])]
rep['repro_legs'] = [[l.get('total'), l.get('mdd'), l.get('trades'), l.get('cost')] for l in r.get('legs', [])]
rep['switch_same'] = [row.get('switch_same_m07'), r.get('switch_same_m07')]
json.dump(rep, open('team/audit/batch_018/part_k4repro.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(rep, ensure_ascii=False, indent=1))
