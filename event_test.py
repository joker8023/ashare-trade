import pandas as pd, numpy as np

d = pd.read_pickle('data/pivots_long_clean.pkl')
O = d['open']; C = d['close']
dates = O.index; codes = np.array(O.columns.tolist(), dtype=str)
print('shape', O.shape, dates.min(), dates.max())

is_main = np.array([(not c.startswith('3')) and (not c.startswith('688')) and (c[0] not in ('4','8','9')) for c in codes])
print('main frac', is_main.mean())

ov = O.values.astype(np.float64); cv = C.values.astype(np.float64)
T, S = ov.shape
pos_o = ov > 0; pos_c = cv > 0
prev_c = np.empty_like(cv); prev_c[0,:] = np.nan; prev_c[1:,:] = cv[:-1,:]
pos_p = prev_c > 0
with np.errstate(all='ignore'):
    ret = cv/prev_c - 1.0
    gap = ov/prev_c - 1.0
th_up = np.where(is_main[None,:], 0.095, 0.19)
th_dn = np.where(is_main[None,:], -0.095, -0.19)
ok_px = pos_o & pos_c & pos_p & np.isfinite(ret)
up_sig = (ret >= th_up) & ok_px
dn_sig = (ret <= th_dn) & ok_px
gap_sig = (gap < -0.03) & pos_o & pos_c & pos_p & np.isfinite(gap)

eval_mask = (dates >= pd.Timestamp('2015-01-01'))
eval_idx = np.where(eval_mask)[0]
print('eval days', eval_mask.sum(), 'up events(eval entry)', up_sig[:-1,:][eval_mask[1:]].sum(),
      'dn events', dn_sig[:-1,:][eval_mask[1:]].sum(), 'gap days-stocks', gap_sig[eval_idx].sum())
COST = 0.005

def run_hold(sig, Ns=(1,3,5,10), chunk=600):
    sumC = {N: np.zeros(T) for N in Ns}; cnt = {N: np.zeros(T) for N in Ns}
    for s0 in range(0, S, chunk):
        s1 = min(S, s0+chunk); sl = slice(s0, s1)
        o = ov[:, sl]; c = cv[:, sl]; sg = sig[:, sl]
        c_prev = np.empty_like(c); c_prev[0,:]=np.nan; c_prev[1:,:]=c[:-1,:]
        with np.errstate(all='ignore'):
            leg_base = c/c_prev - 1.0
            leg_open = c/o - 1.0
        valid_base = np.isfinite(leg_base)&(c>0)&(c_prev>0)
        valid_open = np.isfinite(leg_open)&(c>0)&(o>0)
        Efull = np.zeros_like(sg, dtype=bool)
        Efull[1:,:] = sg[:-1,:] & (o[1:,:]>0) & (c[1:,:]>0)  # next-open entry, no lookahead
        Ecs = np.cumsum(Efull.astype(np.int32), axis=0)
        for N in Ns:
            Ecs_shift = np.zeros_like(Ecs); Ecs_shift[N:,:] = Ecs[:-N,:]
            act = (Ecs - Ecs_shift) > 0
            X = np.zeros_like(Efull, dtype=bool)
            X[N-1:,:] = Efull[:T-N+1,:]
            contrib = np.where(Efull, leg_open, leg_base)
            valid = np.where(Efull, valid_open, valid_base)
            ok = act & valid & np.isfinite(contrib)
            cost = (Efull.astype(np.float64)+X.astype(np.float64))*COST
            cn = np.where(ok, contrib - cost, np.nan)
            sumC[N] += np.nansum(cn, axis=1); cnt[N] += np.sum(ok, axis=1)
    return {N: (np.where(cnt[N]>0, sumC[N]/np.maximum(cnt[N],1), 0.0), cnt[N]) for N in Ns}

def max_dd(eq):
    return float((eq/np.maximum.accumulate(np.maximum(eq,1e-12))-1.0).min())

