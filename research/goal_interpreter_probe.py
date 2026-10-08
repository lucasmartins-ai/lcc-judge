"""One frozen goal-only development probe; no training or production selection."""
import argparse
from collections import Counter
from datetime import datetime
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import resource
import socket
import sys
import time

from bakeoff.adapters import _content_words
from research.audit_tool_relation_confirmation import load, sha
from research.audit_tool_relation_states import recount
from research.audit_varied_relation_dev import read_population
from research.detached_varied_study import digest, now, save
from research.measurement_projection import SUFFIX
from research.tool_relation_contracts import ROLES

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/goal-engine-2026-10-04'
DATA = BASE / 'wording-development-pilot-v1'
OUT = BASE / 'goal-interpreter-probe-v1'


def extract_queries(rows, fields):
    inputs, labels = {}, {}
    for row in rows:
        goal = SUFFIX.fullmatch(row['objective'])
        if goal is None or row['goal_language'] not in ('en', 'pt'):
            raise ValueError('Explicit caller scope and known query language required')
        kind = row['unknown_kind']
        field = row['requested_role'] if kind is None else row['observed_role'] if kind == 'unbound_record' else None
        target = field if field in fields else None
        query_kind = 'direct' if target is not None else 'out_of_registry' if field is not None else kind
        q = dict(language=row['goal_language'], question=goal['question'])
        identity = digest([q['language'], q['question']])
        annotation = dict(target=target, kind=query_kind, source_ids=[], origin_kinds=[], wording_families=[])
        if identity in labels and (labels[identity]['target'], labels[identity]['kind']) != (target, query_kind):
            raise ValueError('One natural question has conflicting authored targets')
        inputs[identity] = dict(id=identity, **q)
        labels.setdefault(identity, annotation)
        labels[identity]['source_ids'].append(row['id'])
        labels[identity]['origin_kinds'].append(kind or 'binary')
        labels[identity]['wording_families'].append(f"{field or row['observed_role']}:{kind}:{row['intent_alias']}")
    for annotation in labels.values():
        for key in ('source_ids', 'origin_kinds', 'wording_families'):
            annotation[key] = sorted(set(annotation[key]))
    return [inputs[k] for k in sorted(inputs)], labels


def route(values, candidates):
    if (len(values) != len(candidates) or not values or len(candidates) != len(set(candidates))
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in values)):
        raise ValueError('Complete finite candidate scores required')
    best = max(values)
    winners = [name for value, name in zip(values, candidates, strict=True) if value == best]
    return winners[0] if len(winners) == 1 and not winners[0].startswith('UNKNOWN:') else None


def reduction(inputs, labels, predictions):
    if len(inputs) != len(predictions) or len({r['id'] for r in inputs}) != len(inputs):
        raise ValueError('Complete unique query predictions required')
    n = len(inputs)
    supported = accepted = correct = covered = unknown = abstained = 0
    confusion = Counter()
    for row, predicted in zip(inputs, predictions, strict=True):
        target = labels[row['id']]['target']
        supported += target is not None
        accepted += predicted is not None
        correct += target is not None and predicted == target
        covered += target is not None and predicted is not None
        unknown += target is None
        abstained += target is None and predicted is None
        confusion[(target or 'UNKNOWN', predicted or 'UNKNOWN')] += 1
    result = dict(n=n, supported=supported, accepted=accepted, correct_bindings=correct,
                  supported_accepted=covered, unknown=unknown, unknown_abstained=abstained,
                  accepted_binding_precision=correct / accepted if accepted else None,
                  supported_coverage=covered / supported if supported else None,
                  correct_supported_coverage=correct / supported if supported else None,
                  unknown_recognition=abstained / unknown if unknown else None,
                  confusion=[dict(expected=a, predicted=b, n=count) for (a, b), count in sorted(confusion.items())])
    result['gate_pass'] = all(result[k] is not None and result[k] >= cutoff for k, cutoff in
                              [('accepted_binding_precision', .99), ('supported_coverage', .80), ('unknown_recognition', .95)])
    return result


