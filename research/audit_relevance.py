"""Independent standard-library reduction of the new P1 study receipts.

No model loading, APIs, training or dependence on current generator/model source.
"""
from __future__ import annotations
import argparse
from bisect import bisect_left
import hashlib
import json
from pathlib import Path
import statistics


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_auc(positives, negatives):
    if not positives or not negatives:
        return None
    ordered = sorted(negatives)
    return sum(bisect_left(ordered, v) for v in positives) / (len(positives) * len(negatives))


def reduce_rows(rows, threshold=None):
    eligible = [r for r in rows if r['score'] is not None and not r.get('error') and not r.get('truncated')]
    negatives = [r['score'] for r in eligible if r['label'] == 0]
    result = dict(n=len(rows), known=sum(r['label'] is not None for r in rows),
                  eligible_known=sum(r['label'] is not None for r in eligible),
                  errors=sum(bool(r.get('error')) for r in rows), cuts=sum(bool(r.get('truncated')) for r in rows),
                  auc=strict_auc([r['score'] for r in eligible if r['label'] == 1], negatives))
    for status in ['healthy', 'anomalous']:
        positives = [r for r in eligible if r['label'] == 1 and r['observation_status'] == status]
        result[status + '_auc'] = strict_auc([r['score'] for r in positives], negatives)
        if threshold is not None:
            result[status + '_recall'] = statistics.mean(r['score'] >= threshold for r in positives)
    if threshold is not None:
        wrong = [r for r in eligible if r['kind'] == 'wrong_entity' and r['observation_status'] == 'anomalous']
        result['wrong_entity_anomaly_rejection'] = statistics.mean(r['score'] < threshold for r in wrong)
    return result


def same_metrics(actual, expected):
    assert set(actual) == set(expected)
    for key, value in actual.items():
        if value is None:
            assert expected[key] is None
        else:
            assert abs(value - expected[key]) < 1e-12, (key, value, expected[key])


def audit(directory):
    protocol = json.loads((directory / 'protocol.json').read_text())
    unsigned = {key: value for key, value in protocol.items() if key != 'sha256'}
    assert hashlib.sha256(json.dumps(unsigned, sort_keys=True).encode()).hexdigest() == protocol['sha256']
    data = {}
    for split, info in protocol['data'].items():
        path = directory / f'{split}.jsonl'
        assert sha(path) == info['sha256']
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert len(rows) == info['n'] and len({r['id'] for r in rows}) == len(rows)
        data[split] = {r['id']: r for r in rows}
    for name, expected in protocol['sources'].items():
        assert sha(directory / 'executed-source' / name) == expected
    for left, right in [('train', 'validation'), ('train', 'final'), ('validation', 'final')]:
        assert not ({r['content_hash'] for r in data[left].values()} & {r['content_hash'] for r in data[right].values()})
    selection = json.loads((directory / 'selection.json').read_text())
    assert selection['final_used_for_selection'] is False
    coverage = json.loads((directory / 'coverage.json').read_text())
    assert all(r['truncated'] == r['incomplete_observations'] == 0 for r in coverage.values())
    validations, finals = {}, {}
    for arm in protocol['arms']:
        validations[arm], finals[arm] = [], []
        for seed in protocol['seeds']:
            target = directory / f'{arm}-{seed}'
            meta = json.loads((target / 'training_meta.json').read_text())
            assert meta['epochs_completed'] == protocol['epochs']
            assert [e['epoch'] for e in meta['history']] == list(range(1, protocol['epochs'] + 1))
            for epoch in meta['history']:
                assert json.loads((target / f'epoch-{epoch["epoch"]}.json').read_text()) == epoch
            if (target / 'weights.pt').exists():
                assert sha(target / 'weights.pt') == meta['weights_sha256']
            for split, file in [('validation', 'validation.json'), ('final', 'final.json')]:
                receipt = json.loads((target / file).read_text())
                rows = receipt['rows']
                assert len(rows) == len(data[split]) and {r['id'] for r in rows} == set(data[split])
                for row in rows:
                    original = data[split][row['id']]
                    assert row['input_sha256'] == original['content_hash']
                    for key in ['label', 'group', 'kind', 'domain', 'observation_status']:
                        assert row[key] == original[key]
                computed = reduce_rows(rows, receipt['threshold'])
                same_metrics(computed, receipt['metrics'])
                (validations if split == 'validation' else finals)[arm].append(computed)
    means = {arm: statistics.mean(m['auc'] for m in validations[arm]) for arm in protocol['arms']}
    same_metrics(means, selection['validation_mean_auc'])
    assert max(protocol['arms'], key=means.get) == selection['selected_arm']
    baselines = {}
    for name in protocol['baselines']:
        receipt = json.loads((directory / 'baselines' / f'{name}.json').read_text())
        assert len(receipt['rows']) == len(data['final'])
        assert {r['id'] for r in receipt['rows']} == set(data['final'])
        for row in receipt['rows']:
            original = data['final'][row['id']]
            assert row['input_sha256'] == original['content_hash']
            for key in ['label', 'group', 'kind', 'domain', 'observation_status']:
                assert row[key] == original[key]
        baselines[name] = reduce_rows(receipt['rows'])
        same_metrics(baselines[name], receipt['metrics'])
    summary = json.loads((directory / 'summary.json').read_text())
    assert summary['selected_arm'] == selection['selected_arm'] and summary['adoption'] is False
    for arm, items in finals.items():
        averaged = {key: statistics.mean(m[key] for m in items) for key in summary['arms'][arm]['mean']}
        same_metrics(averaged, summary['arms'][arm]['mean'])
        passes = []
        criteria = protocol['quality_gate']
        for m in items:
            passes.append(m['eligible_known'] == m['known'] and m['errors'] == m['cuts'] == 0 and
                          m['auc'] >= criteria['pooled_auc_min'] and
                          all(m[key] >= criteria[key + '_min'] for key in averaged if key != 'auc'))
        assert passes == summary['arms'][arm]['seeds_pass']
        assert all(passes) == summary['arms'][arm]['all_seed_gate_pass']
    for name, m in baselines.items():
        same_metrics(m, summary['baselines'][name])
    return dict(schema='direct-relevance-audit/0.1', sources_and_data_valid=True,
                all_training_epochs_receipted=True, weights_checked_when_present=True,
                selected_arm=selection['selected_arm'], final_per_seed=finals, baselines=baselines,
                audit_scope='raw identities, metrics, summary means and gate decisions; bootstrap intervals are not independently rederived here; no independent human ground truth or temporal attestation')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    result = audit(args.directory)
    (args.directory / 'audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
