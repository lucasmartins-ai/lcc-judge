"""Recount frozen varied-state development declarations without producer imports.

Stdlib receipt/graph/string/label checks; optional exact local tokenizer recount.
No tools, model inference, production ground truth or DROP authorization.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import gzip
import hashlib
from itertools import combinations, product
import json
from pathlib import Path
import random

from research.audit_tool_relation_state_cohort import audit_cohort

BASE = Path(__file__).resolve().parent / 'goal-engine-2026-10-04/tool-relation-states-v2'
KINDS = ('derived_or_multifield_goal', 'diagnosis_goal', 'broader_usefulness_goal')
REQUESTS = {'train': {'seed': 442601, 'fixtures': 64}, 'validation': {'seed': 442602, 'fixtures': 32}}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def graph(pairs, roles):
    adjacent = {r: set() for r in roles}
    for a, b in pairs.values():
        assert a != b and a in roles and b in roles
        adjacent[a].add(b); adjacent[b].add(a)
    remaining = set(roles); components = []
    while remaining:
        seen = set(); pending = [min(remaining)]
        while pending:
            role = pending.pop()
            if role in seen:
                continue
            seen.add(role); pending.extend(adjacent[role] - seen)
        remaining -= seen; components.append(sorted(seen))
    return dict(roles=len(roles), unordered_pairs=len(pairs), connected_components=len(components),
                components=components, min_degree=min(map(len, adjacent.values())), max_degree=max(map(len, adjacent.values())))


def audit_design(base=BASE):
    d = json.loads((base / 'supervision-design-v3/protocol.json').read_text())
    assert digest({k: v for k, v in d.items() if k != 'sha256'}) == d['sha256']
    cohort = audit_cohort(base)
    assert d['cohort_sha256'] == cohort['cohort_sha256']
    for name, expected in d['sources'].items():
        assert sha(base / 'supervision-design-v3/sources' / name) == expected
    roles = d['roles']; pairs = d['pairs']
    assert len(roles) == 18 and set(d['portuguese_report_captions']) == set(roles)
    assert {v[0] for v in roles.values()} == {'retry', 'udp', 'git'}
    actual = graph(pairs, roles)
    assert actual == d['graph'] and actual['connected_components'] == 1
    assert actual['unordered_pairs'] == 52 and len({tuple(sorted(p)) for p in pairs.values()}) == 52
    for source in ('retry', 'udp', 'git'):
        expected = {tuple(p) for p in combinations(sorted(r for r in roles if roles[r][0] == source), 2)}
        observed = {tuple(sorted(p)) for p in pairs.values() if all(roles[r][0] == source for r in p)}
        assert observed == expected
    for role, spec in roles.items():
        assert len(spec) == 5 and all(len(spec[i]) == 4 for i in (2, 3, 4))
        assert len(d['portuguese_report_captions'][role]) == 4
        if role.startswith('udp_received_'):
            assert all('recorded' in s and 'budget' in s for s in spec[2] + spec[4])
            assert all('limite de leitura registrado' in s for s in spec[3] + d['portuguese_report_captions'][role])
    for split, request in REQUESTS.items():
        raw = json.loads((base / split / 'raw.json').read_text())
        assert all(set(f['fields']) == set(roles) for f in raw['measurements']['fixtures'])
        completion = json.loads((base / split / 'completion.json').read_text())
        assert datetime.fromisoformat(completion['finished_at_utc']) <= datetime.fromisoformat(d['frozen_at_utc'])
        assignments = list(product(range(4), range(4), ['en', 'pt'])) * (request['fixtures'] // 32)
        random.Random(f"wording-only:{request['seed']}").shuffle(assignments)
        assert d['wording_assignments'][split] == [list(v) for v in assignments]
        assert len(set(map(tuple, assignments))) == 32
        assert d['expected_rows'][split] == request['fixtures'] * (52 * 16 + 18 * 6 + 2)
    for language in ('en', 'pt'):
        assert not set(d['query_frames']['train'][language]) & set(d['query_frames']['validation'][language])
        for kind in KINDS:
            assert not set(d['semantic_UNKNOWN_frames']['train'][kind][language]) & set(d['semantic_UNKNOWN_frames']['validation'][kind][language])
    assert d['derived_rows_emitted'] is d['tokenizer_recount_complete'] is d['quality_approved'] is False
    return dict(status='PASS', design_sha256=d['sha256'], cohort_sha256=cohort['cohort_sha256'],
                graph=actual, fixtures=96, fields=1728, wording_combinations=32, expected_rows=d['expected_rows'],
                model_forwards=0, P2_admission=False, quality_approved=False)


def inspect_row(row, d, raw):
    """Reconstruct one record from the independent frozen declarations/raw fields."""
    split = row['split']; request = REQUESTS[split]
    assert raw['request'] == request
    index = row['binding']['fixture_index']; fixture = raw['measurements']['fixtures'][index]
    fields = fixture['fields']; role = row['observed_role']; spec = d['roles'][role]
    alias, caption_index, report_language = d['wording_assignments'][split][index]
    language = row['goal_language']; assert language in ('en', 'pt')
    assert [row['intent_alias'], row['report_caption'], row['report_language']] == [alias, caption_index, report_language]
    family = row['family']; kind = row['unknown_kind']; requested = row['requested_role']
    group = digest([split, request['seed'], family, index, language]); entity = 'tool-' + group[:12]
    assert row['group'] == group and row['entity'] == entity
    level = ('INFO', 'WARN', 'ERROR')[(index // 2) % 3]
    caption = spec[4][caption_index] if report_language == 'en' else d['portuguese_report_captions'][role][caption_index]
    variant = row['report_variant']
    if row['label'] is not None:
        pair = d['pairs'][family]; assert role in pair and requested in pair
        assert type(row['label']) is int and row['label'] == int(role == requested) and kind is None
        frames = d['query_frames'][split][language]
        frame_index = (index // 4 + sorted(d['pairs']).index(family)) % len(frames)
        intent = d['roles'][requested][2 if language == 'en' else 3][alias]
        question = frames[frame_index].format(intent)
        other = next(r for r in pair if r != role)
        assert variant in ('measured', 'value_swap')
        value_role = role if variant == 'measured' else other
        assert row['id'] == digest([group, requested, role, variant])
    else:
        assert requested is None and kind in (*KINDS, 'unbound_record') and variant == 'measured'
        value_role = role; intent = spec[2 if language == 'en' else 3][alias]
        role_index = sorted(d['roles']).index(role)
        if kind == 'unbound_record':
            assert family == 'structural_unknown' and role == sorted(d['roles'])[index % 18]
            question = d['query_frames'][split][language][0].format(intent)
        else:
            assert family == f'unknown:{role}:{kind}'
            frames = d['semantic_UNKNOWN_frames'][split][kind][language]
            question = frames[(index // 4 + role_index) % len(frames)].format(intent)
        assert row['id'] == digest([group, role, kind])
    value = fields[value_role]
    assert row['binding'] == dict(source=spec[0], field=role, unit=spec[1], value_source_field=value_role,
        actual_value=fields[role], fixture_index=index, fixture_content_sha256=fixture['fixture_content_sha256'])
    assert row['reported_value'] == value and type(row['reported_value']) is int
    assert row['fact_truth'] is (value == fields[role])
    body = dict(entity=entity, level=level, measurement=caption, value=value)
    if kind == 'unbound_record':
        del body['level']
        report = json.dumps(body, sort_keys=True, ensure_ascii=False)
    else:
        report = (f'Tool report {entity} [{level}]: {caption}: {value}.' if index % 2 else
                  json.dumps(body, sort_keys=True, ensure_ascii=False))
    objective = question + f' Report evidence for {entity}; ordinary and unusual values both count.'
    assert row['objective'] == objective and row['text'] == report
    assert row['content_hash'] == digest([objective, report])
    if kind == 'unbound_record':
        assert row['projection_status'] == 'UNKNOWN' and row['projected_input_hash'] is None
        return dict(status='UNKNOWN', objective=None, text=None)
    projected = f'{caption}: {value}.'
    assert row['projection_status'] == 'PROJECTED' and row['projected_input_hash'] == digest([question, projected])
    return dict(status='PROJECTED', objective=question, text=projected)


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def audit(out=BASE / 'supervision-v1', recount_tokenizer=False):
    p = json.loads((out / 'protocol.json').read_text()); c = json.loads((out / 'coverage.json').read_text())
    assert p['sha256'] == digest({k: v for k, v in p.items() if k != 'sha256'}) == c['protocol_sha256']
    for name, expected in p['sources'].items():
        assert sha(out / 'sources' / name) == expected
    for name, expected in p['capture_files'].items():
        assert sha(out / 'captures' / name) == expected
    assert p['design_audit'] == audit_design(out / 'captures')
    d = json.loads((out / 'captures/supervision-design-v3/protocol.json').read_text())
    assert p['design_sha256'] == d['sha256'] and p['model_forwards'] == c['model_forwards'] == 0
    assert p['requests'] == REQUESTS and p['development_only'] is True
    assert p['API_calls'] == 0 and p['calibration_excluded'] == 442600 and p['tokenizer']['window'] == 512
    assert p['P2_admission'] is p['quality_approved'] is p['default_changed'] is p['publishing'] is False
    started = json.loads((out / 'started.json').read_text()); completed = json.loads((out / 'completion.json').read_text())
    assert started['protocol_sha256'] == completed['protocol_sha256'] == p['sha256']
    assert completed['model_forwards'] == 0
    assert datetime.fromisoformat(d['frozen_at_utc']) <= datetime.fromisoformat(p['frozen_at_utc']) <= datetime.fromisoformat(started['started_at_utc']) <= datetime.fromisoformat(completed['finished_at_utc'])
    tokenizer = None
    if recount_tokenizer:
        from transformers import AutoTokenizer
        spec = p['tokenizer']; snapshot = Path.home() / '.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1/snapshots' / spec['revision']
        for name, expected in spec['files'].items():
            assert sha(snapshot / name) == expected
        tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
    sets = {}; results = {}
    for split, request in REQUESTS.items():
        raw = json.loads((out / 'captures' / split / 'raw.json').read_text())
        assert datetime.fromisoformat(p['frozen_at_utc']) >= datetime.fromisoformat(d['frozen_at_utc'])
        expected = c['splits'][split]
        assert sha(out / f'{split}.jsonl.gz') == expected['rows_sha256']
        assert sha(out / f'{split}-views.jsonl.gz') == expected['views_sha256']
        labels = Counter(); kinds = Counter(); languages = Counter(); wording = Counter(); ids = set()
        content = set(); effective = {}; entities = set(); token_cache = {}; raw_max = projected_max = contradictions = 0
        balanced = defaultdict(lambda: {0: [], 1: []}); n = 0
        for row, saved in zip(rows(out / f'{split}.jsonl.gz'), rows(out / f'{split}-views.jsonl.gz'), strict=True):
            n += 1; assert row['id'] not in ids; ids.add(row['id'])
            view = inspect_row(row, d, raw)
            assert saved['id'] == row['id'] and saved['view'] == view
            assert saved['truncated'] is saved['submitted_to_model'] is False
            assert type(saved['raw_tokens']) is int and 0 < saved['raw_tokens'] <= 512
            raw_max = max(raw_max, saved['raw_tokens'])
            label = row['label']; labels[str(label)] += 1; kinds[row['unknown_kind']] += 1
            languages[(row['goal_language'], row['report_language'])] += 1
            wording[(row['intent_alias'], row['report_caption'], row['report_language'])] += 1
            entities.add(row['entity']); content.add(row['content_hash'])
            if view['status'] == 'PROJECTED':
                key = row['projected_input_hash']
                assert key not in effective or effective[key] == label
                effective[key] = label
                assert type(saved['projected_tokens']) is int and 0 < saved['projected_tokens'] <= 512
                projected_max = max(projected_max, saved['projected_tokens'])
            else:
                assert saved['projected_tokens'] is None and label is None
            if label is not None:
                balanced[(row['group'], row['requested_role'])][label].append(row['reported_value'])
                contradictions += int(label == 1 and not row['fact_truth'])
            if tokenizer is not None:
                for a, b, count in [(row['objective'], row['text'], saved['raw_tokens']),
                                     *(([(view['objective'], view['text'], saved['projected_tokens'])]) if view['status'] == 'PROJECTED' else [])]:
                    key = (a, b)
                    if key not in token_cache:
                        token_cache[key] = len(tokenizer(a, b, truncation=False)['input_ids'])
                    assert token_cache[key] == count
        assert n == d['expected_rows'][split] and labels['0'] == labels['1'] == request['fixtures'] * 416
        assert kinds['unbound_record'] == request['fixtures'] * 2
        assert all(kinds[k] == request['fixtures'] * 36 for k in KINDS)
        assert len(wording) == 32 and len(set(wording.values())) == 1
        assert len(languages) == 4 and len(set(languages.values())) == 1
        for values in balanced.values():
            assert sorted(values[0]) == sorted(values[1])
        unique_labels = Counter(str(v) for v in effective.values())
        summary = dict(rows=n, binary=labels['0'] + labels['1'], unknown=labels['None'],
            structural_unknown=kinds['unbound_record'], semantic_unknown=labels['None'] - kinds['unbound_record'],
            projected_rows=n - kinds['unbound_record'], unique_projected_inputs=len(effective),
            unique_projected_labels=dict(sorted(unique_labels.items())), raw_max_tokens=raw_max,
            projected_max_tokens=projected_max, relevant_contradictions=contradictions, cuts=0)
        assert all(expected[k] == v for k, v in summary.items())
        results[split] = summary
        sets[split] = dict(content=content, effective=set(effective), entities=entities)
    overlaps = {k: len(sets['train'][k] & sets['validation'][k]) for k in sets['train']}
    assert not any(overlaps.values())
    return dict(status='PASS', protocol_sha256=p['sha256'], splits=results, cross_split_overlaps=overlaps,
        tokenizer_recounted=recount_tokenizer, raw_fields_independently_recounted=1728,
        model_forwards=0, API_calls=0, quality_approved=False, P2_admission=False,
        scope='Actual authored development direct-record contracts; no unseen tools/primitives/pairs, human ground truth or LCC utility/outcome approval')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=BASE / 'supervision-v1')
    parser.add_argument('--design-only', action='store_true')
    parser.add_argument('--recount-tokenizer', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit_design() if args.design_only else audit(args.out, args.recount_tokenizer), indent=2, allow_nan=False))
