"""Fixed trusted varied-state Retry/UDP/Git worker, separate from v1 receipts.

Only bounded seed/count enters this module. Expected retry exhaustion is measured;
capture errors fail the whole request. UDP prefix reads do not imply packet loss.
Git staged deletions are HEAD/index changes even when absent from current index.
"""

import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import random
import socket
import sys
import tempfile
import time

from research.tool_measurement_worker import validate_request
from research.tool_relation_worker import parse_status,git_command


def require_worker():
    expected='/usr/local/lib/python3.13/site-packages/research/tool_relation_state_worker.py'
    if (os.environ.get('LCC_TOOL_RELATION_STATE_WORKER')!='1' or not Path('/.dockerenv').is_file()
            or str(Path(__file__).resolve())!=expected):
        raise RuntimeError('Varied states require the separate confined trusted worker')


def retry_fields(raw):
    attempts,sleeps=raw['attempts'],raw['sleeps'];outcome=raw['outcome']
    if (outcome not in ('success','exhausted') or not 1<=len(attempts)<=6
            or [a['number'] for a in attempts]!=list(range(1,len(attempts)+1))
            or any(type(a['failed']) is not bool for a in attempts)
            or [a['failed'] for a in attempts]!=[True]*(len(attempts)-1)+[outcome=='exhausted']
            or len(sleeps)!=len(attempts)-1 or raw['statistics']['attempt_number']!=len(attempts)):
        raise ValueError('Complete success or expected exhausted retry trace required')
    times=[raw['before_ns']]+[a['at_ns'] for a in attempts]+[raw['after_ns']]
    if any(type(v) is not int or v<0 for v in times) or times!=sorted(times):
        raise ValueError('Ordered retry monotonic timestamps required')
    planned=actual=0
    for i,sleep in enumerate(sleeps):
        seconds=sleep['seconds'];before=sleep['before_ns'];after=sleep['after_ns']
        if (type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0<seconds<=.005
                or type(before) is not int or type(after) is not int
                or not attempts[i]['at_ns']<=before<=after<=attempts[i+1]['at_ns']):
            raise ValueError('Bounded inter-attempt sleep event required')
        planned+=round(seconds*1e9);actual+=after-before
    idle=raw['statistics']['idle_for'];elapsed=raw['after_ns']-raw['before_ns']
    if (type(idle) not in (int,float) or not math.isfinite(idle)
            or abs(round(idle*1e9)-planned)>len(sleeps) or actual>elapsed):
        raise ValueError('Scheduled and measured waits disagree with retry statistics')
    return dict(retry_attempts=len(attempts),retry_failures=sum(a['failed'] for a in attempts),
        retry_sleep_calls=len(sleeps),retry_scheduled_sleep_ns=planned,
        retry_actual_sleep_ns=actual,retry_elapsed_ns=elapsed)


def udp_fields(raw):
    sends,receives=raw['send_events'],raw['receive_events'];limit=raw['read_limit']
    if type(limit) is not int or not 1<=len(sends)<=8 or not 0<=limit<=len(sends) or len(receives)!=limit:
        raise ValueError('Complete bounded send and prefix-read observation required')
    for events in [sends,receives]:
        for event in events:
            payload=bytes.fromhex(event['payload_hex'])
            if type(event['bytes']) is not int or len(payload)!=event['bytes'] or len(payload)>256:
                raise ValueError('Actual datagram payload length mismatch')
    if [e['payload_hex'] for e in receives]!=[e['payload_hex'] for e in sends[:limit]]:
        raise ValueError('Unexpected UDP prefix/source observation')
    return dict(udp_sent_datagrams=len(sends),udp_received_datagrams=len(receives),
        udp_sent_payload_bytes=sum(e['bytes'] for e in sends),
        udp_received_payload_bytes=sum(e['bytes'] for e in receives))


