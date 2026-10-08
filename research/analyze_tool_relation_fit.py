"""Independent exposed-fit/contrast analysis; no model calls or cutoff fitting."""

import argparse
from collections import Counter,defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics

from research.audit_tool_role_support import audited_scores,close,digest,reduce_metrics
from research.audit_tool_relation_support import normalized_semantic_rows

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'research/goal-engine-2026-10-04'
STUDY=BASE/'tool-relation-support-v1'
DATA=BASE/'tool-relations-grounded-v1/supervision-v1'
FIT=STUDY/'fit-diagnostic-v1'


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def _rows(split):
    return [json.loads(line) for line in (DATA/f'{split}.jsonl').read_text().splitlines()]


def audit_fit():
    protocol=json.loads((FIT/'protocol.json').read_text());study=json.loads((STUDY/'protocol.json').read_text())
    assert protocol['sha256']==digest({k:v for k,v in protocol.items() if k!='sha256'})
    assert protocol['study_protocol_sha256']==study['sha256'] and protocol['seed']==101
    for name,expected in protocol['sources'].items():assert sha(FIT/'sources'/name)==expected
    for name,expected in protocol['data_files'].items():assert sha(DATA/name)==expected
    meta=json.loads((STUDY/'seed-101/training_meta.json').read_text())
    assert protocol['weights_sha256']==meta['weights_sha256']
    assert protocol['thresholds']==json.loads((STUDY/'seed-101/thresholds.json').read_text())['thresholds']
    rows=_rows('train');views=[json.loads(line) for line in (DATA/'train-views.jsonl').read_text().splitlines()]
    raw=audited_scores(FIT/'train-scores.json',rows,views,protocol,False)
    assert raw['complete'] is True and raw['error'] is None
    stored=json.loads((FIT/'metrics.json').read_text());normalized=normalized_semantic_rows(rows)
    result=reduce_metrics(normalized,raw['rows'],protocol['thresholds'])
    close(stored['metrics'],result)
    for column,values in [('by_language',['en','pt']),('by_family',sorted({r['family'] for r in rows if r['label'] is not None}))]:
        recomputed={}
        for value in values:
            field='goal_language' if column=='by_language' else 'family'
            pairs=[(r,s) for r,s in zip(normalized,raw['rows']) if r[field]==value]
            recomputed[value]=reduce_metrics([r for r,s in pairs],[s for r,s in pairs],protocol['thresholds'])
        close(stored[column],recomputed)
    unique={}
    for row,score in zip(rows,raw['rows']):
        if score['status']=='SCORED':
            key=row['projected_input_hash'];label=2 if row['label'] is None else row['label']
            if key not in unique:unique[key]=(label,score['logits'])
            assert unique[key][0]==label
    assert len(unique)==3592
    losses=defaultdict(list);confusion=[[0]*3 for unused in range(3)]
    for label,values in unique.values():
        largest=max(values)
        loss=largest+math.log(sum(math.exp(v-largest) for v in values))-values[label]
        losses[label].append(loss);confusion[label][max(range(3),key=lambda i:values[i])]+=1
    return dict(status='PASS',protocol_sha256=protocol['sha256'],metrics=result,
        unique_training_inputs=len(unique),class_counts={str(k):len(v) for k,v in losses.items()},
        globally_balanced_unique_evaluation_CE=statistics.mean(statistics.mean(v) for v in losses.values()),
        class_argmax_confusion=confusion,valid_pair_forwards=raw['accounting']['valid_score_pairs'],
        valid_nonpadding_tokens=raw['accounting']['valid_score_tokens'],elapsed_s=raw['elapsed_s'],
        criterion_or_threshold_refit=False,model_forwards_by_audit=0,training_reexecuted=False,
        scope='Original exposed first-seed train population; original validation-only cutoffs, no generalization or optimization-cause claim. Unique CE uses first saved evaluation output per repeated input.')


def analyze():
    data_protocol=json.loads((DATA/'protocol.json').read_text())
    graph=defaultdict(set)
    for a,b in data_protocol['train_families'].values():graph[a].add(b);graph[b].add(a)
    components=[];remaining=set(graph)
    while remaining:
        stack=[min(remaining)];component=set()
        while stack:
            node=stack.pop()
            if node in component:continue
            component.add(node);stack.extend(graph[node]-component)
        remaining-=component;components.append(sorted(component))
    component_id={role:index for index,component in enumerate(components) for role in component}
    final_pairs=data_protocol['final_families']
    outside=sum(component_id[a]!=component_id[b] for a,b in final_pairs.values())
    rows=_rows('final');contrasts={}
    for seed in [101,202,303]:
        raw=json.loads((STUDY/f'seed-{seed}/final-scores.json').read_text())
        assert len(rows)==len(raw['rows']) and all(row['id']==score['id'] for row,score in zip(rows,raw['rows']))
        matrices=defaultdict(dict)
        for row,score in zip(rows,raw['rows']):
            if row['label'] is None:continue
            key=(row['family'],row['group'],row['report_variant'],row['goal_language'])
            matrices[key][(row['requested_role'],row['observed_role'])]=score['score']
        grouped=defaultdict(list)
        for (family,group,variant,language),matrix in matrices.items():
            a,b=final_pairs[family];assert set(matrix)=={(a,a),(a,b),(b,a),(b,b)}
            delta_a=matrix[a,a]-matrix[a,b];delta_b=matrix[b,b]-matrix[b,a]
            grouped[family].append(dict(right_goals=int(delta_a>0)+int(delta_b>0),
                same_preference=delta_a*delta_b<0,interaction=delta_a+delta_b))
        contrasts[str(seed)]={family:dict(matrices=len(values),
            both_goals_correct=sum(v['right_goals']==2 for v in values),
            one_goal_correct=sum(v['right_goals']==1 for v in values),
            neither_goal_correct=sum(v['right_goals']==0 for v in values),
            same_report_preference_after_goal_flip=sum(v['same_preference'] for v in values),
            mean_interaction=statistics.mean(v['interaction'] for v in values)) for family,values in grouped.items()}
    result=dict(status='PASS',data_protocol_sha256=data_protocol['sha256'],
        train_graph=dict(roles=len(graph),unordered_pairs=len(data_protocol['train_families']),
            connected_components=len(components),components=components,
            role_degrees=dict(Counter(len(neighbors) for neighbors in graph.values())),
            final_pairs=len(final_pairs),final_pairs_between_different_train_components=outside),
        final_contrasts=contrasts,source_scores_preserved=True,threshold_fitting=False,model_forwards=0,
        scope='Measured contrast/coverage diagnosis on now-exposed final receipts; no causal attribution, new candidate, selective gate or generalization claim')
    if (FIT/'metrics.json').exists():result['fit']=audit_fit()
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.parse_args()
    print(json.dumps(analyze(),indent=2))
