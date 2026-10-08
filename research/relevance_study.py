"""Bounded direct-P1 relevance study; train/validation/final freeze before training.

Run prepare, cache, train, final in order. Final inference requires a pre-existing
validation selection receipt. No historical scores/checkpoints are overwritten.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import time

import numpy as np
import torch
from torch import nn

from research.relevance_corpus import build_split, typed_control, verify_label

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / 'research/goal-engine-2026-10-04/direct-relevance-v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_once(path, value):
    encoded = json.dumps(value, indent=2, sort_keys=True) + '\n'
    if path.exists():
        if path.read_text() != encoded:
            raise ValueError(f'Existing receipt differs: {path}')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded)


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def prepare(out):
    sources = ['research/relevance_study.py', 'research/relevance_corpus.py',
               'specialist/model.py', 'specialist/checkpoint.py', 'bakeoff/adapters.py',
               'research/head_objective_study.py']
    parent = ROOT / 'models/exp02e-unfreeze2'
    protocol = dict(schema='direct-p1-relevance/0.1', seeds=[101, 202, 303], epochs=3,
                    learning_rate=.0003, encoder_learning_rate=.00002, batch_size=8,
                    frozen_batch_size=8, max_pair_tokens=2048, device='mps', threads=8,
                    arms=['frozen', 'last-two'], groups_per_domain=dict(train=24, validation=8, final=12),
                    selection='highest mean validation strict pooled relevance AUC across three seeds; fixed tie order frozen first',
                    initialization='clean parent backbone/last-two/line scorer; new relevance head per matched seed',
                    labels='direct entity/field/inclusive-window observation relevance; normality independent; UNKNOWN excluded from binary loss',
                    threshold='validation only: greatest raw-logit threshold with >=.95 recall in each healthy/anomalous positive stratum',
                    quality_gate=dict(applies_to='each seed of validation-selected arm', pooled_auc_min=.90, healthy_auc_min=.90, anomalous_auc_min=.90,
                                      healthy_recall_min=.95, anomalous_recall_min=.95,
                                      wrong_entity_anomaly_rejection_min=.70, unreported_cuts=0),
                    final_scope='new fields/entities in six withheld synthetic domains; shared schemas/author task, not external semantic confirmation',
                    bootstrap=dict(unit='whole final domain', draws=2000, seed=78111),
                    parent_weights_sha256=sha(parent / 'weights.pt'), parent_config_sha256=sha(parent / 'config.json'),
                    sources={name: sha(ROOT / name) for name in sources}, final_used_for_selection=False,
                    baselines=['typed', 'lexical', 'bge', 'laya', 'parent'], baseline_device='cpu',
                    latency_comparison='not measured; candidate MPS/cache and controls CPU do not support relative latency claims')
    out.mkdir(parents=True, exist_ok=True)
    data = {}
    hashes, entities = {}, {}
    for split, groups in protocol['groups_per_domain'].items():
        rows = build_split(split, groups)
        assert all(row['label'] == verify_label(row) for row in rows)
        assert all(row['label'] == typed_control(row['objective'], row['text']) for row in rows)
        hashes[split] = {r['content_hash'] for r in rows}
        entities[split] = {r['request']['entity'] for r in rows}
        encoded = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows)
        target = out / f'{split}.jsonl'
        if target.exists():
            assert target.read_text() == encoded
        else:
            target.write_text(encoded)
        data[split] = dict(sha256=sha(target), n=len(rows), known=sum(r['label'] is not None for r in rows),
                           domains=sorted({r['domain'] for r in rows}))
    for a, b in [('train', 'validation'), ('train', 'final'), ('validation', 'final')]:
        assert not (hashes[a] & hashes[b]) and not (entities[a] & entities[b])
    protocol['data'] = data
    protocol['sha256'] = hashlib.sha256(json.dumps(protocol, sort_keys=True).encode()).hexdigest()
    write_once(out / 'protocol.json', protocol)
    for name, expected in protocol['sources'].items():
        target = out / 'executed-source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert sha(target) == expected
        else:
            target.write_bytes((ROOT / name).read_bytes())
    return protocol


def load_parent(device, unfreeze):
    from specialist.model import SpecialistHead
    from specialist.checkpoint import load_trained_weights
    model = SpecialistHead(pooling='line-attn', unfreeze_last_n=2, local_files_only=True)
    state = torch.load(ROOT / 'models/exp02e-unfreeze2/weights.pt', weights_only=True, map_location='cpu')
    load_trained_weights(model, state)
    if not unfreeze:
        model.encoder.requires_grad_(False)
    return model.to(device), state


def encode_uncut(model, rows, protocol):
    lengths = [len(model.tokenizer(r['objective'], r['text'], truncation=False)['input_ids']) for r in rows]
    if max(lengths) > protocol['max_pair_tokens']:
        raise ValueError('Uncut full pair exceeds frozen training maximum')
    encoded = model.encode([r['objective'] for r in rows], [r['text'] for r in rows], protocol['max_pair_tokens'])
    return {key: value.to(protocol['device']) for key, value in encoded.items()}, lengths


def coverage(out, protocol):
    from transformers import AutoTokenizer
    from specialist.model import MODERNBERT_REVISION
    tokenizer = AutoTokenizer.from_pretrained('answerdotai/ModernBERT-base', revision=MODERNBERT_REVISION, local_files_only=True)
    result = {}
    for split in protocol['data']:
        lengths = []
        lost = 0
        for row in read_rows(out / f'{split}.jsonl'):
            encoded = tokenizer(row['objective'], row['text'], truncation=False, return_offsets_mapping=True)
            lengths.append(len(encoded['input_ids']))
            a, b = row['evidence_span']
            spans = [span for seq, span in zip(encoded.sequence_ids(), encoded['offset_mapping']) if seq == 1 and span[1] > a and span[0] < b]
            lost += int(not spans or spans[-1][1] < b)
        assert max(lengths) <= protocol['max_pair_tokens'] and lost == 0
        result[split] = dict(n=len(lengths), min_pair_tokens=min(lengths), max_pair_tokens=max(lengths), truncated=0, incomplete_observations=lost)
    write_once(out / 'coverage.json', result)


def create_cache(out, protocol, splits):
    from research.head_objective_study import occupied_line_representations
    target = out / ('final-features.pt' if splits == ['final'] else 'train-validation-features.pt')
    if target.exists():
        meta = json.loads(target.with_suffix('.json').read_text())
        assert meta['sha256'] == sha(target) and meta['protocol_sha256'] == protocol['sha256']
        return torch.load(target, weights_only=True, map_location='cpu')
    model, state = load_parent(protocol['device'], False)
    model.eval()
    cache = dict(parent_state=state, splits={})
    started = time.perf_counter()
    for split in splits:
        rows = read_rows(out / f'{split}.jsonl')
        if split == 'train':
            rows = [r for r in rows if r['label'] is not None]
        features = []
        for offset in range(0, len(rows), protocol['batch_size']):
            enc, _ = encode_uncut(model, rows[offset:offset + protocol['batch_size']], protocol)
            ids = enc.pop('line_ids')
            # no_grad creates ordinary detached tensors, usable by subsequent head training.
            with torch.no_grad():
                hidden = model.encoder(**enc).last_hidden_state
                features.extend(f.detach().cpu().clone() for f in occupied_line_representations(hidden, ids))
            if offset % 200 == 0:
                print(f'cache {split}: {offset}/{len(rows)}', flush=True)
        cache['splits'][split] = dict(rows=rows, features=features)
    torch.save(cache, target)
    write_once(target.with_suffix('.json'), dict(protocol_sha256=protocol['sha256'], sha256=sha(target),
                                              seconds=time.perf_counter() - started, splits=splits))
    return cache


class RelevanceHead(nn.Module):
    def __init__(self, state):
        super().__init__()
        make = lambda: nn.Sequential(nn.Linear(768, 256), nn.GELU(), nn.Dropout(.1), nn.Linear(256, 1))
        self.line_score, self.head = make(), make()
        self.line_score.load_state_dict({k.removeprefix('line_score.'): v for k, v in state.items() if k.startswith('line_score.')})

    def forward(self, features):
        length = max(len(f) for f in features)
        values = torch.zeros(len(features), length, 768)
        mask = torch.ones(len(features), length, dtype=torch.bool)
        for index, feature in enumerate(features):
            values[index, :len(feature)] = feature
            mask[index, :len(feature)] = False
        weights = self.line_score(values).squeeze(-1).masked_fill(mask, torch.finfo(values.dtype).min).softmax(-1)
        return self.head((values * weights.unsqueeze(-1)).sum(1)).squeeze(-1)


def auc(positive, negative):
    if not positive or not negative:
        return None
    ordered = np.sort(np.asarray(negative, dtype=float))
    return float(np.searchsorted(ordered, np.asarray(positive, dtype=float), side='left').sum() / (len(positive) * len(negative)))


def metrics(rows, threshold=None):
    usable = [r for r in rows if r['score'] is not None and not r.get('truncated') and not r.get('error')]
    neg = [r['score'] for r in usable if r['label'] == 0]
    result = dict(n=len(rows), known=sum(r['label'] is not None for r in rows),
                  eligible_known=sum(r['label'] is not None for r in usable),
                  errors=sum(bool(r.get('error')) for r in rows), cuts=sum(bool(r.get('truncated')) for r in rows),
                  auc=auc([r['score'] for r in usable if r['label'] == 1], neg))
    for status in ['healthy', 'anomalous']:
        positives = [r for r in usable if r['label'] == 1 and r['observation_status'] == status]
        result[status + '_auc'] = auc([r['score'] for r in positives], neg)
        if threshold is not None:
            result[status + '_recall'] = float(np.mean([r['score'] >= threshold for r in positives]))
    if threshold is not None:
        wrong = [r for r in usable if r['kind'] == 'wrong_entity' and r['observation_status'] == 'anomalous']
        result['wrong_entity_anomaly_rejection'] = float(np.mean([r['score'] < threshold for r in wrong]))
    return result


def choose_threshold(rows):
    candidates = sorted({r['score'] for r in rows if r['label'] == 1})
    passing = [t for t in candidates if all(np.mean([r['score'] >= t for r in rows if r['label'] == 1 and r['observation_status'] == s]) >= .95 for s in ['healthy', 'anomalous'])]
    return max(passing)


def record(row, score, **extra):
    return dict(id=row['id'], group=row['group'], domain=row['domain'], kind=row['kind'],
                label=row['label'], observation_status=row['observation_status'],
                input_sha256=row['content_hash'], score=float(score) if score is not None else None, **extra)


def feature_scores(model, split):
    model.eval()
    result = []
    with torch.no_grad():
        for offset in range(0, len(split['rows']), 64):
            batch = split['rows'][offset:offset + 64]
            values = model(split['features'][offset:offset + 64])
            result.extend(record(r, v, truncated=False, error=None) for r, v in zip(batch, values))
    return result


def native_scores(model, rows, protocol):
    model.eval()
    result = []
    with torch.no_grad():
        for offset in range(0, len(rows), protocol['batch_size']):
            batch = rows[offset:offset + protocol['batch_size']]
            enc, lengths = encode_uncut(model, batch, protocol)
            values = model(enc).cpu()
            result.extend(record(r, v, actual_tokens=n, truncated=False, error=None) for r, v, n in zip(batch, values, lengths))
    return result


def reset_head(model):
    for module in model.head.modules():
        if isinstance(module, nn.Linear):
            module.reset_parameters()


def matched_reset_head(model, seed):
    # Constructors/loaders consume RNG differently. Reset at the head boundary
    # so adaptation arms start with the same head parameters for the same seed.
    torch.manual_seed(seed)
    reset_head(model)


def train_one(out, protocol, cache, arm, seed):
    target = out / f'{arm}-{seed}'
    if (target / 'validation.json').exists():
        return
    if target.exists():
        raise ValueError(f'Partial run exists: inspect {target}; no silent retry')
    target.mkdir()
    write_once(target / 'started.json', dict(protocol_sha256=protocol['sha256'], seed=seed, arm=arm))
    random.seed(seed)
    torch.manual_seed(seed)
    if arm == 'frozen':
        model = RelevanceHead(cache['parent_state'])
        matched_reset_head(model, seed)
        optimizer = torch.optim.AdamW(model.parameters(), lr=protocol['learning_rate'], weight_decay=.01)
    else:
        model, _ = load_parent(protocol['device'], True)
        matched_reset_head(model, seed)
        optimizer = torch.optim.AdamW([
            dict(params=[p for name, p in model.named_parameters() if name.startswith('encoder.') and p.requires_grad], lr=protocol['encoder_learning_rate']),
            dict(params=[p for name, p in model.named_parameters() if not name.startswith('encoder.')], lr=protocol['learning_rate'])], weight_decay=.01)
    train = cache['splits']['train']
    order = list(range(len(train['rows'])))
    history = []
    for epoch in range(1, protocol['epochs'] + 1):
        model.train()
        # Frozen prefix representations and dropout are fixed, matching the cache arm.
        if arm != 'frozen':
            model.encoder.eval()
        random.shuffle(order)
        total = 0.
        began = time.perf_counter()
        batch_size = protocol['frozen_batch_size'] if arm == 'frozen' else protocol['batch_size']
        for offset in range(0, len(order), batch_size):
            indices = order[offset:offset + batch_size]
            batch = [train['rows'][i] for i in indices]
            if arm == 'frozen':
                logits = model([train['features'][i] for i in indices])
            else:
                enc, _ = encode_uncut(model, batch, protocol)
                logits = model(enc)
            labels = torch.tensor([r['label'] for r in batch], dtype=torch.float32, device=logits.device)
            loss = nn.functional.binary_cross_entropy_with_logits(logits, labels)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total += float(loss.detach().cpu()) * len(batch)
            if offset % (batch_size * 40) == 0:
                print(f'{arm}/{seed} epoch {epoch}: {offset}/{len(order)}', flush=True)
        history.append(dict(epoch=epoch, loss=total / len(order), seconds=time.perf_counter() - began))
        write_once(target / f'epoch-{epoch}.json', history[-1])
    state = copy.deepcopy(cache['parent_state'])
    if arm == 'frozen':
        state.update(model.state_dict())
        rows = feature_scores(model, cache['splits']['validation'])
    else:
        state.update({name: value.detach().cpu().clone() for name, value in model.state_dict().items()
                      if name in cache['parent_state']})
        rows = native_scores(model, read_rows(out / 'validation.jsonl'), protocol)
    torch.save(state, target / 'weights.pt')
    write_once(target / 'config.json', dict(model_id='answerdotai/ModernBERT-base', pooling='line-attn',
                                          unfreeze_last_n=2, max_len=2048, temperature=1., seed=seed,
                                          task='direct-p1-observation-relevance', backbone_revision='8949b909ec900327062f0ebf497f51aef5e6f0c8'))
    threshold = choose_threshold(rows)
    write_once(target / 'training_meta.json', dict(protocol_sha256=protocol['sha256'], seed=seed, arm=arm,
                                                  epochs_completed=len(history), history=history,
                                                  encoder_adapted=arm == 'last-two', weights_sha256=sha(target / 'weights.pt')))
    write_once(target / 'validation.json', dict(rows=rows, threshold=threshold, metrics=metrics(rows, threshold)))
    print(arm, seed, metrics(rows, threshold), flush=True)


def final(out, protocol):
    selection = json.loads((out / 'selection.json').read_text())
    cache = create_cache(out, protocol, ['final'])
    for arm in protocol['arms']:
        for seed in protocol['seeds']:
            target = out / f'{arm}-{seed}'
            if (target / 'final.json').exists():
                continue
            threshold = json.loads((target / 'validation.json').read_text())['threshold']
            state = torch.load(target / 'weights.pt', weights_only=True, map_location='cpu')
            if arm == 'frozen':
                model = RelevanceHead(state)
                model.load_state_dict({name: value for name, value in state.items() if not name.startswith('encoder.')})
                rows = feature_scores(model, cache['splits']['final'])
            else:
                from specialist.checkpoint import load_trained_weights
                model, _ = load_parent(protocol['device'], False)
                load_trained_weights(model, state)
                rows = native_scores(model, cache['splits']['final']['rows'], protocol)
            write_once(target / 'final.json', dict(rows=rows, threshold=threshold, metrics=metrics(rows, threshold),
                                                 selected_before_final=selection['selected_arm'] == arm))
            print('final', arm, seed, metrics(rows, threshold), flush=True)


def baselines(out, protocol):
    if not (out / 'selection.json').exists():
        raise ValueError('Selection must precede final baseline inference too')
    from bakeoff.adapters import LexicalAdapter, OfficialEmbeddingAdapter, PinnedLayaAdapter
    rows = read_rows(out / 'final.jsonl')
    for name in protocol['baselines']:
        target = out / 'baselines' / f'{name}.json'
        if target.exists():
            continue
        partial = target.with_suffix('.jsonl')
        if partial.exists():
            raise ValueError(f'Partial baseline: inspect {partial}')
        target.parent.mkdir(exist_ok=True)
        if name == 'parent':
            cache = create_cache(out, protocol, ['final'])
            model = RelevanceHead(cache['parent_state'])
            model.load_state_dict({k: v for k, v in cache['parent_state'].items() if not k.startswith('encoder.')})
            scored = feature_scores(model, cache['splits']['final'])
        elif name == 'typed':
            scored = [record(row, typed_control(row['objective'], row['text']), truncated=False, error=None) for row in rows]
        else:
            if name == 'lexical':
                adapter = LexicalAdapter()
            elif name == 'bge':
                adapter = OfficialEmbeddingAdapter.bge()
            else:
                adapter = PinnedLayaAdapter('laya-pinned', str(Path.home() / '.cache/huggingface/hub/models--convaiinnovations--laya-multilingual/snapshots/052592a15d198d9ad47da779604259b10b47b7aa'))
            adapter.load()
            scored = []
            with partial.open('x') as stream:
                for index, row in enumerate(rows):
                    value = adapter.score(row['objective'], row['text'])
                    item = record(row, value.value, truncated=value.truncated, error=value.error,
                                  actual_tokens=value.actual_tokens, latency_ms=value.latency_ms)
                    scored.append(item)
                    stream.write(json.dumps(item) + '\n')
                    stream.flush()
                    if index % 100 == 0:
                        print(f'baseline {name}: {index}/{len(rows)}', flush=True)
            adapter.close()
        write_once(target, dict(rows=scored, metrics=metrics(scored), protocol_sha256=protocol['sha256']))
        print('baseline', name, metrics(scored), flush=True)


def summarize(out, protocol):
    selection = json.loads((out / 'selection.json').read_text())
    result = dict(protocol_sha256=protocol['sha256'], selected_arm=selection['selected_arm'], arms={}, baselines={})
    criterion = protocol['quality_gate']
    for arm in protocol['arms']:
        receipts = [json.loads((out / f'{arm}-{seed}/final.json').read_text()) for seed in protocol['seeds']]
        keys = ['auc', 'healthy_auc', 'anomalous_auc', 'healthy_recall', 'anomalous_recall', 'wrong_entity_anomaly_rejection']
        means = {key: float(np.mean([r['metrics'][key] for r in receipts])) for key in keys}
        seeds_pass = []
        for receipt in receipts:
            m = receipt['metrics']
            seeds_pass.append(m['eligible_known'] == m['known'] and m['errors'] == m['cuts'] == 0 and
                              all(m[key] >= criterion[key + '_min'] for key in keys if key != 'auc') and
                              m['auc'] >= criterion['pooled_auc_min'])
        rng = np.random.default_rng(protocol['bootstrap']['seed'])
        domains = sorted({r['domain'] for r in receipts[0]['rows']})
        boot = []
        for _ in range(protocol['bootstrap']['draws']):
            chosen = rng.choice(domains, len(domains), replace=True)
            values = []
            for receipt in receipts:
                sampled = [r for domain in chosen for r in receipt['rows'] if r['domain'] == domain]
                values.append(metrics(sampled)['auc'])
            boot.append(float(np.mean(values)))
        result['arms'][arm] = dict(mean=means, seeds_pass=seeds_pass, all_seed_gate_pass=all(seeds_pass),
                                  pooled_auc_domain_bootstrap_95=np.percentile(boot, [2.5, 97.5]).tolist())
    for name in protocol['baselines']:
        result['baselines'][name] = json.loads((out / 'baselines' / f'{name}.json').read_text())['metrics']
    result['adoption'] = False
    result['reason'] = 'Synthetic P1 gate is separate from old incident gate and downstream LCC outcomes; no policy promotion from this study'
    write_once(out / 'summary.json', result)
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['prepare', 'cache', 'train', 'final', 'baselines', 'summarize'], required=True)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--arm', choices=['frozen', 'last-two', 'all'], default='all')
    args = parser.parse_args()
    protocol = prepare(args.out)
    torch.set_num_threads(protocol['threads'])
    if args.phase == 'prepare':
        coverage(args.out, protocol)
        print(json.dumps(protocol['data'], indent=2))
        return
    if args.phase == 'baselines':
        baselines(args.out, protocol)
        return
    if args.phase == 'summarize':
        summarize(args.out, protocol)
        return
    if args.phase == 'final':
        if not (args.out / 'selection.json').exists():
            raise ValueError('Validation selection must exist before final inference')
        final(args.out, protocol)
        return
    cache = create_cache(args.out, protocol, ['train', 'validation'])
    if args.phase == 'cache':
        return
    for arm in protocol['arms'] if args.arm == 'all' else [args.arm]:
        for seed in protocol['seeds']:
            train_one(args.out, protocol, cache, arm, seed)
    if not all((args.out / f'{arm}-{seed}/validation.json').exists() for arm in protocol['arms'] for seed in protocol['seeds']):
        return
    means = {arm: float(np.mean([json.loads((args.out / f'{arm}-{seed}/validation.json').read_text())['metrics']['auc']
                               for seed in protocol['seeds']])) for arm in protocol['arms']}
    selected = max(protocol['arms'], key=lambda arm: means[arm])
    write_once(args.out / 'selection.json', dict(protocol_sha256=protocol['sha256'], selected_arm=selected,
                                                validation_mean_auc=means, final_used_for_selection=False))


if __name__ == '__main__':
    main()
