"""Saved-input review, not inference, training data admission or human annotation.

The fixed sample covers every pilot field/language/class/UNKNOWN type; selection
is by saved ID, before inspecting scores. All four actual DROPs are supplemental.
Diagnostic targets are annotations only and must never enter a model's inputs.
"""
from collections import Counter, defaultdict
import json
from pathlib import Path

from research.audit_tool_relation_confirmation import load, sha
from research.audit_tool_relation_states import recount
from research.audit_varied_relation_dev import read_population
from research.detached_varied_study import now
from research.measurement_projection import SUFFIX, project_measurement
from research.tool_role_policy import decision

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
DATA = OUT.parent/'wording-development-pilot-v1'
CAPTURES = OUT.parent/'tool-relation-states-v2'
STUDY = DATA/'study-v1'


def interpretation(row):
    # Structural UNKNOWN concerns the record; its goal still names a field.
    if row['unknown_kind'] not in (None,'unbound_record'):
        return 'UNSUPPORTED:'+row['unknown_kind'],None
    return 'DIRECT_FIELD',row['requested_role'] or row['observed_role']


def question(row):
    match = SUFFIX.fullmatch(row['objective'])
    if match is None:
        raise ValueError('Saved caller scope is absent')
    return match['question']


def self_check():
    r = dict(unknown_kind='unbound_record',requested_role=None,observed_role='retry_attempts')
    assert interpretation(r) == ('DIRECT_FIELD','retry_attempts')
    assert interpretation(dict(r,unknown_kind=None,requested_role='retry_failures')) == ('DIRECT_FIELD','retry_failures')
    assert interpretation(dict(r,unknown_kind='diagnosis_goal')) == ('UNSUPPORTED:diagnosis_goal',None)
    r['objective'] = 'Read the attempts. Report evidence for tool-0123456789ab; ordinary and unusual values both count.'
    assert question(r) == 'Read the attempts.'
    try:
        question(dict(r,objective='no explicit caller scope'))
    except ValueError:
        pass
    else:
        raise AssertionError('Missing caller scope must be rejected')


