"""Bounded two-objective development fit using frozen query/definition scores."""
import argparse
import importlib.metadata
import json
from datetime import datetime
import resource
import socket
import sys
import time

import numpy as np

from research import goal_interpreter_probe as base
from research.audit_goal_interpreter_probe import audit as audit_parent

ROOT = base.ROOT
DATA = base.OUT
OUT = DATA.parent / 'goal-support-pilot-v1'
RECIPE = dict(updates=200, lr=.05, weight_penalty=.01, threads=2,
              dtype='float64', initialization='zero', optimizer='Adam', quantiles=21)


def predict(support, field_logits, fields, thresholds):
    support, scores = np.asarray(support, dtype=float), np.asarray(field_logits, dtype=float)
    if (support.ndim != 1 or scores.shape != (len(support), len(fields)) or len(fields) < 2
            or len(fields) != len(set(fields)) or not np.isfinite(support).all()
            or not np.isfinite(scores).all()):
        raise ValueError('Complete finite support and field scores required')
    if thresholds is None:
        return [None] * len(support)
    if set(thresholds) != {'support_floor', 'margin_floor'} or not all(
            type(v) in (int, float) and np.isfinite(v) for v in thresholds.values()):
        raise ValueError('Finite declared policy floors required')
    best = scores.argmax(axis=1)
    ordered = np.sort(scores, axis=1)
    margin = ordered[:, -1] - ordered[:, -2]
    accepted = ((support >= thresholds['support_floor']) & (margin >= thresholds['margin_floor']) & (margin > 0))
    return [fields[i] if ok else None for i, ok in zip(best, accepted, strict=True)]


def passes(metrics):
    cohorts = [metrics['aggregate'], *metrics['by_language'].values()]
    return set(metrics['by_language']) == {'en', 'pt'} and all(
        m['gate_pass'] and m['correct_supported_coverage'] is not None
        and m['correct_supported_coverage'] >= .80 for m in cohorts)


def detailed(inputs, labels, predictions):
    result = base.reductions(inputs, labels, predictions)
    result['router_gate_pass'] = passes(result)
    return result


def calibrate(inputs, labels, support, field_logits, fields):
    predict(support, field_logits, fields, dict(support_floor=0., margin_floor=0.))
    if not inputs or len(inputs) != len(support):
        raise ValueError('Aligned nonempty training queries required')
    scores = np.sort(np.asarray(field_logits), axis=1)
    margin = scores[:, -1] - scores[:, -2]
    floors = [sorted(set(np.quantile(v, np.linspace(0, 1, RECIPE['quantiles'])).tolist() + [float(max(v) + 1)]))
              for v in (support, margin)]
    languages = sorted({q['language'] for q in inputs})
    indices = {lang: [i for i, q in enumerate(inputs) if q['language'] == lang] for lang in languages}
    best = None
    evaluated = 0
    for s in floors[0]:
        for m in floors[1]:
            thresholds = dict(support_floor=s, margin_floor=m)
            pred = predict(support, field_logits, fields, thresholds)
            metrics = dict(aggregate=base.reduction(inputs, labels, pred), by_language={
                lang: base.reduction([inputs[i] for i in ix], labels, [pred[i] for i in ix])
                for lang, ix in indices.items()})
            evaluated += 1
            if passes(metrics):
                coverage = [v['correct_supported_coverage'] for v in metrics['by_language'].values()]
                key = (min(coverage), metrics['aggregate']['correct_supported_coverage'], -s, -m)
                if best is None or key > best[0]:
                    best = (key, thresholds, pred)
    return dict(thresholds=None if best is None else best[1], policies_evaluated=evaluated,
                metrics=None if best is None else detailed(inputs, labels, best[2]),
                fitted_on='train_only', validation_used=False)


