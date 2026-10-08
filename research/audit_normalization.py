"""Saved-score reproduction only; no Torch, API calls or checkpoint requirement."""
import hashlib
import json
from pathlib import Path

import numpy as np
from research.archives import verified_sources

DIRECTORY=Path(__file__).resolve().parent/'goal-engine-2026-10-04/holdout-normalization'


def auc(a,b):return float(np.searchsorted(np.sort(b),a,side='left').sum()/(len(a)*len(b)))


def metrics(a):return {'J':auc(a[:,0],a[:,1]),'D':auc(a[:,0],a[:,2])}


def run():
    p=json.loads((DIRECTORY/'protocol.json').read_text());digest=p.pop('sha256')
    assert hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()==digest
    sources=verified_sources(DIRECTORY,p['sources'])
    grid=json.loads((DIRECTORY/'grid.json').read_text())
    assert hashlib.sha256(json.dumps(grid,sort_keys=True).encode()).hexdigest()==p['grid_sha256']
    summary=json.loads((DIRECTORY/'summary.json').read_text())
    raw_path=DIRECTORY/'scores.json';raw=json.loads(raw_path.read_text())
    assert raw['protocol_sha256']==summary['protocol_sha256']==digest
    assert hashlib.sha256(raw_path.read_bytes()).hexdigest()==summary['scores_sha256']
    assert len(grid)==192 and raw['truncated']==0 and raw['actual_hf_max']<=p['max_pair_hf']
    kinds=['pos','neg_decoy','neg_unrelated'];ids=sorted({r['case_id'] for r in grid})
    assert len(ids)==64 and len({r['content_hash'] for r in grid})==192
    domains=sorted({r['domain'] for r in grid});assert len(domains)==4
    groups=[np.array([i for i,c in enumerate(ids) if c.startswith(d+'-')]) for d in domains]
    assert all(len(g)==16 for g in groups)
    for case in ids:
        selected=[r for r in grid if r['case_id']==case]
        assert len(selected)==3 and {r['kind'] for r in selected}==set(kinds)
        assert len({r['objective'] for r in selected})==1
    arrays={}
    for name,rows in raw['models'].items():
        assert len(rows)==192
        assert [(r['id'],r['domain'],r['objective'],r['kind'],r['case_id']) for r in rows]== \
               [(r['id'],r['domain'],r['objective'],r['kind'],r['case_id']) for r in grid]
        arrays[name]=np.array([[next(r['score'] for r in rows if r['case_id']==c and r['kind']==k) for k in kinds] for c in ids])
        assert np.isfinite(arrays[name]).all()
    recomputed={}
    for name,values in [('parent',[arrays['parent']]),('selected_bce',[arrays[f'bce-{s}'] for s in [101,202,303]])]:
        normalized=[]
        for value in values:
            mean=value.mean(1,keepdims=True);scale=np.sqrt(((value-mean)**2).mean(1,keepdims=True))
            normalized.append((value-mean)/np.where(scale>0,scale,1))
        before={f:float(np.mean([metrics(v)[f] for v in values])) for f in ['J','D']}
        after={f:float(np.mean([metrics(v)[f] for v in normalized])) for f in ['J','D']}
        recorded=summary['summary'][name]
        assert all(abs(recorded['before'][f]-before[f])<1e-12 and abs(recorded['after'][f]-after[f])<1e-12 for f in ['J','D'])
        rng=np.random.default_rng(p['bootstrap']['seed']);draws=[]
        for _ in range(p['bootstrap']['repeats']):
            indices=np.concatenate([groups[i] for i in rng.integers(0,len(groups),len(groups))])
            draws.append(np.mean([metrics(n[indices])['J']-metrics(v[indices])['J'] for v,n in zip(values,normalized)]))
        interval=np.percentile(draws,[2.5,97.5]).tolist()
        assert np.allclose(interval,recorded['delta_J_95ci'],rtol=0,atol=1e-12)
        paired={f:float(np.mean([np.mean(v[:,0]>v[:,i]) for v in values])) for f,i in [('J',1),('D',2)]}
        assert paired==recorded['paired']
        passed=after['J']-before['J']>=.03 and interval[0]>0 and after['D']-before['D']>=-.01
        assert recorded['normalization_criteria_pass'] is passed
        recomputed[name]=dict(before=before,after=after,delta_J_95ci=interval,paired=paired,criteria_pass=passed)
    return dict(n_candidates=192,n_objectives=64,domains=domains,summary=recomputed,
        archived_sources_verified=sources,source_verification_mode='archived',
        inference_reexecuted=False,training_admission=False,temporal_preregistration_certified=False)


if __name__=='__main__':
    result=run();(DIRECTORY/'audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
