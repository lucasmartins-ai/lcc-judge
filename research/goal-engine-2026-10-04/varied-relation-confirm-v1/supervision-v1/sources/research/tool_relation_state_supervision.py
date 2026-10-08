"""Derive bounded bilingual development rows from audited saved tool-state events.

Frozen design, declarations, producer/auditor bytes, captures and tokenizer identity
precede derivation. No models/tools/APIs. Gzip avoids publishing huge duplicate-row
files; duplicate effective inputs are reported, not independent measurements.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import shutil

from research.audit_tool_relation_state_supervision import BASE, KINDS, REQUESTS, audit_design, digest, sha
from research.measurement_projection import project_measurement

ROOT = Path(__file__).resolve().parents[1]


def build_rows(split, raw, d, fixture_limit=None, *, requests=None):
    requests = REQUESTS if requests is None else requests
    if split not in requests or raw['request'] != requests[split]:
        raise ValueError('Exact declared cohort request required; calibration/final excluded by default')
    if raw['status'] != 'MEASURED' or raw['returncode'] != 0 or raw['error'] is not None:
        raise ValueError('Complete measured source required')
    fixtures = raw['measurements']['fixtures']
    if len(fixtures) != requests[split]['fixtures']:
        raise ValueError('Complete fixture population required')
    for fixture in fixtures[:fixture_limit]:
        index = fixture['index']
        alias, caption_index, report_language = d['wording_assignments'][split][index]
        for family_index, (family, pair) in enumerate(sorted(d['pairs'].items())):
            for language in ('en', 'pt'):
                frames = d['query_frames'][split][language]
                for requested in pair:
                    question = frames[(index // 4 + family_index) % len(frames)].format(d['roles'][requested][2 if language == 'en' else 3][alias])
                    for observed in pair:
                        other = next(role for role in pair if role != observed)
                        for variant, value_role in [('measured', observed), ('value_swap', other)]:
                            yield _row(split, fixture, d, family, language, report_language, alias, caption_index,
                                       requested, observed, value_role, question, variant, None, requests[split]['seed'])
        for role_index, role in enumerate(sorted(d['roles'])):
            for kind in KINDS:
                for language in ('en', 'pt'):
                    frames = d['semantic_UNKNOWN_frames'][split][kind][language]
                    intent = d['roles'][role][2 if language == 'en' else 3][alias]
                    question = frames[(index // 4 + role_index) % len(frames)].format(intent)
                    yield _row(split, fixture, d, f'unknown:{role}:{kind}', language, report_language, alias,
                               caption_index, None, role, role, question, 'measured', kind, requests[split]['seed'])
        for language in ('en', 'pt'):
            role = sorted(d['roles'])[index % 18]
            question = d['query_frames'][split][language][0].format(d['roles'][role][2 if language == 'en' else 3][alias])
            yield _row(split, fixture, d, 'structural_unknown', language, report_language, alias,
                       caption_index, None, role, role, question, 'measured', 'unbound_record', requests[split]['seed'])


def _row(split, fixture, d, family, language, report_language, alias, caption_index, requested, observed, value_role, question, variant, kind, seed):
    index = fixture['index']; fields = fixture['fields']; role = d['roles'][observed]
    group = digest([split, seed, family, index, language]); entity = 'tool-' + group[:12]
    caption = role[4][caption_index] if report_language == 'en' else d['portuguese_report_captions'][observed][caption_index]
    value = fields[value_role]; level = ('INFO', 'WARN', 'ERROR')[(index // 2) % 3]
    body = dict(entity=entity, level=level, measurement=caption, value=value)
    if kind == 'unbound_record':
        del body['level']
        text = json.dumps(body, sort_keys=True, ensure_ascii=False)
    else:
        text = (f'Tool report {entity} [{level}]: {caption}: {value}.' if index % 2 else
                json.dumps(body, sort_keys=True, ensure_ascii=False))
    objective = question + f' Report evidence for {entity}; ordinary and unusual values both count.'
    row = dict(id=digest([group, requested, observed, variant]) if kind is None else digest([group, observed, kind]),
        group=group, split=split, family=family, goal_language=language, report_language=report_language,
        entity=entity, requested_role=requested, observed_role=observed,
        label=int(requested == observed) if kind is None else None, unknown_kind=kind,
        objective=objective, text=text, intent_alias=alias, report_caption=caption_index,
        report_variant=variant, reported_value=value, fact_truth=value == fields[observed],
        binding=dict(source=role[0], field=observed, unit=role[1], value_source_field=value_role,
                     actual_value=fields[observed], fixture_index=index, fixture_content_sha256=fixture['fixture_content_sha256']),
        content_hash=digest([objective, text]))
    view = project_measurement(objective, text)
    row['projection_status'] = view['status']; row['projected_input_hash'] = view.get('projected_input_sha256')
    return row


def _save(path, value):
    with path.open('x', encoding='utf-8') as target:
        target.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def write_rows(out, split, records, tokenizer):
    """Shared immutable gzip export; measure complete pairs and never truncate."""
    counts = Counter(); effective = {}; cache = {}; raw_max = projected_max = contradictions = 0
    with (out / f'{split}.jsonl.gz').open('xb') as rf, (out / f'{split}-views.jsonl.gz').open('xb') as vf:
        with gzip.GzipFile(filename='', mode='wb', fileobj=rf, mtime=0) as rstream, gzip.GzipFile(filename='', mode='wb', fileobj=vf, mtime=0) as vstream:
            for row in records:
                view = project_measurement(row['objective'], row['text'])
                projection = {k: view[k] for k in ('status', 'objective', 'text')}
                token_counts = []
                for a, b in [(row['objective'], row['text']), *(([(view['objective'], view['text'])]) if view['status'] == 'PROJECTED' else [])]:
                    key = (a, b)
                    if key not in cache:
                        cache[key] = len(tokenizer(a, b, truncation=False)['input_ids'])
                    if cache[key] > 512:
                        raise ValueError('Whole pair overflow: partial evidence retained, no truncation/retry')
                    token_counts.append(cache[key])
                rn = token_counts[0]; vn = token_counts[1] if len(token_counts) == 2 else None
                raw_max = max(raw_max, rn); projected_max = max(projected_max, vn or 0)
                if row['projected_input_hash']:
                    key = row['projected_input_hash']
                    if key in effective and effective[key] != row['label']:
                        raise ValueError('Conflicting effective-input labels')
                    effective[key] = row['label']
                counts['rows'] += 1; counts['binary' if row['label'] is not None else 'unknown'] += 1
                counts['structural_unknown' if view['status'] == 'UNKNOWN' else 'projected_rows'] += 1
                contradictions += int(row['label'] == 1 and not row['fact_truth'])
                saved = dict(id=row['id'], view=projection, raw_tokens=rn, projected_tokens=vn,
                             truncated=False, submitted_to_model=False)
                for stream, value in [(rstream, row), (vstream, saved)]:
                    stream.write((json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n').encode())
    unique_labels = Counter(str(v) for v in effective.values())
    return dict(counts, semantic_unknown=counts['unknown'] - counts['structural_unknown'],
        unique_projected_inputs=len(effective), unique_projected_labels=dict(sorted(unique_labels.items())),
        raw_max_tokens=raw_max, projected_max_tokens=projected_max, relevant_contradictions=contradictions, cuts=0,
        rows_sha256=sha(out / f'{split}.jsonl.gz'), views_sha256=sha(out / f'{split}-views.jsonl.gz'))


def prepare(base=BASE, out=BASE / 'supervision-v1'):
    if out.exists():
        raise ValueError('New immutable destination required; no overwrite/retry')
    design_audit = audit_design(base)
    d = json.loads((base / 'supervision-design-v3/protocol.json').read_text())
    upstream = json.loads((ROOT / 'research/goal-engine-2026-10-04/semantic-next/upstream/artifacts.json').read_text())
    token_files = {k: v for k, v in upstream['files'].items() if k not in ('model.safetensors', 'README.md')}
    snapshot = Path.home() / '.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1/snapshots' / upstream['revision']
    for name, expected in token_files.items():
        if sha(snapshot / name) != expected:
            raise ValueError('Pinned tokenizer mismatch')
    names = ['research/tool_relation_state_supervision.py', 'research/audit_tool_relation_state_supervision.py',
             'research/audit_tool_relation_state_cohort.py', 'research/audit_tool_relation_states.py', 'research/measurement_projection.py']
    sources = {name: sha(ROOT / name) for name in names}
    capture_names = ['cohort.json', 'supervision-design-v3/protocol.json']
    capture_names += ['supervision-design-v3/sources/' + name for name in d['sources']]
    for split in ('calibration', 'train', 'validation'):
        rp = json.loads((base / split / 'protocol.json').read_text())
        capture_names += [f'{split}/{name}' for name in ['protocol.json', 'started.json', 'completion.json', 'raw.json']]
        capture_names += [f'{split}/sources/{name}' for name in rp['sources']]
    capture_files = {name: sha(base / name) for name in capture_names}
    p = dict(schema='varied-direct-record-development-supervision/0.1', frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        design_sha256=d['sha256'], design_audit=design_audit, sources=sources, capture_files=capture_files,
        requests=REQUESTS, calibration_excluded=442600, tokenizer=dict(repo_id=upstream['repo_id'], revision=upstream['revision'], files=token_files, window=512),
        population='942 authored rows per fixture:832 binary,108 semantic UNKNOWN,2 structural UNKNOWN. All52pairs/18primitives seen; no final.',
        projected_deduplication='Report unique input counts/classes/conflicts; repeated rows are not independent tasks. Future balanced binary loss must account for deduplicated class imbalance.',
        compression='gzip JSONL, mtime0 and empty archive filename; complete original rows/views, no data omitted',
        development_only=True, model_forwards=0, API_calls=0, P2_admission=False, quality_approved=False,
        default_changed=False, publishing=False)
    p['sha256'] = digest(p); out.mkdir(parents=True)
    for name in sources:
        saved = out / 'sources' / name; saved.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ROOT / name, saved)
    for name in capture_files:
        saved = out / 'captures' / name; saved.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(base / name, saved)
    _save(out / 'protocol.json', p)
    _save(out / 'started.json', dict(protocol_sha256=p['sha256'], started_at_utc=datetime.now(timezone.utc).isoformat()))
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
    coverage = dict(protocol_sha256=p['sha256'], model_forwards=0, splits={})
    for split in REQUESTS:
        raw = json.loads((base / split / 'raw.json').read_text())
        coverage['splits'][split] = write_rows(out, split, build_rows(split, raw, d), tokenizer)
    _save(out / 'coverage.json', coverage)
    _save(out / 'completion.json', dict(protocol_sha256=p['sha256'], finished_at_utc=datetime.now(timezone.utc).isoformat(), model_forwards=0))
    return coverage


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=BASE); parser.add_argument('--out', type=Path, default=BASE / 'supervision-v1')
    args = parser.parse_args()
    print(json.dumps(prepare(args.base, args.out), indent=2, allow_nan=False))
