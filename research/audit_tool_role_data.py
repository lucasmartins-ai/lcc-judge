"""Independent raw/label/split audit; no producer imports, model or API calls.

Recorded CLI/API output is reparsed here. Filesystem calls happened in the worker;
this audit verifies their saved receipts rather than recreating their live state.
Optional tokenizer re-count loads only the pinned local tokenizer, never weights.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'research/goal-engine-2026-10-04/tool-role-grounded-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def columns(text, count):
    values = list(map(int, text.split()))
    assert len(values) == count
    return values


def audit_fixture(fixture):
    records = fixture['raw_observations']
    assert len(records) == 16
    fields = {}
    for index, (flag, key) in enumerate([('--lines', 'wc_newlines'), ('--words', 'wc_words'),
                                        ('--chars', 'wc_characters'), ('--bytes', 'wc_bytes')]):
        record = records[index]
        assert record['argv'] == ['/usr/bin/wc', flag, 'data.txt']
        value, filename = record['stdout'].split()
        assert filename == 'data.txt'
        fields[key] = int(value)
    record = records[4]
    assert record['argv'] == ['/usr/bin/stat', '--printf=%s\t%b\t%B\t%h\t%i\t%a\t%o\n', 'data.txt']
    names = ['stat_size_bytes', 'stat_allocated_blocks', 'stat_block_bytes', 'stat_hard_links',
             'stat_inode', 'stat_octal_mode', 'stat_io_hint_bytes']
    fields.update(zip(names, columns(record['stdout'], 7)))
    record = records[5]
    assert record['argv'] == ['/usr/bin/stat', '--printf=%s\t%b\t%B\n', 'sparse.dat']
    logical, blocks, size = columns(record['stdout'], 3)
    fields.update(sparse_logical_bytes=logical, sparse_allocated_bytes=blocks * size)
    for index, key, flags in [(6, 'link_entry_bytes', []), (7, 'link_target_bytes', ['--dereference'])]:
        record = records[index]
        assert record['argv'] == ['/usr/bin/stat', *flags, '--format=%s', 'symbolic']
        fields[key] = columns(record['stdout'], 1)[0]
    for index, key, flags in [(8, 'du_apparent_bytes', ['--apparent-size']), (9, 'du_allocated_bytes', [])]:
        record = records[index]
        assert record['argv'] == ['/usr/bin/du', '--block-size=1', *flags, 'sparse.dat']
        value, filename = record['stdout'].split()
        assert filename == 'sparse.dat'
        fields[key] = int(value)
    assert records[10]['argv'] == ['/usr/bin/df', '--block-size=1', '--output=size,used,avail', 'data.txt']
    fields.update(zip(['df_total_bytes', 'df_used_bytes', 'df_available_bytes'], columns(records[10]['stdout'].splitlines()[-1], 3)))
    assert records[11]['argv'] == ['/usr/bin/df', '--output=itotal,iused,iavail', 'data.txt']
    fields.update(zip(['df_inode_total', 'df_inode_used', 'df_inode_available'], columns(records[11]['stdout'].splitlines()[-1], 3)))
    assert records[12]['argv'] == ['/usr/bin/gzip', '--list', 'data.txt.gz']
    compressed, uncompressed = map(int, records[12]['stdout'].splitlines()[-1].split()[:2])
    fields.update(gzip_compressed_bytes=compressed, gzip_uncompressed_bytes=uncompressed)
    process = records[13]
    assert process['argv'][:3] == ['/usr/local/bin/python', '-I', '-c']
    template = re.fullmatch(r'import sys; print\("observed\\n"\*(\d+),end=""\); sys.exit\((\d+)\)', process['argv'][3])
    assert template is not None
    printed, exit_code = map(int, template.groups())
    assert 1 <= printed <= 12 and exit_code in [0, 2, 7, 42]
    assert process['returncode'] == exit_code and process['stdout'] == 'observed\n' * printed
    fields.update(command_exit_status=exit_code, command_stdout_newlines=process['stdout'].count('\n'))
    env = records[14]
    assert env['argv'][:4] == ['/usr/local/bin/python', '-I', '-S', '-c']
    observed = json.loads(env['stdout'])
    mapping = observed['observed_environment']
    assert observed['defined'] == len(mapping) and observed['empty'] == sum(v == '' for v in mapping.values())
    assert all(k.startswith('K') or k == 'LC_CTYPE' for k in mapping)
    assert all(mapping[k] == v for k, v in env['authored_env'].items())
    fields.update(environment_defined=len(mapping), environment_empty=sum(v == '' for v in mapping.values()))
    clock = records[15]
    assert clock['api'] == 'time.process_time_ns/perf_counter_ns'
    fields.update(profile_cpu_ns=clock['after']['cpu_ns'] - clock['before']['cpu_ns'],
                  profile_elapsed_ns=clock['after']['elapsed_ns'] - clock['before']['elapsed_ns'])
    assert fields['profile_cpu_ns'] >= 0 and fields['profile_elapsed_ns'] >= clock['requested_sleep_ns']
    for index, record in enumerate(records[:15]):
        assert record['stderr'] == ''
        if index != 13:
            assert record['returncode'] == 0
    content = fixture['fixture_content']
    assert hashlib.sha256(content.encode()).hexdigest() == fixture['fixture_content_sha256']
    assert fields['wc_newlines'] == content.count('\n')
    assert fields['wc_words'] == len(content.split())
    assert fields['wc_characters'] == len(content) and fields['wc_bytes'] == len(content.encode())
    assert fields['stat_size_bytes'] == fields['wc_bytes'] == fields['link_target_bytes'] == uncompressed
    assert fields['stat_block_bytes'] == 512 and size == 512
    assert fields['stat_hard_links'] == 1 + fixture['index'] % 4
    assert fields['link_entry_bytes'] == len('data.txt'.encode())
    assert fields['du_apparent_bytes'] == logical and fields['du_allocated_bytes'] == blocks * size
    assert fields['df_used_bytes'] + fields['df_available_bytes'] == fields['df_total_bytes']  # this isolated tmpfs, no reservations
    assert fields['df_inode_used'] + fields['df_inode_available'] == fields['df_inode_total']
    assert len(fields) == 31 and fields == fixture['fields']
    assert all(type(v) is int for v in fixture['fields'].values())
    for check in fixture['checks']:
        assert check['passed'] is True and check['actual'] == fields[check['field']]
        if 'expected' in check:
            assert check['actual'] == check['expected']
        else:
            assert check['actual'] >= check['expected_min']
    return fields


def literals(path, names):
    tree = ast.parse(path.read_text())
    return {node.targets[0].id: ast.literal_eval(node.value)
            for node in tree.body if isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name) and node.targets[0].id in names}


def parse_report(text):
    if text.startswith('{'):
        pairs = json.loads(text, object_pairs_hook=list)
        assert len(pairs) == len(dict(pairs))
        return dict(pairs)
    match = re.fullmatch(r'Tool report (tool-[a-f0-9]{12}) \[(INFO|WARN|ERROR)\]: ([^\r\n]+): (-?\d+)\.', text)
    assert match
    entity, level, caption, value = match.groups()
    return dict(entity=entity, level=level, measurement=caption, value=int(value))


def audit(out=DEFAULT, verify_tokenizer=False, snapshot=None):
    protocol = json.loads((out / 'protocol.json').read_text())
    assert protocol['sha256'] == digest({k: v for k, v in protocol.items() if k != 'sha256'})
    for name, expected in protocol['sources'].items():
        assert sha(out / 'sources' / name) == expected
    definitions = literals(out / 'sources/research/tool_role_contracts.py', ['ROLES', 'TRAIN_FAMILIES', 'FINAL_FAMILIES', 'REFERENCES'])
    assert json.loads(json.dumps(definitions['ROLES'])) == protocol['roles']
    assert json.loads(json.dumps(definitions['TRAIN_FAMILIES'])) == protocol['train_families']
    assert json.loads(json.dumps(definitions['FINAL_FAMILIES'])) == protocol['final_families']
    assert definitions['REFERENCES'] == protocol['primary_references']
    design = literals(out / 'sources/research/tool_role_corpus.py', ['SEEDS', 'COUNTS', 'TEMPLATES'])
    assert json.loads(json.dumps(design['TEMPLATES'])) == protocol['templates']
    for split in design['SEEDS']:
        assert protocol['requests'][split] == dict(seed=design['SEEDS'][split], fixtures=design['COUNTS'][split])
        assert protocol['requests'][split]['seed'] != protocol['calibration_seed_excluded']
    coverage = json.loads((out / 'coverage.json').read_text())
    assert coverage['protocol_sha256'] == protocol['sha256'] and coverage['model_forwards'] == 0
    tokenizer = None
    if verify_tokenizer:
        if snapshot is None:
            snapshot = Path.home() / '.cache/huggingface/hub/models--cross-encoder--ms-marco-MiniLM-L6-v2/snapshots' / protocol['tokenizer']['revision']
        for name, expected in protocol['tokenizer']['files'].items():
            assert sha(snapshot / name) == expected
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
    summary = {}
    hashes, projected, contents, entities = {}, {}, {}, {}
    roles = protocol['roles']
    events = [json.loads(line) for line in (out / 'collection-events.jsonl').read_text().splitlines()]
    assert len(events) == 2 * len(protocol['requests'])
    for split, request in protocol['requests'].items():
        raw = json.loads((out / f'{split}-raw.json').read_text())
        assert raw['status'] == 'MEASURED' and raw['error'] is None and raw['returncode'] == 0
        assert raw['host_measurement_executed'] is False
        assert raw['request'] == request and raw['measurements']['request'] == request
        began, ended = [event for event in events if event['split'] == split]
        assert began['event'] == 'START' and ended['event'] == 'END'
        assert datetime.fromisoformat(protocol['frozen_at_utc']) <= datetime.fromisoformat(began['utc']) <= datetime.fromisoformat(ended['utc'])
        assert began['protocol_sha256'] == ended['protocol_sha256'] == protocol['sha256']
        assert began['request'] == request and ended['raw_sha256'] == sha(out / f'{split}-raw.json') and ended['status'] == 'MEASURED'
        assert raw['request_sha256'] == hashlib.sha256(json.dumps(request, allow_nan=False).encode()).hexdigest()
        assert json.loads(raw['stdout']) == raw['measurements']
        identity = {k: v for k, v in protocol['runtime'].items() if k != 'docker'}
        assert raw['runtime'] == identity
        argv = raw['container_argv']
        assert argv[-4:] == [identity['image_id'], 'python', '-I', '/opt/lcc-measure/worker.py']
        for flag in ['--pull=never', '--network=none', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--user=65534:65534', '--memory=256m', '--cpus=1', '--pids-limit=64']:
            assert flag in argv
        assert not any(v in ['--mount', '--volume', '-v', '--privileged', '--network=host'] for v in argv)
        assert raw['measurements']['all_reference_checks_passed'] is True
        assert raw['measurements']['locale'] == 'C.UTF-8'
        assert raw['measurements']['versions'] == {'wc': 'wc (GNU coreutils) 9.7', 'stat': 'stat (GNU coreutils) 9.7', 'du': 'du (GNU coreutils) 9.7', 'df': 'df (GNU coreutils) 9.7', 'gzip': 'gzip 1.13'}
        fixtures = raw['measurements']['fixtures']
        assert len(fixtures) == request['fixtures']
        fields = {i: audit_fixture(f) for i, f in enumerate(fixtures)}
        assert all(f['index'] == i for i, f in enumerate(fixtures))
        contents[split] = {f['fixture_content_sha256'] for f in fixtures}
        rows = [json.loads(line) for line in (out / f'{split}.jsonl').read_text().splitlines()]
        views = [json.loads(line) for line in (out / f'{split}-views.jsonl').read_text().splitlines()]
        assert len(rows) == len(views) == coverage['splits'][split]['rows']
        for name, suffix in [('rows_sha256', '.jsonl'), ('raw_sha256', '-raw.json'), ('views_sha256', '-views.jsonl')]:
            assert sha(out / f'{split}{suffix}') == coverage['splits'][split][name]
        families = protocol['final_families'] if split == 'final' else protocol['train_families']
        assert len(rows) == request['fixtures'] * (len(families) * 8 * 2 + 8)
        seen_ids = set()
        balances = defaultdict(lambda: [Counter(), Counter()])
        binary_sources = set()
        for row, saved in zip(rows, views):
            assert row['id'] == saved['id'] and row['id'] not in seen_ids
            seen_ids.add(row['id'])
            assert row['split'] == split and row['goal_language'] in ['en', 'pt'] and row['report_language'] == 'en'
            assert row['model_pair'] == {k: row[k] for k in ['objective', 'text']}
            assert row['content_hash'] == digest([row['objective'], row['text']]) == saved['original_input_hash']
            suffix = f" Report evidence for {row['entity']}; ordinary and unusual values both count."
            assert row['objective'].endswith(suffix)
            question = row['objective'][:-len(suffix)]
            observed = row['observed_role']
            field, source, unit = roles[observed][:3]
            binding = row['binding']
            index = binding['fixture_index']
            value_role = binding['value_source_role']
            value_field = roles[value_role][0]
            actual = fields[index][field] * (fields[index]['stat_block_bytes'] if observed == 'allocated' else 1)
            reported = fields[index][value_field] * (fields[index]['stat_block_bytes'] if value_role == 'allocated' else 1)
            assert binding == dict(source=source, field=field, unit=unit, value_source_field=value_field,
                                   value_source_role=value_role, actual_value=actual, fixture_index=index,
                                   fixture_content_sha256=fixtures[index]['fixture_content_sha256'])
            assert row['reported_value'] == reported and row['fact_truth'] == (actual == reported)
            assert row['evidence_span'] == [0, len(row['text'])]
            body = parse_report(row['text'])
            assert body['entity'] == row['entity'] and body['value'] == reported
            if row['label'] is not None:
                assert type(row['label']) is int and row['label'] in [0, 1]
                assert row['family'] in families and observed in families[row['family']]
                assert row['requested_role'] in families[row['family']]
                assert row['label'] == int(row['requested_role'] == observed)
                assert row['unknown_kind'] is None
                assert set(body) == {'entity', 'level', 'measurement', 'value'}
                caption_index = index % 2 if split == 'train' else (2 if split == 'validation' else index % 3)
                assert body['measurement'] == roles[observed][5][caption_index]
                alias_index = index % 2 if split == 'train' else (2 if split == 'validation' else index % 3)
                aliases = roles[row['requested_role']][3 if row['goal_language'] == 'en' else 4]
                templates = protocol['templates'][split][row['goal_language']]
                assert question == templates[(index // 2) % len(templates)].format(aliases[alias_index])
                if row['report_variant'] == 'measured':
                    assert value_role == observed
                else:
                    assert row['report_variant'] == 'value_swap' and value_role != observed
                    assert value_role in families[row['family']]
                balances[(row['group'], row['requested_role'])][row['label']][reported] += 1
                binary_sources.add(source)
            else:
                assert row['family'] == 'unknown' and row['requested_role'] is None
                assert observed == value_role == 'newline' and row['report_variant'] == 'measured'
                if row['unknown_kind'] == 'unsupported_goal':
                    assert question in protocol['unknown_queries'][split][row['goal_language']]
                    assert set(body) == {'entity', 'level', 'measurement', 'value'}
                else:
                    assert row['unknown_kind'] == 'unbound_record'
                    assert set(body) == {'entity', 'measurement', 'value'}
            view = saved['view']
            assert view['original_text'] == row['text'] and view['original_input_sha256'] == row['content_hash']
            assert view['drop_authorized'] is False and saved['submitted_to_model'] is False and saved['truncated'] is False
            expected_projected = row['unknown_kind'] != 'unbound_record'
            assert view['status'] == row['projection_status'] == ('PROJECTED' if expected_projected else 'UNKNOWN')
            assert 0 < saved['raw_tokens'] <= 512
            if expected_projected:
                assert view['objective'] == question and view['text'] == f"{body['measurement']}: {reported}."
                assert view['projected_input_sha256'] == row['projected_input_hash'] == digest([question, view['text']])
                assert 0 < saved['projected_tokens'] <= 512
            else:
                assert saved['projected_tokens'] is None and row['projected_input_hash'] is None
            if tokenizer is not None:
                assert len(tokenizer(row['objective'], row['text'], truncation=False)['input_ids']) == saved['raw_tokens']
                if expected_projected:
                    assert len(tokenizer(view['objective'], view['text'], truncation=False)['input_ids']) == saved['projected_tokens']
        assert all(pos == neg and sum(pos.values()) == 2 for neg, pos in balances.values())
        assert binary_sources == set(protocol['source_clusters']['final' if split == 'final' else 'train'])
        hashes[split] = {r['content_hash'] for r in rows}
        projected[split] = {r['projected_input_hash'] for r in rows if r['projected_input_hash'] is not None}
        entities[split] = {r['entity'] for r in rows}
        raw_max = max(v['raw_tokens'] for v in views)
        projected_max = max(v['projected_tokens'] for v in views if v['projected_tokens'] is not None)
        assert raw_max == coverage['splits'][split]['raw_max_tokens']
        assert projected_max == coverage['splits'][split]['projected_max_tokens']
        assert coverage['splits'][split]['raw_overflow'] == coverage['splits'][split]['projected_overflow'] == 0
        summary[split] = dict(fixtures=len(fixtures), measurement_fields=31 * len(fixtures),
                              raw_observations=16 * len(fixtures), rows=len(rows),
                              binary=sum(r['label'] is not None for r in rows), unknown=sum(r['label'] is None for r in rows),
                              semantic_unknown=sum(r['unknown_kind'] == 'unsupported_goal' for r in rows),
                              structural_unknown=sum(r['unknown_kind'] == 'unbound_record' for r in rows),
                              contradictions=sum(r['fact_truth'] is False for r in rows),
                              relevant_contradictions=sum(r['label'] == 1 and r['fact_truth'] is False for r in rows),
                              language_counts=dict(Counter(r['goal_language'] for r in rows)),
                              unique_raw_inputs=len(hashes[split]), unique_projected_inputs=len(projected[split]),
                              projected_rows=sum(r['projected_input_hash'] is not None for r in rows),
                              binary_source_clusters=sorted(binary_sources), raw_max_tokens=raw_max,
                              projected_max_tokens=projected_max, worker_elapsed_s=raw['elapsed_s'])
    splits = list(summary)
    for i, left in enumerate(splits):
        for right in splits[i + 1:]:
            for collection in [hashes, projected, contents, entities]:
                assert not collection[left] & collection[right]
    return dict(status='PASS', protocol_sha256=protocol['sha256'], splits=summary,
                raw_outputs_reparsed=True, all_31_fields_recomputed=True, source_bindings_and_labels_verified=True,
                per_goal_numeric_label_multisets_equal=True, raw_and_projected_cross_split_overlap=0,
                fixture_content_and_entity_cross_split_overlap=0, tokenizer_recounted=verify_tokenizer,
                model_forwards=0, api_calls=0, p2_labels=0, default_changed=False,
                semantic_unknown_recognized_by_current_projection=False,
                interpretation='Data/receipt validation only; authored fixtures/captions and counterfactuals, three correlated final source clusters, no candidate quality or external/LCC outcome claim')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=DEFAULT)
    parser.add_argument('--verify-tokenizer', action='store_true')
    parser.add_argument('--snapshot', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.out, args.verify_tokenizer, args.snapshot), indent=2, ensure_ascii=False))
