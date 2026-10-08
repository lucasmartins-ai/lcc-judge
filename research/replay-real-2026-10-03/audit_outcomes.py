"""Re-evaluate saved artifacts without rerunning APIs or changing episode receipts."""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from replay.real_fixtures import verify_artifact
from replay.real_pilot import summarize
from replay.tasks import TASKS

OUT=Path(__file__).resolve().parent
DATA=ROOT/'data/d6_real_pilot'


def run():
    tasks={t.task_id:t for t in TASKS}
    files=sorted((DATA/'episodes').glob('*/*/*/receipt.json'))
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    source_hash=hashlib.sha256((ROOT/'replay/real_fixtures.py').read_bytes()).hexdigest()
    rows=[];changes=[];evaluations=[]
    for path in files:
        row=json.loads(path.read_text())
        original=row['verification']
        audited=verify_artifact(tasks[row['task_id']],row['artifact']) if row['status']=='SUCCESS' else original
        key=dict(task_id=row['task_id'],condition=row['condition'],repeat=row['repeat'])
        item=dict(**key,original=original,audited=audited)
        evaluations.append(item)
        if original['passed']!=audited['passed']:
            changes.append(item)
        row['original_verification']=original
        row['verification']=audited
        row['verification_audit']=dict(verifier_source_sha256=source_hash,
            evidence='research/replay-real-2026-10-03/evaluation-audit.json')
        rows.append(row)
    assert len(files)==120
    assert len(changes)==3
    assert all(c['task_id']=='task_018_k8s_pdb' and c['condition']=='ablation'
               and c['original']['passed'] is False and c['audited']['passed'] is True for c in changes)
    evidence=dict(episode_receipts_unchanged=True,episode_receipt_sha256=hashes,
        original_verifier_sha256=json.loads((DATA/'protocol.json').read_text())['files']['replay/real_fixtures.py'],
        audited_verifier_sha256=source_hash,changed_verdicts=changes,evaluations=evaluations,
        reason='PDB maxUnavailable=1 preserves at least three of five replicas and permits one-node maintenance; original verifier erroneously required exactly two.',
        no_new_api_calls=True,original_source_archive='research/replay-real-2026-10-03/executed-source')
    (OUT/'evaluation-audit.json').write_text(json.dumps(evidence,indent=2)+'\n')
    protocol=json.loads((DATA/'protocol.json').read_text())
    summary=summarize(rows,DATA,protocol)
    summary['post_execution_audit']={k:v for k,v in evidence.items() if k not in ['evaluations','episode_receipt_sha256']}
    (DATA/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    records=[json.loads(line) for line in (DATA/'records.jsonl').read_text().splitlines()]
    for record in records:
        record['baseline']['verifier']='curated-executable-contracts/0.2-post-execution-audit'
        record['provenance']['verification_audit']='research/replay-real-2026-10-03/evaluation-audit.json'
    (DATA/'records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    print(json.dumps({k:v for k,v in summary.items() if k not in ['protocol','post_execution_audit']},indent=2))


if __name__=='__main__':run()
