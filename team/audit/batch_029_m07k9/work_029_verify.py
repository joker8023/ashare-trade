import json, subprocess
from pathlib import Path
ROOT = Path('team/audit/batch_029_m07k9/work_029_verify.py').resolve().parents[3]
out = {'checks': {}}
M07 = json.load(open(ROOT/'results/r30_bt/M07_final.json'))
WINS = ['1m','3m','6m','1y','2y','3y']
M07W = {w: M07[w] for w in WINS}
k8 = json.load(open(ROOT/'results/r30_bt/sweep_beat_m07_k8.json'))
mis = []
for x in k8:
    nb = sum(1 for w in WINS if x[w] > M07W[w])
    ba = all(x[w] > M07W[w] for w in WINS)
    x['_re_nb'] = nb; x['_re_ba'] = ba
    if nb != x['nbeat_m07'] or ba != x['beat_all']:
        mis.append(x['tag'])
out['checks']['k8_rows'] = len(k8)
out['checks']['k8_beat_all_true'] = sum(1 for x in k8 if x['_re_ba'])
out['checks']['k8_max_nbeat_new'] = max(x['_re_nb'] for x in k8 if x['tag'] != 'base_M07')
out['checks']['k8_nbeat_ge4'] = sorted(x['tag'] for x in k8 if x['tag'] != 'base_M07' and x['_re_nb'] >= 4)
out['checks']['k8_decl_mismatch'] = mis
b = next(x for x in k8 if x['tag']=='base_M07')
out['checks']['k8_base_dev'] = {k: b[k]-M07[k] for k in ['total','mdd']+WINS}
dt = json.load(open(ROOT/'results/r30_bt/deep_tail_k9.json'))
devs = []
for tag, c in dt['configs'].items():
    [devs.append((c['full_windows'][w]['end_eq']/c['full_windows'][w]['start_eq']-1)*100 - c['full_windows'][w]['ret_full']) for w in c['full_windows']]
out['checks']['deep_retfull_maxdev'] = max(abs(v) for v in devs)
out['checks']['deep_gaps'] = {w: dt['configs']['g_bf07_winA30']['full_windows'][w]['ret_full']-dt['configs']['base_M07']['full_windows'][w]['ret_full'] for w in WINS}
out['checks']['deep_tails_identical'] = {w: dt['tails'][w]['identical'] for w in dt['tails']}
g = dt['configs']['g_bf07_winA30']['round2']
k8g = next(x for x in k8 if x['tag']=='g_bf07_winA30')
out['checks']['deep_vs_k8_g'] = {k: round(g[k]-k8g[k],6) for k in ['total','mdd','1m','3m','6m','1y','2y','3y']}
out['checks']['premise'] = {p: (ROOT/p).exists() for p in ['research/inputs_k9.py','results/r30_bt/sweep_beat_m07_k9.json','research/deep_tail_k9.py','results/r30_bt/deep_tail_k9.json']}
r = subprocess.run(['grep','-rn','shift(-','research/'], capture_output=True, text=True, cwd=ROOT)
out['checks']['shift_neg'] = r.stdout.strip().splitlines() if r.stdout.strip() else []
open(ROOT/'team/audit/batch_029_m07k9/part_029_verify.json','w').write(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out, ensure_ascii=False, indent=1))
