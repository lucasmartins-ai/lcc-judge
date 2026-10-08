"""Independent frozen confirmation declarations, rows and optional token recount.

Reuses the raw-event auditor and independent row inspector, never the producer.
Known primitives and authored wording/pairs are not production ground truth.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations, product
import json
from pathlib import Path
import random

from research.audit_tool_relation_state_supervision import digest, sha, inspect_row, rows, KINDS
from research.audit_tool_relation_states import audit as audit_raw

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'research/goal-engine-2026-10-04/varied-relation-confirm-v1'
DEVELOPMENT = BASE.parent/'tool-relation-states-v2'


def load(path):
    return json.loads(path.read_text())


def check_revision(original, revised, receipt):
    for d in (original, revised):
        assert d['sha256'] == digest({k:v for k,v in d.items() if k != 'sha256'})
    assert revised['previous_design_sha256'] == revised['capture_design_sha256'] == original['sha256']
    assert receipt['original_design_sha256'] == original['sha256']
    assert receipt['replacement_design_sha256'] == revised['sha256']
    assert receipt['status'] == 'SUPERSEDED_BEFORE_DERIVATION'
    assert receipt['raw_recaptures'] == receipt['candidate_final_model_forwards'] == 0
    assert receipt['actual_final_rows_emitted'] is receipt['quality_approved'] is False
    changed = {'frozen_at_utc', 'sources', 'roles', 'portuguese_report_captions', 'sha256'}
    added = {'previous_design_sha256', 'capture_design_sha256', 'revision_reason'}
    assert set(revised) == set(original) | added
    assert all(revised[k] == v for k,v in original.items() if k not in changed)
    assert datetime.fromisoformat(original['frozen_at_utc']) <= datetime.fromisoformat(revised['frozen_at_utc'])
    corrected = {'git_index_files', 'git_index_edits', 'git_worktree_edits'}
    for name in original['roles']:
        assert revised['roles'][name][:2] == original['roles'][name][:2]
        if name not in corrected:
            assert revised['roles'][name] == original['roles'][name]
            assert revised['portuguese_report_captions'][name] == original['portuguese_report_captions'][name]


def audit_design(base=BASE):
    old = load(base/'design/protocol.json'); d = load(base/'design-v2/protocol.json')
    check_revision(old, d, load(base/'design/superseded-before-derivation.json'))
    for directory, declaration in [('design',old), ('design-v2',d)]:
        for name, expected in declaration['sources'].items():
            assert sha(base/directory/'sources'/name) == expected
    development = load(DEVELOPMENT/'supervision-design-v3/protocol.json')
    assert d['development_design_sha256'] == development['sha256']
    roles = d['roles']; known = {tuple(sorted(v)) for v in development['pairs'].values()}
    assert set(roles) == set(development['roles']) and len(roles) == 18
    assert set(map(tuple,d['pairs'].values())) == set(combinations(sorted(roles),2))
    for family, pair in d['pairs'].items():
        seen = tuple(pair) in known
        assert family == f'{"seen_control" if seen else "primary"}:{pair[0]}:{pair[1]}'
        assert d['pair_classes'][family] == ('seen_pair_control' if seen else 'unseen_pair')
    assert sum(k.startswith('primary:') for k in d['pairs']) == 101
    for role, spec in roles.items():
        assert spec[:2] == development['roles'][role][:2]
        for index in (2,3,4):
            assert len(set(spec[index])) == 4
            assert not set(spec[index]) & set(development['roles'][role][index])
        assert len(set(d['portuguese_report_captions'][role])) == 4
        assert not set(d['portuguese_report_captions'][role]) & set(development['portuguese_report_captions'][role])
    for language in ('en','pt'):
        for split in ('train','validation'):
            assert not set(d['query_frames']['final'][language]) & set(development['query_frames'][split][language])
            for kind in KINDS:
                assert not set(d['semantic_UNKNOWN_frames']['final'][kind][language]) & set(development['semantic_UNKNOWN_frames'][split][kind][language])
    assert d['requests'] == {'final': {'seed':552601,'fixtures':64}}
    assignments = list(product(range(4),range(4),['en','pt'])) * 2
    random.Random('wording-only:552601').shuffle(assignments)
    assert d['wording_assignments']['final'] == [list(v) for v in assignments]
    captures = {}; hashes = {}
    for split, request in [('calibration',d['calibration_excluded']),('final',d['requests']['final'])]:
        p = load(base/split/'protocol.json'); raw = load(base/split/'raw.json')
        captures[split] = audit_raw(base/split)
        assert captures[split]['status'] == 'PASS' and p['request'] == raw['request'] == request
        assert p['runtime'] == d['runtime'] and old['sha256'] in p['scope']
        assert datetime.fromisoformat(old['frozen_at_utc']) <= datetime.fromisoformat(p['frozen_at_utc'])
        hashes[split] = {f['fixture_content_sha256'] for f in raw['measurements']['fixtures']}
        assert len(hashes[split]) == request['fixtures']
    assert not hashes['calibration'] & hashes['final']
    prior = set(); prior_files = {}
    for path in sorted(base.parent.rglob('raw.json')):
        if path.is_relative_to(base):
            continue
        value = load(path)
        fixtures = value.get('measurements',{}).get('fixtures',[])
        if fixtures:
            prior.update(f['fixture_content_sha256'] for f in fixtures)
            prior_files[str(path.relative_to(base.parent))] = sha(path)
    assert not prior & (hashes['final'] | hashes['calibration'])
    return dict(status='PASS',design_sha256=d['sha256'],capture_design_sha256=old['sha256'],
                captures=captures,prior_capture_files=prior_files,prior_unique_fixtures=len(prior),
                final_prior_fixture_overlap=0,calibration_prior_fixture_overlap=0,
                model_forwards=0,quality_approved=False)


def audit(out=BASE/'supervision-v1', recount_tokenizer=False):
    p = load(out/'protocol.json'); coverage = load(out/'coverage.json')
    assert p['sha256'] == digest({k:v for k,v in p.items() if k != 'sha256'}) == coverage['protocol_sha256']
    for name, expected in p['sources'].items():
        assert sha(out/'sources'/name) == expected
    for name, expected in p['capture_files'].items():
        assert sha(BASE/name) == expected
    assert p['design_audit'] == audit_design()
    d = load(BASE/'design-v2/protocol.json'); raw = load(BASE/'final/raw.json')
    assert p['design_sha256'] == d['sha256'] and p['requests'] == d['requests']
    started = load(out/'started.json'); completed = load(out/'completion.json')
    assert started['protocol_sha256'] == completed['protocol_sha256'] == p['sha256']
    assert datetime.fromisoformat(d['frozen_at_utc']) <= datetime.fromisoformat(p['frozen_at_utc']) <= datetime.fromisoformat(started['started_at_utc']) <= datetime.fromisoformat(completed['finished_at_utc'])
    assert completed['model_forwards'] == p['model_forwards'] == coverage['model_forwards'] == 0
    assert p['P2_admission'] is p['quality_approved'] is p['default_changed'] is False
    tokenizer = None
    if recount_tokenizer:
        from transformers import AutoTokenizer
        spec = p['tokenizer']
        snapshot = Path.home()/'.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1/snapshots'/spec['revision']
        for name, expected in spec['files'].items():
            assert sha(snapshot/name) == expected
        tokenizer = AutoTokenizer.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False)
    expected = coverage['splits']['final']; counts = Counter(); labels = Counter(); ids = set()
    effective = {}; content = set(); entities = set(); tokens = {}; balanced = defaultdict(lambda: {0:[],1:[]})
    cells = Counter(); edges = Counter(); raw_max = projected_max = contradictions = 0
    for name, key in [('final.jsonl.gz','rows_sha256'),('final-views.jsonl.gz','views_sha256')]:
        assert sha(out/name) == expected[key]
    for row, saved in zip(rows(out/'final.jsonl.gz'),rows(out/'final-views.jsonl.gz'),strict=True):
        assert row['id'] not in ids; ids.add(row['id'])
        view = inspect_row(row,d,raw,requests=d['requests'])
        assert saved['id'] == row['id'] and saved['view'] == view
        assert saved['truncated'] is saved['submitted_to_model'] is False
        assert type(saved['raw_tokens']) is int and 0 < saved['raw_tokens'] <= 512
        raw_max = max(raw_max,saved['raw_tokens'])
        label = row['label']; labels[str(label)] += 1; counts['rows'] += 1
        counts['binary' if label is not None else 'unknown'] += 1
        counts['structural_unknown' if view['status'] == 'UNKNOWN' else 'projected_rows'] += 1
        cells[(row['intent_alias'],row['report_caption'],row['goal_language'],row['report_language'])] += 1
        content.add(row['content_hash']); entities.add(row['entity'])
        if view['status'] == 'PROJECTED':
            key = row['projected_input_hash']; assert key not in effective or effective[key] == label
            effective[key] = label
            assert type(saved['projected_tokens']) is int and 0 < saved['projected_tokens'] <= 512
            projected_max = max(projected_max,saved['projected_tokens'])
        else:
            assert saved['projected_tokens'] is None and label is None
        if label is not None:
            edges[(row['binding']['fixture_index'],row['family'],row['goal_language'],row['requested_role'],row['observed_role'],row['report_variant'])] += 1
            balanced[(row['group'],row['requested_role'])][label].append(row['reported_value'])
            contradictions += int(label == 1 and not row['fact_truth'])
        else:
            counts[row['unknown_kind']] += 1
        if tokenizer:
            for a,b,count in [(row['objective'],row['text'],saved['raw_tokens']), *([(view['objective'],view['text'],saved['projected_tokens'])] if view['status'] == 'PROJECTED' else [])]:
                if (a,b) not in tokens:
                    tokens[(a,b)] = len(tokenizer(a,b,truncation=False)['input_ids'])
                assert tokens[(a,b)] == count
    assert counts['rows'] == d['expected_rows']['final'] == 163712
    assert labels['0'] == labels['1'] == 78336 and labels['None'] == 7040
    assert len(edges) == 156672 and set(edges.values()) == {1}
    assert counts['unbound_record'] == 128 and all(counts[k] == 2304 for k in KINDS)
    assert len(cells) == 64 and len(set(cells.values())) == 1
    assert all(sorted(v[0]) == sorted(v[1]) for v in balanced.values())
    summary = dict(rows=counts['rows'],binary=counts['binary'],unknown=counts['unknown'],
        structural_unknown=counts['structural_unknown'],semantic_unknown=6912,projected_rows=counts['projected_rows'],
        unique_projected_inputs=len(effective),unique_projected_labels=dict(sorted(Counter(str(v) for v in effective.values()).items())),
        raw_max_tokens=raw_max,projected_max_tokens=projected_max,relevant_contradictions=contradictions,cuts=0)
    assert all(expected[k] == v for k,v in summary.items())
    overlaps = {}
    for split in ('train','validation'):
        prior_rows = rows(DEVELOPMENT/'supervision-v1'/f'{split}.jsonl.gz')
        prior_content = set(); prior_effective = set(); prior_entities = set()
        for row in prior_rows:
            prior_content.add(row['content_hash']); prior_entities.add(row['entity'])
            if row['projected_input_hash']:
                prior_effective.add(row['projected_input_hash'])
        overlaps[split] = dict(content=len(content & prior_content),effective=len(set(effective) & prior_effective),entities=len(entities & prior_entities))
        assert not any(overlaps[split].values())
    return dict(status='PASS',protocol_sha256=p['sha256'],design_sha256=d['sha256'],final=summary,
        cross_development_overlaps=overlaps,raw_fields_independently_recounted=1152,
        tokenizer_recounted=recount_tokenizer,model_forwards=0,API_calls=0,P2_admission=False,quality_approved=False,
        scope='64 authored actual-tool fixtures;163712 correlated rows;known18primitives/3tools,101unseen cross-tool pair combinations,52seen-wording controls. No model/outcome approval.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design-only',action='store_true'); parser.add_argument('--recount-tokenizer',action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit_design() if args.design_only else audit(recount_tokenizer=args.recount_tokenizer),indent=2,allow_nan=False))
