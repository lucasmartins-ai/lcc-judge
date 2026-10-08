"""Recompute saved matched controls and grouped objective-study uncertainty."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research/goal-engine-2026-10-04'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def auc(pos, neg):
    # Number of negatives strictly below each positive: ties receive zero.
    return float(np.searchsorted(np.sort(neg), pos, side='left').sum()/(len(pos)*len(neg)))


def metrics(rows, scores=None):
    values = np.asarray(scores if scores is not None else [r['score'] for r in rows])
    kinds = np.asarray([r['kind'] for r in rows])
    positive = values[kinds == 'pos']
    return {f: auc(positive, values[kinds == k]) for f, k in [('J', 'neg_decoy'), ('D', 'neg_unrelated')]}


def head_study():
    directory = OUT/'head-objectives'
    protocol = json.loads((directory/'protocol.json').read_text())
    selection = json.loads((directory/'selection.json').read_text())
    final = json.loads((directory/'final-results.json').read_text())
    parent = final['parent']['101']['rows']
    parent_values = np.asarray([r['score'] for r in parent])
    group_names = sorted({r['domain'] for r in parent})
    groups = [np.array([i for i, r in enumerate(parent) if r['domain'] == d]) for d in group_names]
    parent_metrics = metrics(parent)
    validation = {}; result = {}
    for arm in protocol['arms']:
        validation[arm] = []
        for seed in protocol['seeds']:
            target = directory/f'{arm}-{seed}'
            meta = json.loads((target/'training_meta.json').read_text())
            assert meta['epochs_completed'] == len(meta['history']) == protocol['epochs']
            assert meta['protocol_sha256'] == protocol['sha256'] and meta['heads_trained_on'] == 'train only'
            v = json.loads((target/'validation.json').read_text())
            computed = metrics(v['rows']); assert computed == v['metrics']
            validation[arm].append(np.mean(list(computed.values())))
        values = []
        for seed in protocol['seeds']:
            rows = final[arm][str(seed)]['rows']
            assert [(r['id'], r['kind'], r['domain'], r['objective']) for r in rows] == \
                   [(r['id'], r['kind'], r['domain'], r['objective']) for r in parent]
            assert metrics(rows) == final[arm][str(seed)]['metrics']
            values.append(np.asarray([r['score'] for r in rows]))
        mean_metrics = {f: float(np.mean([metrics(parent, v)[f] for v in values])) for f in ['J', 'D']}
        rng = np.random.default_rng(78103); gains = {'J': [], 'D': []}
        for _ in range(2000):
            indices = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
            sampled = [parent[i] for i in indices]
            base = metrics(sampled, parent_values[indices])
            for f in ['J', 'D']:
                gains[f].append(np.mean([metrics(sampled, v[indices])[f] for v in values])-base[f])
        ci = {f: np.percentile(gains[f], [2.5, 97.5]).tolist() for f in ['J', 'D']}
        deltas = {f: mean_metrics[f]-parent_metrics[f] for f in ['J', 'D']}
        criteria = protocol['criteria']
        passed = mean_metrics['D'] >= criteria['candidate_D_min'] and ci['D'][0] > 0 and \
                 deltas['J'] >= -criteria['candidate_max_J_loss']
        result[arm] = dict(mean_metrics=mean_metrics, delta_from_parent=deltas, delta_95ci=ci,
                           candidate_criteria_pass=passed, selected_on_validation=arm == selection['selected_arm'])
    means = {a: float(np.mean(v)) for a, v in validation.items()}
    assert all(abs(means[a]-selection['validation_means'][a]) < 1e-14 for a in means)
    assert max(means, key=means.get) == selection['selected_arm']
    return dict(parent=parent_metrics, candidates=result, selected_arm=selection['selected_arm'],
                bootstrap=dict(repeats=2000, seed=78103, groups=group_names,
                               method='resample whole domains; average matched three-seed metrics; seeds held fixed',
                               limitation='Only four known synthetic domain groups; not production uncertainty'),
                normalization_tested=False,
                normalization_reason='Generated final items are single candidates; 357 objectives across 480 rows do not form complete matched candidate triplets',
                external_confirmation=False, approved_for_adoption=False,
                inputs={n: sha(directory/n) for n in ['protocol.json', 'selection.json', 'final-results.json']})


def matched_controls():
    directory = OUT/'matched-controls'; protocol = json.loads((directory/'protocol.json').read_text())
    computed = []; identity = {}; normalization = []
    for model in protocol['models']:
        result = json.loads((directory/model/'results.json').read_text())
        assert result['protocol_sha256'] == protocol['sha256']
        saved = [json.loads(s) for s in (directory/model/'scores.jsonl').read_text().splitlines()]
        assert saved == result['rows'] and len(saved) == 372
        for depth in protocol['depths_cl100k']:
            rows = [r for r in saved if r['depth_tokens'] == depth]
            assert len(rows) == 186
            keys = [(r['case_id'], r['kind']) for r in rows]
            assert len(set(keys)) == len(keys)
            for row in rows:
                key = (depth, row['case_id'], row['kind'])
                if key in identity: assert identity[key] == row['input_sha256']
                else: identity[key] = row['input_sha256']
            values = {k: [r['score'] for r in rows if r['kind'] == k]
                      for k in ['fact', 'noise_decoy', 'noise_unrelated']}
            j, d = auc(values['fact'], values['noise_decoy']), auc(values['fact'], values['noise_unrelated'])
            truncations = sum(r['truncated'] for r in rows)
            summary = result['summary'][0]['by_depth'][str(depth)]
            assert round(j, 3) == summary['auc_judge'] and round(d, 3) == summary['auc_detect']
            assert truncations == summary['truncated']
            computed.append(dict(model=model, depth_cl100k=depth, J=j, D=d, n_cases=62,
                                 truncated=truncations, p50_latency_ms=summary['p50_latency_ms'],
                                 gate_eligible=truncations == 0 and not any(r['error'] for r in rows),
                                 gate_pass=truncations == 0 and j >= .90 and d >= .90))
            if model == 'specialist' and not truncations:
                indexed = {(r['case_id'], r['kind']): r['score'] for r in rows}
                case_ids = sorted({r['case_id'] for r in rows})
                probabilities = np.asarray([[indexed[c, k] for k in ['fact', 'noise_decoy', 'noise_unrelated']] for c in case_ids])
                logits = np.log(np.clip(probabilities, 1e-7, 1-1e-7)/(1-np.clip(probabilities, 1e-7, 1-1e-7)))
                scale = logits.std(1, keepdims=True)
                z = (logits-logits.mean(1, keepdims=True))/np.where(scale > 0, scale, 1)
                after = {'J': auc(z[:, 0], z[:, 1]), 'D': auc(z[:, 0], z[:, 2])}
                rng = np.random.default_rng(78104); differences = []
                for _ in range(2000):
                    idx = rng.integers(0, 62, 62)
                    differences.append(auc(z[idx, 0], z[idx, 1])-auc(logits[idx, 0], logits[idx, 1]))
                normalization.append(dict(depth_cl100k=depth, before={'J': j, 'D': d}, after=after,
                    delta_J=after['J']-j, delta_D=after['D']-d, delta_J_95ci=np.percentile(differences, [2.5, 97.5]).tolist(),
                    posthoc=True, label_free_transform=True, probabilistic_calibration=False,
                    deployment_validated=False, candidate_composition='one fact, one decoy, one unrelated per known objective'))
    return dict(rows=computed, same_input_hashes_verified=True, normalization=normalization,
                normalization_bootstrap='2000 whole objective-triplet resamples, seed 78104',
                exploratory=True, effective_context_gate_pass=False,
                latency_fairness='Same CPU/eight threads; GTE fp16 while specialist/BGE fp32; author recipes, no hardware/dtype performance superiority claim')


def main():
    result = dict(head_objectives=head_study(), matched_controls=matched_controls(),
                  analysis_source_sha256=sha(__file__))
    (OUT/'study-analysis.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'matched_controls'}, indent=2))


if __name__ == '__main__': main()