def fit(features, targets, fields):
    import torch
    import torch.nn.functional as F
    matrix = np.asarray(features, dtype=float)
    if (matrix.ndim != 2 or not len(matrix) or matrix.shape[1] < 1 or not np.isfinite(matrix).all()
            or len(targets) != len(matrix) or len(fields) < 2 or len(fields) != len(set(fields))
            or set(t for t in targets if t is not None) != set(fields) or None not in targets):
        raise ValueError('Finite training features with all fields and unsupported queries required')
    torch.set_num_threads(RECIPE['threads'])
    mean, scale = matrix.mean(axis=0), matrix.std(axis=0)
    scale[scale == 0] = 1.
    x = torch.tensor((matrix - mean) / scale, dtype=torch.float64)
    y = torch.tensor([fields.index(t) if t is not None else -1 for t in targets])
    known = y >= 0
    support_w = torch.zeros(x.shape[1], dtype=torch.float64, requires_grad=True)
    support_b = torch.zeros((), dtype=torch.float64, requires_grad=True)
    field_w = torch.zeros((len(fields), x.shape[1]), dtype=torch.float64, requires_grad=True)
    field_b = torch.zeros(len(fields), dtype=torch.float64, requires_grad=True)
    parameters = [support_w, support_b, field_w, field_b]
    optimizer = torch.optim.Adam(parameters, lr=RECIPE['lr'])
    history = []
    for step in range(RECIPE['updates']):
        optimizer.zero_grad()
        binary = F.binary_cross_entropy_with_logits(x @ support_w + support_b, known.to(torch.float64), reduction='none')
        support_loss = .5 * (binary[known].mean() + binary[~known].mean())
        field_loss = F.cross_entropy(x[known] @ field_w.T + field_b, y[known])
        loss = support_loss + field_loss + RECIPE['weight_penalty'] * (support_w.square().mean() + field_w.square().mean())
        if not bool(torch.isfinite(loss)):
            raise ValueError('Nonfinite loss; no checkpoint or retry')
        loss.backward()
        if any(p.grad is None or not bool(torch.isfinite(p.grad).all()) for p in parameters):
            raise ValueError('Nonfinite/incomplete gradients; no checkpoint or retry')
        optimizer.step()
        if any(not bool(torch.isfinite(p).all()) for p in parameters):
            raise ValueError('Nonfinite weights; no checkpoint or retry')
        history.append(dict(update=step + 1, loss=float(loss.detach()),
                            support_loss=float(support_loss.detach()), field_loss=float(field_loss.detach())))
    model = dict(mean=mean.tolist(), scale=scale.tolist(), fields=fields,
                 support_weight=support_w.detach().tolist(), support_bias=float(support_b.detach()),
                 field_weight=field_w.detach().tolist(), field_bias=field_b.detach().tolist())
    return model, history


def logits(features, model):
    matrix = np.asarray(features, dtype=float)
    x = (matrix - model['mean']) / model['scale']
    support = x @ np.asarray(model['support_weight']) + model['support_bias']
    fields = x @ np.asarray(model['field_weight']).T + model['field_bias']
    predict(support, fields, model['fields'], None)
    return support.tolist(), fields.tolist()


def population(split):
    inputs = base.load(DATA / f'{split}-inputs.json')
    labels = base.load(DATA / f'{split}-annotations.json')
    registry = base.load(DATA / 'registry.json')
    candidates = registry['fields'] + registry['unsupported']
    raw = base.load(DATA / f'{split}-scores.json')['rows']
    base.predictions(raw, inputs, candidates)
    features = [[r['score'] for r in raw[i * len(candidates):(i + 1) * len(candidates)]] for i in range(len(inputs))]
    return inputs, labels, features


def prepare():
    if (OUT / 'protocol.json').exists():
        raise ValueError('Already frozen; no overwrite or recipe search')
    audit_parent()
    parent = base.checked_protocol(live=True)
    fields = [f['id'] for f in base.load(DATA / 'registry.json')['fields']]
    assert len(fields) == 8 and len(parent['candidates']) == 12
    sources = dict(parent['sources'])
    sources.update({name: base.sha(ROOT / name) for name in (
        'research/goal_support_pilot.py', 'tests/test_goal_support_pilot.py', 'research/audit_goal_interpreter_probe.py')})
    files = [OUT / 'PLAN.md', DATA / 'protocol.json', DATA / 'audit-summary-supplement.json']
    files += [DATA / f'{split}-{kind}.json' for split in ('train', 'validation') for kind in ('inputs', 'annotations', 'scores')]
    populations = {}
    identities = []
    for split in ('train', 'validation'):
        inputs, labels, features = population(split)
        assert len({q['id'] for q in inputs}) == len(inputs)
        identities.append({q['id'] for q in inputs})
        assert set(labels) == identities[-1] and all(set(q) == {'id', 'language', 'question'} for q in inputs)
        assert all(len(v) == 12 for v in features)
        populations[split] = dict(queries=len(inputs), supported=sum(a['target'] is not None for a in labels.values()))
    assert not (identities[0] & identities[1])
    protocol = dict(schema='cached-goal-support-pilot/0.1', frozen_at_utc=base.now(),
                    parent_protocol_sha256=parent['sha256'], fields=fields, recipe=RECIPE,
                    sources=sources, files={str(f.relative_to(ROOT)): base.sha(f) for f in files},
                    populations=populations, features='12 immutable query/public-definition logits; no annotation or record features',
                    trained_parameters=117, backbone_updates=0, additional_encoder_forwards=0,
                    newly_tokenized_inputs=0, newly_scored_model_tokens=0, API_calls=0,
                    scope='Exposed authored development questions; not fresh confirmation, human certification, full selection or LCC serving',
                    versions={k: importlib.metadata.version(k) for k in ('torch', 'numpy')},
                    P2_admission=False, default_changed=False, independent_human_review=False)
    protocol['sha256'] = base.digest(protocol)
    for name, wanted in sources.items():
        dest = OUT / 'sources' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((ROOT / name).read_bytes())
        assert base.sha(dest) == wanted
    base.save(OUT / 'protocol.json', protocol)
    print(json.dumps(dict(protocol_sha256=protocol['sha256'], populations=populations, additional_encoder_forwards=0)))


