"""Independent stdlib recount of fresh-final logits, gates, chronology and cost.

No producer/policy/model imports, inference or final threshold fitting. Audit
PASS means evidence is consistent; it does not certify engine+LCC usefulness.
"""

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path

from research.audit_tool_relation_confirmation import audit as audit_data, load, sha
from research.audit_tool_role_support import audited_scores, close, digest, disposition, gate, reduce_metrics
from research.audit_tool_relation_support import normalized_semantic_rows
from research.audit_varied_relation_dev import read_population

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'research/goal-engine-2026-10-04/varied-relation-confirm-v1'
OUT = BASE/'evaluation-v1'


def audit(out=OUT):
    p = load(out/'protocol.json')
    assert p['sha256'] == digest({k:v for k,v in p.items() if k != 'sha256'})
    assert p['seeds'] == [101,202,303] and p['expected_rows'] == 163712 and p['expected_unique_inputs'] == 120220
    assert p['score_axes'] == dict(relevance='logit1-logit0',unsupported='independent logit2')
    assert p['device'] == 'cpu' and p['dtype'] == 'float32' and p['window'] == 512
    for name,expected in p['sources'].items():
        assert sha(out/'sources'/name) == expected
    for name,expected in p['files'].items():
        assert sha(ROOT/name) == expected
    design = load(BASE/'design-v2/protocol.json')
    assert p['criteria'] == design['criteria'] and p['design_sha256'] == design['sha256']
    data = BASE/'supervision-v1'
    assert audit_data(data,recount_tokenizer=False)['protocol_sha256'] == p['data_protocol_sha256']
    assert load(data/'audit-corrected-v1.json')['status'] == 'PASS'
    frozen = datetime.fromisoformat(p['frozen_at_utc'])
    started = load(out/'started.json')
    assert started['protocol_sha256'] == p['sha256'] and frozen <= datetime.fromisoformat(started['utc'])
    for key,candidate in p['candidates'].items():
        d = BASE.parent/'varied-relation-dev-v2' if key == '101' else BASE/f'seed{key}'
        meta, cutoff, exited, audited = (load(d/name) for name in ('training_meta.json','thresholds.json','process-exit.json','audit.json'))
        assert meta['seed'] == int(key) and meta['epochs_completed'] == 3
        assert candidate['weights_sha256'] == meta['weights_sha256'] == sha(ROOT/candidate['weights_path'])
        assert candidate['thresholds'] == cutoff['thresholds'] and cutoff['final_inspected'] is False
        assert audited['status'] == 'PASS' and audited['private_weights_verified'] is True
        assert audited['protocol_sha256'] == candidate['protocol_sha256'] == meta['protocol_sha256']
        assert exited['returncode'] == 0 and exited['study_complete'] is True
        assert datetime.fromisoformat(cutoff['frozen_at_utc']) <= datetime.fromisoformat(exited['finished_at_utc']) <= frozen
    rows,views = read_population(data,'final')
    unique = {}
    for r,v in zip(rows,views,strict=True):
        if v['view']['status'] == 'PROJECTED':
            unique.setdefault(r['projected_input_hash'],(r,v))
    keys = sorted(unique)
    unique_rows = [unique[k][0] for k in keys]
    unique_views = [unique[k][1] for k in keys]
    assert len(rows) == p['expected_rows'] and len(keys) == p['expected_unique_inputs']
    normalized = normalized_semantic_rows(rows)
    total_pairs = total_tokens = 0
    receipts = {}
    previous = datetime.fromisoformat(started['utc'])
    for key in ('101','202','303','scalar'):
        scalar = key == 'scalar'
        directory = out/key
        marker = load(directory/'started.json')
        assert marker['protocol_sha256'] == p['sha256']
        assert previous <= datetime.fromisoformat(marker['utc'])
        raw = audited_scores(directory/'unique-scores.json',unique_rows,unique_views,p,scalar)
        assert raw['complete'] is True and raw['error'] is None and raw['elapsed_s'] > 0
        previous = datetime.fromisoformat(raw['finished_at_utc'])
        assert datetime.fromisoformat(marker['utc']) <= previous
        lookup = {s['input_hash']:s for s in raw['rows']}
        assert len(lookup) == len(keys) and set(lookup) == set(keys)
        scores = []
        for row,view in zip(rows,views):
            if row['projected_input_hash'] is None:
                assert view['view']['status'] == 'UNKNOWN'
                score = dict(id=row['id'],status='UNKNOWN')
            else:
                saved = lookup[row['projected_input_hash']]
                if scalar:
                    relevance, support = saved['score'], None
                else:
                    # Independent trained axes from original persisted fp32 logits.
                    values = saved['logits']
                    relevance, support = values[1]-values[0], values[2]
                score = dict(id=row['id'],status='SCORED',score=relevance,support_score=support)
            scores.append(score)
        cutoff = dict(support=None,relevance=None) if scalar else p['candidates'][key]['thresholds']
        recomputed = {}
        for cohort in ('overall','primary','seen_control'):
            eligible = [i for i,r in enumerate(rows) if cohort == 'overall' or r['label'] is None or r['family'].split(':')[0] == cohort]
            for field,language in ((None,None),('goal_language','en'),('goal_language','pt'),('report_language','en'),('report_language','pt')):
                indices = [i for i in eligible if field is None or rows[i][field] == language]
                rs,ss = [normalized[i] for i in indices], [scores[i] for i in indices]
                value = reduce_metrics(rs,ss,cutoff,scalar)
                value['dispositions'] = {}
                for group in ('positive','negative','semantic_unknown','structural_unknown'):
                    counts = Counter()
                    for r,s in zip(rs,ss):
                        wanted = ('positive' if r['label'] == 1 else 'negative' if r['label'] == 0
                                  else 'structural_unknown' if r['unknown_kind'] == 'unbound_record' else 'semantic_unknown')
                        if wanted == group:
                            counts[disposition(s,cutoff,scalar)] += 1
                    value['dispositions'][group] = {d:counts[d] for d in ('KEEP','DROP','UNKNOWN')}
                name = cohort if field is None else f'{cohort}/{field}/{language}'
                recomputed[name] = value
        receipt = load(directory/'metrics.json')
        assert receipt['protocol_sha256'] == p['sha256'] and receipt['candidate'] == key
        assert receipt['raw_scores_sha256'] == sha(directory/'unique-scores.json')
        close(receipt['metrics'],recomputed)
        close(receipt['thresholds'],cutoff)
        close(receipt['accounting'],raw['accounting'])
        close(receipt['elapsed_scoring_s'],raw['elapsed_s'])
        assert receipt['additional_model_forwards'] == 0 and receipt['fixture_denominator'] == 64
        assert receipt['correlated_rows'] == len(rows)
        passed = False if scalar else all(gate(v,p['criteria']) for v in recomputed.values())
        assert receipt['passes_point_criteria'] is passed
        assert receipt['quality_approved'] is receipt['default_changed'] is receipt['P2_admission'] is False
        receipts[key] = receipt
        total_pairs += raw['accounting']['forward_completed_pairs']
        total_tokens += raw['accounting']['forward_completed_tokens']
        previous = datetime.fromisoformat(receipt['finished_at_utc'])
    summary = load(out/'summary.json')
    assert summary['protocol_sha256'] == p['sha256']
    assert summary['seed_passes'] == [receipts[k]['passes_point_criteria'] for k in ('101','202','303')]
    assert summary['all_seeds_pass'] is all(summary['seed_passes'])
    assert summary['model_forwards'] == total_pairs == 4*len(keys)
    assert summary['nonpadding_tokens'] == total_tokens
    assert summary['API_calls'] == 0 and summary['quality_approved'] is summary['default_changed'] is summary['P2_admission'] is False
    assert previous <= datetime.fromisoformat(summary['finished_at_utc'])
    exited = load(out/'process-exit.json')
    assert exited['returncode'] == 0 and exited['study_complete'] is True
    assert exited['protocol_sha256'] == p['sha256'] and datetime.fromisoformat(summary['finished_at_utc']) <= datetime.fromisoformat(exited['utc'])
    return dict(status='PASS',protocol_sha256=p['sha256'],seed_passes=summary['seed_passes'],
                all_seeds_pass=summary['all_seeds_pass'],model_forwards=total_pairs,nonpadding_tokens=total_tokens,
                model_forwards_by_audit=0,quality_approved=False,scope=p['scope'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(audit(),indent=2,allow_nan=False))
