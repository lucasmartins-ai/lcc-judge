"""Recount the declared direct-record corpus without importing its producer.

Default audit uses saved strings, raw tool receipts and archived declarations.
Optional tokenizer recount uses the pinned local tokenizer, with zero model
forwards. Authored meanings are transparent, not independent human ground truth.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path

from research.audit_tool_relations import audit as audit_raw

DEFAULT = Path(__file__).resolve().parent / 'goal-engine-2026-10-04/tool-relations-grounded-v1/supervision-v1'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(out=DEFAULT, recount_tokenizer=False):
    protocol = json.loads((out / 'protocol.json').read_text())
    coverage = json.loads((out / 'coverage.json').read_text())
    assert protocol['sha256'] == digest({k: v for k, v in protocol.items() if k != 'sha256'})
    assert coverage['protocol_sha256'] == protocol['sha256']
    for name, expected in protocol['sources'].items():
        assert sha(out / 'sources' / name) == expected
    assert protocol['calibration_excluded'] == 442500
    assert protocol['model_forwards'] == coverage['model_forwards'] == 0
    assert protocol['training'] is protocol['P2_admission'] is protocol['default_changed'] is False
    assert protocol['requests'] == {'train': {'seed': 442511, 'fixtures': 32},
                                    'validation': {'seed': 442512, 'fixtures': 12},
                                    'final': {'seed': 442513, 'fixtures': 24}}
    tokenizer = None
    if recount_tokenizer:
        from transformers import AutoTokenizer
        spec = protocol['tokenizer']
        snapshot = Path.home() / '.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1/snapshots' / spec['revision']
        for name, expected in spec['files'].items():
            assert sha(snapshot / name) == expected
        tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
    results, split_sets = {}, {}
    semantic_kinds = ('derived_or_multifield_goal', 'diagnosis_goal', 'broader_usefulness_goal')
    for split, request in protocol['requests'].items():
        for name, expected in protocol['capture_files'][split].items():
            assert sha(out / 'captures' / split / name) == expected
        raw_result = audit_raw(out / 'captures' / split)
        assert raw_result == protocol['raw_receipt_audits'][split]
        raw = json.loads((out / 'captures' / split / 'raw.json').read_text())
        assert raw['request'] == request
        assert datetime.fromisoformat(json.loads((out / 'captures' / split / 'completion.json').read_text())['finished_at_utc']) <= datetime.fromisoformat(protocol['frozen_at_utc'])
        rows = [json.loads(line) for line in (out / f'{split}.jsonl').read_text().splitlines()]
        views = [json.loads(line) for line in (out / f'{split}-views.jsonl').read_text().splitlines()]
        expected = coverage['splits'][split]
        assert sha(out / f'{split}.jsonl') == expected['rows_sha256']
        assert sha(out / f'{split}-views.jsonl') == expected['views_sha256']
        assert len(rows) == len(views) == expected['rows']
        families = protocol['final_families'] if split == 'final' else protocol['train_families']
        assert len(rows) == request['fixtures'] * (16 * len(families) + 8)
        assert len({row['id'] for row in rows}) == len(rows)
        labels, languages, kinds, wording = Counter(), Counter(), Counter(), Counter()
        per_goal_values = defaultdict(lambda: {0: [], 1: []})
        effective_classes, effective, entities = {}, set(), set()
        contradictions = 0
        projected = structural = semantic = 0
        raw_lengths, view_lengths = [], []
        for row, saved in zip(rows, views):
            assert row['split'] == split and row['id'] == saved['id']
            index = row['binding']['fixture_index']
            fixture = raw['measurements']['fixtures'][index]
            fields = fixture['fields']
            observed, value_field = row['observed_role'], row['binding']['value_source_field']
            role_spec = protocol['roles'][observed]
            assert row['binding'] == dict(source=role_spec[0], field=observed, unit=role_spec[1],
                value_source_field=value_field, actual_value=fields[observed], fixture_index=index,
                fixture_content_sha256=fixture['fixture_content_sha256'])
            assert row['reported_value'] == fields[value_field]
            assert row['fact_truth'] is (row['reported_value'] == fields[observed])
            language = row['goal_language']
            assert language in ('en', 'pt') and row['report_language'] == 'en'
            languages[language] += 1
            group = digest([split, request['seed'], row['family'], index, language])
            entity = 'tool-' + group[:12]
            assert row['group'] == group and row['entity'] == entity
            entities.add(entity)
            alias = (index // 2) % 2 if split == 'train' else (2 if split == 'validation' else 3)
            caption_index = index % 2 if split == 'train' else (2 if split == 'validation' else 3)
            assert row['intent_alias'] == alias and row['report_caption'] == caption_index
            caption = role_spec[4][caption_index]
            value = row['reported_value']
            level = ('INFO', 'WARN', 'ERROR')[(index // 8) % 3]
            body = dict(entity=entity, level=level, measurement=caption, value=value)
            report = (f'Tool report {entity} [{level}]: {caption}: {value}.' if (index // 4) % 2
                      else json.dumps(body, sort_keys=True))
            label = row['label']
            if label is not None:
                requested = row['requested_role']
                pair = families[row['family']]
                assert requested in pair and observed in pair and type(label) is int
                assert label == int(requested == observed) and row['unknown_kind'] is None
                choices = protocol['templates'][split][language]
                question = choices[(index // 4) % len(choices)].format(protocol['roles'][requested][2 if language == 'en' else 3][alias])
                assert row['report_variant'] in ('measured', 'value_swap')
                other = pair[1] if observed == pair[0] else pair[0]
                assert value_field == (observed if row['report_variant'] == 'measured' else other)
                assert row['id'] == digest([group, requested, observed, row['report_variant']])
                assert row['report_id'] == digest([group, observed, row['report_variant']])
                per_goal_values[(group, requested)][label].append(value)
                wording[(alias, caption_index)] += 1
                contradictions += int(label == 1 and not row['fact_truth'])
            else:
                assert row['family'] == 'unknown' and row['requested_role'] is None
                assert observed == ('retry_attempts', 'udp_received_payload_bytes', 'git_index_files')[index % 3]
                assert value_field == observed and row['report_variant'] == 'measured'
                kind = row['unknown_kind']
                kinds[kind] += 1
                if kind == 'unbound_record':
                    case = 3
                    question = protocol['templates'][split][language][0].format(role_spec[2 if language == 'en' else 3][alias])
                    report = json.dumps(dict(entity=entity, measurement=caption, value=value))
                else:
                    case = semantic_kinds.index(kind)
                    question = protocol['unknown_queries'][split][language][case]
                assert row['id'] == row['report_id'] == digest([group, case])
            labels[str(label)] += 1
            objective = question + f' Report evidence for {entity}; ordinary and unusual values both count.'
            assert row['objective'] == objective and row['text'] == report
            assert row['model_pair'] == dict(objective=objective, text=report)
            content_hash = digest([objective, report])
            assert row['content_hash'] == saved['original_input_hash'] == content_hash
            view = saved['view']
            assert view['original_text'] == report and view['original_input_sha256'] == content_hash
            assert view['drop_authorized'] is False and saved['truncated'] is saved['submitted_to_model'] is False
            if row['unknown_kind'] == 'unbound_record':
                structural += 1
                assert row['projection_status'] == view['status'] == 'UNKNOWN'
                assert row['projected_input_hash'] is None and saved['projected_tokens'] is None
                assert view['objective'] is view['text'] is None
            else:
                projected += 1
                semantic += int(label is None)
                text = f'{caption}: {value}.'
                input_hash = digest([question, text])
                assert row['projection_status'] == view['status'] == 'PROJECTED'
                assert row['projected_input_hash'] == view['projected_input_sha256'] == input_hash
                assert view['objective'] == question and view['text'] == text and view['error'] is None
                if input_hash in effective_classes:
                    assert effective_classes[input_hash] == label
                effective_classes[input_hash] = label
                effective.add(input_hash)
                assert type(saved['projected_tokens']) is int and 0 < saved['projected_tokens'] <= 512
                view_lengths.append(saved['projected_tokens'])
                if tokenizer is not None:
                    assert len(tokenizer(question, text, truncation=False)['input_ids']) == saved['projected_tokens']
            assert type(saved['raw_tokens']) is int and 0 < saved['raw_tokens'] <= 512
            raw_lengths.append(saved['raw_tokens'])
            if tokenizer is not None:
                assert len(tokenizer(objective, report, truncation=False)['input_ids']) == saved['raw_tokens']
        for label_values in per_goal_values.values():
            assert sorted(label_values[0]) == sorted(label_values[1])
        assert languages['en'] == languages['pt']
        assert labels['0'] == labels['1'] == request['fixtures'] * len(families) * 8
        assert labels['None'] == request['fixtures'] * 8
        assert structural == request['fixtures'] * 2 and semantic == request['fixtures'] * 6
        if split == 'train':
            assert set(wording) == {(0, 0), (0, 1), (1, 0), (1, 1)}
            assert len(set(wording.values())) == 1
        assert expected['binary'] == labels['0'] + labels['1']
        assert expected['unknown'] == structural + semantic
        assert expected['structural_unknown'] == structural and expected['projected_rows'] == projected
        assert expected['unique_projected_inputs'] == len(effective)
        assert expected['raw_max_tokens'] == max(raw_lengths) and expected['projected_max_tokens'] == max(view_lengths)
        assert expected['cuts'] == 0
        results[split] = dict(rows=len(rows), labels=dict(labels), semantic_unknown=semantic,
            structural_unknown=structural, unique_projected_inputs=len(effective), projected_rows=projected,
            raw_max_tokens=max(raw_lengths), projected_max_tokens=max(view_lengths), relevant_contradictions=contradictions,
            wording_counts={f'{a}:{c}': n for (a, c), n in sorted(wording.items())}, numeric_multisets_balanced=True)
        split_sets[split] = dict(content={row['content_hash'] for row in rows}, effective=effective, entities=entities,
            fixtures={f['fixture_content_sha256'] for f in raw['measurements']['fixtures']})
    overlaps = {}
    for a, b in (('train', 'validation'), ('train', 'final'), ('validation', 'final')):
        overlaps[a + ':' + b] = {key: len(split_sets[a][key] & split_sets[b][key]) for key in split_sets[a]}
        assert not any(overlaps[a + ':' + b].values())
    train_pairs = {tuple(sorted(pair)) for pair in protocol['train_families'].values()}
    final_pairs = {tuple(sorted(pair)) for pair in protocol['final_families'].values()}
    assert not train_pairs & final_pairs
    assert {role for pair in protocol['train_families'].values() for role in pair} == set(protocol['roles'])
    assert len(protocol['roles']) == 18
    return dict(status='PASS', protocol_sha256=protocol['sha256'], splits=results, cross_split_overlaps=overlaps,
        raw_fields_independently_recounted=1224, tokenizer_recounted=recount_tokenizer,
        declared_token_counts_bounded=True, model_forwards=0, API_calls=0, P2_admission=False,
        source_holdout=False, primitive_holdout=False, novel_final_pair_combinations=len(final_pairs),
        scope='Saved actual-tool receipt/declarative label/input audit on authored direct-record tasks; not human-reviewed semantic ground truth, P2, production or LCC replacement quality')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=DEFAULT)
    parser.add_argument('--recount-tokenizer', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.out, args.recount_tokenizer), indent=2))
