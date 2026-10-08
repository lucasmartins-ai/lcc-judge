"""Independent input-view/raw receipt reduction; standard library, no inference."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

from research.audit_reranker_diagnostic import digest, sha, reduce

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT/'research/goal-engine-2026-10-04/measurement-projection-v1'


def equal(a, b):
    if isinstance(a, dict):
        assert set(a) == set(b)
        for key in a:
            equal(a[key], b[key])
    elif isinstance(a, list):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            equal(x, y)
    else:
        assert a == b, (a, b)


def audit(out):
    protocol = json.loads((out/'protocol.json').read_text())
    assert digest({k:v for k,v in protocol.items() if k!='sha256'}) == protocol['sha256']
    for name, expected in protocol['sources'].items():
        assert sha(out/'executed-source'/name) == expected
    raw_control = ROOT/'research/goal-engine-2026-10-04/reranker-known-control'
    previous = json.loads((raw_control/'protocol.json').read_text())
    assert protocol['exposed_cohort_protocol_sha256'] == previous['sha256']
    data, metrics, final_rows, accounting, max_tokens = {}, {}, [], {}, 0
    accounting = dict(counted_tokens=0, submitted_tokens=0, forward_completed_tokens=0, valid_score_tokens=0)
    threshold_receipt = json.loads((out/'threshold.json').read_text())
    assert threshold_receipt['protocol_sha256'] == protocol['sha256'] and not threshold_receipt['final_used']
    threshold = threshold_receipt['threshold']
    for split, meta in protocol['data'].items():
        assert sha(out/f'{split}.jsonl') == meta['sha256'] == previous['data'][split]['sha256']
        records = [json.loads(line) for line in (out/f'{split}.jsonl').read_text().splitlines()]
        data[split] = {r['id']:r for r in records}
        assert len(records) == len(data[split]) == meta['n']
        view_receipt = json.loads((out/f'{split}-views.json').read_text())
        assert view_receipt['protocol_sha256'] == protocol['sha256']
        views = view_receipt['rows']
        assert [v['id'] for v in views] == list(data[split])
        for record, view in zip(records, views):
            assert view['status'] == 'PROJECTED' and view['drop_authorized'] is False
            assert view['error'] is None and view['original_text'] == record['text']
            suffix = f" Report evidence for {record['entity']}; ordinary and unusual values both count."
            assert record['objective'].endswith(suffix)
            expected_question = record['objective'][:-len(suffix)]
            if record['text'].startswith('{'):
                body = json.loads(record['text'])
                assert body['entity'] == record['entity']
                measurement, value = body['measurement'], body['value']
            else:
                prefix = f"Tool report {record['entity']} ["
                assert record['text'].startswith(prefix) and record['text'].endswith('.')
                level, remainder = record['text'][len(prefix):].split(']: ', 1)
                assert level in ['INFO', 'WARN', 'ERROR']
                measurement, numeric = remainder[:-1].rsplit(': ',1)
                value = int(numeric)
            assert view['objective'] == expected_question
            assert view['text'] == f'{measurement}: {value}.'
            assert view['original_input_sha256'] == record['content_hash'] == digest([record['objective'], record['text']])
            assert view['projected_input_sha256'] == digest([view['objective'], view['text']])
        saved = []
        for repeat in range(protocol['repeats']):
            receipt = json.loads((out/f'{split}-{repeat}.json').read_text())
            assert receipt['protocol_sha256'] == protocol['sha256'] and receipt['threshold'] == threshold
            assert [r['id'] for r in receipt['rows']] == list(data[split])
            for row, view in zip(receipt['rows'],views):
                record = data[split][row['id']]
                for key in ['domain', 'report_id', 'label']:
                    assert row[key] == record[key]
                assert row['original_input_sha256'] == record['content_hash']
                assert row['input_sha256'] == view['projected_input_sha256']
                assert row['submitted'] and row['forward_completed'] and row['status'] == 'SCORED'
                assert not row['error'] and not row['window_exceeded'] and not row['truncated']
                assert 0 < row['actual_tokens'] <= protocol['pair_window']
                max_tokens = max(max_tokens,row['actual_tokens'])
                for key in accounting:
                    accounting[key] += row['actual_tokens']
            calculated = reduce(receipt['rows'],threshold,data[split])
            equal(calculated,receipt['metrics'])
            saved.append(receipt)
        assert all([r['score'] for r in saved[0]['rows']] == [r['score'] for r in receipt['rows']] for receipt in saved[1:])
        metrics[split] = saved[0]['metrics']
        if split == 'validation':
            positive = [r['score'] for r in saved[0]['rows'] if r['label'] == 1]
            assert max(t for t in set(positive) if statistics.mean(s>=t for s in positive)>=.95) == threshold
            assert digest(saved[0]['rows']) == threshold_receipt['raw_validation_sha256']
        else:
            final_rows = saved[0]['rows']
    run = json.loads((out/'run.json').read_text())
    assert run['protocol_sha256'] == protocol['sha256']
    equal(metrics,run['metrics'])
    equal(accounting,run['accounting'])
    final = metrics['final']
    passed = final['n'] == final['eligible'] and final['cuts'] == final['errors'] == 0
    passed &= all(final[k.removesuffix('_min')]>=v for k,v in protocol['criteria'].items() if k.endswith('_min'))
    assert bool(passed) == run['final_gate_pass'] and run['adoption'] is False
    load = json.loads((out/'load.json').read_text())
    assert load['protocol_sha256'] == protocol['sha256'] and load['socket_connect_blocked']
    assert load['identity']['model_sha256'] == protocol['model']['files']['model.safetensors']
    assert not load['identity']['loading_info']['missing_keys'] and not load['identity']['loading_info']['mismatched_keys']
    assert set(load['identity']['loading_info']['unexpected_keys']) <= {'bert.embeddings.position_ids'}
    original_final = json.loads((raw_control/'final-0.json').read_text())['rows']
    assert [r['id'] for r in original_final] == [r['id'] for r in final_rows]
    control_metrics = reduce(original_final,json.loads((raw_control/'threshold.json').read_text())['threshold'],data['final'])
    return dict(schema='scope-checked-measurement-view-audit/0.1',protocol_sha256=protocol['sha256'],
        archived_sources_data_views_scores_threshold_gate_verified=True, metrics=metrics,
        raw_control_final=control_metrics, final_gate_pass=bool(passed), max_actual_pair_tokens=max_tokens,
        total_pair_evaluations=protocol['repeats']*sum(m['n'] for m in protocol['data'].values()),
        accounting_from_raw=accounting, setup_receipt_preserved=True, peak_process_rss_bytes=run['peak_process_rss_bytes'],
        inference_reexecuted=False,model_calls_during_audit=0,API_calls_during_audit=0,adoption=False,
        scope='one altered-input representation on exposed authored data; no independent confirmation, causal attribution, production or P2')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,default=DEFAULT)
    args=parser.parse_args()
    result=audit(args.out)
    (args.out/'audit.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,indent=2))
