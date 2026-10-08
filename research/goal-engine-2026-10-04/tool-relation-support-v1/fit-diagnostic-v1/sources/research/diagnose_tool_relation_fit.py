"""One exposed train-fit check on the fixed first rejected seed, without refitting.

Not another candidate or a holdout result. Retains the original validation cutoffs
and original complete training-row population. Does not train, alter final scores,
choose a seed, or promote a policy. Raw evidence survives reduction failure.
"""

from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import socket

import torch
from safetensors.torch import load_file

from research.reranker_control import PairReranker
from research.tool_relation_adaptation import configure_adaptation,frozen_parameter_sha256
from research.tool_relation_support_study import DATA,dataset,score_population,snapshot_path
from research.tool_role_policy import metrics
from specialist.checkpoint import load_trained_weights

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/'research/goal-engine-2026-10-04/tool-relation-support-v1'
OUT=STUDY/'fit-diagnostic-v1'


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def save(path,value):
    with path.open('x') as target:target.write(json.dumps(value,indent=2,allow_nan=False)+'\n')


def run():
    if OUT.exists():raise ValueError('Inspect existing diagnostic; no selective repeat')
    study=json.loads((STUDY/'protocol.json').read_text());meta=json.loads((STUDY/'seed-101/training_meta.json').read_text())
    thresholds=json.loads((STUDY/'seed-101/thresholds.json').read_text())['thresholds']
    weight=ROOT/meta['weights_path'];assert sha(weight)==meta['weights_sha256']
    names=['research/diagnose_tool_relation_fit.py','research/tool_relation_support_study.py',
        'research/tool_relation_adaptation.py','research/ranking_support_initialization.py',
        'research/tool_role_policy.py','research/reranker_control.py','specialist/checkpoint.py']
    protocol=dict(schema='exposed-train-fit/0.1',frozen_at_utc=datetime.now(timezone.utc).isoformat(),seed=101,
        study_protocol_sha256=study['sha256'],weights_sha256=meta['weights_sha256'],model=study['model'],
        data_files={name:sha(DATA/name) for name in ['train.jsonl','train-views.jsonl']},
        sources={name:sha(ROOT/name) for name in names},batch_size=16,threads=8,device='cpu',dtype='float32',window=512,
        thresholds=thresholds,seed_selection='Fixed first protocol seed, not best final seed',
        scope='Original exposed train population, same private weights and validation-only cutoffs; no tuning/training or generalization claim',
        training=False,API_calls=0,P2_admission=False,adoption=False,default_changed=False)
    protocol['sha256']=hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest()
    OUT.mkdir()
    save(OUT/'protocol.json',protocol)
    for name in names:
        path=OUT/'sources'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((ROOT/name).read_bytes())
    original=socket.socket.connect
    def denied(*args,**kwargs):raise RuntimeError('Network denied during fit check')
    socket.socket.connect=denied
    torch.set_num_threads(8)
    try:
        scorer=PairReranker.from_snapshot(snapshot_path(study['model']),study['model'],batch_size=16)
        configure_adaptation(scorer.model,101,last_n=2)
        load_trained_weights(scorer.model,load_file(str(weight),device='cpu'))
        assert frozen_parameter_sha256(scorer.model)==study['trainability']['frozen_parameter_sha256']
        rows,views=dataset('train')
        raw=score_population(scorer,rows,views,protocol,OUT/'train-scores.json')
        result=dict(metrics=metrics(rows,raw['rows'],thresholds),by_language={},by_family={})
        for column,values in [('by_language',['en','pt']),('by_family',sorted({r['family'] for r in rows if r['label'] is not None}))]:
            for value in values:
                field='goal_language' if column=='by_language' else 'family'
                paired=[(r,s) for r,s in zip(rows,raw['rows']) if r[field]==value]
                result[column][value]=metrics([r for r,s in paired],[s for r,s in paired],thresholds)
        result.update(protocol_sha256=protocol['sha256'],scope=protocol['scope'],training=False,thresholds_refit=False,API_calls=0)
        save(OUT/'metrics.json',result);print(json.dumps(result,indent=2))
    except Exception as exc:
        save(OUT/'failure.json',dict(error_type=type(exc).__name__,error=str(exc),training=False,selective_retry=False))
        raise
    finally:socket.socket.connect=original


if __name__=='__main__':run()