def git_fields(raw):
    def names(value):
        if not isinstance(value,str) or value and not value.endswith('\0'):
            raise ValueError('Complete null-separated Git paths required')
        values=value.split('\0')[:-1]
        if len(values)!=len(set(values)):raise ValueError('Duplicate Git paths')
        return set(values)
    head=names(raw['head_paths_stdout']);index=names(raw['index_stdout'])
    other=names(raw['untracked_stdout']);ignored=names(raw['ignored_stdout'])
    states=dict((p,s) for s,p in parse_status(raw['status_stdout']))
    if (index&other or index&ignored or other&ignored
            or {p for p,s in states.items() if s=='??'}!=other
            or {p for p,s in states.items() if s=='!!'}!=ignored):
        raise ValueError('Git index and other/ignored paths disagree')
    changed={p:s for p,s in states.items() if s not in {'??','!!'}}
    if set(changed)-head-index:raise ValueError('Changed path absent from both HEAD and index')
    if ({p for p,s in changed.items() if s[0]=='D'}!=head-index
            or {p for p,s in changed.items() if s[0]=='A'}!=index-head
            or any(s[1]!=' ' and p not in index for p,s in changed.items())):
        raise ValueError('Staged addition/deletion or worktree state disagrees with index')
    content={p:bytes.fromhex(v) for p,v in raw['current_file_hex'].items()}
    missing={p for p,s in changed.items() if s[1]=='D'}
    if set(content)!=(index|other|ignored)-missing:
        raise ValueError('Filesystem paths disagree with current index/status')
    return dict(git_index_files=len(index),git_untracked_files=len(other),git_ignored_files=len(ignored),
        git_index_edits=sum(s[0]!=' ' for s in changed.values()),
        git_worktree_edits=sum(s[1]!=' ' for s in changed.values()),
        git_clean_tracked_files=len(index-set(changed)),
        git_tracked_fs_bytes=sum(len(content[p]) for p in index if p in content),
        git_untracked_fs_bytes=sum(len(content[p]) for p in other))


def observe_retry(rng,index):
    require_worker()
    from tenacity import Retrying,stop_after_attempt,wait_fixed,retry_if_exception_type
    class AuthoredRetryFailure(RuntimeError):pass
    mode=index%3;budget=1 if mode==0 else rng.randint(2,6)
    failures=0 if mode==0 else (budget-1 if mode==1 else budget)
    wait_ms=rng.randint(1,5);attempts=[];sleeps=[]
    def call():
        number=len(attempts)+1;failed=number<=failures
        attempts.append(dict(number=number,failed=failed,at_ns=time.perf_counter_ns()))
        if failed:raise AuthoredRetryFailure('trusted authored operation failure')
        return 'observed success'
    def sleep(seconds):
        before=time.perf_counter_ns();time.sleep(seconds)
        sleeps.append(dict(seconds=float(seconds),before_ns=before,after_ns=time.perf_counter_ns()))
    retry=Retrying(stop=stop_after_attempt(budget),wait=wait_fixed(wait_ms/1000),
                   sleep=sleep,retry=retry_if_exception_type(AuthoredRetryFailure),reraise=True)
    before=time.perf_counter_ns()
    try:result=retry(call);outcome='success';error_type=None
    except AuthoredRetryFailure:
        if mode!=2:raise
        result=None;outcome='exhausted';error_type='AuthoredRetryFailure'
    except Exception as error:
        error.partial=dict(api='tenacity.Retrying',attempts=attempts,sleeps=sleeps,
            statistics=dict(retry.statistics),before_ns=before,after_ns=time.perf_counter_ns(),outcome='capture_error')
        raise
    after=time.perf_counter_ns()
    raw=dict(api='tenacity.Retrying',attempts=attempts,sleeps=sleeps,statistics=dict(retry.statistics),
        before_ns=before,after_ns=after,result=result,outcome=outcome,error_type=error_type,
        authored=dict(attempt_budget=budget,failed_calls=failures,wait_ms=wait_ms,mode=mode))
    try:values=retry_fields(raw)
    except Exception as error:error.partial=raw;raise
    assert values['retry_attempts']==budget and values['retry_failures']==failures
    assert values['retry_scheduled_sleep_ns']==(budget-1)*wait_ms*1000000
    return values,raw


