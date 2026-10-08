"""Complete the failed metadata report from saved scores; stdlib, no inference/API.

This does not manufacture the original run.json or recover unsaved setup/RSS.
"""
from __future__ import annotations

import argparse
import ast
from bisect import bisect_left
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT/'research/goal-engine-2026-10-04/reranker-known-control'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def reduce(rows, threshold=None, source=None):
    valid = [r for r in rows if r['score'] is not None and math.isfinite(r['score'])
             and not r.get('truncated') and not r.get('error')]
    positive = [r['score'] for r in valid if r['label'] == 1]
    negative = sorted(r['score'] for r in valid if r['label'] == 0)
    wins = sum(bisect_left(negative, score) for score in positive)
    pairs = defaultdict(lambda: {0: [], 1: []})
    for row in valid:
        pairs[row['report_id']][row['label']].append(row['score'])
    paired = [p > n for pair in pairs.values() for p, n in zip(pair[1], pair[0])]
    metrics = dict(n=len(rows), eligible=len(valid),
                   cuts=sum(bool(r.get('truncated')) for r in rows),
                   errors=sum(bool(r.get('error')) for r in rows),
                   auc=wins/(len(positive)*len(negative)) if positive and negative else None,
                   paired_auc=statistics.mean(paired) if paired else None,
                   paired_reports=len(paired))
    if threshold is not None:
        metrics.update(positive_recall=statistics.mean(p >= threshold for p in positive),
                       negative_rejection=statistics.mean(n < threshold for n in negative))
    if source is not None:
        by_objective = defaultdict(lambda: {0: [], 1: []})
        for row in valid:
            by_objective[source[row['id']]['objective']][row['label']].append(row['score'])
        comparisons = [p > n for pair in by_objective.values() for p in pair[1] for n in pair[0]]
        metrics['within_objective'] = dict(wins=sum(comparisons), comparisons=len(comparisons),
                                          auc=statistics.mean(comparisons), objectives=len(by_objective))
    return metrics


def verify_metrics(a, b):
    assert set(a) == set(b), (set(a), set(b))
    for key in a:
        assert abs(a[key]-b[key]) < 1e-12, (key, a[key], b[key])