def stats(port_full, cnt_full):
    port = port_full[eval_idx]
    ann = port.mean()*252; vol = port.std(ddof=1)*np.sqrt(252)
    sh = ann/vol if vol>0 else 0.0
    mdd = -max_dd(np.cumprod(1+port))
    act = cnt_full[eval_idx]>0
    wd = float((port[act]>0).mean()) if act.sum()>0 else float('nan')
    return ann, vol, sh, mdd, wd, float(act.mean())

print('run limit-down...'); dn_out = run_hold(dn_sig)
print('run limit-up...'); up_out = run_hold(up_sig)

def trade_stats(sig, Ns):
    res = {}
    for N in Ns:
        tot=wins=0; parts=[]
        for s0 in range(0, S, 1000):
            s1=min(S,s0+1000); sl=slice(s0,s1)
            o=ov[:,sl]; c=cv[:,sl]; sg=sig[:,sl]
            es,ss = np.where(sg[:-1,:])
            keep = eval_mask[es+1]; es=es[keep]; ss=ss[keep]
            ex = es+N; v = ex<T; es=es[v]; ss=ss[v]; ex=ex[v]
            e_idx = es+1
            with np.errstate(all='ignore'):
                gross = c[ex,ss]/o[e_idx,ss]-1.0
            ok = np.isfinite(gross)&(o[e_idx,ss]>0)&(c[ex,ss]>0)
            net = gross[ok]-2*COST
            tot+=int(ok.sum()); wins+=int((net>0).sum()); parts.append(net)
        a = np.concatenate(parts) if parts else np.array([])
        res[N]=(tot, (wins/tot if tot else float('nan')), (float(a.mean()) if tot else float('nan')))
    return res

dn_tr = trade_stats(dn_sig,[1,3,5,10]); up_tr = trade_stats(up_sig,[1,3,5,10])

# gap intraday reversal
sumC_g=np.zeros(T); cnt_g=np.zeros(T); tot=wins=0; parts=[]
for s0 in range(0,S,1000):
    s1=min(S,s0+1000); sl=slice(s0,s1)
    o=ov[:,sl]; c=cv[:,sl]; sg=gap_sig[:,sl]
    with np.errstate(all='ignore'):
        net = c/o-1.0-2*COST
    ok = sg & np.isfinite(net)
    sumC_g += np.nansum(np.where(ok,net,np.nan),axis=1); cnt_g += np.sum(ok,axis=1)
    m = ok[eval_idx,:]; v = net[eval_idx,:][m]
    tot+=int(m.sum()); wins+=int((v>0).sum()); parts.append(v)
allr = np.concatenate(parts)
gap_port = np.where(cnt_g>0, sumC_g/np.maximum(cnt_g,1), 0.0)
g = stats(gap_port, cnt_g)

import csv
rows=[['strategy','N','n_events','ann','vol','sharpe','maxDD','winrate_daily_active','winrate_trade','mean_trade_net','exposure']]
for N in [1,3,5,10]:
    a,v,s,m,w,e = stats(*dn_out[N]); n,wt,mt = dn_tr[N]
    rows.append(['limit_down_reversal',N,n,round(a,4),round(v,4),round(s,3),round(m,4),round(w,4),round(wt,4),round(mt,5),round(e,4)])
for N in [1,3,5,10]:
    a,v,s,m,w,e = stats(*up_out[N]); n,wt,mt = up_tr[N]
    rows.append(['limit_up_momentum',N,n,round(a,4),round(v,4),round(s,3),round(m,4),round(w,4),round(wt,4),round(mt,5),round(e,4)])
rows.append(['gap_down3pct_intraday', 'intraday', tot, round(g[0],4),round(g[1],4),round(g[2],3),round(g[3],4),
             round(g[4],4), round(float(wins/tot),4), round(float(allr.mean()),5), round(g[5],4)])
with open('results/event_test.csv','w',newline='') as f:
    csv.writer(f).writerows(rows)
print('saved results/event_test.csv')
for r in rows: print(r)
