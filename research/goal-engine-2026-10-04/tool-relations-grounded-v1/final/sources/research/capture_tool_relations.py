"""Immutable actual-tool capture receipts; failures cannot be selectively retried."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

from research.tool_relation_runtime import SOURCES,dependency_manifest,measure_batch,runtime_identity
from research.tool_measurement_worker import validate_request

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'research/goal-engine-2026-10-04/tool-relations-grounded-v1/calibration'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_once(path,value):
    with path.open('x') as stream:stream.write(json.dumps(value,indent=2,allow_nan=False)+'\n')


def freeze(out,request,scope):
    validate_request(request)
    if (out/'protocol.json').exists():
        protocol=json.loads((out/'protocol.json').read_text())
        if protocol['request']!=request or protocol['scope']!=scope:
            raise ValueError('Existing protocol has different request/scope')
        for name,expected in protocol['sources'].items():
            if sha(ROOT/name)!=expected:raise ValueError('Source drift; audit old receipts and use a new output directory')
        return protocol
    identity=runtime_identity()
    if identity is None:raise RuntimeError('Explicit pinned trusted relation image setup required')
    names=SOURCES+['research/capture_tool_relations.py','research/audit_tool_relations.py']
    protocol=dict(schema='actual-tool-relations-capture/0.1',frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        request=request,scope=scope,runtime={k:v for k,v in identity.items() if k!='docker'},
        sources={name:sha(ROOT/name) for name in names},worker_sources={name:sha(ROOT/name) for name in SOURCES},
        dependencies=dependency_manifest(),timeout_s=45,output_limit_per_stream_bytes=4*1024*1024,
        meanings='Retry attempts include initial call; scheduled/actual sleep/elapsed differ. UDP datagrams/payload bytes, not wire/IP packets. Git index/other/ignored and index/worktree edits differ.',
        execution='Fixed trusted worker, no caller code/path/command/address, confined nonnetworked container, one original request, no selective retry',
        provenance='Authored fixtures and actual API/CLI receipts, local hashes/timestamps not independent registration/production/P2',
        model_forwards=0,API_calls=0,P2_admission=False,default_changed=False,publishing=False)
    protocol['sha256']=digest(protocol)
    out.mkdir(parents=True,exist_ok=True)
    for name,expected in protocol['sources'].items():
        path=out/'sources'/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes((ROOT/name).read_bytes());assert sha(path)==expected
    save_once(out/'protocol.json',protocol)
    return protocol


def capture(out,protocol):
    if (out/'raw.json').exists():
        raise FileExistsError('Capture already attempted; audit saved raw evidence, no automatic retry')
    current=runtime_identity()
    if current is None or {k:v for k,v in current.items() if k!='docker'}!=protocol['runtime']:
        raise ValueError('Frozen runtime identity changed before capture')
    save_once(out/'started.json',dict(protocol_sha256=protocol['sha256'],at_utc=datetime.now(timezone.utc).isoformat()))
    raw=measure_batch(protocol['request'],timeout=protocol['timeout_s'])
    save_once(out/'raw.json',raw)
    receipt=dict(protocol_sha256=protocol['sha256'],raw_sha256=sha(out/'raw.json'),
                 status=raw['status'],finished_at_utc=datetime.now(timezone.utc).isoformat(),
                 no_retry=True,admission=False,model_forwards=0,API_calls=0)
    save_once(out/'completion.json',receipt)
    print(json.dumps(receipt,indent=2))
    if raw['status']!='MEASURED':raise RuntimeError('Tool capture failed; raw/partial evidence preserved without admission')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',required=True,choices=['freeze','capture'])
    parser.add_argument('--out',type=Path,default=DEFAULT)
    parser.add_argument('--seed',type=int,default=442500)
    parser.add_argument('--fixtures',type=int,default=4)
    parser.add_argument('--scope',default='Exposed calibration only, excluded from all train/validation/fresh confirmation')
    args=parser.parse_args()
    protocol=freeze(args.out,dict(seed=args.seed,fixtures=args.fixtures),args.scope)
    if args.phase=='freeze':print(protocol['sha256'])
    else:capture(args.out,protocol)
