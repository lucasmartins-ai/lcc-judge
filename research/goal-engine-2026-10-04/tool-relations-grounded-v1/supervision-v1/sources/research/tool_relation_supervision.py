"""Prepare a fresh direct-record retrieval cohort from saved actual-tool receipts.

No model is loaded or trained. All labels are authored task contracts. Broader
diagnosis/derivation/usefulness is UNKNOWN, not another binary negative. Final
reserves new pair combinations and wording; every primitive/source is seen in
training. This is not an unseen-tool or production evaluation.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random

from research.audit_tool_relations import audit as audit_raw, recount
from research.measurement_projection import project_measurement
from research.tool_relation_contracts import FINAL_FAMILIES, REFERENCES, ROLES, TEMPLATES, TRAIN_FAMILIES, UNKNOWN

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / 'research/goal-engine-2026-10-04/tool-relations-grounded-v1'
OUT = CAPTURE / 'supervision-v1'
REQUESTS = {'train': {'seed': 442511, 'fixtures': 32},
            'validation': {'seed': 442512, 'fixtures': 12},
            'final': {'seed': 442513, 'fixtures': 24}}
KINDS = ('derived_or_multifield_goal', 'diagnosis_goal', 'broader_usefulness_goal')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _save_once(path, value):
    with path.open('x', encoding='utf-8') as target:
        target.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def _write_rows(path, rows):
    with path.open('x', encoding='utf-8') as target:
        for row in rows:
            target.write(json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n')


def _validated_fixtures(split, raw):
    if split not in REQUESTS or raw['request'] != REQUESTS[split]:
        raise ValueError('Exact fresh request required; calibration is excluded')
    if (raw['status'] != 'MEASURED' or raw['returncode'] != 0 or raw['error'] is not None
            or raw['host_measurement_executed'] is not False
            or json.loads(raw['stdout']) != raw['measurements']
            or raw['measurements']['request'] != raw['request']):
        raise ValueError('Complete confined measurement receipt required')
    fixtures = raw['measurements']['fixtures']
    if len(fixtures) != REQUESTS[split]['fixtures']:
        raise ValueError('Missing fixtures')
    for index, fixture in enumerate(fixtures):
        if fixture['index'] != index or recount(fixture) != fixture['fields']:
            raise ValueError('Invalid fixture order or measurement')
    return fixtures


def _report(entity, caption, value, index):
    level = ('INFO', 'WARN', 'ERROR')[(index // 8) % 3]
    if (index // 4) % 2:
        return f'Tool report {entity} [{level}]: {caption}: {value}.'
    return json.dumps(dict(entity=entity, level=level, measurement=caption, value=value), sort_keys=True)


def build_rows(split, raw):
    fixtures = _validated_fixtures(split, raw)
    rows = []
    families = FINAL_FAMILIES if split == 'final' else TRAIN_FAMILIES
    for fixture in fixtures:
        index, fields = fixture['index'], fixture['fields']
        # Four training combinations occur across fixtures, eight fixtures each.
        # A single combination per fixture limits replication; they are NOT four
        # independent copies or four independently sampled semantic tasks.
        alias = (index // 2) % 2 if split == 'train' else (2 if split == 'validation' else 3)
        caption_index = index % 2 if split == 'train' else (2 if split == 'validation' else 3)
        for family, roles in families.items():
            for language in ('en', 'pt'):
                group = digest([split, raw['request']['seed'], family, index, language])
                entity = 'tool-' + group[:12]
                for requested in roles:
                    intent = ROLES[requested][2 if language == 'en' else 3][alias]
                    choices = TEMPLATES[split][language]
                    question = choices[(index // 4) % len(choices)].format(intent)
                    objective = question + f' Report evidence for {entity}; ordinary and unusual values both count.'
                    for observed in roles:
                        other = roles[1] if observed == roles[0] else roles[0]
                        caption = ROLES[observed][4][caption_index]
                        for variant, value_field in (('measured', observed), ('value_swap', other)):
                            value = fields[value_field]
                            text = _report(entity, caption, value, index)
                            rows.append(dict(id=digest([group, requested, observed, variant]), group=group,
                                report_id=digest([group, observed, variant]), split=split, family=family,
                                goal_language=language, report_language='en', entity=entity,
                                requested_role=requested, observed_role=observed, label=int(requested == observed),
                                unknown_kind=None, objective=objective, text=text, intent_alias=alias,
                                report_caption=caption_index, report_variant=variant,
                                reported_value=value, fact_truth=value == fields[observed],
                                binding=dict(source=ROLES[observed][0], field=observed, unit=ROLES[observed][1],
                                    value_source_field=value_field, actual_value=fields[observed], fixture_index=index,
                                    fixture_content_sha256=fixture['fixture_content_sha256']),
                                framing='authored direct-record claim retrieval, not generic LCC usefulness/P2'))
        for language in ('en', 'pt'):
            group = digest([split, raw['request']['seed'], 'unknown', index, language])
            entity = 'tool-' + group[:12]
            observed = ('retry_attempts', 'udp_received_payload_bytes', 'git_index_files')[index % 3]
            caption = ROLES[observed][4][caption_index]
            report = _report(entity, caption, fields[observed], index)
            examples = [(question, report, kind) for question, kind in zip(UNKNOWN[split][language], KINDS)]
            intent = ROLES[observed][2 if language == 'en' else 3][alias]
            question = TEMPLATES[split][language][0].format(intent)
            # Structural UNKNOWN is bypassed before learned support scoring.
            examples.append((question, json.dumps(dict(entity=entity, measurement=caption, value=fields[observed])),
                             'unbound_record'))
            for case, (question, text, kind) in enumerate(examples):
                objective = question + f' Report evidence for {entity}; ordinary and unusual values both count.'
                rows.append(dict(id=digest([group, case]), group=group, report_id=digest([group, case]),
                    split=split, family='unknown', goal_language=language, report_language='en', entity=entity,
                    requested_role=None, observed_role=observed, label=None, unknown_kind=kind,
                    objective=objective, text=text, intent_alias=alias, report_caption=caption_index,
                    report_variant='measured', reported_value=fields[observed], fact_truth=True,
                    binding=dict(source=ROLES[observed][0], field=observed, unit=ROLES[observed][1],
                        value_source_field=observed, actual_value=fields[observed], fixture_index=index,
                        fixture_content_sha256=fixture['fixture_content_sha256']),
                    framing='authored broader-goal or structurally unbound UNKNOWN; retain original block'))
    for row in rows:
        row['model_pair'] = dict(objective=row['objective'], text=row['text'])
        row['content_hash'] = digest([row['objective'], row['text']])
        view = project_measurement(**row['model_pair'])
        row['projection_status'] = view['status']
        row['projected_input_hash'] = view.get('projected_input_sha256')
    random.Random(REQUESTS[split]['seed']).shuffle(rows)
    return rows


def check_row_binding(row, raw):
    """Validate one derived row against raw fields and the declared task contract."""
    fixture = raw['measurements']['fixtures'][row['binding']['fixture_index']]
    binding = row['binding']
    role, value_role = row['observed_role'], binding['value_source_field']
    expected = dict(source=ROLES[role][0], field=role, unit=ROLES[role][1], value_source_field=value_role,
                    actual_value=fixture['fields'][role], fixture_index=fixture['index'],
                    fixture_content_sha256=fixture['fixture_content_sha256'])
    if binding != expected or value_role not in ROLES or row['split'] not in REQUESTS:
        raise ValueError('Changed observation binding')
    value = fixture['fields'][value_role]
    if (row['reported_value'] != value or row['fact_truth'] != (value == fixture['fields'][role])
            or row['content_hash'] != digest([row['objective'], row['text']])):
        raise ValueError('Changed numeric claim or content')
    if row['label'] is not None:
        if type(row['label']) is not int or row['label'] != int(row['requested_role'] == role):
            raise ValueError('Changed direct-record label')
        if row['unknown_kind'] is not None:
            raise ValueError('A binary label cannot contain an UNKNOWN kind')
    elif row['unknown_kind'] not in (*KINDS, 'unbound_record') or row['requested_role'] is not None:
        raise ValueError('Missing explicit UNKNOWN contract')
    return True


def prepare(capture=CAPTURE, out=OUT):
    if out.exists():
        raise ValueError('New immutable output destination required; no overwrite')
    audits = {split: audit_raw(capture / split) for split in REQUESTS}
    manifest_path = ROOT / 'research/goal-engine-2026-10-04/semantic-next/upstream/artifacts.json'
    manifest = json.loads(manifest_path.read_text())
    snapshot = Path.home() / '.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1/snapshots' / manifest['revision']
    token_files = {k: v for k, v in manifest['files'].items() if k not in ('model.safetensors', 'README.md')}
    for name, expected in token_files.items():
        if sha(snapshot / name) != expected:
            raise ValueError('Pinned tokenizer identity mismatch')
    names = ['research/tool_relation_contracts.py', 'research/tool_relation_supervision.py',
             'research/audit_tool_relation_supervision.py', 'research/audit_tool_relations.py',
             'research/measurement_projection.py']
    sources = {name: sha(ROOT / name) for name in names}
    capture_files = {}
    for split in REQUESTS:
        raw_protocol = json.loads((capture / split / 'protocol.json').read_text())
        capture_names = ['raw.json', 'protocol.json', 'completion.json', 'started.json']
        capture_names.extend('sources/' + name for name in raw_protocol['sources'])
        capture_files[split] = {name: sha(capture / split / name) for name in capture_names}
    protocol = dict(schema='tool-relation-direct-record/0.1', frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        capture_files=capture_files, requests=REQUESTS, sources=sources, roles=ROLES,
        train_families=TRAIN_FAMILIES, final_families=FINAL_FAMILIES, templates=TEMPLATES,
        unknown_queries=UNKNOWN, primary_references=REFERENCES, raw_receipt_audits=audits,
        tokenizer=dict(repo_id=manifest['repo_id'], revision=manifest['revision'], files=token_files, window=512),
        wording='Train intent (fixture_index//2)%2 and caption fixture_index%2: four combinations, eight fixtures each. Validation index2; final index3. Report form/level vary separately.',
        label='1 report directly claims the requested recorded field; 0 claims the other field; null broader/derived/diagnostic goal or unbound record. False requested claims remain relevant contradictions.',
        heldout_scope='New raw fixture/content/entity/effective input, six pair combinations and aliases/captions. All eighteen field primitives and all three sources occur in training; no unseen tool/domain or production claim.',
        limits='Authored language/fixtures and successful bounded APIs. Related/derivable counters may be useful to LCC; binary labels never authorize their general dismissal. UDP is payload/datagram, not wire/IP capture. Git index/worktree edits are fixed2/3.',
        calibration_excluded=442500, model_forwards=0, training=False, P2_admission=False,
        default_changed=False, production=False, quality_approved=False)
    protocol['sha256'] = digest(protocol)
    out.mkdir(parents=True)
    for name in sources:
        saved = out / 'sources' / name
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes((ROOT / name).read_bytes())
    for split in REQUESTS:
        target = out / 'captures' / split
        target.mkdir(parents=True)
        for name in protocol['capture_files'][split]:
            saved = target / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes((capture / split / name).read_bytes())
    _save_once(out / 'protocol.json', protocol)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
    coverage = dict(protocol_sha256=protocol['sha256'], model_forwards=0, splits={})
    for split in REQUESTS:
        raw = json.loads((capture / split / 'raw.json').read_text())
        rows = build_rows(split, raw)
        views = []
        for row in rows:
            check_row_binding(row, raw)
            view = project_measurement(**row['model_pair'])
            raw_n = len(tokenizer(row['objective'], row['text'], truncation=False)['input_ids'])
            view_n = len(tokenizer(view['objective'], view['text'], truncation=False)['input_ids']) if view['status'] == 'PROJECTED' else None
            if raw_n > 512 or (view_n is not None and view_n > 512):
                raise ValueError('Whole pair overflow; no truncation allowed')
            views.append(dict(id=row['id'], raw_tokens=raw_n, projected_tokens=view_n, view=view,
                              original_input_hash=row['content_hash'], truncated=False, submitted_to_model=False))
        _write_rows(out / f'{split}.jsonl', rows)
        _write_rows(out / f'{split}-views.jsonl', views)
        lengths = [v['projected_tokens'] for v in views if v['projected_tokens'] is not None]
        coverage['splits'][split] = dict(rows=len(rows), rows_sha256=sha(out / f'{split}.jsonl'),
            views_sha256=sha(out / f'{split}-views.jsonl'), raw_max_tokens=max(v['raw_tokens'] for v in views),
            projected_max_tokens=max(lengths), projected_rows=len(lengths),
            unique_projected_inputs=len({r['projected_input_hash'] for r in rows if r['projected_input_hash']}),
            binary=sum(r['label'] is not None for r in rows), unknown=sum(r['label'] is None for r in rows),
            structural_unknown=sum(v['view']['status'] == 'UNKNOWN' for v in views), cuts=0)
    _save_once(out / 'coverage.json', coverage)
    return coverage


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, default=CAPTURE)
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    print(json.dumps(prepare(args.capture, args.out), indent=2))
