"""One bounded development-only adaptation, reusing the verified finite trainer.

Only the known-report/new-goal-wording data pilot changes. One fixed seed101,
three epochs, original model/loss/LRs/CPU recipe. Not a full18field confirmation.
"""

import argparse
import importlib.metadata
import json
import math
import os
from pathlib import Path
import subprocess
import sys

from research.audit_tool_relation_confirmation import load, sha
from research.audit_tool_role_support import digest
from research.audit_varied_relation_dev import read_population, reconstruct_training
from research.detached_varied_study import checked_protocol, now, process_identity, save

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'research/goal-engine-2026-10-04/wording-development-pilot-v1'
OUT = DATA/'study-v1'
ORIGINAL = DATA.parent/'varied-relation-dev-v2'
WEIGHTS = ROOT/'models/wording-development-pilot-v1/model.safetensors'


def prepare():
    if OUT.exists() or WEIGHTS.exists():
        raise ValueError('New original study and weight destinations required')
    original = checked_protocol(ORIGINAL,verify_current=False)
    audit = load(DATA/'audit.json')
    data = load(DATA/'protocol.json')
    assert audit['status'] == 'PASS' and audit['protocol_sha256'] == data['sha256']
    assert digest({k:v for k,v in data.items() if k != 'sha256'}) == data['sha256']
    assert audit['split_projected_overlap'] == 0 and audit['cuts'] == 0 and audit['model_forwards'] == 0
    rows,views = read_population(DATA,'train')
    items,units,counts = reconstruct_training(rows,views)
    lengths = {r['projected_input_hash']:v['projected_tokens'] for r,v in zip(rows,views) if r['projected_input_hash']}
    item_tokens = sum(lengths[i['input_hash']] for i in items)
    unit_tokens = sum(lengths[k] for unit in units for k in unit)
    names = ['protocol.json','audit.json']+[f'{s}{suffix}' for s in ('train','validation') for suffix in ('.jsonl.gz','-views.jsonl.gz')]
    sources = {n:sha(ROOT/n) for n in original['sources']}
    sources.update({n:sha(ROOT/n) for n in ('research/wording_pilot_study.py','research/wording_development_pilot.py')})
    p = dict(original)
    p.pop('sha256')
    p.pop('infrastructure_continuation',None)
    p.update(schema='bounded-held-goal-wording-development-pilot/0.1',frozen_at_utc=now(),
             data_audit=audit,data_directory='..',source_data_protocol_sha256=data['sha256'],
             data_files={n:sha(DATA/n) for n in names},sources=sources,
             versions={n:importlib.metadata.version(n) for n in original['versions']},
             train_unique=len(items),train_class_counts=counts,train_unique_items_sha256=digest(items),
             train_unique_quartets=len(units),train_quartets_sha256=digest(units),
             binary_fraction=sum(counts[:2])/sum(counts),unknown_fraction=counts[2]/sum(counts),
             relevance_class_weights=[sum(counts)/(2*counts[0]),sum(counts)/(2*counts[1]),0.],
             declared_updates=3*(math.ceil(len(items)/16)+math.ceil(len(units)/4)),
             declared_training_pairs=3*(len(items)+4*len(units)),
             declared_training_nonpadding_tokens=3*(item_tokens+unit_tokens),
             hypothesis='Whole held goal-wording families on difficult distinctions may improve exposed development transfer; known report captions. Population/scope change jointly, no isolated causal claim.',
             limits=data['scope'],seed=101,epochs=3,new_confirmation_required=True,
             selection_for_adoption=False,scalar_control='Immutable scalar on the identical validation inputs; shadow ordering only, no DROP authority')
    assert p['versions'] == original['versions']
    p['sha256'] = digest(p)
    OUT.mkdir()
    for name,value in sources.items():
        target = OUT/'sources'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write((ROOT/name).read_bytes())
        assert sha(target) == value
    save(OUT/'protocol.json',p)
    return dict(protocol_sha256=p['sha256'],updates=p['declared_updates'],
                training_pairs=p['declared_training_pairs'],training_tokens=p['declared_training_nonpadding_tokens'],
                model_forwards=0)


def checked():
    p = checked_protocol(OUT)
    assert p['seed'] == 101 and p['epochs'] == 3 and p['selection_for_adoption'] is False
    assert p['source_data_protocol_sha256'] == load(DATA/'protocol.json')['sha256']
    assert all(sha(DATA/n) == v for n,v in p['data_files'].items())
    assert p['versions'] == {n:importlib.metadata.version(n) for n in p['versions']}
    return p


def run():
    from research import varied_relation_dev_detached as study
    from research.reranker_control import PairReranker
    from research.tool_relation_support_study import snapshot_path, score_population
    from research.tool_role_policy import metrics
    p = checked()
    study.OUT,study.DATA,study.WEIGHTS = OUT,DATA,WEIGHTS
    complete,error = False,None
    try:
        result = study.run(p)
        # Fixed ordering control, included in cost; never chooses a candidate.
        scorer = PairReranker.from_snapshot(snapshot_path(p['model']),p['model'],max_pair_tokens=512,batch_size=16)
        rows,views = read_population(DATA,'validation')
        raw = score_population(scorer,rows,views,p,OUT/'scalar-validation-scores.json',scalar=True)
        control = dict(protocol_sha256=p['sha256'],metrics=metrics(rows,raw['rows'],dict(support=None,relevance=None),shadow=True),
                       accounting=raw['accounting'],elapsed_s=raw['elapsed_s'],finished_at_utc=now(),quality_approved=False)
        save(OUT/'scalar-validation-metrics.json',control)
        complete = True
        return dict(protocol_sha256=p['sha256'],development_promising=result['development_promising'],
                    scalar_validation_pooled=control['metrics']['pooled_auc'],quality_approved=False)
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        save(OUT/'process-exit.json',dict(protocol_sha256=p['sha256'],returncode=0 if complete else 1,
                                       study_complete=complete,error=error,utc=now(),quality_approved=False))


def launch():
    p = checked()
    if (OUT/'started.json').exists() or WEIGHTS.exists():
        raise ValueError('Original study started; no selective restart')
    save(OUT/'launch-marker.json',dict(protocol_sha256=p['sha256'],utc=now()))
    env = dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    with (OUT/'run.log').open('xb') as stdout,(OUT/'run-errors.log').open('xb') as stderr:
        child = subprocess.Popen([sys.executable,'-m','research.wording_pilot_study','run'],cwd=ROOT,env=env,
                                 stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True,close_fds=True,shell=False)
    receipt = dict(protocol_sha256=p['sha256'],**process_identity(child.pid),utc=now())
    save(OUT/'launch.json',receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','launch','run'))
    args = parser.parse_args()
    print(json.dumps({'prepare':prepare,'launch':launch,'run':run}[args.action](),indent=2,allow_nan=False))
