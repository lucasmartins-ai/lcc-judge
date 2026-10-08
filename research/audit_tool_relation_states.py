"""Independent stdlib recount of varied-state tool receipts, without tool calls."""

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re

DEFAULT=Path(__file__).resolve().parent/'goal-engine-2026-10-04/tool-relation-states-v2/calibration'


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def paths(text):
    assert isinstance(text,str) and (not text or text.endswith('\0'))
    values=text.split('\0')[:-1];assert len(values)==len(set(values)) and all(values)
    return set(values)


def git_blob(hex_content):
    content=bytes.fromhex(hex_content)
    return hashlib.sha1(f'blob {len(content)}\0'.encode()+content).hexdigest()


def object_rows(text,head=False):
    assert not text or text.endswith('\0');result={}
    for record in text.split('\0')[:-1]:
        left,path=record.split('\t',1);mode,middle,last=left.split(' ')
        assert path and path not in result and mode=='100644'
        if head:assert middle=='blob';oid=last
        else:assert last=='0';oid=middle
        assert re.fullmatch('[0-9a-f]{40}',oid);result[path]=oid
    return result


def recount_git(raw):
    authored=raw['authored'];head=object_rows(raw['head_tree_stdout'],True);index=object_rows(raw['index_stage_stdout'])
    assert raw['head_paths_stdout']==''.join(p+'\0' for p in head)
    assert paths(raw['index_stdout'])==set(index)
    assert {p:git_blob(v) for p,v in authored['baseline_file_hex'].items()}==head
    assert {p:git_blob(v) for p,v in authored['index_file_hex'].items()}==index
    assert raw['current_file_hex']==authored['current_file_hex']
    current=raw['current_file_hex'];other=paths(raw['untracked_stdout']);ignored=paths(raw['ignored_stdout'])
    assert not (set(index)&other or set(index)&ignored or other&ignored)
    assert other==set(authored['untracked_file_hex']) and ignored==set(authored['ignored_file_hex'])
    for group in ['untracked_file_hex','ignored_file_hex']:
        assert {p:current[p] for p in authored[group]}==authored[group]
    expected={}
    for path in set(head)|set(index):
        x=('A' if path not in head else 'D' if path not in index else 'M' if head[path]!=index[path] else ' ')
        y=(' ' if path not in index else 'D' if path not in current else 'M' if git_blob(current[path])!=index[path] else ' ')
        if x+y!='  ':expected[path]=x+y
    expected.update({p:'??' for p in other});expected.update({p:'!!' for p in ignored})
    status=raw['status_stdout'];assert not status or status.endswith('\0');actual={}
    for entry in status.split('\0')[:-1]:
        assert len(entry)>=4 and entry[2]==' ' and entry[3:] not in actual
        actual[entry[3:]]=entry[:2]
    assert actual==expected
    deleted={p for p,s in expected.items() if s[1]=='D'}
    assert set(current)==(set(index)|other|ignored)-deleted
    changed={p:s for p,s in expected.items() if s not in {'??','!!'}}
    for hex_content in current.values():bytes.fromhex(hex_content)
    return dict(git_index_files=len(index),git_untracked_files=len(other),git_ignored_files=len(ignored),
        git_index_edits=sum(s[0]!=' ' for s in changed.values()),git_worktree_edits=sum(s[1]!=' ' for s in changed.values()),
        git_clean_tracked_files=len(set(index)-set(changed)),
        git_tracked_fs_bytes=sum(len(bytes.fromhex(current[p])) for p in index if p in current),
        git_untracked_fs_bytes=sum(len(bytes.fromhex(current[p])) for p in other))


