"""Read-only observer; executed study/supervisor archives remain unchanged.

macOS resolves/replaces displayed interpreter paths after spawn. Match PID,
recorded birth and fixed module/action suffix, not the transient executable text.
A live unmatched process is UNKNOWN, never a reason to start another job.
"""

import json

from research.detached_varied_study import OUT,checked_protocol,now,process_identity,sha


def identity_matches(saved,current,suffix):
    return (current['live'] and current['pid']==saved['pid'] and current['birth']==saved['birth']
            and isinstance(current['command'],str) and current['command'].split()[-len(suffix):]==suffix)


def process_state(supervisor_live,child_live,supervisor_matches,child_matches,exit_receipt):
    if supervisor_matches and child_matches:return 'RUNNING'
    if not supervisor_live and child_matches:return 'RUNNING_ORPHAN_CHILD'
    if supervisor_live or child_live:return 'UNKNOWN_PROCESS_IDENTITY'
    if exit_receipt and exit_receipt['returncode']==0 and exit_receipt['study_complete']:return 'COMPLETED'
    return 'STOPPED'


def observe():
    p=checked_protocol(verify_current=False);parent=json.loads((OUT/'launch.json').read_text());child=json.loads((OUT/'child-process.json').read_text())
    if parent['protocol_sha256']!=p['sha256'] or child['protocol_sha256']!=p['sha256']:
        raise ValueError('Saved process/protocol identity mismatch')
    a=process_identity(parent['pid']);b=process_identity(child['pid'])
    am=identity_matches(parent,a,['-m','research.detached_varied_study','supervise'])
    bm=identity_matches(child,b,['-m','research.varied_relation_dev_detached','run'])
    path=OUT/'process-exit.json';exit_receipt=json.loads(path.read_text()) if path.exists() else None
    if exit_receipt and exit_receipt['protocol_sha256']!=p['sha256']:raise ValueError('Exit identity mismatch')
    return dict(protocol_sha256=p['sha256'],state=process_state(a['live'],b['live'],am,bm,exit_receipt),
                supervisor=a,child=b,supervisor_matches=am,child_matches=bm,process_exit=exit_receipt,
                observation_at_utc=now(),observer_source_sha256=sha(__import__('pathlib').Path(__file__)),
                scope='PID/birth/fixed module/action observation; archived frozen source hashes checked, no study mutation/restart/model calls or quality approval')


if __name__=='__main__':print(json.dumps(observe(),indent=2))
