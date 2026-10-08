"""Versioned v3 capture path: producer-side per-observation metadata.

Wraps the unchanged v2 trusted observers (research/tool_relation_state_worker.py).
Each record carries a wall-clock UTC time read from the system clock right after
its source was observed, and field/unit from the collector schema below. Records
missing any slot convert to UNKNOWN blocks; nothing is fabricated or dropped.
"""

from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
import random
import re
import sys

from research import tool_relation_state_worker as v2

SCHEMA='trusted-tool-relation-states-metadata/0.3'
CLOCK='system_wall_utc'
LEVEL='INFO'  # producer-declared: only fully measured observations are emitted; capture errors fail the request with a partial receipt
# Collector schema: exactly the keys retry_fields/udp_fields/git_fields return, with the unit each one counts.
FIELD_UNITS={
    'retry':dict(retry_attempts='count',retry_failures='count',retry_sleep_calls='count',
        retry_scheduled_sleep_ns='ns',retry_actual_sleep_ns='ns',retry_elapsed_ns='ns'),
    'udp':dict(udp_sent_datagrams='count',udp_received_datagrams='count',
        udp_sent_payload_bytes='bytes',udp_received_payload_bytes='bytes'),
    'git':dict(git_index_files='count',git_untracked_files='count',git_ignored_files='count',
        git_index_edits='count',git_worktree_edits='count',git_clean_tracked_files='count',
        git_tracked_fs_bytes='bytes',git_untracked_fs_bytes='bytes'),
}
SLOTS=('time','level','entity','field','value','unit')
_TIME=re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z')


def utc_now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def capture_fixture(seed,index,*,clock=utc_now):
    rng=random.Random(f'relation-states-v3:{seed}:{index}')
    entity='tool-'+hashlib.sha256(f'relation-states-v3:{seed}:{index}'.encode()).hexdigest()[:12]
    observations=[];raw={}
    for name,units in FIELD_UNITS.items():
        try:
            values,raw[name]=getattr(v2,f'observe_{name}')(rng,index);at=clock()
            if set(values)!=set(units):raise ValueError(f'Collector schema drift: {name}')
        except Exception as error:
            raw.pop(name,None)  # failed source is kept only as partial_source, mirroring v2
            preserved=ValueError(f'Varied-state capture failed: {name}: {type(error).__name__}: {error}')
            preserved.partial=dict(index=index,entity=entity,observations=observations,raw_observations=raw,
                failed_source=name,partial_source=getattr(error,'partial',None),all_reference_checks_passed=False)
            raise preserved from error
        observations+=[dict(time=at,level=LEVEL,entity=entity,field=f,value=values[f],unit=u,clock=CLOCK,source=name)
                       for f,u in units.items()]
    content=json.dumps({name:raw[name]['authored'] for name in FIELD_UNITS},sort_keys=True)
    return dict(index=index,entity=entity,fixture_content=content,
                fixture_content_sha256=hashlib.sha256(content.encode()).hexdigest(),
                observations=observations,raw_observations=raw,all_reference_checks_passed=True)


def to_observation_blocks(records):
    """Deterministic v3 record -> rank_observations block; any missing slot keeps the block UNKNOWN."""
    blocks=[]
    for i,r in enumerate(records):
        missing=[k for k in SLOTS if r.get(k) is None]
        if r.get('clock')!=CLOCK or not isinstance(r.get('time'),str) or not _TIME.fullmatch(r['time']):
            missing=sorted(set(missing)|{'time'})
        present={k:r[k] for k in SLOTS if k not in missing}
        # ponytail: an incomplete JSON object fails the engine's exact six-key grammar -> UNKNOWN/KEEP
        blocks.append(dict(id=f'obs-{i}',text=json.dumps(present,sort_keys=True),
                           status='UNKNOWN' if missing else 'COMPLETE',missing=missing))
    return blocks


def main():
    # Same receipt shape as v2 main: provenance always, partial receipt printed before re-raising.
    v2.require_worker();request=v2.validate_request(json.load(sys.stdin));fixtures=[]
    versions=dict(git=v2.git_command(['--version'],'/tmp')['stdout'].strip(),tenacity=importlib.metadata.version('tenacity'))
    try:
        for index in range(request['fixtures']):fixtures.append(capture_fixture(request['seed'],index))
    except Exception as error:
        print(json.dumps(dict(schema=SCHEMA,request=request,versions=versions,python=sys.version,fixtures=fixtures,
            partial_fixture=getattr(error,'partial',None),all_reference_checks_passed=False,
            error_type=type(error).__name__,error=str(error)),allow_nan=False),flush=True)
        raise
    print(json.dumps(dict(schema=SCHEMA,request=request,versions=versions,python=sys.version,
        fixtures=fixtures,all_reference_checks_passed=True),allow_nan=False))

if __name__=='__main__':main()