def recount(fixture):
    observations=fixture['raw_observations'];retry=observations['retry'];attempts=retry['attempts'];sleeps=retry['sleeps']
    source=retry['authored'];budget=source['attempt_budget'];failures=source['failed_calls'];wait=source['wait_ms']
    mode=fixture['index']%3
    assert source['mode']==mode and type(budget) is int and 1<=budget<=6 and type(wait) is int and 1<=wait<=5
    assert failures==(0 if mode==0 else budget-1 if mode==1 else budget)
    assert (mode!=0 or budget==1) and len(attempts)==budget and len(sleeps)==budget-1
    outcome='exhausted' if mode==2 else 'success';assert retry['outcome']==outcome
    assert retry['result']==(None if mode==2 else 'observed success')
    assert retry['error_type']==('AuthoredRetryFailure' if mode==2 else None)
    assert [a['number'] for a in attempts]==list(range(1,budget+1))
    assert all(type(a['failed']) is bool for a in attempts)
    assert [a['failed'] for a in attempts]==[True]*(budget-1)+[mode==2]
    times=[retry['before_ns']]+[a['at_ns'] for a in attempts]+[retry['after_ns']]
    assert all(type(t) is int and t>=0 for t in times) and times==sorted(times)
    actual=scheduled=0
    for i,sleep in enumerate(sleeps):
        assert type(sleep['seconds']) is float and math.isfinite(sleep['seconds']) and sleep['seconds']==wait/1000
        assert attempts[i]['at_ns']<=sleep['before_ns']<=sleep['after_ns']<=attempts[i+1]['at_ns']
        actual+=sleep['after_ns']-sleep['before_ns'];scheduled+=round(sleep['seconds']*1e9)
    elapsed=retry['after_ns']-retry['before_ns'];assert 0<=actual<=elapsed
    assert retry['statistics']['attempt_number']==budget
    assert abs(round(retry['statistics']['idle_for']*1e9)-scheduled)<=len(sleeps)
    assert scheduled==(budget-1)*wait*1000000
    result=dict(retry_attempts=budget,retry_failures=sum(a['failed'] for a in attempts),retry_sleep_calls=len(sleeps),
        retry_scheduled_sleep_ns=scheduled,retry_actual_sleep_ns=actual,retry_elapsed_ns=elapsed)
    udp=observations['udp'];sends=udp['send_events'];receives=udp['receive_events'];limit=udp['read_limit']
    assert udp['source'][0]==udp['destination'][0]=='127.0.0.1'
    assert all(type(p) is int and 0<p<=65535 for p in [udp['source'][1],udp['destination'][1]])
    assert 2<=len(sends)<=8 and type(limit) is int and 0<=limit<=len(sends) and len(receives)==limit
    assert udp['authored']==dict(payloads=[e['payload_hex'] for e in sends],read_limit=limit,mode=mode)
    assert limit==(len(sends) if mode==0 else 0 if mode==2 else limit)
    if mode==1:assert 0<limit<len(sends)
    assert sends[0]['payload_hex']=='' and sends[0]['bytes']==0
    assert [e['index'] for e in sends]==list(range(len(sends)))
    assert [e['index'] for e in receives]==list(range(len(receives)))
    for events in [sends,receives]:
        assert all(type(e['at_ns']) is int and e['at_ns']>=0 for e in events)
        assert [e['at_ns'] for e in events]==sorted(e['at_ns'] for e in events)
        for event in events:
            payload=bytes.fromhex(event['payload_hex']);assert type(event['bytes']) is int and event['bytes']==len(payload)<=256
    assert [e['payload_hex'] for e in receives]==[e['payload_hex'] for e in sends[:limit]]
    assert all(e['from_address']==udp['source'] for e in receives)
    if receives:assert sends[-1]['at_ns']<=receives[0]['at_ns']
    result.update(udp_sent_datagrams=len(sends),udp_received_datagrams=len(receives),
        udp_sent_payload_bytes=sum(e['bytes'] for e in sends),udp_received_payload_bytes=sum(e['bytes'] for e in receives))
    git=observations['git'];authored=git['authored'];assert authored['mode']==fixture['index']%8
    slots=['slot one.txt','slot\ntwo.txt','slot-three.txt','slot-four.txt','slot-five.txt','slot-six.txt']
    assert set(authored['actions'])==set(slots)
    assert set(authored['actions'].values())<={'clean','staged_modified','worktree_modified','both_modified','worktree_deleted','index_deleted'}
    prefix=['/usr/bin/git','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','-c','core.autocrlf=false']
    arguments=[['init','--quiet','--template=','--initial-branch=main','--object-format=sha1'],
        ['add','--',*sorted(authored['baseline_file_hex'])],['commit','--quiet','--no-gpg-sign','-m','trusted varied state']]
    removals=sorted(p for p,a in authored['actions'].items() if a=='index_deleted')
    staged=sorted([p for p,a in authored['actions'].items() if a in ['staged_modified','both_modified']]+list(authored['staged_additions']))
    if removals:arguments.append(['rm','--quiet','--',*removals])
    if staged:arguments.append(['add','--',*staged])
    tail=[['status','--porcelain=v1','-z','--untracked-files=all','--ignored=matching'],['ls-files','--cached','-z'],
        ['ls-files','--others','--exclude-standard','-z'],['ls-files','--others','--ignored','--exclude-standard','-z'],
        ['ls-tree','-r','-z','HEAD'],['ls-files','--stage','-z']]
    arguments+=tail;assert len(arguments)==len(git['commands'])
    for args,command in zip(arguments,git['commands']):
        assert command['argv']==prefix+args and command['returncode']==0 and command['stderr']==''
    for command,key in zip(git['commands'][-6:],['status_stdout','index_stdout','untracked_stdout','ignored_stdout','head_tree_stdout','index_stage_stdout']):
        assert command['stdout']==git[key]
    result.update(recount_git(git))
    content={name:observations[name]['authored'] for name in ['retry','udp','git']}
    assert json.loads(fixture['fixture_content'])==content
    assert hashlib.sha256(fixture['fixture_content'].encode()).hexdigest()==fixture['fixture_content_sha256']
    assert len(result)==18 and result==fixture['fields'] and all(type(v) is int and v>=0 for v in result.values())
    assert fixture['all_reference_checks_passed'] is True
    return result


