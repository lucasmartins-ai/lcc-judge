"""Pilot-specific data inspection plus the unchanged independent training auditor.

The historical auditor's data callback is temporarily bound to this new schema;
its update/order/calibration/logit/metric/frozen-weight checks remain unchanged.
No trainer, policy or model imports/calls. Tokenizer-only recount is local.
"""

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path

from research import audit_varied_relation_dev as core
from research.audit_tool_relation_confirmation import load, sha
from research.audit_tool_relation_state_supervision import digest, inspect_row, rows
from research.audit_tool_relation_states import audit as audit_raw
from research.audit_tool_role_support import audited_scores, close, reduce_metrics
from research.audit_tool_relation_support import normalized_semantic_rows

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'research/goal-engine-2026-10-04/wording-development-pilot-v1'
OUT = DATA/'study-v1'
ORIGINAL = DATA.parent/'tool-relation-states-v2'


def inspected_data(data, recount_tokenizer=False):
    assert data.resolve() == DATA.resolve()
    p,receipt = load(DATA/'protocol.json'),load(DATA/'audit.json')
    assert p['sha256'] == digest({k:v for k,v in p.items() if k != 'sha256'}) == receipt['protocol_sha256']
    for name,value in p['sources'].items():
        assert sha(DATA/'sources'/name) == value
    for name,value in p['capture_files'].items():
        assert sha(ORIGINAL/name) == value
    assert p['model_forwards'] == p['API_calls'] == 0 and p['quality_approved'] is False
    assert datetime.fromisoformat(p['frozen_at_utc']) <= datetime.fromisoformat(receipt['finished_at_utc'])
    assert len(p['paired_fields']) == 4 and len({r for pair in p['paired_fields'].values() for r in pair}) == 8
    tokenizer = None
    if recount_tokenizer:
        from transformers import AutoTokenizer
        directory = Path.home()/'.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1/snapshots'/p['tokenizer']['revision']
        assert all(sha(directory/n) == value for n,value in p['tokenizer']['files'].items())
        tokenizer = AutoTokenizer.from_pretrained(directory,local_files_only=True,trust_remote_code=False)
    inputs = {}
    for split in ('train','validation'):
        assert digest(audit_raw(ORIGINAL/split)) == digest(p['reused_capture_independent_audits'][split])
        raw = load(ORIGINAL/split/'raw.json')
        rfile,vfile = DATA/f'{split}.jsonl.gz',DATA/f'{split}-views.jsonl.gz'
        saved = receipt['coverage'][split]
        assert sha(rfile) == saved['rows_sha256'] and sha(vfile) == saved['views_sha256']
        rs,vs = list(rows(rfile)),list(rows(vfile))
        assert len(rs) == len(vs) == p['expected_rows'][split]
        counts = Counter();unique = {};ids = set();raw_max = projected_max = contradictions = 0
        for r,v in zip(rs,vs):
            inspect_row(r,p['recipes'][split],raw,requests=p['requests'])
            assert r['id'] == v['id'] and r['id'] not in ids
            ids.add(r['id'])
            assert v['truncated'] is v['submitted_to_model'] is False
            assert type(v['raw_tokens']) is int and 0 < v['raw_tokens'] <= 512
            if tokenizer:
                assert len(tokenizer(r['objective'],r['text'],truncation=False)['input_ids']) == v['raw_tokens']
            raw_max = max(raw_max,v['raw_tokens'])
            counts['rows'] += 1
            counts['binary' if r['label'] is not None else 'unknown'] += 1
            contradictions += int(r['label'] == 1 and r['fact_truth'] is False)
            if r['projected_input_hash']:
                key = r['projected_input_hash']
                assert v['view']['status'] == 'PROJECTED' and digest([v['view']['objective'],v['view']['text']]) == key
                assert type(v['projected_tokens']) is int and 0 < v['projected_tokens'] <= 512
                if tokenizer:
                    assert len(tokenizer(v['view']['objective'],v['view']['text'],truncation=False)['input_ids']) == v['projected_tokens']
                assert key not in unique or unique[key] == r['label']
                unique[key] = r['label']
                projected_max = max(projected_max,v['projected_tokens'])
                counts['projected_rows'] += 1
            else:
                assert v['view']['status'] == 'UNKNOWN' and v['projected_tokens'] is None
                counts['structural_unknown'] += 1
        result = dict(counts,semantic_unknown=counts['unknown']-counts['structural_unknown'],
                      unique_projected_inputs=len(unique),unique_projected_labels=dict(Counter(str(v) for v in unique.values())),
                      raw_max_tokens=raw_max,projected_max_tokens=projected_max,relevant_contradictions=contradictions,cuts=0,
                      rows_sha256=sha(rfile),views_sha256=sha(vfile))
        close(saved,result)
        inputs[split] = set(unique)
    assert not inputs['train'] & inputs['validation']
    for role in {r for pair in p['paired_fields'].values() for r in pair}:
        for position in (2,3):
            assert not set(p['recipes']['train']['roles'][role][position]) & set(p['recipes']['validation']['roles'][role][position])
    # Return the independently verified original receipt for the legacy auditor's
    # equality check, retaining its historical completion timestamp unchanged.
    return receipt


def audit():
    data_audit = inspected_data(DATA,recount_tokenizer=True)
    p = load(OUT/'protocol.json')
    assert p['schema'] == 'bounded-held-goal-wording-development-pilot/0.1'
    assert p['data_directory'] == '..'  # Preserved original producer metadata typo.
    previous = core.audit_data
    core.audit_data = inspected_data
    try:
        result = core.audit(OUT,verify_weights=True,data_override=DATA)
    finally:
        core.audit_data = previous
    rs,vs = core.read_population(DATA,'validation')
    raw = audited_scores(OUT/'scalar-validation-scores.json',rs,vs,p,True)
    assert raw['complete'] is True and raw['error'] is None
    control = load(OUT/'scalar-validation-metrics.json')
    close(control['metrics'],reduce_metrics(normalized_semantic_rows(rs),raw['rows'],dict(support=None,relevance=None),True))
    close(control['accounting'],raw['accounting'])
    exited = load(OUT/'process-exit.json')
    assert exited['returncode'] == 0 and exited['study_complete'] is True and exited['protocol_sha256'] == p['sha256']
    assert datetime.fromisoformat(load(OUT/'summary.json')['finished_at_utc']) <= datetime.fromisoformat(raw['finished_at_utc']) <= datetime.fromisoformat(control['finished_at_utc']) <= datetime.fromisoformat(exited['utc'])
    result.update(independent_data_tokenizer_recount=True,data_protocol_sha256=data_audit['protocol_sha256'],
                  metadata_erratum=dict(original_data_directory=p['data_directory'],correct_data_directory='.',
                                        frozen_protocol_preserved=True,all_data_file_hashes_verified=True),
                  scalar_validation_forwards=raw['accounting']['valid_score_pairs'],scalar_validation_tokens=raw['accounting']['valid_score_tokens'],
                  total_evaluation_forwards=result['valid_evaluation_forwards']+raw['accounting']['valid_score_pairs'],
                  total_evaluation_tokens=result['valid_evaluation_nonpadding_tokens']+raw['accounting']['valid_score_tokens'],
                  audit_source_sha256=sha(Path(__file__)),core_audit_source_sha256=sha(Path(core.__file__)),quality_approved=False,scope=p['limits'])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-only',action='store_true')
    args = parser.parse_args()
    result = inspected_data(DATA,True) if args.data_only else audit()
    print(json.dumps(result,indent=2,allow_nan=False))