def checked():
    p = base.load(OUT / 'protocol.json')
    assert base.digest({k: v for k, v in p.items() if k != 'sha256'}) == p['sha256'] and p['recipe'] == RECIPE
    for name, wanted in p['sources'].items():
        assert base.sha(ROOT / name) == wanted and base.sha(OUT / 'sources' / name) == wanted, name
    for name, wanted in p['files'].items():
        assert base.sha(ROOT / name) == wanted, name
    assert base.checked_protocol(live=True)['sha256'] == p['parent_protocol_sha256']
    return p


def run():
    p = checked()
    if (OUT / 'started.json').exists():
        raise ValueError('Already started; inspect receipts without restarting')
    base.save(OUT / 'started.json', dict(protocol_sha256=p['sha256'], utc=base.now()))
    def denied(*args, **kwargs):
        raise RuntimeError('Network forbidden during local cached-head fit')
    socket.socket.connect = denied
    inputs, labels, features = population('train')
    began = time.perf_counter()
    model, history = fit(features, [labels[q['id']]['target'] for q in inputs], p['fields'])
    fit_s = time.perf_counter() - began
    base.save(OUT / 'head.json', model)
    base.save(OUT / 'training.json', dict(protocol_sha256=p['sha256'], completed_updates=len(history),
              history=history, loss_scope='Before each optimizer update; not final-model loss', fit_s=fit_s,
              support_training_row_forwards=len(inputs) * len(history),
              field_training_row_forwards=p['populations']['train']['supported'] * len(history),
              trained_parameters=sum(len(v) for v in model['field_weight']) + len(model['field_bias']) + len(model['support_weight']) + 1,
              head_sha256=base.sha(OUT / 'head.json'), backbone_updates=0, additional_encoder_forwards=0,
              finished_at_utc=base.now()))
    support, fields = logits(features, model)
    calibration = calibrate(inputs, labels, support, fields, p['fields'])
    base.save(OUT / 'calibration.json', calibration)
    results = {}
    for split in ('train', 'validation'):
        q, ann, x = population(split)
        s, f = logits(x, model)
        predictions = predict(s, f, p['fields'], calibration['thresholds'])
        result = dict(protocol_sha256=p['sha256'], support_logits=s, field_logits=f, predictions=predictions,
                      metrics=detailed(q, ann, predictions),
                      zero_floor_diagnostic=detailed(q, ann, predict(s, f, p['fields'], dict(support_floor=0., margin_floor=0.))),
                      zero_floor_diagnostic_is_adopted=False)
        base.save(OUT / f'{split}-results.json', result)
        results[split] = result
    passed = calibration['thresholds'] is not None and results['validation']['metrics']['router_gate_pass']
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    summary = dict(protocol_sha256=p['sha256'], finished_at_utc=base.now(),
                   validation=results['validation']['metrics']['aggregate'], router_gate_pass=passed,
                   next_action='prepare_fresh_family_confirmation' if passed else 'STOP_before_fresh_confirmation_and_LCC',
                   train_policy_available=calibration['thresholds'] is not None,
                   trained_parameters=117, completed_updates=len(history), head_fit_s=fit_s,
                   elapsed_after_train_inputs_s=time.perf_counter() - began,
                   peak_head_process_rss_bytes=rss if sys.platform == 'darwin' else rss * 1024,
                   performance_scope='Cached-head fit/evaluation; excludes predecessor encoder scoring/setup and LCC serving',
                   additional_encoder_forwards=0, newly_scored_model_tokens=0, API_calls=0,
                   P2_admission=False, default_changed=False, independent_human_review=False)
    base.save(OUT / 'summary.json', summary)
    print(json.dumps({k: summary[k] for k in ('protocol_sha256', 'router_gate_pass', 'train_policy_available', 'next_action')}))