def observe_udp(rng,index):
    require_worker();payloads=[b'']+[rng.randbytes(rng.randint(1,256)) for i in range(rng.randint(1,7))]
    mode=index%3;limit=len(payloads) if mode==0 else (rng.randint(1,len(payloads)-1) if mode==1 else 0)
    sends=[];receives=[];source=destination=None
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver,socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sender:
            receiver.settimeout(1);sender.settimeout(1);receiver.bind(('127.0.0.1',0));sender.bind(('127.0.0.1',0))
            source=list(sender.getsockname());destination=list(receiver.getsockname())
            for i,payload in enumerate(payloads):
                count=sender.sendto(payload,tuple(destination))
                sends.append(dict(index=i,payload_hex=payload.hex(),bytes=count,at_ns=time.perf_counter_ns()))
            for i in range(limit):
                payload,address=receiver.recvfrom(4096)
                if list(address)!=source:raise ValueError('Unexpected loopback UDP source')
                receives.append(dict(index=i,payload_hex=payload.hex(),bytes=len(payload),from_address=list(address),at_ns=time.perf_counter_ns()))
    except Exception as error:
        error.partial=dict(api='socket.sendto/recvfrom',source=source,destination=destination,
                           read_limit=limit,send_events=sends,receive_events=receives,capture_complete=False)
        raise
    raw=dict(api='socket.sendto/recvfrom',source=source,destination=destination,send_events=sends,
        receive_events=receives,read_limit=limit,authored=dict(payloads=[p.hex() for p in payloads],read_limit=limit,mode=mode),
        scope='Prefix-budget application receives; unread queued sends are unobserved, not proven lost. UDP payload/datagram, not IP/wire.')
    try:values=udp_fields(raw)
    except Exception as error:error.partial=raw;raise
    return values,raw


def observe_git(rng,index):
    require_worker();records=[]
    with tempfile.TemporaryDirectory(prefix='git-states-',dir='/tmp') as directory:
        base=Path(directory)
        def command(args):
            try:result=git_command(args,directory)
            except Exception as error:
                error.partial=dict(api='git status/ls-files/ls-tree',commands=records,failed_arguments=args,capture_complete=False)
                raise
            records.append(result);return result['stdout']
        command(['init','--quiet','--template=','--initial-branch=main','--object-format=sha1'])
        slots=['slot one.txt','slot\ntwo.txt','slot-three.txt','slot-four.txt','slot-five.txt','slot-six.txt']
        baseline={'.gitignore':b'ignored-*.tmp\n',**{name:rng.randbytes(rng.randint(2,96)) for name in slots}}
        baseline.update({f'clean-{i}.txt':rng.randbytes(rng.randint(2,96)) for i in range(rng.randint(0,4))})
        for name,content in baseline.items():(base/name).write_bytes(content)
        command(['add','--',*sorted(baseline)])
        command(['commit','--quiet','--no-gpg-sign','-m','trusted varied state'])
        mode=index%8;actions={p:'clean' for p in slots}
        if mode==1:actions.update({p:'staged_modified' for p in slots[:rng.randint(1,3)]})
        elif mode==2:actions.update({p:'worktree_modified' for p in slots[:rng.randint(1,4)]})
        elif mode==3:actions.update(dict(zip(slots,['both_modified','staged_modified','worktree_modified','worktree_deleted','clean','clean'])))
        elif mode==4:actions.update({p:'index_deleted' for p in slots[:rng.randint(1,3)]})
        elif mode==5:actions.update({slots[0]:'staged_modified',slots[1]:'worktree_deleted'})
        elif mode==6:actions.update(dict(zip(slots,['both_modified','index_deleted','worktree_deleted','staged_modified','worktree_modified','clean'])))
        elif mode==7:actions.update({p:rng.choice(['staged_modified','worktree_modified','both_modified']) for p in slots})
        indexed=dict(baseline);staged=[]
        removals=[p for p,a in actions.items() if a=='index_deleted']
        if removals:
            command(['rm','--quiet','--',*sorted(removals)])
            for p in removals:indexed.pop(p)
        for p,a in actions.items():
            if a in ['staged_modified','both_modified']:
                value=b'staged '+rng.randbytes(rng.randint(2,48));(base/p).write_bytes(value)
                indexed[p]=value;staged.append(p)
        additions={f'staged-new-{i}.txt':rng.randbytes(rng.randint(2,64)) for i in range(rng.randint(1,2) if mode in [5,6] else 0)}
        for p,value in additions.items():(base/p).write_bytes(value);indexed[p]=value;staged.append(p)
        if staged:command(['add','--',*sorted(staged)])
        for p,a in actions.items():
            if a in ['worktree_modified','both_modified']:(base/p).write_bytes(b'worktree '+rng.randbytes(rng.randint(2,48)))
            elif a=='worktree_deleted':(base/p).unlink()
        other={f'untracked {i}.txt':rng.randbytes(rng.randint(1,120)) for i in range(rng.randint(0,6))}
        ignored={f'ignored-{i}.tmp':rng.randbytes(rng.randint(1,80)) for i in range(rng.randint(0,3))}
        for p,value in {**other,**ignored}.items():(base/p).write_bytes(value)
        status=command(['status','--porcelain=v1','-z','--untracked-files=all','--ignored=matching'])
        index_paths=command(['ls-files','--cached','-z'])
        untracked=command(['ls-files','--others','--exclude-standard','-z'])
        excluded=command(['ls-files','--others','--ignored','--exclude-standard','-z'])
        head_tree=command(['ls-tree','-r','-z','HEAD']);index_stage=command(['ls-files','--stage','-z'])
        head_paths=''.join(entry.split('\t',1)[1]+'\0' for entry in head_tree.split('\0')[:-1])
        current={p.name:p.read_bytes().hex() for p in base.iterdir() if p.is_file()}
    authored=dict(mode=mode,actions=actions,baseline_file_hex={p:v.hex() for p,v in baseline.items()},
        index_file_hex={p:v.hex() for p,v in indexed.items()},staged_additions={p:v.hex() for p,v in additions.items()},
        untracked_file_hex={p:v.hex() for p,v in other.items()},ignored_file_hex={p:v.hex() for p,v in ignored.items()},current_file_hex=current)
    raw=dict(api='git status/ls-files/ls-tree',status_stdout=status,index_stdout=index_paths,
        untracked_stdout=untracked,ignored_stdout=excluded,head_tree_stdout=head_tree,index_stage_stdout=index_stage,
        head_paths_stdout=head_paths,current_file_hex=current,commands=records,authored=authored)
    try:values=git_fields(raw)
    except Exception as error:error.partial=raw;raise
    return values,raw


