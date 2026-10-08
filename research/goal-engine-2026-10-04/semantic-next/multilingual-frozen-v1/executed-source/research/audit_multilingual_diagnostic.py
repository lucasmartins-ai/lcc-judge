"""Independent stdlib audit of exposed multilingual ranking receipts, no inference."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path

from research.audit_tool_role_support import close, digest, reduce_metrics, sha

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'research/goal-engine-2026-10-04/semantic-next/multilingual-frozen-v1'


def reduced(rows, scores):
    aggregate = reduce_metrics(rows, scores, {}, shadow=True)
    groups = {}
    for column, values in [('by_language', ['en', 'pt']),
                           ('by_family', sorted({r['family'] for r in rows if r['label'] is not None}))]:
        groups[column] = {}
        for value in values:
            selected = [(r, s) for r, s in zip(rows, scores) if r['label'] is not None and
                        (r['goal_language'] if column == 'by_language' else r['family']) == value]
            groups[column][value] = reduce_metrics([r for r, s in selected], [s for r, s in selected], {}, shadow=True)
    passed = all(v[key] is not None and v[key] >= .90 for v in [aggregate, *groups['by_language'].values()]
                 for key in ['pooled_auc', 'within_goal_auc'])
    return dict(metrics=aggregate, **groups, ranking_criteria_pass=passed)


def audit(out=DEFAULT):
    protocol = json.loads((out / 'protocol.json').read_text())
    assert digest({k: v for k, v in protocol.items() if k != 'sha256'}) == protocol['sha256']
    assert protocol['complete_pair_window'] == 512
    for name, expected in protocol['sources'].items():
        assert sha(out / 'executed-source' / name) == expected
    for name, expected in protocol['data_files'].items():
        assert sha(out / name) == expected
    load = json.loads((out / 'load.json').read_text())
    assert load['protocol_sha256'] == protocol['sha256'] and load['socket_connect_blocked']
    assert load['identity']['model_sha256'] == protocol['model']['files']['model.safetensors']
    assert load['complete_pair_window'] == protocol['complete_pair_window']
    for key in ['missing_keys', 'unexpected_keys', 'mismatched_keys']:
        assert not load['identity']['loading_info'][key]
    assert load['identity']['dtype'] == 'float32' and load['identity']['device'] == 'cpu'
    accounting = dict(counted_tokens=0, submitted_tokens=0, forward_completed_tokens=0, valid_score_tokens=0)
    results, elapsed, max_tokens, pairs = {}, {}, 0, 0
    for split in ['validation', 'final']:
        rows = [json.loads(line) for line in (out / f'{split}.jsonl').read_text().splitlines()]
        views = [json.loads(line) for line in (out / f'{split}-views.jsonl').read_text().splitlines()]
        raw = json.loads((out / f'{split}-scores.json').read_text())
        assert raw['protocol_sha256'] == protocol['sha256']
        assert datetime.fromisoformat(protocol['frozen_at_utc']) <= datetime.fromisoformat(raw['finished_at_utc'])
        scores = raw['rows']
        assert len(rows) == len(views) == len(scores)
        assert len({r['id'] for r in rows}) == len(rows)
        for row, saved, score in zip(rows, views, scores):
            view = saved['view']
            assert row['id'] == saved['id'] == score['id']
            assert score['original_input_hash'] == row['content_hash']
            assert score['input_hash'] == score['input_sha256'] == row['projected_input_hash']
            assert score['support_score'] is None and score['error'] is None
            assert score['truncated'] is score['window_exceeded'] is False
            if view['status'] == 'UNKNOWN':
                assert row['unknown_kind'] == 'unbound_record' and row['label'] is None
                assert score['input_hash'] is score['score'] is score['actual_tokens'] is None
                assert score['status'] == 'UNKNOWN' and score['submitted'] is score['forward_completed'] is False
                assert score['guard_reason'] == view['error']
            else:
                assert digest([view['objective'], view['text']]) == row['projected_input_hash']
                assert score['status'] == 'SCORED' and type(score['score']) is float and math.isfinite(score['score'])
                assert score['submitted'] is score['forward_completed'] is True
                assert type(score['actual_tokens']) is int and 0 < score['actual_tokens'] <= 512
                assert score['batch_wall_s'] >= 0
                max_tokens = max(max_tokens, score['actual_tokens'])
                pairs += 1
                for key in accounting:
                    accounting[key] += score['actual_tokens']
        previous_path = out / f'{split}-previous-scores.json'
        assert sha(previous_path) == protocol['previous_scalar_scores'][split]
        previous = json.loads(previous_path.read_text())['rows']
        assert len(previous) == len(scores)
        for old, current in zip(previous, scores):
            assert old['id'] == current['id'] and old['input_hash'] == current['input_hash']
        result = dict(protocol_sha256=protocol['sha256'], current=reduced(rows, scores),
                      previous_scalar=reduced(rows, previous), policy_shadow=True)
        close(result, json.loads((out / f'{split}-metrics.json').read_text()))
        results[split] = result
        elapsed[split] = raw['elapsed_s']
    summary = json.loads((out / 'summary.json').read_text())
    assert summary['protocol_sha256'] == protocol['sha256']
    close(summary['final'], results['final'])
    close(summary['accounting'], accounting)
    assert summary['ranking_criteria_pass'] == results['final']['current']['ranking_criteria_pass']
    assert summary['API_calls'] == 0
    for flag in ['training_executed', 'P2_admission', 'default_changed', 'adoption', 'useful_context_validated']:
        assert summary[flag] is False
    return dict(status='PASS', protocol_sha256=protocol['sha256'], raw_inputs_sources_and_rank_reductions_verified=True,
        original_scalar_scores_reused_without_new_forwards=True, evaluated_pairs=pairs,
        max_complete_pair_tokens=max_tokens, accounting_from_raw=accounting,
        parameters=load['identity']['parameters'], setup_s=load['setup_s'], elapsed_pass_s=elapsed,
        peak_diagnostic_process_rss_bytes=summary['peak_diagnostic_process_rss_bytes'],
        final=results['final'], ranking_criteria_pass=summary['ranking_criteria_pass'],
        model_forwards_during_audit=0, API_calls=0, training_reexecuted=False, adoption=False,
        scope='Exposed authored EN/PT ranking diagnostic; no calibrated support/DROP/production/P2/LCC-outcome or isolated architecture/language cause')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=DEFAULT)
    args = parser.parse_args()
    print(json.dumps(audit(args.out), indent=2, allow_nan=False))