def review():
    self_check()
    p = load(DATA/'protocol.json')
    audit = load(STUDY/'audit.json')
    assert audit['status'] == 'PASS' and audit['data_protocol_sha256'] == p['sha256']
    names = ['research/measurement_projection.py','research/tool_relation_state_supervision.py',
             'research/audit_tool_relation_states.py','research/tool_role_policy.py',
             'lcc_engine/observations.py','docs/10_OBSERVATION_OPERATION.md']
    files = [DATA/'protocol.json',DATA/'audit.json',STUDY/'protocol.json',STUDY/'audit.json',
             STUDY/'thresholds.json',STUDY/'validation-scores.json',STUDY/'validation-metrics.json']
    coverage = {};populations = {}
    for split in ('train','validation'):
        rows,views = read_population(DATA,split)
        raw = load(CAPTURES/split/'raw.json')
        fixtures = raw['measurements']['fixtures']
        for fixture in fixtures:recount(fixture)
        assert sha(CAPTURES/split/'raw.json') == p['capture_files'][f'{split}/raw.json']
        goals = defaultdict(set);targets = {};role_goals = defaultdict(set);shapes = Counter()
        for row,view in zip(rows,views,strict=True):
            scope,field = interpretation(row);q = question(row)
            assert q not in targets or targets[q] == (scope,field)
            targets[q] = scope,field
            kind = 'direct_goal_bad_record' if row['unknown_kind'] == 'unbound_record' else 'direct_field' if row['label'] is not None else row['unknown_kind']
            goals[kind].add(q)
            if row['label'] is not None:role_goals[row['requested_role']].add(q)
            projected = project_measurement(row['objective'],row['text'])
            assert {k:view['view'][k] for k in ('status','objective','text')} == {k:projected[k] for k in ('status','objective','text')}
            assert row['projected_input_hash'] == projected.get('projected_input_sha256')
            binding = row['binding'];fixture = fixtures[binding['fixture_index']]
            assert fixture['fixture_content_sha256'] == binding['fixture_content_sha256']
            assert fixture['fields'][binding['field']] == binding['actual_value']
            assert row['reported_value'] == fixture['fields'][binding['value_source_field']]
            shape = ','.join(sorted(json.loads(row['text']))) if row['text'].startswith('{') else 'prose'
            shapes[shape] += 1
        coverage[split] = dict(rows=len(rows),unique_goal_questions=len(targets),
                               unique_questions_by_kind={k:len(v) for k,v in goals.items()},
                               direct_questions_per_role={k:len(v) for k,v in role_goals.items()},record_shapes=dict(shapes))
        populations[split] = rows,views
        files += [DATA/f'{split}.jsonl.gz',DATA/f'{split}-views.jsonl.gz',CAPTURES/split/'raw.json']
    rows,views = populations['validation'];lookup = {r['id']:(r,v) for r,v in zip(rows,views,strict=True)}
    raw = load(STUDY/'validation-scores.json');scores = {s['id']:s for s in raw['rows']}
    assert set(scores) == set(lookup)
    cutoffs = load(STUDY/'thresholds.json')['thresholds'];selected = []
    fields = sorted({field for pair in p['paired_fields'].values() for field in pair})
    for field in fields:
        for language in ('en','pt'):
            for label in (0,1):
                candidates = [r for r in rows if r['requested_role'] == field and r['goal_language'] == language and r['label'] == label]
                candidates.sort(key=lambda r:(r['fact_truth'] if label else r['report_variant'] != 'measured',r['id']))
                assert candidates
                selected.append((candidates[0],'fixed_binary'))
            for kind in ('derived_or_multifield_goal','diagnosis_goal','broader_usefulness_goal','unbound_record'):
                candidates = sorted((r for r in rows if r['observed_role'] == field and r['goal_language'] == language and r['unknown_kind'] == kind),key=lambda r:r['id'])
                assert candidates
                selected.append((candidates[0],'fixed_unknown'))
    assert len(selected) == len({r['id'] for r,reason in selected}) == 96
    chosen = {r['id'] for r,reason in selected}
    drops = [r for r in rows if decision(scores[r['id']],cutoffs) == 'DROP']
    assert len(drops) == 4
    selected += [(r,'supplemental_actual_drop') for r in sorted(drops,key=lambda r:r['id']) if r['id'] not in chosen]
    cases = []
    for row,reason in selected:
        scope,field = interpretation(row);score = scores[row['id']]
        cases.append(dict(row_id=row['id'],selection=reason,goal_language=row['goal_language'],report_language=row['report_language'],
                          question=question(row),report=row['text'],expected_goal_scope=scope,expected_goal_field=field,
                          expected_record_field=row['observed_role'],label=row['label'],unknown_kind=row['unknown_kind'],
                          fact_truth=row['fact_truth'],binding=row['binding'],decision=decision(score,cutoffs),
                          score=score['score'],support_score=score.get('support_score')))
    protocol = dict(schema='saved-semantic-goal-review/0.1',created_at_utc=now(),
                    data_protocol_sha256=p['sha256'],study_protocol_sha256=audit['protocol_sha256'],
                    files={str(f.relative_to(ROOT)):sha(f) for f in files},
                    sources={n:sha(ROOT/n) for n in names},review_source_sha256=sha(Path(__file__)),
                    selection='96 field/language/class/kind strata by ID; positives prefer contradictions, negatives prefer measured values; scores not used. Additional actual DROPs are explicitly supplemental.',
                    model_forwards=0,API_calls=0,training_executed=False,independent_human_review=False,
                    gate_or_defaults_changed=False,scope='Exposed author-created development inputs; annotation/code review, not new labels or model certification')
    receipt = dict(status='PASS',created_at_utc=now(),coverage=coverage,sampled_cases=len(cases),
                   fixed_cases=96,supplemental_cases=len(cases)-96,actual_drops=4,conflicting_question_targets=0,
                   reviewed_raw_fixtures=96,model_forwards=0,API_calls=0,
                   interpretation_targets_are_diagnostic_annotations=True,independent_human_review=False,
                   scope='Mechanical input/raw/sample integrity only. Semantic agent review is recorded separately in REVIEW.md.')
    for name,value in [('protocol.json',protocol),('summary.json',receipt),('cases.json',cases)]:
        with (OUT/name).open('x') as stream:stream.write(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__ == '__main__':review()
