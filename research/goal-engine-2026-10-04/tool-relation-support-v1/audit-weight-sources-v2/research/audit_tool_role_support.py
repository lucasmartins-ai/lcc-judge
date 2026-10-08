"""Independent standard-library reduction of frozen support-study receipts.

No training/policy/scorer imports, model inference or API calls. The default
verifies saved evidence; --verify-weights additionally hashes private weights.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/goal-engine-2026-10-04/tool-role-support-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def close(left, right):
    if isinstance(left, dict):
        assert set(left) == set(right)
        for key in left:
            close(left[key], right[key])
    elif isinstance(left, list):
        assert len(left) == len(right)
        for a, b in zip(left, right):
            close(a, b)
    elif type(left) is float:
        assert math.isfinite(left) and math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9), (left, right)
    else:
        assert left == right, (left, right)


def disposition(score, thresholds, shadow=False):
    if shadow or score['status'] != 'SCORED':
        return 'UNKNOWN'
    if score['support_score'] >= thresholds['support']:
        return 'UNKNOWN'
    return 'KEEP' if score['score'] >= thresholds['relevance'] else 'DROP'


def thresholds_from_validation(rows, scores):
    support = min(s['support_score'] for r, s in zip(rows, scores) if r['unknown_kind'] == 'unsupported_goal')
    values = {s['score'] for r, s in zip(rows, scores) if r['label'] is not None}
    values |= {math.nextafter(min(values), -math.inf), math.nextafter(max(values), math.inf)}
    feasible = []
    for value in sorted(values):
        good = True
        for language in ['en', 'pt']:
            for contradictions_only in [False, True]:
                selected = [s for r, s in zip(rows, scores) if r['label'] == 1 and r['goal_language'] == language
                            and (not contradictions_only or r['fact_truth'] is False)]
                assert selected
                if sum(s['support_score'] >= support or s['score'] >= value for s in selected) / len(selected) < .95:
                    good = False
        if good:
            feasible.append(value)
    assert feasible
    return dict(support=support, relevance=max(feasible), validation_semantic_unknown_recall=1.0,
                recipe='minimum semantic-UNKNOWN support margin; greatest global relevance cutoff meeting .95 positive/contradiction keep recall in each language')


def reduce_metrics(rows, scores, thresholds, shadow=False):
    binary = [(r, s) for r, s in zip(rows, scores) if r['label'] is not None]
    positives = [(r, s) for r, s in binary if r['label'] == 1]
    negatives = [(r, s) for r, s in binary if r['label'] == 0]
    negative_values = sorted(s['score'] for r, s in negatives)
    pooled_wins = sum(bisect_left(negative_values, s['score']) for r, s in positives)
    comparisons = len(positives) * len(negatives)
    def contrast(field):
        buckets = defaultdict(lambda: [[], []])
        for r, s in binary:
            buckets[r[field]][r['label']].append(s['score'])
        won = total = 0
        for negative, positive in buckets.values():
            won += sum(p > n for p in positive for n in negative)
            total += len(positive) * len(negative)
        return dict(wins=won, comparisons=total, auc=won / total if total else None)
    within = contrast('objective')
    goal_axis = contrast('report_id')
    semantic = [(r, s) for r, s in zip(rows, scores) if r['unknown_kind'] == 'unsupported_goal']
    structural = [(r, s) for r, s in zip(rows, scores) if r['unknown_kind'] == 'unbound_record']
    contradictions = [(r, s) for r, s in positives if r['fact_truth'] is False]
    def fraction(group, states):
        return sum(disposition(s, thresholds, shadow) in states for r, s in group) / len(group) if group else None
    return dict(n=len(rows), binary=len(binary), positive=len(positives), negative=len(negatives),
                pooled_wins=pooled_wins, pooled_comparisons=comparisons, pooled_auc=pooled_wins / comparisons,
                within_goal=within, within_goal_auc=within['auc'], same_report_goal=goal_axis,
                positive_keep_recall=fraction(positives, {'KEEP', 'UNKNOWN'}),
                contradiction_keep_recall=fraction(contradictions, {'KEEP', 'UNKNOWN'}),
                negative_drop_rejection=fraction(negatives, {'DROP'}), binary_unknown_rate=fraction(binary, {'UNKNOWN'}),
                semantic_unknown=len(semantic), structural_unknown=len(structural),
                semantic_unknown_recognition=fraction(semantic, {'UNKNOWN'}), structural_unknown_recognition=fraction(structural, {'UNKNOWN'}),
                unknown_drops=sum(disposition(s, thresholds, shadow) == 'DROP' for r, s in semantic + structural),
                control_shadow=shadow)


def gate(result, criteria):
    for name in ['pooled_auc', 'within_goal_auc', 'positive_keep_recall', 'contradiction_keep_recall',
                 'negative_drop_rejection', 'semantic_unknown_recognition', 'structural_unknown_recognition']:
        if result[name] is None or result[name] < criteria[name]:
            return False
    return result['unknown_drops'] == criteria['unknown_drops']


def audited_scores(path, rows, views, protocol, scalar):
    raw = json.loads(path.read_text())
    assert raw['protocol_sha256'] == protocol['sha256'] and raw['scalar_control'] is scalar
    assert len(raw['rows']) == len(rows) == len(views)
    eligible = tokens = 0
    for row, saved, score in zip(rows, views, raw['rows']):
        assert score['id'] == row['id'] == saved['id']
        assert score['original_input_hash'] == row['content_hash']
        assert score['input_hash'] == row['projected_input_hash']
        assert score['actual_tokens'] == saved['projected_tokens'] and score['truncated'] is False and score['error'] is None
        if saved['view']['status'] == 'UNKNOWN':
            assert row['label'] is None and row['unknown_kind'] == 'unbound_record'
            assert score['status'] == 'UNKNOWN' and score['score'] is score['support_score'] is score['logits'] is None
            assert score['submitted'] is score['forward_completed'] is False
            assert score['guard_reason'] == 'unsupported_record'
            continue
        assert score['status'] == 'SCORED' and score['submitted'] is score['forward_completed'] is True
        assert score['guard_reason'] is None and 0 < score['actual_tokens'] <= 512
        assert type(score['score']) is float and math.isfinite(score['score'])
        if scalar:
            assert score['support_score'] is score['logits'] is None
        else:
            logits = score['logits']
            assert len(logits) == 3 and all(type(v) is float and math.isfinite(v) for v in logits)
            assert math.isclose(score['score'], logits[1] - logits[0], abs_tol=1e-6)
            largest = max(logits[:2])
            wanted = logits[2] - largest - math.log(sum(math.exp(v - largest) for v in logits[:2]))
            assert math.isclose(score['support_score'], wanted, abs_tol=1e-6)
        eligible += 1
        tokens += score['actual_tokens']
    close(raw['accounting'], dict(counted_pairs=eligible, counted_tokens=tokens, submitted_pairs=eligible,
                                 submitted_tokens=tokens, forward_completed_pairs=eligible, forward_completed_tokens=tokens,
                                 valid_score_pairs=eligible, valid_score_tokens=tokens))
    return raw


def audit(out=OUT, verify_weights=False):
    protocol = json.loads((out / 'protocol.json').read_text())
    assert protocol['sha256'] == digest({k: v for k, v in protocol.items() if k != 'sha256'})
    for name, expected in protocol['sources'].items():
        assert sha(out / 'executed-source' / name) == expected
    data = out.parent / protocol['data_directory']
    for name, expected in protocol['data_files'].items():
        assert sha(data / name) == expected
    data_protocol = json.loads((data / 'protocol.json').read_text())
    assert data_protocol['sha256'] == protocol['data_protocol_sha256']
    datasets = {}
    for split in ['train', 'validation', 'final']:
        rows = [json.loads(line) for line in (data / f'{split}.jsonl').read_text().splitlines()]
        views = [json.loads(line) for line in (data / f'{split}-views.jsonl').read_text().splitlines()]
        datasets[split] = (rows, views)
    train_rows, train_views = datasets['train']
    unique = {}
    for row, saved in zip(train_rows, train_views):
        if saved['view']['status'] != 'PROJECTED':
            assert row['label'] is None
            continue
        key = row['projected_input_hash']
        label = 2 if row['label'] is None else row['label']
        if key not in unique:
            unique[key] = dict(input_hash=key, objective=saved['view']['objective'], text=saved['view']['text'], class_id=label, receipt_ids=[])
        assert unique[key]['class_id'] == label
        unique[key]['receipt_ids'].append(row['id'])
    items = [unique[key] for key in sorted(unique)]
    assert digest(items) == protocol['train_unique_items_sha256'] and len(items) == protocol['train_unique']
    counts = Counter(item['class_id'] for item in items)
    assert [counts[i] for i in range(3)] == protocol['train_class_counts']
    close(protocol['global_class_weights'], [len(items) / (3 * counts[i]) for i in range(3)])
    lengths = {row['projected_input_hash']: saved['projected_tokens'] for row, saved in zip(train_rows, train_views) if row['projected_input_hash'] is not None}
    expected_tokens = sum(lengths[item['input_hash']] for item in items)
    started = json.loads((out / 'started.json').read_text())
    selection = json.loads((out / 'selection.json').read_text())
    assert started['protocol_sha256'] == selection['protocol_sha256'] == protocol['sha256']
    assert selection['final_inspected'] is False and selection['seeds'] == protocol['seeds']
    assert datetime.fromisoformat(protocol['frozen_at_utc']) <= datetime.fromisoformat(started['utc']) <= datetime.fromisoformat(selection['frozen_at_utc'])
    final_metrics = []
    total_steps = total_training_pairs = total_training_tokens = total_scoring_pairs = total_scoring_tokens = 0
    for candidate in ['frozen'] + [f'seed-{seed}' for seed in protocol['seeds']]:
        directory = out / candidate
        scalar = candidate == 'frozen'
        meta = None
        thresholds = dict(support=None, relevance=None)
        if not scalar:
            seed = int(candidate.removeprefix('seed-'))
            meta = json.loads((directory / 'training_meta.json').read_text())
            assert meta['protocol_sha256'] == protocol['sha256'] and meta['seed'] == seed
            assert meta['epochs_completed'] == protocol['epochs'] == 3 and meta['final_inspected'] is False
            assert meta['identity']['output_classes'] == 3 and meta['identity']['adapted_parameters'] == 22714371
            assert meta['identity']['model_sha256'] == protocol['model']['files']['model.safetensors']
            assert selection['weights_sha256'][str(seed)] == meta['weights_sha256']
            saved_thresholds = json.loads((directory / 'thresholds.json').read_text())
            assert saved_thresholds == selection['calibration'][str(seed)] and saved_thresholds['final_inspected'] is False
            assert datetime.fromisoformat(saved_thresholds['frozen_at_utc']) <= datetime.fromisoformat(selection['frozen_at_utc'])
            thresholds = saved_thresholds['thresholds']
            for epoch, history in enumerate(meta['history'], 1):
                receipt = json.loads((directory / f'epoch-{epoch}.json').read_text())
                assert receipt == history and receipt['epoch'] == epoch and receipt['seed'] == seed
                assert receipt['protocol_sha256'] == protocol['sha256'] and receipt['all_updates_finite'] is True
                assert math.isfinite(receipt['weighted_mean_loss']) and receipt['weighted_mean_loss'] >= 0
                assert receipt['steps'] == math.ceil(len(items) / protocol['batch_size'])
                assert receipt['unique_pairs'] == len(items) and receipt['submitted_nonpadding_tokens'] == expected_tokens
                assert receipt['padded_token_slots'] >= expected_tokens and receipt['seconds'] > 0
                assert datetime.fromisoformat(receipt['finished_at_utc']) <= datetime.fromisoformat(selection['frozen_at_utc'])
                total_steps += receipt['steps']; total_training_pairs += receipt['unique_pairs']; total_training_tokens += expected_tokens
            if verify_weights:
                assert sha(ROOT / meta['weights_path']) == meta['weights_sha256']
        for split in ['validation', 'final']:
            rows, views = datasets[split]
            raw = audited_scores(directory / f'{split}-scores.json', rows, views, protocol, scalar)
            if split == 'validation' and not scalar:
                close(thresholds, thresholds_from_validation(rows, raw['rows']))
            if split == 'final':
                assert datetime.fromisoformat(selection['frozen_at_utc']) <= datetime.fromisoformat(raw['finished_at_utc'])
            reduced = reduce_metrics(rows, raw['rows'], thresholds, scalar)
            stored = json.loads((directory / f'{split}-metrics.json').read_text())
            assert stored['protocol_sha256'] == protocol['sha256'] and stored['scalar_control'] is scalar
            close(stored['thresholds'], thresholds)
            close(stored['metrics'], reduced)
            by_language = {}
            for language in ['en', 'pt']:
                selected = [(r, s) for r, s in zip(rows, raw['rows']) if r['goal_language'] == language]
                by_language[language] = reduce_metrics([r for r, s in selected], [s for r, s in selected], thresholds, scalar)
            close(stored['by_language'], by_language)
            for column, values in [('by_family', sorted({r['family'] for r in rows if r['label'] is not None})),
                                   ('by_binary_source', sorted({r['binding']['source'] for r in rows if r['label'] is not None}))]:
                recomputed = {}
                for value in values:
                    selected = [(r, s) for r, s in zip(rows, raw['rows']) if r['label'] is not None and
                                (r['family'] if column == 'by_family' else r['binding']['source']) == value]
                    recomputed[value] = reduce_metrics([r for r, s in selected], [s for r, s in selected], thresholds, scalar)
                close(stored[column], recomputed)
            passed = gate(reduced, protocol['criteria']) and all(gate(m, protocol['criteria']) for m in by_language.values())
            assert stored['passed'] == passed
            if split == 'final' and not scalar:
                final_metrics.append(stored)
            if split == 'validation' and meta:
                assert meta['validation_pass'] == passed
            total_scoring_pairs += raw['accounting']['valid_score_pairs']
            total_scoring_tokens += raw['accounting']['valid_score_tokens']
    summary = json.loads((out / 'summary.json').read_text())
    assert summary['protocol_sha256'] == protocol['sha256']
    assert summary['seed_passes'] == [r['passed'] for r in final_metrics]
    assert summary['all_seeds_pass'] == all(r['passed'] for r in final_metrics)
    close(summary['mean'], {key: statistics.mean(r['metrics'][key] for r in final_metrics) for key in summary['mean']})
    assert summary['unknown_drops'] == [r['metrics']['unknown_drops'] for r in final_metrics]
    close(summary['frozen_final'], json.loads((out / 'frozen/final-metrics.json').read_text())['metrics'])
    assert summary['API_calls'] == 0 and summary['P2_admission'] is summary['default_changed'] is summary['adoption'] is False
    return dict(status='PASS', protocol_sha256=protocol['sha256'], source_data_inputs_and_score_axes_verified=True,
                calibration_selection_epoch_and_metrics_verified=True, private_weight_hashes_verified=verify_weights,
                finite_epoch_receipts=protocol['epochs'] * len(protocol['seeds']), accepted_update_steps=total_steps,
                training_unique_pair_presentations=total_training_pairs, training_nonpadding_tokens=total_training_tokens,
                scored_pairs=total_scoring_pairs, scored_nonpadding_tokens=total_scoring_tokens,
                seed_passes=summary['seed_passes'], all_seeds_pass=summary['all_seeds_pass'],
                mean_final=summary['mean'], unknown_drops=summary['unknown_drops'],
                API_calls=0, model_forwards_executed_by_audit=0, training_reexecuted=False,
                scope='Recorded source/data/score/epoch/policy reduction; authored fixtures/captions, three final source clusters, no production/P2/adoption claim')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--verify-weights', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.out, args.verify_weights), indent=2))