def reductions(inputs, annotations, predictions):
    result = dict(aggregate=reduction(inputs, annotations, predictions))
    for column in ('language', 'kind', 'wording_family'):
        groups = {}
        for i, row in enumerate(inputs):
            values = [row['language']] if column == 'language' else [annotations[row['id']]['kind']] if column == 'kind' else annotations[row['id']]['wording_families']
            for value in values:
                groups.setdefault(value, []).append(i)
        result['by_' + column] = {key: reduction([inputs[i] for i in indices], annotations,
                                                [predictions[i] for i in indices]) for key, indices in sorted(groups.items())}
    result['router_gate_pass'] = set(result['by_language']) == {'en', 'pt'} and all(
        m['gate_pass'] for m in [result['aggregate'], *result['by_language'].values()])
    return result


def prepare():
    if (OUT / 'protocol.json').exists():
        raise ValueError('Protocol already frozen; do not overwrite or reselect the study')
    registry = load(OUT / 'registry.json')
    fields = [r['id'] for r in registry['fields']]
    candidates = registry['fields'] + registry['unsupported']
    assert len(fields) == 8 and len(set(fields)) == 8 and len(candidates) == 12
    for field in registry['fields']:
        assert (field['source'], field['unit']) == ROLES[field['id']][:2]
    raw_checks = {}
    for split in ('train', 'validation'):
        raw = load(BASE / 'tool-relation-states-v2' / split / 'raw.json')
        for fixture in raw['measurements']['fixtures']:
            recount(fixture)
        raw_checks[split] = len(raw['measurements']['fixtures'])
    model = load(BASE / 'semantic-next/upstream/artifacts.json')
    snapshot = Path.home() / '.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1/snapshots' / model['revision']
    for name, h in model['files'].items():
        assert sha(snapshot / name) == h, name
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
    populations, lengths, sets = {}, {}, {}
    for split in ('train', 'validation'):
        rows, _ = read_population(DATA, split)
        queries, labels = extract_queries(rows, fields)
        sets[split] = {q['id'] for q in queries}
        populations[split] = dict(queries=len(queries), rows=len(rows),
                                 supported=sum(a['target'] is not None for a in labels.values()),
                                 by_kind=dict(Counter(a['kind'] for a in labels.values())))
        lengths[split] = [len(tokenizer(q['question'], c['definition'], truncation=False)['input_ids'])
                          for q in queries for c in candidates]
        if max(lengths[split]) > 512:
            raise ValueError('Whole query/definition exceeds the fixed pair window')
        save(OUT / f'{split}-inputs.json', queries)
        save(OUT / f'{split}-annotations.json', labels)
    if sets['train'] & sets['validation']:
        raise ValueError('A literal query crosses the development split')
    forwards = sum(len(v) for v in lengths.values())
    if forwards > 30000:
        raise ValueError('The fixed probe exceeds its total neural pair-forward cap')
    save(OUT / 'token-lengths.json', lengths)
    sources = ['research/goal_interpreter_probe.py', 'tests/test_goal_interpreter_probe.py',
               'research/reranker_control.py', 'research/measurement_projection.py',
               'research/audit_varied_relation_dev.py', 'research/audit_tool_relation_states.py',
               'research/audit_tool_relation_confirmation.py', 'research/detached_varied_study.py',
               'bakeoff/adapters.py', 'bakeoff/probes.py', 'research/tool_relation_state_worker.py']
    sources += ['research/tool_relation_contracts.py']
    data_files = [OUT / name for name in ('registry.json', 'CONTRACT.md', 'token-lengths.json')]
    data_files += [OUT / f'{split}-{kind}.json' for split in ('train', 'validation') for kind in ('inputs', 'annotations')]
    data_files += [DATA / f'{split}.jsonl.gz' for split in ('train', 'validation')]
    data_files += [BASE / 'tool-relation-states-v2' / split / 'raw.json' for split in ('train', 'validation')]
    protocol = dict(schema='frozen-goal-interpreter-probe/0.1', frozen_at_utc=now(), model=model,
                    sources={n: sha(ROOT / n) for n in sources},
                    files={str(f.relative_to(ROOT)): sha(f) for f in data_files}, populations=populations,
                    raw_fixtures_recounted=raw_checks, candidates=[c['id'] for c in candidates],
                    declared_pair_forwards=forwards, maximum_pair_forwards=30000,
                    declared_nonpadding_tokens=sum(sum(v) for v in lengths.values()),
                    maximum_pair_tokens=max(max(v) for v in lengths.values()),
                    recipe='Unique argmax of the same 12 fixed bilingual definitions; unsupported winners/ties UNKNOWN. No cutoff fit or logit probability claim.',
                    input='Only natural question and public candidate definition; no entity suffix, record, target role or annotation in neural inputs',
                    gate=dict(precision_min=.99, supported_coverage_min=.80, unknown_recognition_min=.95,
                              applies_to='Aggregate and EN/PT separately; unique questions, not repeated records'),
                    device='cpu', dtype='float32', threads=8, batch_size=16, pair_window=512,
                    versions={n: importlib.metadata.version(n) for n in ('torch', 'transformers', 'tokenizers', 'numpy')},
                    scope='Exposed author-created development queries. Not fresh confirmation, full 18-field quality, human ground truth or LCC utility.',
                    training=False, threshold_fit=False, fresh_confirmation=False, API_calls=0,
                    P2_admission=False, default_changed=False, independent_human_review=False)
    protocol['sha256'] = digest(protocol)
    for name, h in protocol['sources'].items():
        dest = OUT / 'sources' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((ROOT / name).read_bytes())
        assert sha(dest) == h
    save(OUT / 'protocol.json', protocol)
    print(json.dumps({k: protocol[k] for k in ('sha256', 'populations', 'declared_pair_forwards', 'declared_nonpadding_tokens', 'maximum_pair_tokens')}), flush=True)