def audit(out):
    protocol = json.loads((out/'protocol.json').read_text())
    assert digest({k: v for k, v in protocol.items() if k != 'sha256'}) == protocol['sha256']
    for name, expected in protocol['sources'].items():
        assert sha(out/'executed-source'/name) == expected
    # Annotation source was frozen by the earlier CPU study, not by this model
    # protocol. This additional check is retrospective and explicitly attributed.
    old = ROOT/'research/goal-engine-2026-10-04/semantic-tool-cpu-v2'
    original = json.loads((old/'protocol.json').read_text())
    annotation = old/'executed-source/research/semantic_corpus.py'
    assert sha(annotation) == original['sources']['research/semantic_corpus.py']
    families = next(ast.literal_eval(n.value) for n in ast.parse(annotation.read_text()).body
                    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'FAMILIES' for t in n.targets))
    data, entities, hashes = {}, {}, {}
    for split, meta in protocol['data'].items():
        path = out/f'{split}.jsonl'
        assert sha(path) == meta['sha256'] == original['data'][split]['sha256']
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert len(rows) == len({r['id'] for r in rows}) == meta['n']
        data[split] = {r['id']: r for r in rows}
        entities[split] = {r['entity'] for r in rows}
        hashes[split] = {r['content_hash'] for r in rows}
        for row in rows:
            assert type(row['label']) is int and row['label'] == int(row['requested_slot'] == row['semantic_slot'])
            suffix = f" Report evidence for {row['entity']}; ordinary and unusual values both count."
            assert row['objective'] in [q+suffix for q in families[row['domain']][row['requested_slot']][0]]
            meanings = families[row['domain']][row['semantic_slot']][1]
            if row['text'].startswith('{'):
                record = json.loads(row['text'])
                assert set(record) == {'entity', 'level', 'measurement', 'value'}
                assert record['entity'] == row['entity'] and record['measurement'] in meanings
                assert record['level'] in ['INFO', 'WARN', 'ERROR'] and type(record['value']) is int
            else:
                assert any(row['text'].startswith(f"Tool report {row['entity']} [{level}]: {meaning}: ")
                           for level in ['INFO', 'WARN', 'ERROR'] for meaning in meanings)
            assert digest([row['objective'], row['text']]) == row['content_hash']
            assert row['evidence_span'] == [0, len(row['text'])]
    assert not entities['validation'] & entities['final']
    assert not hashes['validation'] & hashes['final']
    assert not {r['domain'] for r in data['validation'].values()} & {r['domain'] for r in data['final'].values()}
    threshold_receipt = json.loads((out/'threshold.json').read_text())
    assert threshold_receipt['protocol_sha256'] == protocol['sha256'] and threshold_receipt['final_used'] is False
    threshold = threshold_receipt['threshold']
    receipts, metrics, timings = {}, {}, {}
    accounting = dict(counted_tokens=0, submitted_tokens=0, forward_completed_tokens=0, valid_score_tokens=0)
    max_tokens, scored_pairs, all_identical = 0, 0, True
    for split in ['validation', 'final']:
        receipts[split], timings[split] = [], []
        for repeat in range(protocol['repeats']):
            receipt = json.loads((out/f'{split}-{repeat}.json').read_text())
            assert receipt['protocol_sha256'] == protocol['sha256'] and receipt['threshold'] == threshold
            assert [r['id'] for r in receipt['rows']] == list(data[split])
            for row in receipt['rows']:
                source = data[split][row['id']]
                for key in ['group', 'report_id', 'domain', 'label', 'observation_status']:
                    assert row[key] == source[key]
                assert row['input_sha256'] == source['content_hash']
                assert type(row['actual_tokens']) is int and 0 < row['actual_tokens'] <= protocol['pair_window']
                assert row['submitted'] and row['forward_completed'] and row['status'] == 'SCORED'
                assert row['error'] is None and not row['truncated'] and not row['window_exceeded']
                assert type(row['score']) in (int, float) and math.isfinite(row['score'])
                max_tokens = max(max_tokens, row['actual_tokens'])
                for key in accounting:
                    accounting[key] += row['actual_tokens']
                scored_pairs += 1
            calculated = reduce(receipt['rows'], threshold)
            verify_metrics(calculated, receipt['metrics'])
            assert math.isfinite(receipt['elapsed_pass_s']) and receipt['elapsed_pass_s'] > 0
            if repeat:
                def fingerprint(rows):
                    return [{k: v for k, v in r.items() if k != 'batch_wall_s'} for r in rows]
                all_identical &= fingerprint(receipt['rows']) == fingerprint(receipts[split][0]['rows'])
            receipts[split].append(receipt)
            timings[split].append(receipt['elapsed_pass_s'])
        metrics[split] = reduce(receipts[split][0]['rows'], threshold, data[split])
    first = receipts['validation'][0]['rows']
    positives = [r['score'] for r in first if r['label'] == 1]
    chosen = max(t for t in set(positives) if statistics.mean(s >= t for s in positives) >= .95)
    assert chosen == threshold and digest(first) == threshold_receipt['raw_validation_sha256']
    final = receipts['final'][0]['rows']
    domains = sorted({r['domain'] for r in final})
    rng = random.Random(protocol['bootstrap']['seed'])
    boot = []
    for _ in range(protocol['bootstrap']['draws']):
        choices = rng.choices(domains, k=len(domains))
        boot.append(reduce([r for domain in choices for r in final if r['domain'] == domain])['auc'])
    boot.sort()
    def percentile(p):
        position = (len(boot)-1)*p
        low = int(position)
        return boot[low]+(boot[min(low+1, len(boot)-1)]-boot[low])*(position-low)
    final_metrics = metrics['final']
    passed = final_metrics['n'] == final_metrics['eligible'] and final_metrics['cuts'] == final_metrics['errors'] == 0
    passed &= all(final_metrics[k.removesuffix('_min')] >= value
                  for k, value in protocol['criteria'].items() if k.endswith('_min'))
    log = ROOT/'research/goal-engine-2026-10-04/reranker-run.log'
    assert "Object of type set is not JSON serializable" in log.read_text()
    assert not (out/'run.json').exists(), 'Do not replace the missing original process receipt'
    return dict(schema='compact-reranker-offline-completion/0.1', protocol_sha256=protocol['sha256'],
                sources_data_annotations_raw_metrics_threshold_verified=True, scoring_completed=True,
                original_report_serialization_failed=True, original_run_json_missing=True,
                failure_log_sha256=sha(log), setup_s=None, peak_process_rss_bytes=None,
                unsaved_environment_identity_recovered=False, metrics=metrics,
                metric_axes=dict(pooled='all positive versus all negative rows; strict >',
                    paired_auc='same report under two different neighboring goals; strict >',
                    within_objective='positive versus negative reports under exactly the same goal; strict >'),
                scored_pair_evaluations=scored_pairs, accounting_reduced_from_raw=accounting,
                max_actual_pair_tokens=max_tokens, all_repetitions_identical=all_identical,
                observed_pass_s=timings, final_auc_family_bootstrap_95=[percentile(.025), percentile(.975)],
                final_gate_pass=bool(passed), family_metrics={d: reduce([r for r in final if r['domain'] == d], threshold, data['final']) for d in domains},
                annotation_source=dict(path=str(annotation.relative_to(ROOT)), sha256=sha(annotation), retrospective_supplement=True),
                scope='exposed authored short-input diagnostic, not independent transfer/production/P2',
                artifact_loading_reexecuted=False, API_calls_during_audit=0, model_calls_during_audit=0,
                adoption=False, current_default_changed=False,
                temporal_attestation='source/data hashes do not provide external temporal attestation')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=DEFAULT)
    args = parser.parse_args()
    result = audit(args.out)
    (args.out/'audit.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'family_metrics'}, indent=2))
