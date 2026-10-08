"""Actual retry/UDP/Git on authored fixtures in a separate trusted container.

No caller source, command, import, path or address is accepted. Exact seed/count
only; observations never run on host. This does not broaden generated-fixture API.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import random
import socket
import subprocess
import sys
import tempfile
import time

from research.tool_measurement_worker import validate_request


def require_worker():
    expected='/usr/local/lib/python3.13/site-packages/research/tool_relation_worker.py'
    if (os.environ.get('LCC_TOOL_RELATION_WORKER')!='1' or not Path('/.dockerenv').is_file()
            or str(Path(__file__).resolve())!=expected):
        raise RuntimeError('Relations require the confined trusted worker')


def parse_status(text):
    if not isinstance(text,str) or (text and not text.endswith('\0')):
        raise ValueError('Complete porcelain-v1 -z output required')
    result=[]
    for item in text.split('\0')[:-1]:
        if len(item)<4 or item[2]!=' ' or not item[3:]:
            raise ValueError('Malformed status path')
        state=item[:2]
        if state not in {'??','!!'} and (any(c not in ' MAD' for c in state) or state=='  '):
            raise ValueError('Only authored non-rename/non-merge Git states supported')
        result.append((state,item[3:]))
    if len({path for state,path in result})!=len(result):
        raise ValueError('Duplicate Git path status')
    return result


def retry_fields(raw):
    attempts,sleeps=raw['attempts'],raw['sleeps']
    if (not 1<=len(attempts)<=6 or [r['number'] for r in attempts]!=list(range(1,len(attempts)+1))
            or [r['failed'] for r in attempts]!=[True]*(len(attempts)-1)+[False]
            or len(sleeps)!=len(attempts)-1 or raw['statistics']['attempt_number']!=len(attempts)):
        raise ValueError('Retry trace/statistics do not describe a complete success')
    if type(raw['before_ns']) is not int or type(raw['after_ns']) is not int or not 0<=raw['before_ns']<=raw['after_ns']:
        raise ValueError('Ordered monotonic retry timestamps required')
    planned=actual=0
    for item in sleeps:
        seconds=item['seconds']
        if type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0<seconds<=.005:
            raise ValueError('Bounded finite scheduled sleep required')
        if (type(item['before_ns']) is not int or type(item['after_ns']) is not int
                or not raw['before_ns']<=item['before_ns']<=item['after_ns']<=raw['after_ns']):
            raise ValueError('Ordered actual sleep timestamps required')
        planned+=round(seconds*1e9)
        actual+=item['after_ns']-item['before_ns']
    idle=raw['statistics']['idle_for']
    if type(idle) not in (int,float) or not math.isfinite(idle) or abs(round(idle*1e9)-planned)>len(sleeps):
        raise ValueError('Tenacity idle_for is inconsistent with scheduled waits')
    if actual>raw['after_ns']-raw['before_ns']:
        raise ValueError('Sleep duration exceeds whole elapsed time')
    return dict(retry_attempts=len(attempts),retry_failures=len(attempts)-1,retry_sleep_calls=len(sleeps),
                retry_scheduled_sleep_ns=planned,retry_actual_sleep_ns=actual,
                retry_elapsed_ns=raw['after_ns']-raw['before_ns'])


def udp_fields(raw):
    events=raw['events']
    if not 1<=len(events)<=8:
        raise ValueError('Bounded complete local datagram trace required')
    sent=received=0
    for event in events:
        left,right=bytes.fromhex(event['sent_hex']),bytes.fromhex(event['received_hex'])
        if (type(event['sent_bytes']) is not int or type(event['received_bytes']) is not int
                or left!=right or len(left)!=event['sent_bytes'] or len(right)!=event['received_bytes']
                or len(left)>256):
            raise ValueError('Datagram payload observation mismatch')
        sent+=len(left);received+=len(right)
    return dict(udp_sent_datagrams=len(events),udp_received_datagrams=len(events),
                udp_sent_payload_bytes=sent,udp_received_payload_bytes=received)


def git_fields(raw):
    def names(value):
        if value and not value.endswith('\0'):raise ValueError('Complete Git path list required')
        values=value.split('\0')[:-1]
        if len(values)!=len(set(values)):raise ValueError('Duplicate Git path')
        return set(values)
    index=names(raw['index_stdout']);untracked=names(raw['untracked_stdout']);ignored=names(raw['ignored_stdout'])
    pairs=parse_status(raw['status_stdout'])
    if (index&untracked or index&ignored or untracked&ignored
            or {p for s,p in pairs if s=='??'}!=untracked or {p for s,p in pairs if s=='!!'}!=ignored
            or any(p not in index for s,p in pairs if s not in {'??','!!'})):
        raise ValueError('Git index/status/other path lists disagree')
    index_edits={p for s,p in pairs if s not in {'??','!!'} and s[0]!=' '}
    worktree_edits={p for s,p in pairs if s not in {'??','!!'} and s[1]!=' '}
    manifest={name:bytes.fromhex(value) for name,value in raw['current_file_hex'].items()}
    # Deleted worktree files remain indexed while lacking a current file.
    expected=(index|untracked|ignored)-{p for s,p in pairs if s not in {'??','!!'} and s[1]=='D'}
    if set(manifest)!=expected:raise ValueError('Current authored filesystem paths do not match status')
    return dict(git_index_files=len(index),git_untracked_files=len(untracked),git_ignored_files=len(ignored),
                git_index_edits=len(index_edits),git_worktree_edits=len(worktree_edits),
                git_clean_tracked_files=len(index-index_edits-worktree_edits),
                git_tracked_fs_bytes=sum(len(data) for p,data in manifest.items() if p in index),
                git_untracked_fs_bytes=sum(len(data) for p,data in manifest.items() if p in untracked))


def observe_retry(rng):
    require_worker()
    from tenacity import Retrying,stop_after_attempt,wait_fixed,retry_if_exception_type
    failures=rng.randint(1,5);wait_ms=rng.randint(1,5)
    attempts,sleeps=[],[]
    def call():
        number=len(attempts)+1;failed=number<=failures
        attempts.append(dict(number=number,failed=failed,at_ns=time.perf_counter_ns()))
        if failed:raise RuntimeError('authored transient failure')
        return 'observed success'
    def sleep(seconds):
        before=time.perf_counter_ns();time.sleep(seconds);after=time.perf_counter_ns()
        sleeps.append(dict(seconds=float(seconds),before_ns=before,after_ns=after))
    retry=Retrying(stop=stop_after_attempt(failures+1),wait=wait_fixed(wait_ms/1000),
                   sleep=sleep,retry=retry_if_exception_type(RuntimeError),reraise=True)
    before=time.perf_counter_ns();result=retry(call);after=time.perf_counter_ns()
    raw=dict(api='tenacity.Retrying',attempts=attempts,sleeps=sleeps,statistics=dict(retry.statistics),
             before_ns=before,after_ns=after,result=result,authored=dict(failures=failures,wait_ms=wait_ms))
    fields=retry_fields(raw)
    assert fields['retry_attempts']==failures+1 and fields['retry_scheduled_sleep_ns']==failures*wait_ms*1000000
    return fields,raw


def observe_udp(rng):
    require_worker()
    payloads=[b'']+[rng.randbytes(rng.randint(1,256)) for i in range(rng.randint(1,7))]
    events=[]
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver, socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sender:
        receiver.settimeout(1);sender.settimeout(1);receiver.bind(('127.0.0.1',0));sender.bind(('127.0.0.1',0))
        destination=receiver.getsockname();source=sender.getsockname()
        for payload in payloads:
            transmitted=sender.sendto(payload,destination)
            received,address=receiver.recvfrom(4096)
            if address!=source:raise ValueError('Unexpected loopback datagram source')
            events.append(dict(sent_hex=payload.hex(),received_hex=received.hex(),sent_bytes=transmitted,
                               received_bytes=len(received),from_address=list(address)))
    raw=dict(api='socket.sendto/recvfrom',events=events,source=list(source),destination=list(destination),
             sent_payloads=[p.hex() for p in payloads],scope='local UDP payload/datagram observations, not wire/IP packet counters')
    return udp_fields(raw),raw


def git_command(arguments,directory):
    require_worker()
    argv=['/usr/bin/git','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','-c','core.autocrlf=false',*arguments]
    env=dict(PATH='/usr/local/bin:/usr/bin:/bin',LANG='C.UTF-8',LC_ALL='C.UTF-8',
             GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',GIT_ATTR_NOSYSTEM='1',
             GIT_AUTHOR_NAME='Fixture',GIT_AUTHOR_EMAIL='fixture@example.invalid',
             GIT_COMMITTER_NAME='Fixture',GIT_COMMITTER_EMAIL='fixture@example.invalid',
             GIT_AUTHOR_DATE='2000-01-01T00:00:00+0000',GIT_COMMITTER_DATE='2000-01-01T00:00:00+0000')
    result=subprocess.run(argv,cwd=directory,env=env,capture_output=True,text=True,timeout=3)
    if result.returncode or len(result.stdout.encode())+len(result.stderr.encode())>16384:
        raise ValueError(f'Trusted Git command failed: {arguments[0]}')
    return dict(argv=argv,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)


def observe_git(rng):
    require_worker();records=[]
    with tempfile.TemporaryDirectory(prefix='git-relations-',dir='/tmp') as directory:
        base=Path(directory)
        def command(args):
            result=git_command(args,directory);records.append(result);return result['stdout']
        command(['init','--quiet','--template=','--initial-branch=main'])
        baseline={'.gitignore':b'ignored-*.tmp\n','staged name.txt':b'original staged\n',
                  'unstaged name.txt':b'original worktree\n','both\nname.txt':b'original both\n','removed.txt':b'original removed\n'}
        baseline.update({f'clean-{i}.txt':rng.randbytes(rng.randint(1,96)) for i in range(rng.randint(1,5))})
        for name,data in baseline.items():(base/name).write_bytes(data)
        command(['add','--',*sorted(baseline)])
        command(['commit','--quiet','--no-gpg-sign','-m','authored initial state'])
        (base/'staged name.txt').write_bytes(b'changed staged '+rng.randbytes(12))
        (base/'both\nname.txt').write_bytes(b'changed staged both\n')
        command(['add','--','staged name.txt','both\nname.txt'])
        (base/'both\nname.txt').write_bytes(b'changed worktree both '+rng.randbytes(9))
        (base/'unstaged name.txt').write_bytes(b'changed worktree '+rng.randbytes(15))
        (base/'removed.txt').unlink()
        untracked={f'untracked {i}.txt':rng.randbytes(rng.randint(1,120)) for i in range(rng.randint(1,6))}
        ignored={f'ignored-{i}.tmp':rng.randbytes(rng.randint(1,80)) for i in range(rng.randint(1,4))}
        for name,data in {**untracked,**ignored}.items():(base/name).write_bytes(data)
        status=command(['status','--porcelain=v1','-z','--untracked-files=all','--ignored=matching'])
        index=command(['ls-files','--cached','-z'])
        others=command(['ls-files','--others','--exclude-standard','-z'])
        excluded=command(['ls-files','--others','--ignored','--exclude-standard','-z'])
        manifest={path.name:path.read_bytes().hex() for path in base.iterdir() if path.is_file()}
    authored=dict(baseline_file_hex={k:v.hex() for k,v in baseline.items()},untracked_file_hex={k:v.hex() for k,v in untracked.items()},
                  ignored_file_hex={k:v.hex() for k,v in ignored.items()},current_file_hex=manifest)
    raw=dict(api='git status/ls-files',status_stdout=status,index_stdout=index,untracked_stdout=others,
             ignored_stdout=excluded,current_file_hex=manifest,commands=records,authored=authored)
    fields=git_fields(raw)
    assert fields['git_index_files']==len(baseline) and fields['git_untracked_files']==len(untracked)
    assert fields['git_ignored_files']==len(ignored) and fields['git_index_edits']==2 and fields['git_worktree_edits']==3
    assert fields['git_clean_tracked_files']==len(baseline)-4
    return fields,raw


def measured_fixture(seed,index):
    require_worker();rng=random.Random(f'relations:{seed}:{index}')
    fields={};raw={}
    for name,observe in [('retry',observe_retry),('udp',observe_udp),('git',observe_git)]:
        values,observation=observe(rng);fields.update(values);raw[name]=observation
    authored=dict(retry=raw['retry']['authored'],udp_payloads=raw['udp']['sent_payloads'],git=raw['git']['authored'])
    content=json.dumps(authored,sort_keys=True)
    assert len(fields)==18 and all(type(v) is int and v>=0 for v in fields.values())
    return dict(index=index,fixture_content=content,fixture_content_sha256=hashlib.sha256(content.encode()).hexdigest(),
                fields=fields,raw_observations=raw,all_reference_checks_passed=True,
                scope='actual APIs on authored fixtures; no production/model/P2 evidence')


def main():
    require_worker();request=validate_request(json.load(sys.stdin))
    versions=dict(git=git_command(['--version'],'/tmp')['stdout'].strip(),tenacity=importlib.metadata.version('tenacity'))
    fixtures=[measured_fixture(request['seed'],i) for i in range(request['fixtures'])]
    print(json.dumps(dict(schema='trusted-tool-relations/0.1',request=request,versions=versions,python=sys.version,
                          fixtures=fixtures,all_reference_checks_passed=True),ensure_ascii=False,allow_nan=False))


if __name__=='__main__':
    main()