def checked_protocol(*, live=False):
    p = load(OUT / 'protocol.json')
    assert digest({k: v for k, v in p.items() if k != 'sha256'}) == p['sha256']
    for name, h in p['files'].items():
        assert sha(ROOT / name) == h, name
    for name, h in p['sources'].items():
        assert sha(OUT / 'sources' / name) == h, name
        if live:
            assert sha(ROOT / name) == h, name
    assert p['declared_pair_forwards'] <= p['maximum_pair_forwards'] == 30000
    return p


def predictions(raw, inputs, candidates):
    if len(raw) != len(inputs) * len(candidates):
        raise ValueError('No missing query/candidate pair is permitted')
    values = []
    for i, q in enumerate(inputs):
        chunk = raw[i * len(candidates):(i + 1) * len(candidates)]
        for score, c in zip(chunk, candidates, strict=True):
            if (score['input_sha256'] != digest([q['question'], c['definition']])
                    or score['status'] != 'SCORED' or score['error'] or score['truncated']
                    or not score['submitted'] or not score['forward_completed']):
                raise ValueError('Complete declared input scores required; no subset result')
        values.append(route([s['score'] for s in chunk], [c['id'] for c in candidates]))
    return values


def run():
    p = checked_protocol(live=True)
    if (OUT / 'started.json').exists():
        raise ValueError('This probe already started; inspect partial evidence, do not rescore')
    save(OUT / 'started.json', dict(protocol_sha256=p['sha256'], utc=now()))
    import torch
    from research.reranker_control import PairReranker
    torch.set_num_threads(p['threads'])
    def denied(*args, **kwargs):
        raise RuntimeError('Network forbidden during local goal probe')
    socket.socket.connect = denied
    began = time.perf_counter()
    snapshot = Path.home() / '.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1/snapshots' / p['model']['revision']
    scorer = PairReranker.from_snapshot(snapshot, p['model'], max_pair_tokens=512, batch_size=16)
    save(OUT / 'load.json', dict(protocol_sha256=p['sha256'], identity=scorer.identity, setup_s=time.perf_counter() - began,
                               python=sys.version, platform=platform.platform(), network_blocked=True))
    registry = load(OUT / 'registry.json')
    candidates = registry['fields'] + registry['unsupported']
    results = {}
    for split in ('train', 'validation'):
        inputs = load(OUT / f'{split}-inputs.json')
        annotations = load(OUT / f'{split}-annotations.json')
        began = time.perf_counter()
        raw = scorer.score([q['question'] for q in inputs for _ in candidates],
                           [c['definition'] for _ in inputs for c in candidates])
        elapsed = time.perf_counter() - began
        save(OUT / f'{split}-scores.json', dict(protocol_sha256=p['sha256'], rows=raw, elapsed_s=elapsed, finished_at_utc=now()))
        predicted = predictions(raw, inputs, candidates)
        lexical = []
        for q in inputs:
            words = _content_words(q['question'])
            scores = [len(words & _content_words(c['definition'])) / max(1, len(words)) for c in candidates]
            lexical.append(route(scores, p['candidates']))
        result = dict(neural=reductions(inputs, annotations, predicted),
                      lexical=reductions(inputs, annotations, lexical),
                      predictions=predicted, lexical_predictions=lexical)
        save(OUT / f'{split}-metrics.json', result)
        results[split] = result
        print(split, json.dumps(result['neural']['aggregate']), round(elapsed, 3), flush=True)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    save(OUT / 'summary.json', dict(protocol_sha256=p['sha256'], finished_at_utc=now(),
         router_gate_pass=results['validation']['neural']['router_gate_pass'],
         validation=results['validation']['neural']['aggregate'], accounting=scorer.accounting,
         pair_forwards=p['declared_pair_forwards'], lexical_comparisons=p['declared_pair_forwards'],
         peak_probe_process_rss_bytes=rss if sys.platform == 'darwin' else rss * 1024,
         performance_scope='Whole goal/definition scoring including tokenization; peak includes imports/model and controls, not LCC serving or model compression',
         next_action='fresh_confirmation_required' if results['validation']['neural']['router_gate_pass'] else 'STOP_before_fresh_confirmation_and_LCC',
         training=False, API_calls=0, P2_admission=False, default_changed=False, independent_human_review=False))