def measured_fixture(seed,index):
    require_worker();rng=random.Random(f'relation-states-v2:{seed}:{index}');fields={};raw={}
    for name,observe in [('retry',observe_retry),('udp',observe_udp),('git',observe_git)]:
        try:values,observation=observe(rng,index);fields.update(values);raw[name]=observation
        except Exception as error:
            preserved=ValueError(f'Varied-state capture failed: {name}: {type(error).__name__}: {error}')
            preserved.partial=dict(index=index,fields=fields,raw_observations=raw,failed_source=name,
                partial_source=getattr(error,'partial',None),all_reference_checks_passed=False)
            raise preserved from error
    authored={name:raw[name]['authored'] for name in ['retry','udp','git']}
    content=json.dumps(authored,sort_keys=True)
    assert len(fields)==18 and all(type(v) is int and v>=0 for v in fields.values())
    return dict(index=index,fixture_content=content,fixture_content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        fields=fields,raw_observations=raw,all_reference_checks_passed=True,scope='Actual authored varied tool states; not production/P2')


def main():
    require_worker();request=validate_request(json.load(sys.stdin));fixtures=[]
    versions=dict(git=git_command(['--version'],'/tmp')['stdout'].strip(),tenacity=importlib.metadata.version('tenacity'))
    try:
        for index in range(request['fixtures']):fixtures.append(measured_fixture(request['seed'],index))
    except Exception as error:
        print(json.dumps(dict(schema='trusted-tool-relation-states/0.2',request=request,versions=versions,
            fixtures=fixtures,partial_fixture=getattr(error,'partial',None),all_reference_checks_passed=False,
            error_type=type(error).__name__,error=str(error)),allow_nan=False),flush=True)
        raise
    print(json.dumps(dict(schema='trusted-tool-relation-states/0.2',request=request,versions=versions,python=sys.version,
        fixtures=fixtures,all_reference_checks_passed=True),allow_nan=False))


if __name__=='__main__':main()
