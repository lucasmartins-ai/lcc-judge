"""Immutable varied-state captures with fixed original requests and no retry."""

import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

from research.tool_relation_state_runtime import SOURCES,dependency_manifest,runtime_identity,measure_batch
from research.tool_measurement_worker import validate_request

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'research/goal-engine-2026-10-04/tool-relation-states-v2/calibration'


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()


def save_new(path,value):
    with path.open('x') as target:target.write(json.dumps(value,indent=2,allow_nan=False)+'\n')


def freeze(out,request,scope):
    validate_request(request)
    if (out/'protocol.json').exists():
        p=json.loads((out/'protocol.json').read_text())
        if p['request']!=request or p['scope']!=scope or digest({k:v for k,v in p.items() if k!='sha256'})!=p['sha256']:
            raise ValueError('Frozen request/scope/protocol changed')
        for name,wanted in p['sources'].items():
            if sha(ROOT/name)!=wanted or sha(out/'sources'/name)!=wanted:raise ValueError('Source drift; retain old capture and use a new protocol')
        return p
    identity=runtime_identity()
    if identity is None:raise RuntimeError('Explicit verified separate varied-state worker setup required')
    names=SOURCES+['research/capture_tool_relation_states.py','research/audit_tool_relation_states.py']
    p=dict(schema='actual-tool-relation-states-capture/0.2',frozen_at_utc=now(),request=request,scope=scope,
        runtime={k:v for k,v in identity.items() if k!='docker'},sources={name:sha(ROOT/name) for name in names},
        worker_sources={name:sha(ROOT/name) for name in SOURCES},dependencies=dependency_manifest(),timeout_s=45,
        output_limit_per_stream_bytes=4*1024*1024,
        meanings='Retry success/exhaustion are operation outcomes; capture error UNKNOWN. UDP successful sends and actual prefix-budget receives/bytes, not loss/IP/wire. Git staged deletion counts HEAD/index edits even absent from current index; worktree compares index with disk.',
        execution='Trusted fixed source, bounded seed/count only; no caller code/path/command/address, confined original request once',
        model_forwards=0,API_calls=0,P2_admission=False,default_changed=False,publishing=False)
    p['sha256']=digest(p);out.mkdir(parents=True,exist_ok=True)
    for name,wanted in p['sources'].items():
        target=out/'sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write((ROOT/name).read_bytes())
        if sha(target)!=wanted:raise ValueError('Source changed during freeze')
    save_new(out/'protocol.json',p);return p


def capture(out,p):
    if (out/'started.json').exists():raise FileExistsError('Original request already started; inspect raw/partial evidence, no selective retry')
    identity=runtime_identity()
    if identity is None or {k:v for k,v in identity.items() if k!='docker'}!=p['runtime']:
        raise ValueError('Runtime identity changed before capture')
    save_new(out/'started.json',dict(protocol_sha256=p['sha256'],at_utc=now()))
    raw=measure_batch(p['request'],timeout=p['timeout_s']);save_new(out/'raw.json',raw)
    receipt=dict(protocol_sha256=p['sha256'],raw_sha256=sha(out/'raw.json'),status=raw['status'],
                 finished_at_utc=now(),no_retry=True,admission=False,model_forwards=0,API_calls=0)
    save_new(out/'completion.json',receipt);print(json.dumps(receipt,indent=2))
    if raw['status']!='MEASURED':raise RuntimeError('Capture UNKNOWN; preserve completed/partial evidence without admission or retry')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',required=True,choices=['freeze','capture'])
    parser.add_argument('--out',type=Path,default=DEFAULT);parser.add_argument('--seed',type=int,default=442600)
    parser.add_argument('--fixtures',type=int,default=16)
    parser.add_argument('--scope',default='Exposed calibration only, excluded from train/validation/confirmation')
    args=parser.parse_args();p=freeze(args.out,dict(seed=args.seed,fixtures=args.fixtures),args.scope)
    if args.phase=='freeze':print(p['sha256'])
    else:capture(args.out,p)