def audit():
    p = checked()
    model = base.load(OUT / 'head.json')
    training = base.load(OUT / 'training.json')
    assert training['protocol_sha256'] == p['sha256'] and training['head_sha256'] == base.sha(OUT / 'head.json')
    assert training['completed_updates'] == len(training['history']) == RECIPE['updates']
    assert [r['update'] for r in training['history']] == list(range(1, RECIPE['updates'] + 1))
    assert all(np.isfinite(r[k]) for r in training['history'] for k in ('loss', 'support_loss', 'field_loss'))
    inputs, labels, features = population('train')
    mean, scale = np.mean(features, axis=0), np.std(features, axis=0)
    scale[scale == 0] = 1.
    assert model['mean'] == mean.tolist() and model['scale'] == scale.tolist() and model['fields'] == p['fields']
    assert np.shape(model['field_weight']) == (8, 12) and np.shape(model['field_bias']) == (8,)
    assert np.shape(model['support_weight']) == (12,) and np.shape(model['support_bias']) == ()
    assert training['support_training_row_forwards'] == len(inputs) * 200
    assert training['field_training_row_forwards'] == sum(a['target'] is not None for a in labels.values()) * 200
    assert training['backbone_updates'] == training['additional_encoder_forwards'] == 0
    support, fields = logits(features, model)
    calibration = calibrate(inputs, labels, support, fields, p['fields'])
    assert calibration == base.load(OUT / 'calibration.json')
    for split in ('train', 'validation'):
        q, ann, x = population(split)
        s, f = logits(x, model)
        pred = predict(s, f, p['fields'], calibration['thresholds'])
        saved = base.load(OUT / f'{split}-results.json')
        assert saved == dict(protocol_sha256=p['sha256'], support_logits=s, field_logits=f, predictions=pred,
                             metrics=detailed(q, ann, pred),
                             zero_floor_diagnostic=detailed(q, ann, predict(s, f, p['fields'], dict(support_floor=0., margin_floor=0.))),
                             zero_floor_diagnostic_is_adopted=False)
    summary = base.load(OUT / 'summary.json')
    passed = calibration['thresholds'] is not None and saved['metrics']['router_gate_pass']
    assert summary['protocol_sha256'] == p['sha256'] and summary['validation'] == saved['metrics']['aggregate']
    assert summary['router_gate_pass'] is passed and summary['train_policy_available'] is (calibration['thresholds'] is not None)
    assert summary['next_action'] == ('prepare_fresh_family_confirmation' if passed else 'STOP_before_fresh_confirmation_and_LCC')
    assert summary['completed_updates'] == training['completed_updates'] == 200
    assert summary['trained_parameters'] == training['trained_parameters'] == p['trained_parameters'] == 117
    assert summary['head_fit_s'] == training['fit_s'] >= 0
    assert summary['elapsed_after_train_inputs_s'] >= summary['head_fit_s']
    assert summary['peak_head_process_rss_bytes'] > 0
    assert (datetime.fromisoformat(p['frozen_at_utc']) <= datetime.fromisoformat(base.load(OUT / 'started.json')['utc'])
            <= datetime.fromisoformat(training['finished_at_utc']) <= datetime.fromisoformat(summary['finished_at_utc']))
    for key in ('API_calls', 'newly_scored_model_tokens', 'additional_encoder_forwards'):
        assert summary[key] == p[key] == 0
    for flag in ('P2_admission', 'default_changed', 'independent_human_review'):
        assert summary[flag] is p[flag] is False
    result = dict(status='PASS', protocol_sha256=p['sha256'], head_sha256=training['head_sha256'],
                  scope='Offline inputs/weights/policy/math/summary integrity; no independent semantic certification or optimizer replay',
                  router_gate_pass=passed, additional_encoder_forwards=0, additional_training_updates=0,
                  results={name: base.sha(OUT / name) for name in (
                      'train-results.json', 'validation-results.json', 'training.json', 'calibration.json', 'summary.json')})
    path = OUT / 'audit.json'
    if path.exists():
        assert result == base.load(path)
    else:
        base.save(path, result)
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', required=True, choices=('prepare', 'run', 'audit'))
    args = parser.parse_args()
    {'prepare': prepare, 'run': run, 'audit': audit}[args.phase]()
