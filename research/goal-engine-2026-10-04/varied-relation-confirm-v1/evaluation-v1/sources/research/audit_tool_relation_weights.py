"""Additive private-weight audit accepting the verified upstream position buffer.

The frozen receipt auditor remains unchanged. Its first weight parser assumed all
tensors were float32; the upstream artifact also carries a deterministic int64
position-id buffer. This checker validates that exact buffer, hashes only declared
learned parameters, and never reruns training or changes any quality criterion.
"""

import argparse
import hashlib
import json
import math
import mmap
from pathlib import Path
import struct

from research.audit_tool_relation_support import audit as audit_receipts

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/goal-engine-2026-10-04/tool-relation-support-v1'
POSITION_BUFFER='roberta.embeddings.position_ids'


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def header(path):
    with path.open('rb') as stream:
        size=int.from_bytes(stream.read(8),'little');assert 0<size<1024*1024
        tensors=json.loads(stream.read(size))
    tensors={name:spec for name,spec in tensors.items() if name!='__metadata__'}
    length=path.stat().st_size-8-size;intervals=[]
    for name,spec in tensors.items():
        if spec['dtype']=='F32':item_bytes=4
        else:
            assert name==POSITION_BUFFER and spec['dtype']=='I64' and spec['shape']==[1,514]
            item_bytes=8
        assert all(type(n) is int and n>0 for n in spec['shape'])
        start,end=spec['data_offsets']
        assert type(start) is int and type(end) is int and 0<=start<end<=length
        assert end-start==math.prod(spec['shape'])*item_bytes
        intervals.append((start,end))
    intervals.sort();assert intervals[0][0]==0 and intervals[-1][1]==length
    assert all(a[1]==b[0] for a,b in zip(intervals,intervals[1:]))
    if POSITION_BUFFER in tensors:
        start,end=tensors[POSITION_BUFFER]['data_offsets']
        with path.open('rb') as stream:
            stream.seek(8+size+start);values=stream.read(end-start)
        assert values==struct.pack('<514q',*range(514))
    return tensors,8+size


def frozen_hash(path,names):
    tensors,prefix=header(path)
    assert len(names)==len(set(names)) and set(names)<=set(tensors) and POSITION_BUFFER not in names
    digest=hashlib.sha256()
    with path.open('rb') as stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as mapped:
        with memoryview(mapped) as buffer:
            for name in sorted(names):
                spec=tensors[name];assert spec['dtype']=='F32'
                metadata=dict(name=name,shape=spec['shape'],dtype='torch.float32')
                digest.update(json.dumps(metadata,sort_keys=True).encode()+b'\0')
                start,end=spec['data_offsets'];digest.update(buffer[prefix+start:prefix+end])
    return digest.hexdigest()


def audit(out=OUT):
    receipt=audit_receipts(out,verify_weights=False)
    protocol=json.loads((out/'protocol.json').read_text());recipe=protocol['trainability']
    names=['research/audit_tool_relation_weights.py','research/audit_tool_relation_support.py',
        'research/audit_tool_role_support.py','research/audit_tool_relation_supervision.py','research/audit_tool_relations.py']
    sources={name:sha(ROOT/name) for name in names}
    snapshot=Path.home()/'.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1/snapshots'/protocol['model']['revision']
    original=snapshot/'model.safetensors';assert sha(original)==protocol['model']['files']['model.safetensors']
    assert frozen_hash(original,recipe['frozen_names'])==recipe['frozen_parameter_sha256']
    for seed in protocol['seeds']:
        meta=json.loads((out/f'seed-{seed}/training_meta.json').read_text());path=ROOT/meta['weights_path']
        assert sha(path)==meta['weights_sha256']
        assert frozen_hash(path,recipe['frozen_names'])==recipe['frozen_parameter_sha256']
        tensors,unused=header(path)
        parameters={name:spec for name,spec in tensors.items() if name!=POSITION_BUFFER}
        assert set(parameters)==set(recipe['frozen_names'])|set(recipe['trainable_names'])
        assert sum(math.prod(spec['shape']) for spec in parameters.values())==recipe['total_parameters']
        assert sum(math.prod(parameters[name]['shape']) for name in recipe['trainable_names'])==recipe['trainable_parameters']
        assert parameters['classifier.out_proj.weight']['shape']==[3,384]
    target=out/'audit-weight-sources-v2'
    if target.exists():
        for name,expected in sources.items():assert sha(target/name)==expected
    else:
        for name in sources:
            destination=target/name;destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes((ROOT/name).read_bytes())
    return dict(**{k:v for k,v in receipt.items() if k not in ['private_weight_hashes_verified','frozen_parameters_independently_verified']},
        private_weight_hashes_verified=True,frozen_parameters_independently_verified=True,
        known_upstream_integer_position_buffer_verified=True,additive_audit_sources=sources,
        training_protocol_or_sources_changed=False,quality_criteria_changed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=OUT)
    args=parser.parse_args();print(json.dumps(audit(args.out),indent=2))
