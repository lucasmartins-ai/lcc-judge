"""Independent stdlib replay of saved actual-tool observations, no worker imports."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

DEFAULT=Path(__file__).resolve().parent/'goal-engine-2026-10-04/tool-relations-grounded-v1/calibration'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recount(fixture):
    raw=fixture['raw_observations'];result={}
    retry=raw['retry'];attempts=retry['attempts'];sleeps=retry['sleeps'];stats=retry['statistics']
    assert 1<=len(attempts)<=6 and len(sleeps)==len(attempts)-1
    assert [a['number'] for a in attempts]==list(range(1,len(attempts)+1))
    assert all(type(a['failed']) is bool for a in attempts)
    assert [a['failed'] for a in attempts]==[True]*(len(attempts)-1)+[False]
    assert stats['attempt_number']==len(attempts)
    assert retry['before_ns']<=attempts[0]['at_ns']<=attempts[-1]['at_ns']<=retry['after_ns']
    actual=scheduled=0
    for i,event in enumerate(sleeps):
        assert type(event['seconds']) in (int,float) and math.isfinite(event['seconds']) and 0<event['seconds']<=.005
        assert attempts[i]['at_ns']<=event['before_ns']<=event['after_ns']<=attempts[i+1]['at_ns']
        actual+=event['after_ns']-event['before_ns'];scheduled+=round(event['seconds']*1e9)
    assert abs(round(stats['idle_for']*1e9)-scheduled)<=len(sleeps)
    assert retry['result']=='observed success'
    assert len(attempts)==retry['authored']['failures']+1
    assert scheduled==retry['authored']['failures']*retry['authored']['wait_ms']*1000000
    elapsed=retry['after_ns']-retry['before_ns'];assert 0<=actual<=elapsed
    result.update(retry_attempts=len(attempts),retry_failures=sum(a['failed'] for a in attempts),
                  retry_sleep_calls=len(sleeps),retry_scheduled_sleep_ns=scheduled,
                  retry_actual_sleep_ns=actual,retry_elapsed_ns=elapsed)
    udp=raw['udp'];events=udp['events'];assert 1<=len(events)<=8
    assert udp['source'][0]==udp['destination'][0]=='127.0.0.1'
    assert all(type(p) is int and 0<p<=65535 for p in [udp['source'][1],udp['destination'][1]])
    assert [event['sent_hex'] for event in events]==udp['sent_payloads']
    sent=received=0
    for event in events:
        left=bytes.fromhex(event['sent_hex']);right=bytes.fromhex(event['received_hex'])
        assert left==right and len(left)<=256
        assert type(event['sent_bytes']) is int and event['sent_bytes']==len(left)
        assert type(event['received_bytes']) is int and event['received_bytes']==len(right)
        assert event['from_address']==udp['source'];sent+=len(left);received+=len(right)
    assert any(event['sent_hex']=='' for event in events)
    result.update(udp_sent_datagrams=len(events),udp_received_datagrams=len(events),
                  udp_sent_payload_bytes=sent,udp_received_payload_bytes=received)
    git=raw['git'];commands=git['commands']
    assert len(commands)==8 and all(c['returncode']==0 and not c['stderr'] for c in commands)
    for c in commands:
        assert c['argv'][:7]==['/usr/bin/git','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','-c','core.autocrlf=false']
    for i,key,command in [(4,'status_stdout','status'),(5,'index_stdout','ls-files'),
                         (6,'untracked_stdout','ls-files'),(7,'ignored_stdout','ls-files')]:
        assert commands[i]['argv'][7]==command and commands[i]['stdout']==git[key]
    def paths(text):
        assert text.endswith('\0');tokens=text.split('\0')[:-1]
        assert len(tokens)==len(set(tokens));return set(tokens)
    index=paths(git['index_stdout']);untracked=paths(git['untracked_stdout']);ignored=paths(git['ignored_stdout'])
    status=git['status_stdout'];assert status.endswith('\0')
    status_rows=status.split('\0')[:-1];states={}
    for entry in status_rows:
        assert len(entry)>=4 and entry[2]==' ' and entry[3:] not in states
        state=entry[:2];assert state in {'M ',' M','MM',' D','??','!!'}
        states[entry[3:]]=state
    assert {p for p,s in states.items() if s=='??'}==untracked
    assert {p for p,s in states.items() if s=='!!'}==ignored
    assert not(index&untracked or index&ignored or untracked&ignored)
    changed={p:s for p,s in states.items() if s not in {'??','!!'}}
    assert set(changed)<=index
    content={name:bytes.fromhex(value) for name,value in git['current_file_hex'].items()}
    assert set(content)==(index|untracked|ignored)-{p for p,s in changed.items() if s[1]=='D'}
    assert git['authored']['current_file_hex']==git['current_file_hex']
    assert index==set(git['authored']['baseline_file_hex'])
    assert untracked==set(git['authored']['untracked_file_hex']) and ignored==set(git['authored']['ignored_file_hex'])
    assert changed=={'staged name.txt':'M ','unstaged name.txt':' M','both\nname.txt':'MM','removed.txt':' D'}
    result.update(git_index_files=len(index),git_untracked_files=len(untracked),git_ignored_files=len(ignored),
        git_index_edits=sum(s[0]!=' ' for s in changed.values()),git_worktree_edits=sum(s[1]!=' ' for s in changed.values()),
        git_clean_tracked_files=len(index)-len(changed),git_tracked_fs_bytes=sum(len(content[p]) for p in index if p in content),
        git_untracked_fs_bytes=sum(len(content[p]) for p in untracked))
    authored=dict(retry=retry['authored'],udp_payloads=udp['sent_payloads'],git=git['authored'])
    assert json.loads(fixture['fixture_content'])==authored
    assert sha_text(fixture['fixture_content'])==fixture['fixture_content_sha256']
    assert fixture['all_reference_checks_passed'] is True
    assert len(result)==18 and all(type(v) is int and v>=0 for v in fixture['fields'].values())
    assert fixture['fields']==result
    return result


def sha_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def audit(out=DEFAULT):
    protocol=json.loads((out/'protocol.json').read_text());raw=json.loads((out/'raw.json').read_text())
    assert digest({k:v for k,v in protocol.items() if k!='sha256'})==protocol['sha256']
    for name,expected in protocol['sources'].items():assert sha(out/'sources'/name)==expected
    worker_sources={name:sha(out/'sources'/name) for name in protocol['worker_sources']}
    assert worker_sources==protocol['worker_sources']
    assert digest(dict(sources=worker_sources,dependencies=protocol['dependencies']))==protocol['runtime']['source_sha256']
    assert digest(protocol['dependencies'])==protocol['runtime']['dependency_sha256']
    began=json.loads((out/'started.json').read_text());ended=json.loads((out/'completion.json').read_text())
    assert began['protocol_sha256']==ended['protocol_sha256']==protocol['sha256']
    assert datetime.fromisoformat(protocol['frozen_at_utc'])<=datetime.fromisoformat(began['at_utc'])<=datetime.fromisoformat(ended['finished_at_utc'])
    assert ended['raw_sha256']==sha(out/'raw.json') and ended['status']==raw['status']=='MEASURED'
    assert ended['no_retry'] is True and ended['admission'] is False
    assert raw['returncode']==0 and raw['error'] is None and raw['host_measurement_executed'] is False
    assert raw['runtime']==protocol['runtime'] and raw['profile']=='trusted-tool-relations/0.1'
    request=protocol['request'];assert raw['request']==request
    assert raw['request_sha256']==hashlib.sha256(json.dumps(request,allow_nan=False).encode()).hexdigest()
    argv=raw['container_argv']
    for flag in ['--pull=never','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=64',
                 '--memory=256m','--memory-swap=256m','--cpus=1','--user=65534:65534','LCC_TOOL_RELATION_WORKER=1']:
        assert flag in argv
    assert not any(a in {'-v','--volume','--mount','--privileged','--env-file'} for a in argv)
    assert argv[-5:]==[protocol['runtime']['image_id'],'python','-I','-m','research.tool_relation_worker']
    measurements=json.loads(raw['stdout']);assert measurements==raw['measurements']
    assert measurements['request']==request and measurements['all_reference_checks_passed'] is True
    assert measurements['versions']==dict(git='git version 2.47.3',tenacity='9.1.4')
    fixtures=measurements['fixtures'];assert len(fixtures)==request['fixtures']
    assert [f['index'] for f in fixtures]==list(range(request['fixtures']))
    all_fields=[recount(fixture) for fixture in fixtures]
    assert len({f['fixture_content_sha256'] for f in fixtures})==len(fixtures)
    return dict(status='PASS',protocol_sha256=protocol['sha256'],raw_sha256=ended['raw_sha256'],
        fixtures=len(fixtures),fields_per_fixture=18,verified_fields=18*len(fixtures),
        source_image_dependency_and_raw_fields_verified=True,versions=measurements['versions'],
        observed_capture_wall_s=raw['elapsed_s'],minimum_datagrams=min(f['udp_received_datagrams'] for f in all_fields),
        empty_datagram_checked_in_each_fixture=True,model_forwards=0,API_calls=0,P2_admission=False,default_changed=False,
        tools_reexecuted_during_audit=False,admission=False,
        scope=protocol['scope']+'; saved authored fixtures/actual tool receipts, not independent production/P2 certification')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=DEFAULT)
    args=parser.parse_args();print(json.dumps(audit(args.out),indent=2,allow_nan=False))
