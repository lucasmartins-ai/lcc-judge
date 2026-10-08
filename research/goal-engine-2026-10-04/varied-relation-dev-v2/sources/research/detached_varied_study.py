"""Fixed source-checked POSIX supervisor for one authorized local development run.

No caller executable/module/argv/path. A separate process session and file stdio
avoid coupling the job to an observer pipe. No guarantee against shutdown or
arbitrary process termination. PID and birth/command identity precede monitoring.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/goal-engine-2026-10-04/varied-relation-dev-v2'
MODULE='research.varied_relation_dev_detached'


def now():return datetime.now(timezone.utc).isoformat()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,value):
    with path.open('x') as stream:stream.write(json.dumps(value,indent=2,allow_nan=False)+'\n')


def checked_protocol(out=None):
    out=OUT if out is None else out
    p=json.loads((out/'protocol.json').read_text())
    if digest({k:v for k,v in p.items() if k!='sha256'})!=p['sha256']:
        raise ValueError('Frozen protocol drift')
    for name,expected in p['sources'].items():
        if sha(ROOT/name)!=expected or sha(out/'sources'/name)!=expected:
            raise ValueError('Frozen executable source drift')
    return p


def process_identity(pid):
    if type(pid) is not int or pid<=0:raise ValueError('Positive process identity required')
    result=subprocess.run(['ps','-p',str(pid),'-o','lstart=','-o','stat=','-o','command='],capture_output=True,text=True)
    line=result.stdout.strip()
    if result.returncode or not line:return dict(pid=pid,live=False,birth=None,command=None)
    parts=line.split(None,6)
    if len(parts)!=7:raise RuntimeError('Unexpected POSIX process identity format')
    return dict(pid=pid,birth=' '.join(parts[:5]),live=not parts[5].startswith('Z'),command=parts[6])


def launch():
    p=checked_protocol()
    if os.name!='posix':raise RuntimeError('This fixed detached supervisor requires POSIX')
    if (OUT/'launch-marker.json').exists() or (OUT/'started.json').exists():
        raise ValueError('Original launch marker exists; inspect status, never implicit restart')
    save(OUT/'launch-marker.json',dict(protocol_sha256=p['sha256'],launch_requested_at_utc=now()))
    env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    try:
        with (OUT/'supervisor.log').open('xb') as stdout,(OUT/'supervisor-errors.log').open('xb') as stderr:
            child=subprocess.Popen([sys.executable,'-m','research.detached_varied_study','supervise'],
                cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,
                start_new_session=True,close_fds=True,shell=False)
        identity=process_identity(child.pid)
        receipt=dict(protocol_sha256=p['sha256'],**identity,launched_at_utc=now(),
                     stdio='DEVNULL input; separate file output/error, no observer pipe',start_new_session=True)
        save(OUT/'launch.json',receipt)
        return receipt
    except Exception as exc:
        save(OUT/'launch-failure.json',dict(protocol_sha256=p['sha256'],error_type=type(exc).__name__,error=str(exc),utc=now()))
        raise


def supervise():
    p=checked_protocol()
    if (OUT/'supervisor-started.json').exists() or (OUT/'started.json').exists():
        raise ValueError('Original supervisor/study exists; no duplicate execution')
    save(OUT/'supervisor-started.json',dict(protocol_sha256=p['sha256'],pid=os.getpid(),utc=now()))
    env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    with (OUT/'run.log').open('xb') as stdout,(OUT/'run-errors.log').open('xb') as stderr:
        child=subprocess.Popen([sys.executable,'-m',MODULE,'run'],cwd=ROOT,env=env,
            stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,close_fds=True,shell=False)
        save(OUT/'child-process.json',dict(protocol_sha256=p['sha256'],**process_identity(child.pid),started_at_utc=now()))
        code=child.wait()
    complete=code==0 and (OUT/'summary.json').exists()
    result=dict(protocol_sha256=p['sha256'],returncode=code,study_complete=complete,finished_at_utc=now(),
                quality_approved=False,default_changed=False,P2_admission=False)
    save(OUT/'process-exit.json',result)
    return result


def status():
    p=checked_protocol();receipt=json.loads((OUT/'launch.json').read_text())
    if receipt['protocol_sha256']!=p['sha256']:raise ValueError('Launch/protocol identity mismatch')
    current=process_identity(receipt['pid'])
    same=current['live'] and current['birth']==receipt['birth'] and current['command']==receipt['command']
    exit_path=OUT/'process-exit.json';exit_receipt=json.loads(exit_path.read_text()) if exit_path.exists() else None
    if exit_receipt is not None and exit_receipt['protocol_sha256']!=p['sha256']:raise ValueError('Exit/protocol identity mismatch')
    state='RUNNING' if same else ('COMPLETED' if exit_receipt and exit_receipt['study_complete'] else 'STOPPED')
    return dict(protocol_sha256=p['sha256'],state=state,supervisor_identity=current,identity_matches=same,
                process_exit=exit_receipt,observation_at_utc=now(),quality_approved=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['launch','supervise','status'])
    args=parser.parse_args();print(json.dumps({'launch':launch,'supervise':supervise,'status':status}[args.action](),indent=2))