def audit():
    p = checked_protocol(live=True)
    registry = load(OUT / 'registry.json')
    candidates = registry['fields'] + registry['unsupported']
    lengths = load(OUT / 'token-lengths.json')
    count = tokens = 0
    for split in ('train', 'validation'):
        rows, _ = read_population(DATA, split)
        inputs, labels = extract_queries(rows, [c['id'] for c in registry['fields']])
        assert inputs == load(OUT / f'{split}-inputs.json') and labels == load(OUT / f'{split}-annotations.json')
        receipt = load(OUT / f'{split}-scores.json')
        assert receipt['protocol_sha256'] == p['sha256']
        raw = receipt['rows']
        assert [s['actual_tokens'] for s in raw] == lengths[split]
        predicted = predictions(raw, inputs, candidates)
        recorded = load(OUT / f'{split}-metrics.json')
        assert recorded['predictions'] == predicted and recorded['neural'] == reductions(inputs, labels, predicted)
        lexical = [route([len(_content_words(q['question']) & _content_words(c['definition'])) / max(1, len(_content_words(q['question'])))
                          for c in candidates], p['candidates']) for q in inputs]
        assert recorded['lexical_predictions'] == lexical and recorded['lexical'] == reductions(inputs, labels, lexical)
        count += len(raw)
        tokens += sum(s['actual_tokens'] for s in raw)
    summary = load(OUT / 'summary.json')
    assert summary['pair_forwards'] == count == p['declared_pair_forwards']
    assert tokens == p['declared_nonpadding_tokens']
    assert set(summary['accounting'].values()) == {tokens}
    assert summary['router_gate_pass'] == recorded['neural']['router_gate_pass']
    loaded = load(OUT / 'load.json')['identity']
    assert loaded['model_sha256'] == p['model']['files']['model.safetensors'] and loaded['revision'] == p['model']['revision']
    assert (datetime.fromisoformat(p['frozen_at_utc']) <= datetime.fromisoformat(load(OUT / 'started.json')['utc'])
            <= datetime.fromisoformat(load(OUT / 'train-scores.json')['finished_at_utc'])
            <= datetime.fromisoformat(load(OUT / 'validation-scores.json')['finished_at_utc'])
            <= datetime.fromisoformat(summary['finished_at_utc']))
    result = dict(status='PASS', scope='Offline receipt/input/math integrity using pinned implementation; not independent semantic certification',
                  protocol_sha256=p['sha256'], checked_pairs=count, checked_tokens=tokens,
                  router_gate_pass=summary['router_gate_pass'], additional_model_forwards=0,
                  independent_human_review=False)
    if (OUT / 'audit.json').exists():
        assert result == load(OUT / 'audit.json')
    else:
        save(OUT / 'audit.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', required=True, choices=('prepare', 'run', 'audit'))
    args = parser.parse_args()
    {'prepare': prepare, 'run': run, 'audit': audit}[args.phase]()
