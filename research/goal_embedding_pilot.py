"""One frozen-query encoder pilot, reusing the unchanged support/field recipe."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import resource
import socket
import sys
import time

import numpy as np

from research import goal_support_pilot as head
from research import goal_interpreter_probe as base

ROOT = base.ROOT
DATA = base.OUT
OUT = DATA.parent / 'goal-embedding-pilot-v1'


def masked_mean(hidden, mask):
    values, mask = np.asarray(hidden), np.asarray(mask)
    if (values.ndim != 3 or mask.shape != values.shape[:2] or not np.isfinite(values).all()
            or not np.isin(mask, [0, 1]).all() or not (mask.sum(1) > 0).all()):
        raise ValueError('Finite attended hidden states with aligned nonempty binary masks required')
    weights = mask.astype(values.dtype)
    return ((values * weights[:, :, None]).sum(1) / weights.sum(1)[:, None]).tolist()


def snapshot(model):
    return Path.home() / '.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1/snapshots' / model['revision']


def queries(split):
    return base.load(DATA / f'{split}-inputs.json'), base.load(DATA / f'{split}-annotations.json')


def prepare():
    if (OUT / 'protocol.json').exists():
        raise ValueError('Already frozen; no recipe overwrite')
    parent = head.checked()
    assert base.load(head.OUT / 'summary.json')['router_gate_pass'] is False
    model = base.checked_protocol(live=True)['model']
    for name, wanted in model['files'].items():
        assert base.sha(snapshot(model) / name) == wanted, name
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(snapshot(model), local_files_only=True, trust_remote_code=False)
    lengths = {split: [len(tokenizer(q['question'], truncation=False)['input_ids']) for q in queries(split)[0]]
               for split in ('train', 'validation')}
    assert max(max(v) for v in lengths.values()) <= 512
    base.save(OUT / 'token-lengths.json', lengths)
    sources = dict(parent['sources'])
    sources.update({name: base.sha(ROOT / name) for name in (
        'research/goal_embedding_pilot.py', 'tests/test_goal_embedding_pilot.py', 'research/reranker_control.py')})
    files = [OUT / 'PLAN.md', OUT / 'token-lengths.json', head.OUT / 'protocol.json', head.OUT / 'summary.json', head.OUT / 'audit.json']
    files += [DATA / f'{split}-{kind}.json' for split in ('train', 'validation') for kind in ('inputs', 'annotations')]
    dimension = base.load(snapshot(model) / 'config.json')['hidden_size']
    protocol = dict(schema='frozen-query-embedding-pilot/0.1', frozen_at_utc=base.now(),
                    parent_protocol_sha256=parent['sha256'], sources=sources,
                    files={str(f.relative_to(ROOT)): base.sha(f) for f in files}, model=model,
                    fields=parent['fields'], populations=parent['populations'], recipe=head.RECIPE,
                    encoder=dict(dtype='float32', device='cpu', threads=8, batch_size=16, window=512,
                                 pooling='Mean last hidden state over every attended token, including special tokens; padding excluded'),
                    dimension=dimension, trained_parameters=9 * (dimension + 1),
                    declared_query_forwards=sum(len(v) for v in lengths.values()),
                    maximum_query_forwards=30000, declared_encoder_tokens=sum(sum(v) for v in lengths.values()),
                    input='Natural query only; no definitions, labels, records, entity suffix or field metadata',
                    API_calls=0, backbone_updates=0, P2_admission=False, default_changed=False, independent_human_review=False)
    assert protocol['declared_query_forwards'] <= protocol['maximum_query_forwards']
    protocol['sha256'] = base.digest(protocol)
    for name, wanted in sources.items():
        dest = OUT / 'sources' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((ROOT / name).read_bytes())
        assert base.sha(dest) == wanted
    base.save(OUT / 'protocol.json', protocol)
    print(json.dumps({k: protocol[k] for k in ('sha256', 'declared_query_forwards', 'declared_encoder_tokens', 'dimension', 'trained_parameters')}))


def checked():
    p = base.load(OUT / 'protocol.json')
    assert base.digest({k: v for k, v in p.items() if k != 'sha256'}) == p['sha256'] and p['recipe'] == head.RECIPE
    assert p['parent_protocol_sha256'] == head.checked()['sha256']
    for name, wanted in p['sources'].items():
        assert base.sha(ROOT / name) == wanted and base.sha(OUT / 'sources' / name) == wanted, name
    for name, wanted in p['files'].items():
        assert base.sha(ROOT / name) == wanted, name
    return p


def features(split, p):
    q, labels = queries(split)
    saved = base.load(OUT / f'{split}-embeddings.json')
    lengths = base.load(OUT / 'token-lengths.json')[split]
    assert saved['protocol_sha256'] == p['sha256'] and len(saved['rows']) == len(q)
    for item, row, n in zip(saved['rows'], q, lengths, strict=True):
        assert item['id'] == row['id'] and item['query_sha256'] == base.digest(row['question'])
        assert item['actual_tokens'] == n and item['status'] == 'ENCODED'
        assert len(item['embedding']) == p['dimension'] and np.isfinite(item['embedding']).all()
    return q, labels, [r['embedding'] for r in saved['rows']]


def evaluate(p, model, calibration):
    results = {}
    for split in ('train', 'validation'):
        q, labels, x = features(split, p)
        s, f = head.logits(x, model)
        pred = head.predict(s, f, p['fields'], calibration['thresholds'])
        results[split] = dict(protocol_sha256=p['sha256'], support_logits=s, field_logits=f, predictions=pred,
                             metrics=head.detailed(q, labels, pred),
                             zero_floor_diagnostic=head.detailed(q, labels, head.predict(s, f, p['fields'], dict(support_floor=0., margin_floor=0.))),
                             zero_floor_diagnostic_is_adopted=False)
    return results


def run():
    p = checked()
    if (OUT / 'started.json').exists():
        raise ValueError('Already started; no rescore/retry')
    base.save(OUT / 'started.json', dict(protocol_sha256=p['sha256'], utc=base.now()))
    def denied(*args, **kwargs):
        raise RuntimeError('Network forbidden in local encoder/head pilot')
    socket.socket.connect = denied
    import torch
    from research.reranker_control import PairReranker
    torch.set_num_threads(8)
    began = time.perf_counter()
    scorer = PairReranker.from_snapshot(snapshot(p['model']), p['model'], max_pair_tokens=512, batch_size=16)
    scorer.model.requires_grad_(False)
    base.save(OUT / 'load.json', dict(identity=scorer.identity, elapsed_s=time.perf_counter() - began,
                                    encoder_trainable_parameters=sum(t.numel() for t in scorer.model.parameters() if t.requires_grad)))
    batches = count = tokens = 0
    lengths = base.load(OUT / 'token-lengths.json')
    for split in ('train', 'validation'):
        q, _ = queries(split)
        rows = []
        start = time.perf_counter()
        for offset in range(0, len(q), 16):
            chunk = q[offset:offset + 16]
            encoded = scorer.tokenizer([r['question'] for r in chunk], padding=True, truncation=False, return_tensors='pt')
            actual = encoded['attention_mask'].sum(1).tolist()
            assert actual == lengths[split][offset:offset + 16] and max(actual) <= 512
            with torch.inference_mode():
                hidden = scorer.model.base_model(**encoded).last_hidden_state
                vectors = masked_mean(hidden.detach().numpy(), encoded['attention_mask'].numpy())
            assert all(len(v) == p['dimension'] for v in vectors)
            rows.extend(dict(id=r['id'], query_sha256=base.digest(r['question']), actual_tokens=n,
                             embedding=v, status='ENCODED') for r, n, v in zip(chunk, actual, vectors, strict=True))
            batches += 1
            count += len(chunk)
            tokens += sum(actual)
        base.save(OUT / f'{split}-embeddings.json', dict(protocol_sha256=p['sha256'], rows=rows,
                  elapsed_s=time.perf_counter() - start, finished_at_utc=base.now()))
    assert count == p['declared_query_forwards'] and tokens == p['declared_encoder_tokens']
    q, labels, x = features('train', p)
    fit_start = time.perf_counter()
    model, history = head.fit(x, [labels[r['id']]['target'] for r in q], p['fields'])
    fit_s = time.perf_counter() - fit_start
    base.save(OUT / 'head.json', model)
    base.save(OUT / 'training.json', dict(protocol_sha256=p['sha256'], completed_updates=len(history), history=history,
              head_sha256=base.sha(OUT / 'head.json'), fit_s=fit_s, finished_at_utc=base.now(),
              support_training_row_forwards=len(q) * len(history), field_training_row_forwards=sum(a['target'] is not None for a in labels.values()) * len(history),
              loss_scope='Before each optimizer update; not final-model loss', trained_parameters=p['trained_parameters'], backbone_updates=0))
    s, f = head.logits(x, model)
    calibration = head.calibrate(q, labels, s, f, p['fields'])
    base.save(OUT / 'calibration.json', calibration)
    results = evaluate(p, model, calibration)
    for split, result in results.items():
        base.save(OUT / f'{split}-results.json', result)
    passed = calibration['thresholds'] is not None and results['validation']['metrics']['router_gate_pass']
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    summary = dict(protocol_sha256=p['sha256'], finished_at_utc=base.now(), router_gate_pass=passed,
                   train_policy_available=calibration['thresholds'] is not None, validation=results['validation']['metrics']['aggregate'],
                   next_action='prepare_fresh_family_confirmation' if passed else 'STOP_before_fresh_confirmation_and_LCC',
                   encoder_query_forwards=count, encoder_batch_forwards=batches, scored_encoder_tokens=tokens,
                   trained_parameters=p['trained_parameters'], completed_updates=len(history), head_fit_s=fit_s,
                   elapsed_s=time.perf_counter() - began, peak_process_rss_bytes=rss if sys.platform == 'darwin' else rss * 1024,
                   performance_scope='Local encoder loading/whole-query encoding/head fit/evaluation; not LCC serving',
                   API_calls=0, backbone_updates=0, P2_admission=False, default_changed=False, independent_human_review=False)
    base.save(OUT / 'summary.json', summary)
    print(json.dumps({k: summary[k] for k in ('router_gate_pass', 'train_policy_available', 'next_action', 'encoder_query_forwards', 'scored_encoder_tokens')}))


def audit():
    p = checked()
    model = base.load(OUT / 'head.json')
    training = base.load(OUT / 'training.json')
    assert training['protocol_sha256'] == p['sha256'] and training['head_sha256'] == base.sha(OUT / 'head.json')
    assert training['completed_updates'] == len(training['history']) == head.RECIPE['updates']
    assert [r['update'] for r in training['history']] == list(range(1, 201))
    assert all(np.isfinite(r[k]) for r in training['history'] for k in ('loss', 'support_loss', 'field_loss'))
    q, labels, x = features('train', p)
    mean, scale = np.mean(x, axis=0), np.std(x, axis=0)
    scale[scale == 0] = 1.
    assert model['mean'] == mean.tolist() and model['scale'] == scale.tolist() and model['fields'] == p['fields']
    assert np.shape(model['field_weight']) == (8, p['dimension']) and np.shape(model['support_weight']) == (p['dimension'],)
    assert np.shape(model['field_bias']) == (8,) and np.shape(model['support_bias']) == ()
    assert training['support_training_row_forwards'] == len(q) * 200
    assert training['field_training_row_forwards'] == sum(a['target'] is not None for a in labels.values()) * 200
    s, f = head.logits(x, model)
    calibration = head.calibrate(q, labels, s, f, p['fields'])
    assert calibration == base.load(OUT / 'calibration.json')
    results = evaluate(p, model, calibration)
    for split, result in results.items():
        assert result == base.load(OUT / f'{split}-results.json')
    summary = base.load(OUT / 'summary.json')
    passed = calibration['thresholds'] is not None and results['validation']['metrics']['router_gate_pass']
    assert summary['protocol_sha256'] == p['sha256'] and summary['validation'] == results['validation']['metrics']['aggregate']
    assert summary['router_gate_pass'] is passed and summary['train_policy_available'] is (calibration['thresholds'] is not None)
    assert summary['next_action'] == ('prepare_fresh_family_confirmation' if passed else 'STOP_before_fresh_confirmation_and_LCC')
    assert summary['completed_updates'] == training['completed_updates'] == 200
    assert summary['trained_parameters'] == training['trained_parameters'] == p['trained_parameters'] == 9 * (p['dimension'] + 1)
    assert summary['head_fit_s'] == training['fit_s'] >= 0 and summary['elapsed_s'] >= summary['head_fit_s']
    assert summary['peak_process_rss_bytes'] > 0
    assert summary['encoder_query_forwards'] == p['declared_query_forwards'] == sum(len(queries(s)[0]) for s in results)
    assert summary['scored_encoder_tokens'] == p['declared_encoder_tokens'] == sum(sum(v) for v in base.load(OUT / 'token-lengths.json').values())
    assert summary['encoder_batch_forwards'] == sum((len(queries(s)[0]) + 15) // 16 for s in results)
    loaded = base.load(OUT / 'load.json')
    assert loaded['identity']['model_sha256'] == p['model']['files']['model.safetensors'] and loaded['encoder_trainable_parameters'] == 0
    assert loaded['identity']['revision'] == p['model']['revision']
    chronology = [p['frozen_at_utc'], base.load(OUT / 'started.json')['utc']]
    chronology += [base.load(OUT / f'{s}-embeddings.json')['finished_at_utc'] for s in results]
    chronology += [training['finished_at_utc'], summary['finished_at_utc']]
    assert [datetime.fromisoformat(v) for v in chronology] == sorted(datetime.fromisoformat(v) for v in chronology)
    for flag in ('P2_admission', 'default_changed', 'independent_human_review'):
        assert summary[flag] is p[flag] is False
    assert summary['API_calls'] == p['API_calls'] == summary['backbone_updates'] == training['backbone_updates'] == 0
    result = dict(status='PASS', protocol_sha256=p['sha256'], router_gate_pass=passed,
                  scope='Offline source/input/embedding identity/head/policy/math/accounting integrity; no encoder or optimizer replay, human semantic certification or serving evidence',
                  additional_encoder_forwards=0, additional_training_updates=0,
                  results={name: base.sha(OUT / name) for name in (
                      'head.json', 'training.json', 'calibration.json', 'summary.json', 'train-embeddings.json',
                      'validation-embeddings.json', 'train-results.json', 'validation-results.json')})
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
