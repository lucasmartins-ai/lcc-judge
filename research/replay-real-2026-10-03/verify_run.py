"""Verify real pilot receipts independently of its summary/labeling implementation."""
import hashlib
import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
DATA=ROOT/'data/d6_real_pilot'
sys.path.insert(0,str(ROOT))
from research.archives import verified_sources, read_ledger, call_fingerprints


def run():
    protocol=json.loads((DATA/'protocol.json').read_text())
    digest=protocol.pop('protocol_sha256')
    # v0.1 hashed numeric map keys before JSON serialized them as strings.
    # Reproduce that historical hash; v0.2 normalizes keys before hashing.
    hash_input=json.loads(json.dumps(protocol))
    if protocol['version']=='real-replay/0.1':
        hash_input['public_interfaces']={int(k):v for k,v in hash_input['public_interfaces'].items()}
    assert hashlib.sha256(json.dumps(hash_input,sort_keys=True).encode()).hexdigest()==digest
    archived_sources=verified_sources(OUT,protocol['files'])
    verified_sources(OUT,{'replay/tasks.py':protocol['original_suite_sha256']})
    audit=json.loads((OUT/'evaluation-audit.json').read_text())
    verified_sources(OUT,{'replay/real_fixtures.py':audit['audited_verifier_sha256']},archive='audited-source')
    files=sorted((DATA/'episodes').glob('*/*/*/receipt.json'))
    assert len(files)==120
    rows=[json.loads(p.read_text()) for p in files]
    keys={(r['task_id'],r['condition'],r['repeat']) for r in rows}
    expected={(t,c,i) for t in protocol['task_ids'] for c in ['baseline','ablation'] for i in range(3)}
    assert keys==expected
    sessions=[]
    for path,r in zip(files,rows):
        assert hashlib.sha256(path.read_bytes()).hexdigest()==audit['episode_receipt_sha256'][str(path.relative_to(ROOT))]
        assert r['protocol_sha256']==digest
        assert hashlib.sha256((path.parent/'query.txt').read_bytes()).hexdigest()==r['input_sha256']
        packet=json.loads((path.parent/'packet.json').read_text())
        assert 'is_decisive' not in json.dumps(packet) and 'required_keywords' not in json.dumps(packet)
        assert all('decisive' not in b['block_id'] for b in packet['context'])
        if 'hermes_receipt' in r:
            terminal=[json.loads(line) for line in (path.parent/'stdout.jsonl').read_text().splitlines()
                      if line.startswith('{') and json.loads(line).get('type')=='result']
            assert len(terminal)==1 and terminal[0]==r['hermes_receipt']
            assert terminal[0]['exit_code']==0 and r['tool_events']==0
            sessions.append(terminal[0]['session_id'])
        if r.get('jev_diagnostic',{}).get('status')=='SUCCESS':
            assert json.loads((path.parent/'jev-response.json').read_text())==r['jev_diagnostic']
            assert r['jev_diagnostic']['response']['model']=='jev-1.13.0'
    assert len(set(sessions))==len(sessions), 'Reused model conversation'
    # Independently derive the sole corrected contract from the saved answer;
    # every other verdict must equal the original immutable episode verdict.
    for r in rows:
        expected_verdict=r['verification']['passed']
        if r['task_id']=='task_018_k8s_pdb':
            a=r['artifact'];params={k:v for k,v in a['parameters'].items() if v is not None}
            expected_verdict=(a['status']=='ANSWER' and a['mechanism']=='configure_pdb' and
                (set(params)=={'min_available'} and type(params['min_available']) is int and params['min_available'] in [3,4]
                 or set(params)=={'max_unavailable'} and type(params['max_unavailable']) is int and params['max_unavailable'] in [1,2]))
        item=next(e for e in audit['evaluations'] if (e['task_id'],e['condition'],e['repeat'])==(r['task_id'],r['condition'],r['repeat']))
        assert item['original']==r['verification']
        assert item['audited']['passed']==expected_verdict
        r['verification']=item['audited']
    labels={};agreement=0
    for task in protocol['task_ids']:
        values={c:[next(r for r in rows if (r['task_id'],r['condition'],r['repeat'])==(task,c,i))['verification']['passed']
                   for i in range(3)] for c in ['baseline','ablation']}
        stable=all(None not in v and len(set(v))==1 for v in values.values())
        agreement+=stable
        labels[task]='UNKNOWN'
        if stable and all(values['baseline']):
            labels[task]='UNNECESSARY' if all(values['ablation']) else 'NECESSARY'
    records=[json.loads(line) for line in (DATA/'records.jsonl').read_text().splitlines()]
    assert len(records)==20
    assert all(r['labels']['necessary']==labels[r['task_id']] for r in records)
    assert all(r['training_eligible'] is False for r in records)
    summary=json.loads((DATA/'summary.json').read_text())
    assert summary['label_counts']==dict(Counter(labels.values()))
    assert summary['concordance_rate']==agreement/20
    assert summary['unknown_rate']==sum(v=='UNKNOWN' for v in labels.values())/20
    hermes_input=sum(r['hermes_receipt']['tokens']['input'] for r in rows)
    hermes_output=sum(r['hermes_receipt']['tokens']['output'] for r in rows)
    jevs=[r['jev_diagnostic'] for r in rows if 'jev_diagnostic' in r]
    assert summary['costing']['jev_calls']==len(jevs)==119
    assert summary['costing']['hermes_input_tokens']==hermes_input
    assert summary['costing']['hermes_output_tokens']==hermes_output
    ledger=read_ledger(OUT)
    expected_calls=Counter((r['response']['usage']['input_tokens'],r['response']['usage']['output_tokens'],
                            r['response']['answers']['supported']['noul']) for r in jevs)
    assert call_fingerprints(ledger,'supported')==expected_calls and len(ledger)==119
    # Wilson interval for the observed task concordance (descriptive n=20 pilot).
    p=agreement/20;z=1.96;denom=1+z*z/20
    centre=(p+z*z/40)/denom
    width=z*math.sqrt(p*(1-p)/20+z*z/(4*400))/denom
    jev_mismatches=[]
    for r in rows:
        diagnostic=r.get('jev_diagnostic',{})
        if diagnostic.get('status')=='SUCCESS':
            prob=diagnostic['response']['answers']['supported']['noul']
            if r['verification']['passed'] is not None and (prob>=.5)!=r['verification']['passed']:
                jev_mismatches.append(dict(task_id=r['task_id'],condition=r['condition'],repeat=r['repeat'],
                                          fixture_pass=r['verification']['passed'],jev_noul=prob))
    return dict(verified_episode_count=120,unique_sessions=len(set(sessions)),
                label_counts=dict(Counter(labels.values())),labels=labels,
                concordance_rate=p,concordance_wilson_95ci=[centre-width,centre+width],
                unknown_rate=summary['unknown_rate'],
                pilot_targets_pass=p>=.95 and summary['unknown_rate']<=.10,
                source_versions_verified=True,archived_executed_sources=archived_sources,
                source_verification_mode='archived',canonical_ledger_scope='run-local-export',
                canonical_ledger_entries=len(ledger),temporal_preregistration_certified=False,
                episode_receipts_unchanged=True,post_execution_changed_verdicts=len(audit['changed_verdicts']),
                jev_diagnostic_disagreements=jev_mismatches,
                requested_seed_is_metadata_not_sampling_seed=True,
                input_seed_field_changes_between_repetitions=True,
                production_sessions_replayed=False, training_eligible_records=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--write-report',action='store_true')
    args=parser.parse_args()
    evidence=run()
    if args.write_report:
        (OUT/'verification.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({k:v for k,v in evidence.items() if k not in ['labels','jev_diagnostic_disagreements']},indent=2))
