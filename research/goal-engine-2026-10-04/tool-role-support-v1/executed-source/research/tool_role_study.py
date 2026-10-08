"""Bounded full MiniLM adaptation with explicit semantic UNKNOWN supervision."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import random
import resource
import socket
import statistics
import sys
import time

import torch
from safetensors.torch import load_file, save_file

from research.audit_tool_role_data import audit as audit_data
from research.reranker_control import PairReranker
from research.tool_role_training import training_items, class_weights, classification_loss, score_axes
from research.tool_role_policy import calibrate, metrics, passes
from specialist.checkpoint import load_trained_weights
from specialist.numerical import finite_update

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/goal-engine-2026-10-04/tool-role-support-v1'
DATA = ROOT / 'research/goal-engine-2026-10-04/tool-role-grounded-v1'
WEIGHTS = ROOT / 'models/tool-role-support-v1'
UPSTREAM = ROOT / 'research/goal-engine-2026-10-04/rerank-next/upstream-manifest.json'
SOURCES = ['research/tool_role_study.py', 'research/tool_role_training.py', 'research/tool_role_policy.py',
           'research/audit_tool_role_support.py', 'research/audit_tool_role_data.py',
           'research/reranker_control.py', 'specialist/checkpoint.py', 'specialist/numerical.py']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def save_once(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if json.loads(path.read_text()) != value:
            raise ValueError(f'Frozen receipt changed: {path.name}')
        return
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def now():
    return datetime.now(timezone.utc).isoformat()


def snapshot_path(manifest):
    return Path.home() / '.cache/huggingface/hub/models--cross-encoder--ms-marco-MiniLM-L6-v2/snapshots' / manifest['revision']


def dataset(split):
    rows = [json.loads(line) for line in (DATA / f'{split}.jsonl').read_text().splitlines()]
    views = [json.loads(line) for line in (DATA / f'{split}-views.jsonl').read_text().splitlines()]
    return rows, views


def fresh_head(model, seed):
    # Deterministic local head initialization. The pretrained scalar head is
    # intentionally replaced; the pretrained encoder state remains untouched.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        layer = torch.nn.Linear(model.config.hidden_size, 3)
        torch.nn.init.normal_(layer.weight, mean=0, std=.02)
        torch.nn.init.zeros_(layer.bias)
    model.classifier = layer
    model.config.num_labels = model.num_labels = 3
    model.config.id2label = {0: 'IRRELEVANT', 1: 'RELEVANT', 2: 'UNKNOWN'}
    model.config.label2id = {v: k for k, v in model.config.id2label.items()}


def numeric_batch(encoded, lengths, window):
    if encoded['input_ids'].shape[1] > window or encoded['attention_mask'].sum(1).tolist() != lengths:
        raise ValueError('Whole-pair attention mask/window mismatch')
    return int(encoded['attention_mask'].sum()), encoded['input_ids'].numel()


def prepare():
    if (OUT / 'protocol.json').exists():
        protocol = json.loads((OUT / 'protocol.json').read_text())
        if digest({k: v for k, v in protocol.items() if k != 'sha256'}) != protocol['sha256']:
            raise ValueError('Changed study protocol')
        for name, expected in protocol['sources'].items():
            if sha(ROOT / name) != expected or sha(OUT / 'executed-source' / name) != expected:
                raise ValueError(f'Changed frozen study source: {name}')
        for name, expected in protocol['data_files'].items():
            if sha(DATA / name) != expected:
                raise ValueError('Changed referenced dataset')
        return protocol
    data_audit = audit_data(DATA, verify_tokenizer=True)
    manifest = json.loads(UPSTREAM.read_text())
    for name, expected in manifest['files'].items():
        if sha(snapshot_path(manifest) / name) != expected:
            raise ValueError(f'Original pinned model/tokenizer mismatch: {name}')
    rows, views = dataset('train')
    items = training_items(rows, views)
    weights = class_weights(items)
    data_files = {name: sha(DATA / name) for name in ['protocol.json', 'coverage.json'] +
                  [f'{split}{suffix}' for split in ['train', 'validation', 'final'] for suffix in ['.jsonl', '-views.jsonl', '-raw.json']]}
    protocol = dict(schema='tool-role-support/0.1', frozen_at_utc=now(), model=manifest,
                    data_protocol_sha256=data_audit['protocol_sha256'], data_directory=DATA.name, data_files=data_files,
                    data_scope='Actual tools on authored fixtures, authored EN/PT goals and English captions; counterfactual claims; only DU/DF/GZIP binary supervision/strings withheld, raw receipts include every tool; three correlated final sources and shared concepts',
                    sources={name: sha(ROOT / name) for name in SOURCES},
                    versions={name: importlib.metadata.version(name) for name in ['torch', 'transformers', 'tokenizers', 'numpy', 'safetensors']},
                    seeds=[101, 202, 303], epochs=3, batch_size=16, device='cpu', dtype='float32', threads=8,
                    optimizer=dict(name='AdamW', lr=.00002, weight_decay=.01, betas=[.9, .999], eps=1e-8),
                    adaptation='All pretrained encoder parameters; scalar head replaced by Linear(hidden_size,3), Normal(0,.02) weight/zero bias at declared seed; no encoder reset',
                    labels=['IRRELEVANT', 'RELEVANT', 'UNKNOWN'], train_unique=len(items),
                    train_class_counts=[sum(item['class_id'] == label for item in items) for label in range(3)],
                    global_class_weights=weights, train_unique_items_sha256=digest(items),
                    objective='Mean per-item cross entropy times fixed N/(3*n_class) after training-view deduplication; structural UNKNOWN bypasses model; no P2 labels',
                    batch_recipe='Sorted unique input hashes shuffled by random.Random(seed*100+epoch), chunks of16, last partial batch retained',
                    numerical_guard='Finite loss/gradients/parameters/optimizer state each update; abort invalid run, no selective retry/extra epochs',
                    score_axes=dict(relevance='logit1-logit0', unsupported='logit2-logsumexp(logit0,logit1)'),
                    calibration='Per seed: lowest validation semantic UNKNOWN support score; greatest single global relevance threshold satisfying .95 positive/contradiction keep recall in each language',
                    criteria=dict(aggregate_and_each_language=True, pooled_auc=.90, within_goal_auc=.90, positive_keep_recall=.95,
                                  contradiction_keep_recall=.95, negative_drop_rejection=.70, semantic_unknown_recognition=.95,
                                  structural_unknown_recognition=1.0, unknown_drops=0, all_seeds_required=True, complete_pairs=True),
                    controls='Original frozen scalar MiniLM on identical views; scores measured, policy blanket UNKNOWN/KEEP, no support detector or DROP authority',
                    selection='Fixed three-class candidate, all seeds required; calibration only on validation; all3weights/thresholds frozen before any final scores',
                    final_action='One complete final pass per seed and frozen control; no tuning/retry/selection on final',
                    no_independence_interval=True, API_calls=0, P2_admission=False, default_changed=False, publishing=False)
    protocol['sha256'] = digest(protocol)
    save_once(OUT / 'protocol.json', protocol)
    save_once(OUT / 'data-audit-before-training.json', data_audit)
    for name, expected in protocol['sources'].items():
        target = OUT / 'executed-source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write((ROOT / name).read_bytes())
        if sha(target) != expected:
            raise ValueError('Source changed during freeze')
    return protocol


def evaluate(scorer, split, protocol, directory, scalar=False, thresholds=None):
    rows, saved_views = dataset(split)
    scorer.model.eval()
    began = time.perf_counter()
    results = [dict(id=row['id'], original_input_hash=row['content_hash'], input_hash=row['projected_input_hash'],
                    status='UNKNOWN', score=None, support_score=None, logits=None,
                    actual_tokens=saved['projected_tokens'], submitted=False, forward_completed=False,
                    truncated=False, error=None, guard_reason='unsupported_record' if saved['view']['status'] == 'UNKNOWN' else None)
               for row, saved in zip(rows, saved_views)]
    eligible = [i for i, saved in enumerate(saved_views) if saved['view']['status'] == 'PROJECTED']
    accounting = dict(counted_pairs=len(eligible), counted_tokens=sum(saved_views[i]['projected_tokens'] for i in eligible),
                      submitted_pairs=0, submitted_tokens=0, forward_completed_pairs=0, forward_completed_tokens=0, valid_score_pairs=0, valid_score_tokens=0)
    if scalar:
        output = scorer.score([saved_views[i]['view']['objective'] for i in eligible], [saved_views[i]['view']['text'] for i in eligible])
        for i, score in zip(eligible, output):
            if score['status'] != 'SCORED' or score['truncated'] or score['error']:
                raise ValueError('Incomplete frozen control')
            if score['input_sha256'] != results[i]['input_hash'] or score['actual_tokens'] != results[i]['actual_tokens']:
                raise ValueError('Frozen control input/coverage mismatch')
            results[i].update(status='SCORED', score=score['score'], submitted=True, forward_completed=True)
        accounting.update(submitted_pairs=len(eligible), submitted_tokens=accounting['counted_tokens'],
                          forward_completed_pairs=len(eligible), forward_completed_tokens=accounting['counted_tokens'],
                          valid_score_pairs=len(eligible), valid_score_tokens=accounting['counted_tokens'])
    else:
        for start in range(0, len(eligible), protocol['batch_size']):
            indices = eligible[start:start + protocol['batch_size']]
            views = [saved_views[i]['view'] for i in indices]
            encoded = scorer.tokenizer([v['objective'] for v in views], [v['text'] for v in views], padding=True, truncation=False, return_tensors='pt')
            token_count, unused = numeric_batch(encoded, [results[i]['actual_tokens'] for i in indices], scorer.window)
            accounting['submitted_pairs'] += len(indices)
            accounting['submitted_tokens'] += token_count
            with torch.inference_mode():
                logits = scorer.model(**encoded).logits
            if logits.shape != (len(indices), 3) or not bool(torch.isfinite(logits).all()):
                raise ValueError('Incomplete/nonfinite three-class scoring')
            accounting['forward_completed_pairs'] += len(indices)
            accounting['forward_completed_tokens'] += token_count
            relevance, unsupported = score_axes(logits)
            for offset, i in enumerate(indices):
                results[i].update(status='SCORED', logits=logits[offset].tolist(), score=float(relevance[offset]),
                                  support_score=float(unsupported[offset]), submitted=True, forward_completed=True)
            accounting['valid_score_pairs'] += len(indices)
            accounting['valid_score_tokens'] += token_count
    raw = dict(protocol_sha256=protocol['sha256'], split=split, scalar_control=scalar,
               rows=results, accounting=accounting, elapsed_s=time.perf_counter() - began, finished_at_utc=now())
    # Raw scores survive a later reduction/calibration serialization failure.
    save_once(directory / f'{split}-scores.json', raw)
    if not scalar and thresholds is None:
        thresholds = calibrate(rows, results)
        save_once(directory / 'thresholds.json', dict(protocol_sha256=protocol['sha256'], thresholds=thresholds, final_inspected=False, frozen_at_utc=now()))
    if scalar:
        thresholds = dict(support=None, relevance=None)
    overall = metrics(rows, results, thresholds, scalar)
    by_language = {}
    for language in ['en', 'pt']:
        selected = [(r, s) for r, s in zip(rows, results) if r['goal_language'] == language]
        by_language[language] = metrics([r for r, s in selected], [s for r, s in selected], thresholds, scalar)
    breakdown = {}
    for source in protocol.get('breakdown_sources', ['wc', 'stat', 'clock', 'command', 'environment', 'du', 'df', 'gzip']):
        selected = [(r, s) for r, s in zip(rows, results) if r['label'] is not None and r['binding']['source'] == source]
        if selected:
            breakdown[source] = metrics([r for r, s in selected], [s for r, s in selected], thresholds, scalar)
    by_family = {}
    for family in sorted({row['family'] for row in rows if row['label'] is not None}):
        selected = [(r, s) for r, s in zip(rows, results) if r['family'] == family]
        by_family[family] = metrics([r for r, s in selected], [s for r, s in selected], thresholds, scalar)
    result = dict(protocol_sha256=protocol['sha256'], thresholds=thresholds, metrics=overall, by_language=by_language,
                  by_binary_source=breakdown, by_family=by_family,
                  passed=passes(overall) and all(passes(m) for m in by_language.values()), scalar_control=scalar)
    save_once(directory / f'{split}-metrics.json', result)
    return result


def train(seed, protocol):
    directory = OUT / f'seed-{seed}'
    torch.manual_seed(seed)
    scorer = PairReranker.from_snapshot(snapshot_path(protocol['model']), protocol['model'], batch_size=protocol['batch_size'])
    identity = scorer.identity.copy()
    fresh_head(scorer.model, seed)
    model = scorer.model
    identity.update(adapted_parameters=sum(p.numel() for p in model.parameters()), output_classes=3,
                    initial_head_sha256=hashlib.sha256(model.classifier.weight.detach().numpy().tobytes() + model.classifier.bias.detach().numpy().tobytes()).hexdigest())
    save_once(directory / 'started.json', dict(protocol_sha256=protocol['sha256'], seed=seed, initial_identity=identity, started_at_utc=now()))
    rows, views = dataset('train')
    items = training_items(rows, views)
    if digest(items) != protocol['train_unique_items_sha256']:
        raise ValueError('Unique training inputs changed')
    lengths = {saved['view']['projected_input_sha256']: saved['projected_tokens'] for saved in views if saved['view']['status'] == 'PROJECTED'}
    spec = protocol['optimizer']
    optimizer = torch.optim.AdamW(model.parameters(), lr=spec['lr'], weight_decay=spec['weight_decay'], betas=tuple(spec['betas']), eps=spec['eps'])
    history = []
    for epoch in range(1, protocol['epochs'] + 1):
        model.train()
        order = list(items)
        random.Random(seed * 100 + epoch).shuffle(order)
        losses, token_count, padded_slots, processed = [], 0, 0, 0
        began = time.perf_counter()
        for start in range(0, len(order), protocol['batch_size']):
            batch = order[start:start + protocol['batch_size']]
            encoded = scorer.tokenizer([item['objective'] for item in batch], [item['text'] for item in batch], padding=True, truncation=False, return_tensors='pt')
            tokens, slots = numeric_batch(encoded, [lengths[item['input_hash']] for item in batch], scorer.window)
            loss = classification_loss(batch, model(**encoded).logits, protocol['global_class_weights'])
            try:
                finite_update(loss, model, optimizer)
            except Exception as exc:
                save_once(directory / 'failed-update.json', dict(protocol_sha256=protocol['sha256'], seed=seed,
                          epoch=epoch, step=len(losses) + 1, completed_pairs_before_failed_update=processed,
                          error_type=type(exc).__name__, error=str(exc), loss_representation=str(float(loss.detach())),
                          epoch_complete=False, candidate_valid=False, utc=now()))
                raise
            losses.append((float(loss.detach()), len(batch)))
            processed += len(batch); token_count += tokens; padded_slots += slots
            if len(losses) % 50 == 0:
                print(seed, 'epoch', epoch, 'step', len(losses), 'loss', round(sum(v * n for v, n in losses) / processed, 5), flush=True)
        receipt = dict(protocol_sha256=protocol['sha256'], seed=seed, epoch=epoch, steps=len(losses), unique_pairs=processed,
                       weighted_mean_loss=sum(v * n for v, n in losses) / processed,
                       submitted_nonpadding_tokens=token_count, padded_token_slots=padded_slots,
                       all_updates_finite=True, seconds=time.perf_counter() - began, finished_at_utc=now())
        save_once(directory / f'epoch-{epoch}.json', receipt)
        history.append(receipt)
        print(seed, 'EPOCH', receipt, flush=True)
    path = WEIGHTS / f'seed-{seed}/model.safetensors'
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError('Refusing candidate weight overwrite')
    save_file({k: v.detach().contiguous() for k, v in model.state_dict().items()}, str(path))
    validation = evaluate(scorer, 'validation', protocol, directory)
    save_once(directory / 'training_meta.json', dict(protocol_sha256=protocol['sha256'], seed=seed,
              epochs_completed=len(history), history=history, weights_path=str(path.relative_to(ROOT)), weights_sha256=sha(path),
              identity=identity, metadata_origin='Direct driver receipts after finite updates and completed validation; no terminal reconstruction',
              final_inspected=False, validation_pass=validation['passed']))
    print(seed, 'VALIDATION', validation['metrics'], flush=True)


def run(protocol):
    if (OUT / 'summary.json').exists():
        return json.loads((OUT / 'summary.json').read_text())
    if (OUT / 'started.json').exists():
        raise ValueError('Existing partial study: inspect live handle/failure, never selective retry')
    save_once(OUT / 'started.json', dict(protocol_sha256=protocol['sha256'], utc=now(), python=sys.version, platform=platform.platform()))
    torch.set_num_threads(protocol['threads'])
    def denied(*args, **kwargs):
        raise RuntimeError('No network during model training/evaluation')
    socket.socket.connect = denied
    try:
        baseline = PairReranker.from_snapshot(snapshot_path(protocol['model']), protocol['model'], batch_size=protocol['batch_size'])
        evaluate(baseline, 'validation', protocol, OUT / 'frozen', scalar=True)
        del baseline
        for seed in protocol['seeds']:
            train(seed, protocol)
        calibration = {str(seed): json.loads((OUT / f'seed-{seed}/thresholds.json').read_text()) for seed in protocol['seeds']}
        weight_ids = {str(seed): json.loads((OUT / f'seed-{seed}/training_meta.json').read_text())['weights_sha256'] for seed in protocol['seeds']}
        save_once(OUT / 'selection.json', dict(protocol_sha256=protocol['sha256'], fixed_candidate='three-class full adaptation', seeds=protocol['seeds'],
                                             weights_sha256=weight_ids, calibration=calibration, final_inspected=False, frozen_at_utc=now()))
        finals = []
        for seed in protocol['seeds']:
            directory = OUT / f'seed-{seed}'
            meta = json.loads((directory / 'training_meta.json').read_text())
            scorer = PairReranker.from_snapshot(snapshot_path(protocol['model']), protocol['model'], batch_size=protocol['batch_size'])
            fresh_head(scorer.model, seed)
            path = ROOT / meta['weights_path']
            if sha(path) != meta['weights_sha256']:
                raise ValueError('Candidate weight changed')
            load_trained_weights(scorer.model, load_file(str(path), device='cpu'))
            final = evaluate(scorer, 'final', protocol, directory, thresholds=calibration[str(seed)]['thresholds'])
            finals.append(final)
            print(seed, 'FINAL', final['metrics'], flush=True)
            del scorer
        baseline = PairReranker.from_snapshot(snapshot_path(protocol['model']), protocol['model'], batch_size=protocol['batch_size'])
        frozen = evaluate(baseline, 'final', protocol, OUT / 'frozen', scalar=True)
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        summary = dict(protocol_sha256=protocol['sha256'], seed_passes=[r['passed'] for r in finals], all_seeds_pass=all(r['passed'] for r in finals),
                       mean={k: statistics.mean(r['metrics'][k] for r in finals) for k in ['pooled_auc', 'within_goal_auc', 'positive_keep_recall', 'contradiction_keep_recall', 'negative_drop_rejection', 'semantic_unknown_recognition']},
                       unknown_drops=[r['metrics']['unknown_drops'] for r in finals], frozen_final=frozen['metrics'],
                       peak_study_process_rss_bytes=peak if sys.platform == 'darwin' else peak * 1024,
                       API_calls=0, P2_admission=False, default_changed=False, adoption=False, finished_at_utc=now())
        save_once(OUT / 'summary.json', summary)
        return summary
    except Exception as exc:
        save_once(OUT / 'failure.json', dict(protocol_sha256=protocol['sha256'], error_type=type(exc).__name__, error=str(exc),
                                          completed_candidates=[p.parent.name for p in OUT.glob('*/training_meta.json')],
                                          study_complete=False, selective_retry_allowed=False, utc=now()))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'run'])
    args = parser.parse_args()
    protocol = prepare()
    print(json.dumps(run(protocol) if args.action == 'run' else dict(protocol_sha256=protocol['sha256'], train_unique=protocol['train_unique']), indent=2))
