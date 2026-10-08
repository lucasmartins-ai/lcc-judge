"""Recompute a fixed two-logit diagnostic; stdlib only, no model/API calls."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics

from research.audit_reranker_diagnostic import digest,sha,reduce
from research.audit_reranker_projection import equal

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'research/goal-engine-2026-10-04/compact-relation-v1'
DEFAULT=ROOT/'research/goal-engine-2026-10-04/report-prior-diagnostic-v1'


def audit(out):
    protocol=json.loads((out/'protocol.json').read_text())
    assert digest({k:v for k,v in protocol.items() if k!='sha256'})==protocol['sha256']
    original=json.loads((OLD/'protocol.json').read_text())
    selection=json.loads((OLD/'selection.json').read_text())
    assert protocol['base_protocol_sha256']==original['sha256']
    assert protocol['selected_by_original_validation']==selection['selected_arm']
    equal(protocol['criteria'],original['criteria'])
    for name,expected in protocol['sources'].items():
        assert sha(out/'executed-source'/name)==expected
    finals=[]
    base_finals=[]
    pairs=0
    tokens=0
    max_tokens=0
    family_metrics={}
    for seed in protocol['seeds']:
        arm=protocol['selected_by_original_validation']
        meta=json.loads((OLD/f'{arm}-{seed}/training_meta.json').read_text())
        assert meta['weights_sha256']==protocol['weights_sha256'][str(seed)]
        cumulative=dict(counted_tokens=0,submitted_tokens=0,forward_completed_tokens=0,valid_score_tokens=0)
        threshold=None
        for split in ['validation','final']:
            assert sha(OLD/f'{split}.jsonl')==protocol['data'][split]['sha256']
            assert sha(OLD/f'{split}-views.jsonl')==protocol['data'][split]['views_sha256']
            source={r['id']:r for r in (json.loads(line) for line in (OLD/f'{split}.jsonl').read_text().splitlines())}
            views={r['id']:r for r in (json.loads(line) for line in (OLD/f'{split}-views.jsonl').read_text().splitlines())}
            base_path=OLD/f'{arm}-{seed}/{split}.json'
            assert sha(base_path)==protocol['base_receipt_sha256'][str(seed)][split]
            base=json.loads(base_path.read_text())
            receipt=json.loads((out/f'{seed}/{split}.json').read_text())
            assert receipt['protocol_sha256']==protocol['sha256'] and receipt['split']==split and receipt['seed']==seed
            equal(receipt['base_metrics'],base['metrics'])
            assert [r['id'] for r in receipt['rows']]==[r['id'] for r in base['rows']]==list(source)
            controls={r['report_id']:r for r in receipt['reference_rows']}
            assert len(controls)==len(receipt['reference_rows'])==receipt['new_reference_pair_forwards']
            assert set(controls)=={r['report_id'] for r in source.values()}
            for row in source.values():
                control=controls[row['report_id']]
                assert control['input_sha256']==digest([protocol['reference_question'],views[row['id']]['text']])
            for control in controls.values():
                assert control['submitted'] and control['forward_completed'] and control['status']=='SCORED'
                assert control['error'] is None and not control['truncated'] and not control['window_exceeded']
                assert 0<control['actual_tokens']<=protocol['pair_window'] and math.isfinite(control['score'])
                max_tokens=max(max_tokens,control['actual_tokens'])
                tokens+=control['actual_tokens']
                pairs+=1
                for key in cumulative:
                    cumulative[key]+=control['actual_tokens']
            equal(cumulative,receipt['cumulative_reference_accounting'])
            for saved,raw in zip(receipt['rows'],base['rows']):
                control=controls[raw['report_id']]
                assert saved['base_forward_preexisting'] is True
                assert saved['base_raw_score']==raw['score'] and saved['reference_raw_score']==control['score']
                assert saved['score']==raw['score']-control['score'] and math.isfinite(saved['score'])
                assert saved['reference_input_sha256']==control['input_sha256']
                for key in raw:
                    if key!='score':
                        assert saved[key]==raw[key]
            result=reduce(receipt['rows'],receipt['threshold'],source)
            equal(result,receipt['metrics'])
            assert result['paired_auc']==base['metrics']['paired_auc'], 'Same report control cancels on the goal axis'
            if split=='validation':
                positive=[r['score'] for r in receipt['rows'] if r['label']==1]
                threshold=max(t for t in set(positive) if statistics.mean(s>=t for s in positive)>=.95)
            assert receipt['threshold']==threshold
            if split=='final':
                finals.append(result)
                base_finals.append(base['metrics'])
                family_metrics[seed]={d:reduce([r for r in receipt['rows'] if r['domain']==d],threshold,source)
                                      for d in protocol['data']['final']['domains']}
    summary=json.loads((out/'summary.json').read_text())
    assert summary['protocol_sha256']==protocol['sha256']
    mean={k:statistics.mean(r[k] for r in finals) for k in ['auc','paired_auc','positive_recall','negative_rejection']}
    equal(mean,summary['mean'])
    assert summary['mean_within_objective_auc']==statistics.mean(r['within_objective']['auc'] for r in finals)
    gates=[]
    for result in finals:
        values=result.copy();values['within_objective_auc']=result['within_objective']['auc']
        gates.append(result['n']==result['eligible'] and result['errors']==result['cuts']==0 and
                     all(values[k.removesuffix('_min')]>=v for k,v in protocol['criteria'].items() if k.endswith('_min')))
    assert gates==summary['seeds_pass'] and all(gates)==summary['all_seeds_pass'] and not summary['adoption']
    return dict(schema='generic-report-control-audit/0.1',protocol_sha256=protocol['sha256'],
        archived_sources_base_controls_subtraction_threshold_metrics_gates_verified=True,
        reference_question=protocol['reference_question'],mean=mean,
        mean_within_objective_auc=summary['mean_within_objective_auc'],seeds_pass=gates,all_seeds_pass=all(gates),
        base_mean={k:statistics.mean(r[k] for r in base_finals) for k in mean},
        new_reference_pair_forwards=pairs,reference_nonpadding_tokens=tokens,max_reference_pair_tokens=max_tokens,
        paired_goal_axis_unchanged=True,base_inference_reexecuted=False,training_executed=False,
        model_calls_during_audit=0,API_calls_during_audit=0,adoption=False,family_metrics=family_metrics,
        scope='one fixed reference on exposed authored compact cohorts, no transfer confirmation/calibrated probability/P2/production')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=DEFAULT)
    args=parser.parse_args();result=audit(args.out)
    (args.out/'audit.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='family_metrics'},indent=2))
