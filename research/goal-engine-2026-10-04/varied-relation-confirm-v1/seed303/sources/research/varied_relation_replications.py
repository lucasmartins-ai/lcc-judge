"""The two predeclared independent adaptations; original seed101 is reused.

Fixed local module, seeds, data, CPU recipe and destinations. Original finite
training/evaluation implementation is reused; no final access or implicit retry.
"""

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

from research.detached_varied_study import checked_protocol, process_identity, save, now
from research.audit_tool_relation_state_supervision import digest, sha

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'research/goal-engine-2026-10-04/varied-relation-confirm-v1'
ORIGINAL = BASE.parent/'varied-relation-dev-v2'
SEEDS = (202,303)


def seed_output(seed):
    if type(seed) is not int or seed not in SEEDS:
        raise ValueError('Only the predeclared independent seeds202/303 are authorized')
    return BASE/f'seed{seed}'


def checked(seed):
    p = checked_protocol(seed_output(seed))
    if p['seed'] != seed or p['epochs'] != 3 or p['evaluation'] != ['validation','train']:
        raise ValueError('Fixed development replication required')
    design = json.loads((BASE/'design-v2/protocol.json').read_text())
    if p['confirmation_design_sha256'] != design['sha256']:
        raise ValueError('Confirmation declaration changed')
    data = ORIGINAL.parent/'tool-relation-states-v2/supervision-v1'
    if any(sha(data/name) != expected for name,expected in p['data_files'].items()):
        raise ValueError('Original training/validation bytes changed')
    return p


def prepare():
    from research import varied_relation_dev_detached as study
    from research.audit_tool_relation_state_supervision import audit
    from research.tool_relation_adaptation import configure_adaptation
    from research.reranker_control import PairReranker
    from research.tool_relation_support_study import snapshot_path
    import torch

    original = checked_protocol(ORIGINAL,verify_current=False)
    meta = json.loads((ORIGINAL/'training_meta.json').read_text())
    audited = json.loads((ORIGINAL/'audit.json').read_text())
    exit_receipt = json.loads((ORIGINAL/'process-exit.json').read_text())
    if (audited['status'] != 'PASS' or exit_receipt['returncode'] != 0
            or exit_receipt['study_complete'] is not True or sha(ROOT/meta['weights_path']) != meta['weights_sha256']):
        raise ValueError('Completed audited original derivative required')
    design = json.loads((BASE/'design-v2/protocol.json').read_text())
    if design['sha256'] != digest({k:v for k,v in design.items() if k != 'sha256'}) or design['candidate_seeds'] != [101,202,303]:
        raise ValueError('Bound predeclared confirmation required')
    if any(seed_output(seed).exists() for seed in SEEDS):
        raise ValueError('Immutable original replication destinations required')
    data_audit = audit(study.DATA,recount_tokenizer=False)
    torch.set_num_threads(original['threads'])
    protocols = []
    for seed in SEEDS:
        scalar = PairReranker.from_snapshot(snapshot_path(original['model']),original['model'],batch_size=16)
        trainability = configure_adaptation(scalar.model,seed,last_n=2); del scalar
        p = dict(original); p.pop('sha256'); p.pop('infrastructure_continuation',None)
        p.update(schema='varied-balanced-relation-independent-replication/0.1',frozen_at_utc=now(),seed=seed,
            confirmation_design_sha256=design['sha256'],data_audit=data_audit,
            data_directory='../tool-relation-states-v2/supervision-v1',trainability=trainability,
            independent_replication_of=dict(protocol_sha256=original['sha256'],audit_sha256=sha(ORIGINAL/'audit.json'),
                training_meta_sha256=sha(ORIGINAL/'training_meta.json'),weights_sha256=meta['weights_sha256'],
                reason='Independent predeclared seed from immutable base; unchanged train/validation and fixed three epochs. No original101 retraining or quality-based retry.'),
            sources={name:sha(ROOT/name) for name in study.SOURCES+['research/varied_relation_replications.py']},
            versions={name:importlib.metadata.version(name) for name in original['versions']})
        if p['versions'] != original['versions']:
            raise ValueError('Original dependency versions required')
        p['sha256'] = digest(p); out = seed_output(seed); out.mkdir()
        for name, expected in p['sources'].items():
            target = out/'sources'/name; target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as stream:
                stream.write((ROOT/name).read_bytes())
            if sha(target) != expected:
                raise ValueError('Source changed during freeze')
        save(out/'protocol.json',p); protocols.append({'seed':seed,'protocol_sha256':p['sha256']})
    return protocols


def launch():
    protocols = {str(seed):checked(seed)['sha256'] for seed in SEEDS}
    save(BASE/'replications-launch-marker.json',dict(protocols=protocols,utc=now()))
    env = dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    with (BASE/'replications-supervisor.log').open('xb') as stdout, (BASE/'replications-supervisor-errors.log').open('xb') as stderr:
        child = subprocess.Popen([sys.executable,'-m','research.varied_relation_replications','supervise'],
            cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True,close_fds=True,shell=False)
    receipt = dict(protocols=protocols,**process_identity(child.pid),utc=now(),start_new_session=True)
    save(BASE/'replications-launch.json',receipt)
    return receipt


def supervise():
    save(BASE/'replications-supervisor-started.json',dict(pid=os.getpid(),utc=now()))
    results = []
    for seed in SEEDS:
        p = checked(seed); out = seed_output(seed)
        if (out/'started.json').exists():
            raise ValueError('Original study started; no duplicate or selective restart')
        with (out/'run.log').open('xb') as stdout, (out/'run-errors.log').open('xb') as stderr:
            child = subprocess.Popen([sys.executable,'-m','research.varied_relation_replications','run','--seed',str(seed)],
                cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,close_fds=True,shell=False)
            save(out/'child-process.json',dict(protocol_sha256=p['sha256'],**process_identity(child.pid),utc=now()))
            code = child.wait()
        result = dict(protocol_sha256=p['sha256'],returncode=code,study_complete=code==0 and (out/'summary.json').exists(),
            finished_at_utc=now(),quality_approved=False,default_changed=False,P2_admission=False)
        save(out/'process-exit.json',result); results.append(result)
        if code:
            break
    save(BASE/'replications-process-exit.json',dict(results=results,all_complete=len(results)==2 and all(r['study_complete'] for r in results),utc=now()))
    return results


def run(seed):
    from research import varied_relation_dev_detached as study
    p = checked(seed)
    study.OUT = seed_output(seed)
    study.WEIGHTS = ROOT/'models/varied-relation-confirm-v1'/f'seed{seed}'/'model.safetensors'
    return study.run(p)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','launch','supervise','run'])
    parser.add_argument('--seed',type=int,choices=SEEDS)
    args = parser.parse_args()
    if (args.action == 'run') != (args.seed is not None):
        parser.error('Only run requires one of the fixed seeds')
    result = run(args.seed) if args.action == 'run' else {'prepare':prepare,'launch':launch,'supervise':supervise}[args.action]()
    print(json.dumps(result,indent=2,allow_nan=False))