def audit(out=DEFAULT):
    p=json.loads((out/'protocol.json').read_text());raw=json.loads((out/'raw.json').read_text())
    assert digest({k:v for k,v in p.items() if k!='sha256'})==p['sha256']
    for name,wanted in p['sources'].items():assert sha(out/'sources'/name)==wanted
    workers={name:sha(out/'sources'/name) for name in p['worker_sources']}
    assert workers==p['worker_sources']
    assert digest(dict(sources=workers,dependencies=p['dependencies']))==p['runtime']['source_sha256']
    assert digest(p['dependencies'])==p['runtime']['dependency_sha256']
    assert p['dependencies']['base']=='python@sha256:3dd7cc108ec1493442514f5c2a871af6af0ec31d768ff6e378a93340c3b3db5f'
    assert p['dependencies']['tenacity_version']=='9.1.4'
    began=json.loads((out/'started.json').read_text());ended=json.loads((out/'completion.json').read_text())
    assert began['protocol_sha256']==ended['protocol_sha256']==p['sha256']
    assert datetime.fromisoformat(p['frozen_at_utc'])<=datetime.fromisoformat(began['at_utc'])<=datetime.fromisoformat(ended['finished_at_utc'])
    assert ended['raw_sha256']==sha(out/'raw.json') and ended['status']==raw['status']=='MEASURED'
    assert ended['no_retry'] is True and ended['admission'] is False
    assert raw['runtime']==p['runtime'] and raw['profile']=='trusted-tool-relation-states/0.2'
    assert raw['returncode']==0 and raw['error'] is None and raw['host_measurement_executed'] is False
    assert raw['request']==p['request'] and raw['request_sha256']==hashlib.sha256(json.dumps(p['request'],allow_nan=False).encode()).hexdigest()
    argv=raw['container_argv']
    for flag in ['--pull=never','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
                 '--pids-limit=64','--memory=256m','--memory-swap=256m','--cpus=1','--user=65534:65534',
                 'LCC_TOOL_RELATION_STATE_WORKER=1','LCC_TOOL_RELATION_WORKER=1']:
        assert flag in argv
    assert not any(a in {'-v','--volume','--mount','--privileged','--env-file','--publish','-p'} for a in argv)
    assert argv[-5:]==[p['runtime']['image_id'],'python','-I','-m','research.tool_relation_state_worker']
    data=json.loads(raw['stdout']);assert data==raw['measurements'] and data['schema']=='trusted-tool-relation-states/0.2'
    assert data['request']==p['request'] and data['all_reference_checks_passed'] is True
    assert data['versions']==dict(git='git version 2.47.3',tenacity='9.1.4')
    fixtures=data['fixtures'];assert len(fixtures)==p['request']['fixtures']
    assert [f['index'] for f in fixtures]==list(range(len(fixtures)))
    values=[recount(f) for f in fixtures]
    assert len({f['fixture_content_sha256'] for f in fixtures})==len(fixtures)
    outcomes=Counter(f['raw_observations']['retry']['outcome'] for f in fixtures)
    reads=Counter(f['raw_observations']['udp']['authored']['mode'] for f in fixtures)
    return dict(status='PASS',protocol_sha256=p['sha256'],raw_sha256=ended['raw_sha256'],fixtures=len(fixtures),
        verified_fields=18*len(fixtures),retry_outcomes=dict(outcomes),udp_read_modes=dict(reads),
        git_index_edits=sorted({v['git_index_edits'] for v in values}),git_worktree_edits=sorted({v['git_worktree_edits'] for v in values}),
        git_clean_tracked=sorted({v['git_clean_tracked_files'] for v in values}),
        git_staged_delete_fixtures=sum(any(s['argv'][7]=='rm' for s in f['raw_observations']['git']['commands']) for f in fixtures),
        zero_observed_receive_fixtures=sum(v['udp_received_datagrams']==0 for v in values),
        actual_git_blob_identities_verified=True,source_image_dependency_and_raw_fields_verified=True,
        observed_capture_wall_s=raw['elapsed_s'],model_forwards=0,API_calls=0,P2_admission=False,default_changed=False,
        tools_reexecuted_during_audit=False,admission=False,
        scope=p['scope']+'; authored actual-tool states, prefix reads not loss, expected exhaustion not capture failure, no production/P2/model quality claim')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=DEFAULT);args=parser.parse_args()
    print(json.dumps(audit(args.out),indent=2,allow_nan=False))
