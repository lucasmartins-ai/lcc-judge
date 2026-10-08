"""Independent, standard-library receipt reduction; no model/API execution."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

from research.archives import verified_sources, read_ledger, call_fingerprints

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'data/d6_referenced_pilot_v03'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seal(data):
    """Post-execution preservation only; never a temporal attestation."""
    path = data/'audit-manifest.json'
    files = [p for p in data.rglob('*') if p.is_file() and
             p.name not in {'audit-manifest.json', 'audit.json'} and '__pycache__' not in p.parts]
    manifest = {'schema': 'referenced-receipt-seal/0.1',
                'exported_after_execution': True, 'externally_attested': False,
                'files': {str(p.relative_to(data)): sha(p) for p in sorted(files)}}
    assert not path.exists(), 'Existing seal must be preserved'
    path.write_text(json.dumps(manifest, indent=2)+'\n')


def audit(data=DATA):
    data = Path(data)
    manifest = json.loads((data/'audit-manifest.json').read_text())
    for name, expected in manifest['files'].items():
        assert sha(data/name) == expected, f'Evidence changed: {name}'
    protocol = json.loads((data/'protocol.json').read_text())
    digest = protocol.pop('protocol_sha256')
    assert hashlib.sha256(json.dumps(protocol, sort_keys=True).encode()).hexdigest() == digest
    sources = verified_sources(data, protocol['files'])
    paths = sorted((data/'episodes').glob('*/*/*/receipt.json'))
    rows = [json.loads(p.read_text()) for p in paths]
    expected_keys = {(t, c, i) for t in protocol['task_ids']
                     for c in ['baseline', 'ablation'] for i in range(3)}
    assert len(rows) == 120 and {(r['task_id'], r['condition'], r['repeat']) for r in rows} == expected_keys
    sessions = []; questions = Counter(); jevs = []
    for path, row in zip(paths, rows):
        assert row['protocol_sha256'] == digest and row['outcome_review_completed']
        assert row['training_eligible'] is False
        assert sha(path.parent/'query.txt') == row['input_sha256']
        packet = json.loads((path.parent/'packet.json').read_text())
        assert 'is_decisive' not in json.dumps(packet)
        assert all('decisive' not in b['block_id'] for b in packet['context'])
        if row['status'] == 'SUCCESS':
            assert row['tool_events'] == 0
            terminal = [json.loads(line) for line in (path.parent/'stdout.jsonl').read_text().splitlines()
                        if line.startswith('{') and json.loads(line).get('type') == 'result']
            assert len(terminal) == 1 and terminal[0] == row['hermes_receipt']
            sessions.append(terminal[0]['session_id'])
        else:
            assert row['verification'] == {'passed': None, 'reason': 'executor_error'}
            assert row['artifact'] is None and 'timed out' in row['error']
        original = json.loads((path.parent/'execution-receipt.json').read_text())
        assert original['artifact'] == row['artifact'] and original['status'] == row['status']
        task_number = int(row['task_id'].split('_')[1])
        if task_number in protocol['quarantined_task_numbers']:
            assert row['verification'] == {'passed': None, 'reason': 'reference_contract_quarantined'}
        diagnostic = row.get('jev_diagnostic')
        if diagnostic:
            assert original['verification']['passed'] is True
            assert diagnostic == json.loads((path.parent/'jev-response.json').read_text())
            assert diagnostic['status'] == 'SUCCESS'
            assert diagnostic['response']['model'] == protocol['jev_model']
            request = json.loads((path.parent/'jev-request.json').read_text())
            key = 'text_consistent' if task_number == 18 else 'consistent'
            assert request['questions'] == (protocol['pdb_question'] if task_number == 18 else protocol['questions'])
            assert request['feature'] == 'lcc_judge_referenced_replay'
            probability = diagnostic['response']['answers'][key]['noul']
            assert row['verification']['passed'] is (probability >= protocol['semantic_threshold'])
            questions[key] += 1; jevs.append((key, diagnostic))
        else:
            assert row['verification'] == original['verification']
    assert len(set(sessions)) == len(sessions), 'Reused executor session'
    labels = {}; agreement = 0; task_verdicts = {}
    for task in protocol['task_ids']:
        values = {c: [next(r for r in rows if (r['task_id'], r['condition'], r['repeat']) == (task, c, i))
                       ['verification']['passed'] for i in range(3)] for c in ['baseline', 'ablation']}
        stable = all(None not in v and len(set(v)) == 1 for v in values.values())
        agreement += stable
        labels[task] = ('UNNECESSARY' if all(values['ablation']) else 'NECESSARY') \
            if stable and all(values['baseline']) else 'UNKNOWN'
        task_verdicts[task] = values
    records = [json.loads(line) for line in (data/'records.jsonl').read_text().splitlines()]
    assert len(records) == 20 and all(r['training_eligible'] is False for r in records)
    assert {r['task_id']: r['labels']['necessary'] for r in records} == labels
    summary = json.loads((data/'summary.json').read_text())
    counts = dict(Counter(labels.values())); unknown = counts['UNKNOWN']/20
    assert summary['label_counts'] == counts and summary['concordance_rate'] == agreement/20
    assert summary['unknown_rate'] == unknown and summary['episodes'] == len(rows)
    quarantined = sum(r['verification']['reason'] == 'reference_contract_quarantined' for r in rows)
    executor_errors = sum(r['status'] == 'ERROR' for r in rows)
    unknown_verdicts = sum(r['verification']['passed'] is None for r in rows)
    assert summary['execution_errors'] == unknown_verdicts == quarantined+executor_errors
    input_tokens = sum(r.get('hermes_receipt', {}).get('tokens', {}).get('input', 0) for r in rows)
    output_tokens = sum(r.get('hermes_receipt', {}).get('tokens', {}).get('output', 0) for r in rows)
    jev_tokens = sum(j['response']['usage']['input_tokens'] for _, j in jevs)
    assert (summary['costing']['hermes_input_tokens'], summary['costing']['hermes_output_tokens'],
            summary['costing']['jev_calls'], summary['costing']['jev_input_tokens']) == \
           (input_tokens, output_tokens, len(jevs), jev_tokens)
    ledger_count = 0
    for key in questions:
        directory = data/('ledger-actual-'+key.replace('_', '-'))
        ledger = read_ledger(directory); ledger_count += len(ledger)
        expected = Counter((j['response']['usage']['input_tokens'], j['response']['usage']['output_tokens'],
                            j['response']['answers'][key]['noul']) for q, j in jevs if q == key)
        assert call_fingerprints(ledger, key) == expected
    assert ledger_count == len(jevs)
    passed = agreement/20 >= protocol['passing_pilot_targets']['concordance_min'] and \
        unknown <= protocol['passing_pilot_targets']['unknown_max']
    assert summary['pilot_targets_pass'] is passed
    return dict(episodes=len(rows), unique_executor_sessions=len(set(sessions)), label_counts=counts,
                concordance_rate=agreement/20, unknown_rate=unknown, pilot_targets_pass=passed,
                executor_successes=120-executor_errors, executor_errors=executor_errors,
                attempted_executor_calls=120, executor_calls_with_final_receipt=len(sessions),
                tokens_exclude_unobserved_timeout_usage=True,
                quarantined_verdicts=quarantined, unknown_verdicts=unknown_verdicts,
                misleading_summary_field='execution_errors counts all None verdicts, including quarantine',
                task_verdicts=task_verdicts, labels=labels, canonical_ledger_entries=ledger_count,
                ledger_questions=dict(questions), requested_feature='lcc_judge_referenced_replay',
                actual_ledger_feature='lcc_judge_replay_real', ledger_feature_misrouted=True,
                hermes_input_tokens=input_tokens, hermes_output_tokens=output_tokens,
                jev_input_tokens=jev_tokens, median_episode_wall_s=statistics.median(r['wall_time_s'] for r in rows),
                archived_sources_verified=sources, source_verification_mode='archived',
                outcomes_reexecuted=False, independently_human_reviewed=False,
                temporal_preregistration_certified=False, training_eligible_records=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=DATA)
    parser.add_argument('--seal', action='store_true')
    parser.add_argument('--write-report', action='store_true')
    args = parser.parse_args()
    if args.seal: seal(args.data)
    result = audit(args.data)
    if args.write_report: (args.data/'audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ['labels', 'task_verdicts']}, indent=2))
