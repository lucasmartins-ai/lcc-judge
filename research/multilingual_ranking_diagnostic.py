"""Frozen scalar ranking diagnostic on exposed pairs, without DROP authority."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import resource
import socket
import sys
import time

import torch

from research.audit_tool_role_data import audit as audit_data
from research.reranker_control import PairReranker
from research.tool_role_policy import metrics

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/goal-engine-2026-10-04'
DATA = BASE / 'tool-role-grounded-v1'
OLD = BASE / 'tool-role-support-v1'
OUT = BASE / 'semantic-next/multilingual-frozen-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def save_once(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as target:
        target.write(json.dumps(value, indent=2, allow_nan=False) + '\n')


def score_views(rows, views, scorer):
    if len(rows) != len(views) or any(r['id'] != v['id'] for r, v in zip(rows, views)):
        raise ValueError('Complete aligned original cohort required')
    eligible = []
    for i, (row, saved) in enumerate(zip(rows, views)):
        view = saved['view']
        if view['status'] == 'PROJECTED':
            if digest([view['objective'], view['text']]) != row['projected_input_hash']:
                raise ValueError('Changed declared model input')
            eligible.append(i)
        elif view['status'] != 'UNKNOWN' or row['projected_input_hash'] is not None:
            raise ValueError('Invalid structural guard view')
    raw = scorer.score([views[i]['view']['objective'] for i in eligible],
                       [views[i]['view']['text'] for i in eligible])
    if len(raw) != len(eligible):
        raise ValueError('Missing original row score')
    mapped = dict(zip(eligible, raw))
    result = []
    for i, row in enumerate(rows):
        score = mapped.get(i, dict(score=None, input_sha256=None, status='UNKNOWN',
            actual_tokens=None, truncated=False, window_exceeded=False, submitted=False,
            forward_completed=False, error=None, guard_reason=views[i]['view'].get('error')))
        if score['input_sha256'] != row['projected_input_hash']:
            raise ValueError('Model pair identity mismatch')
        result.append(dict(id=row['id'], original_input_hash=row['content_hash'],
                           input_hash=row['projected_input_hash'], support_score=None, **score))
    return result


def rank_pass(aggregate, languages):
    return (set(languages) == {'en', 'pt'} and all(
        type(value.get(key)) in (int, float) and math.isfinite(value[key]) and value[key] >= .90
        for value in [aggregate, *languages.values()] for key in ['pooled_auc', 'within_goal_auc']))


def reductions(rows, scores):
    aggregate = metrics(rows, scores, {}, shadow=True)
    groups = {}
    for column, values in [('by_language', ['en', 'pt']),
                           ('by_family', sorted({r['family'] for r in rows if r['label'] is not None}))]:
        groups[column] = {}
        for value in values:
            paired = [(r, s) for r, s in zip(rows, scores) if r['label'] is not None and
                      (r['goal_language'] if column == 'by_language' else r['family']) == value]
            groups[column][value] = metrics([r for r, s in paired], [s for r, s in paired], {}, shadow=True)
    return dict(metrics=aggregate, **groups,
                ranking_criteria_pass=rank_pass(aggregate, groups['by_language']))


def prepare(out=OUT):
    target = out / 'protocol.json'
    if target.exists():
        protocol = json.loads(target.read_text())
        for name, expected in protocol['sources'].items():
            if sha(ROOT / name) != expected:
                raise ValueError('Live source drift; audit archived run before reuse')
        return protocol
    assert audit_data(DATA)['status'] == 'PASS'
    model = json.loads((BASE / 'semantic-next/upstream/artifacts.json').read_text())
    names = ['research/multilingual_ranking_diagnostic.py', 'research/reranker_control.py',
             'research/tool_role_policy.py', 'research/audit_tool_role_data.py',
             'research/audit_multilingual_diagnostic.py', 'research/audit_tool_role_support.py']
    data_files = {name: sha(DATA / name) for split in ['validation', 'final']
                  for name in [f'{split}.jsonl', f'{split}-views.jsonl']}
    controls = {split: sha(OLD / f'frozen/{split}-scores.json') for split in ['validation', 'final']}
    protocol = dict(schema='multilingual-frozen-ranking/0.1',
        frozen_at_utc=datetime.now(timezone.utc).isoformat(), model=model,
        data_protocol_sha256=json.loads((DATA / 'protocol.json').read_text())['sha256'],
        data_files=data_files, previous_scalar_scores=controls,
        sources={name: sha(ROOT / name) for name in names}, device='cpu', dtype='float32',
        threads=8, batch_size=16, complete_pair_window=512,
        versions={name: importlib.metadata.version(name) for name in ['torch', 'transformers', 'tokenizers', 'numpy']},
        scoring='One complete validation and final pass; fixed original projected strings; all structural UNKNOWN bypasses the model',
        ranking_criterion='Strict pooled and within-goal AUC >=.90 in aggregate AND each EN/PT language; diagnostic only',
        policy='Blanket shadow UNKNOWN/KEEP; no learned support detection or calibrated threshold; no DROP authority',
        scope='Already exposed authored tool-role cohorts/English captions/shared concepts; not fresh confirmation, production or P2',
        limitations='Different upstream architecture/tokenizer/training data/parameter count; comparison does not isolate language pretraining as a cause',
        training_executed=False, final_threshold_tuning=False, adoption=False, API_calls=0,
        P2_admission=False, default_changed=False, publishing=False)
    protocol['sha256'] = digest(protocol)
    for name, expected in protocol['sources'].items():
        destination = out / 'executed-source' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / name).read_bytes())
        assert sha(destination) == expected
    for name, expected in data_files.items():
        (out / name).write_bytes((DATA / name).read_bytes())
        assert sha(out / name) == expected
    for split, expected in controls.items():
        (out / f'{split}-previous-scores.json').write_bytes((OLD / f'frozen/{split}-scores.json').read_bytes())
        assert sha(out / f'{split}-previous-scores.json') == expected
    save_once(target, protocol)
    return protocol


def run(protocol, snapshot, out=OUT):
    if (out / 'summary.json').exists():
        return
    save_once(out / 'started.json', dict(protocol_sha256=protocol['sha256'], started_at_utc=datetime.now(timezone.utc).isoformat()))
    torch.set_num_threads(protocol['threads'])
    def denied(*args, **kwargs):
        raise RuntimeError('Network forbidden during diagnostic')
    socket.socket.connect = denied
    began = time.perf_counter()
    scorer = PairReranker.from_snapshot(snapshot, protocol['model'], max_pair_tokens=512, batch_size=16)
    save_once(out / 'load.json', dict(protocol_sha256=protocol['sha256'], identity=scorer.identity,
        setup_s=time.perf_counter()-began, complete_pair_window=scorer.window,
        socket_connect_blocked=True, python=sys.version, platform=platform.platform()))
    results = {}
    for split in ['validation', 'final']:
        rows = [json.loads(line) for line in (out / f'{split}.jsonl').read_text().splitlines()]
        views = [json.loads(line) for line in (out / f'{split}-views.jsonl').read_text().splitlines()]
        began = time.perf_counter()
        scores = score_views(rows, views, scorer)
        elapsed = time.perf_counter()-began
        save_once(out / f'{split}-scores.json', dict(protocol_sha256=protocol['sha256'], rows=scores,
            elapsed_s=elapsed, finished_at_utc=datetime.now(timezone.utc).isoformat()))
        if any(s['status'] != 'SCORED' or s['error'] or not math.isfinite(s['score'])
               for r, s in zip(rows, scores) if r['projected_input_hash'] is not None):
            raise ValueError('Incomplete projected cohort; no subset ranking pass')
        previous = json.loads((out / f'{split}-previous-scores.json').read_text())['rows']
        if any(s['id'] != old['id'] or s['input_hash'] != old['input_hash']
               for s, old in zip(scores, previous)) or len(previous) != len(scores):
            raise ValueError('Old scalar control is not the identical input cohort')
        result = dict(protocol_sha256=protocol['sha256'], current=reductions(rows, scores),
                      previous_scalar=reductions(rows, previous), policy_shadow=True)
        save_once(out / f'{split}-metrics.json', result)
        results[split] = result
        print(split, json.dumps(result['current']['metrics']), elapsed, flush=True)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    save_once(out / 'summary.json', dict(protocol_sha256=protocol['sha256'],
        ranking_criteria_pass=results['final']['current']['ranking_criteria_pass'],
        final=results['final'], accounting=scorer.accounting,
        peak_diagnostic_process_rss_bytes=rss if sys.platform == 'darwin' else rss*1024,
        training_executed=False, API_calls=0, P2_admission=False,
        default_changed=False, adoption=False, useful_context_validated=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', required=True, choices=['prepare', 'run'])
    parser.add_argument('--snapshot', type=Path)
    args = parser.parse_args()
    protocol = prepare()
    if args.phase == 'prepare':
        print(protocol['sha256'])
    else:
        snapshot = args.snapshot or Path.home() / '.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1/snapshots' / protocol['model']['revision']
        try:
            run(protocol, snapshot)
        except Exception as error:
            save_once(OUT / 'failure.json', dict(protocol_sha256=protocol['sha256'], error_type=type(error).__name__, error=str(error)))
            raise
