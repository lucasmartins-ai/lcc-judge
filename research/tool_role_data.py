"""Freeze, capture and bind grounded tool-role data; no model inference/training."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from research.tool_measurement_runtime import measure_batch, runtime_identity
from research.tool_role_contracts import REFERENCES, ROLES, TRAIN_FAMILIES, FINAL_FAMILIES
from research.tool_role_corpus import COUNTS, SEEDS, TEMPLATES, UNKNOWN_QUERIES, build_rows, digest, validate_receipt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/goal-engine-2026-10-04/tool-role-grounded-v1'
SOURCES = ['research/tool_measurement_worker.py', 'research/tool_measurement_runtime.py',
           'replay/sandbox.py', 'research/tool_role_contracts.py', 'research/tool_role_corpus.py',
           'research/tool_role_data.py', 'research/measurement_projection.py',
           'research/audit_tool_role_data.py']
UPSTREAM = ROOT / 'research/goal-engine-2026-10-04/rerank-next/upstream-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def _verify(out, check_live=True):
    protocol = json.loads((out / 'protocol.json').read_text())
    if protocol['sha256'] != digest({k: v for k, v in protocol.items() if k != 'sha256'}):
        raise ValueError('Changed protocol; never reuse this collection')
    for name, expected in protocol['sources'].items():
        if sha(out / 'sources' / name) != expected or (check_live and sha(ROOT / name) != expected):
            raise ValueError(f'Changed frozen source: {name}')
    return protocol


def freeze(out=OUT):
    if (out / 'protocol.json').exists():
        return _verify(out)
    identity = runtime_identity()
    if identity is None:
        raise ValueError('Build the separately confined trusted-tool worker first')
    upstream = json.loads(UPSTREAM.read_text())
    sources = {name: sha(ROOT / name) for name in SOURCES}
    protocol = dict(schema='tool-role-grounded/0.1', frozen_at_utc=datetime.now(timezone.utc).isoformat(), sources=sources,
                    runtime=identity, requests={k: dict(seed=SEEDS[k], fixtures=COUNTS[k]) for k in SEEDS},
                    calibration_seed_excluded=442420, roles=ROLES,
                    train_families=TRAIN_FAMILIES, final_families=FINAL_FAMILIES,
                    templates=TEMPLATES, unknown_queries=UNKNOWN_QUERIES, primary_references=REFERENCES,
                    reference_version_scope='GNU manuals 9.11/latest; actual pinned tools report 9.7/gzip 1.13, behavior checked on receipts',
                    language_scope='English and Portuguese goals; English authored report captions only',
                    heldout_scope='DU/DF/GZIP binary sources, concrete fixture inputs, aliases/report captions and question templates; shared author/schema and some underlying measurement concepts',
                    source_clusters=dict(train=['wc', 'stat', 'clock', 'command', 'environment'], final=['du', 'df', 'gzip']),
                    row_unit='8 binary rows per family/fixture/language; 4 UNKNOWN rows per fixture/language; correlated/shared values, duplicate projected pairs disclosed',
                    numeric_control='Measured and value-swap claims give identical numeric multisets to both labels per goal; false requested claims remain relevant',
                    p1_label='1 requested role equals reported role; 0 other role; null unsupported goal or unbound record; not P2 necessity',
                    unknown_policy='Current projection detects unsupported syntax/scope only; semantic UNKNOWN needs a future support decision before DROP',
                    tokenizer=dict(repo_id=upstream['repo_id'], revision=upstream['revision'], window=512,
                                   files={k: v for k, v in upstream['files'].items() if k not in ['model.safetensors', 'README.md']},
                                   use='Coverage count only; zero model forwards'),
                    model_scoring_executed=False, training_executed=False, production_data=False,
                    no_default_or_publication_change=True)
    protocol['sha256'] = digest(protocol)
    # JSON is the durable representation; first call and resumed reads must
    # return the same types, including list-valued declarative contracts.
    protocol = json.loads(json.dumps(protocol))
    out.mkdir(parents=True, exist_ok=True)
    for name, expected in sources.items():
        dest = out / 'sources' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as stream:
            stream.write((ROOT / name).read_bytes())
        if sha(dest) != expected:
            raise ValueError('Source changed while freezing')
    _write(out / 'protocol.json', protocol)
    return protocol


def collect(out=OUT):
    protocol = _verify(out)
    identity = runtime_identity()
    if identity != protocol['runtime']:
        raise ValueError('Runtime changed since prospective freeze')
    for split, request in protocol['requests'].items():
        path = out / f'{split}-raw.json'
        if path.exists():
            raw = json.loads(path.read_text())
        else:
            with (out / 'collection-events.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(dict(split=split, event='START', utc=datetime.now(timezone.utc).isoformat(),
                                             protocol_sha256=protocol['sha256'], request=request)) + '\n')
            raw = measure_batch(request)
            _write(path, raw)
            with (out / 'collection-events.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(dict(split=split, event='END', utc=datetime.now(timezone.utc).isoformat(),
                                             protocol_sha256=protocol['sha256'], raw_sha256=sha(path), status=raw['status'])) + '\n')
        validate_receipt(raw)
        if raw['request'] != request or raw['runtime'] != {k: v for k, v in identity.items() if k != 'docker'}:
            raise ValueError('Receipt request/runtime differs from frozen protocol')
        rows = build_rows(split, raw)
        destination = out / f'{split}.jsonl'
        encoded = ''.join(json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n' for row in rows)
        if destination.exists():
            if destination.read_text() != encoded:
                raise ValueError('Existing corpus changed; no overwrite')
        else:
            with destination.open('x', encoding='utf-8') as stream:
                stream.write(encoded)
        print(json.dumps(dict(split=split, fixtures=len(raw['measurements']['fixtures']), rows=len(rows), status='CAPTURED')), flush=True)


def coverage(out=OUT, snapshot=None):
    protocol = _verify(out)
    if snapshot is None:
        snapshot = Path.home() / '.cache/huggingface/hub/models--cross-encoder--ms-marco-MiniLM-L6-v2/snapshots' / protocol['tokenizer']['revision']
    for name, expected in protocol['tokenizer']['files'].items():
        if sha(snapshot / name) != expected:
            raise ValueError(f'Tokenizer snapshot mismatch: {name}')
    from transformers import AutoTokenizer
    from research.measurement_projection import project_measurement
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
    result = dict(protocol_sha256=protocol['sha256'], tokenizer=protocol['tokenizer'], model_forwards=0, splits={})
    for split in SEEDS:
        rows = [json.loads(line) for line in (out / f'{split}.jsonl').read_text().splitlines()]
        views = []
        for row in rows:
            view = project_measurement(**row['model_pair'])
            raw_tokens = len(tokenizer(row['objective'], row['text'], truncation=False)['input_ids'])
            projected_tokens = None
            if view['status'] == 'PROJECTED':
                projected_tokens = len(tokenizer(view['objective'], view['text'], truncation=False)['input_ids'])
            views.append(dict(id=row['id'], original_input_hash=row['content_hash'], raw_tokens=raw_tokens,
                              projected_tokens=projected_tokens, view=view, truncated=False, submitted_to_model=False))
        dest = out / f'{split}-views.jsonl'
        encoded = ''.join(json.dumps(v, sort_keys=True, ensure_ascii=False) + '\n' for v in views)
        if dest.exists():
            if dest.read_text() != encoded:
                raise ValueError('Coverage changed; no overwrite')
        else:
            with dest.open('x', encoding='utf-8') as stream:
                stream.write(encoded)
        raw_lengths = [v['raw_tokens'] for v in views]
        projected_lengths = [v['projected_tokens'] for v in views if v['projected_tokens'] is not None]
        result['splits'][split] = dict(rows=len(rows), rows_sha256=sha(out / f'{split}.jsonl'),
                                      raw_sha256=sha(out / f'{split}-raw.json'), views_sha256=sha(dest),
                                      raw_max_tokens=max(raw_lengths), projected_max_tokens=max(projected_lengths),
                                      raw_overflow=sum(n > 512 for n in raw_lengths), projected_overflow=sum(n > 512 for n in projected_lengths))
    if any(v['raw_overflow'] or v['projected_overflow'] for v in result['splits'].values()):
        raise ValueError('Whole-pair coverage failed; never silently truncate')
    dest = out / 'coverage.json'
    if dest.exists():
        if json.loads(dest.read_text()) != result:
            raise ValueError('Coverage summary changed')
    else:
        _write(dest, result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['freeze', 'collect', 'coverage'])
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--snapshot', type=Path)
    args = parser.parse_args()
    result = freeze(args.out) if args.action == 'freeze' else (collect(args.out) if args.action == 'collect' else coverage(args.out, args.snapshot))
    if result is not None:
        print(json.dumps(result, indent=2, ensure_ascii=False))
