"""Exploratory, label-free per-objective normalization on saved CLEAN scores.

Requires three candidates at inference time. Candidate composition is curated in
this benchmark; gains do not establish M12 calibration or independent OOD transfer.
Run: python -m research.normalization_pilot
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np


KINDS = ['fact', 'noise_decoy', 'noise_unrelated']


def pooled(pos, neg):
    return float(np.mean(np.asarray(pos)[:, None] > np.asarray(neg)[None, :]))


def normalize(probabilities):
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-7, 1-1e-7)
    logits = np.log(p / (1-p))
    scale = logits.std(axis=1, keepdims=True)
    return (logits-logits.mean(axis=1, keepdims=True)) / np.where(scale > 0, scale, 1)


def run(source=Path('bakeoff/results/results.json'), out=Path('research/continuation-2026-10-03')):
    out.mkdir(exist_ok=True, parents=True)
    protocol = dict(version='objective-zscore-logit/0.1', depths=[0, 512],
                    models=['specialist-exp05-frozen-8k', 'specialist-exp05-unfreeze2-8k'],
                    bootstrap_repeats=2000, bootstrap_seed=42,
                    transform='zscore(logit(probability)) over all three candidates for each objective',
                    criteria=dict(min_delta_J=.03, delta_J_ci_low_strictly_positive=True, max_D_loss=.01),
                    source_file=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    limitations=['Exploratory continuation; original terminal-only pilot not reproduced.',
                                 'No calibration fit and no untouched confirmatory split.',
                                 'Requires a candidate set; score depends on its composition.',
                                 'AUC gains are not probabilistic calibration evidence.'])
    # Persist the recipe and fixed criteria before calculating results.
    (out/'normalization-protocol.json').write_text(json.dumps(protocol, indent=2)+'\n')
    rows = json.loads(source.read_text())['rows']
    summary, evidence = {}, []
    for model in protocol['models']:
        summary[model] = {}
        for depth in protocol['depths']:
            selected = [r for r in rows if r['model'] == model and r['depth_tokens'] == depth]
            indexed = {(r['case_id'], r['kind']): r for r in selected}
            ids = sorted({r['case_id'] for r in selected})
            if len(ids) != 62 or len(indexed) != 186 or len(selected) != 186:
                raise ValueError('Require exactly 62 complete independent case triplets')
            if any(r['score'] is None or r.get('error') or r['truncated'] for r in selected):
                raise ValueError('Invalid/truncated source scores')
            values = np.array([[indexed[c, k]['score'] for k in KINDS] for c in ids])
            transformed = normalize(values)
            before = dict(J=pooled(values[:, 0], values[:, 1]), D=pooled(values[:, 0], values[:, 2]))
            after = dict(J=pooled(transformed[:, 0], transformed[:, 1]), D=pooled(transformed[:, 0], transformed[:, 2]))
            rng = np.random.default_rng(protocol['bootstrap_seed'])
            gains = []
            for _ in range(protocol['bootstrap_repeats']):
                indices = rng.integers(0, len(ids), size=len(ids))
                a, b = values[indices], transformed[indices]
                gains.append(pooled(b[:, 0], b[:, 1])-pooled(a[:, 0], a[:, 1]))
            ci = np.percentile(gains, [2.5, 97.5]).tolist()
            delta_j, delta_d = after['J']-before['J'], after['D']-before['D']
            summary[model][str(depth)] = dict(n=len(ids), before=before, after=after,
                delta_J=delta_j, delta_D=delta_d, delta_J_95ci=ci,
                exploratory_criteria_pass=delta_j >= .03 and ci[0] > 0 and delta_d >= -.01,
                gate_090_pass=after['J'] >= .9 and after['D'] >= .9,
                validated_for_deployment=False)
            evidence.extend(dict(model=model, depth=depth, case_id=c, probabilities=values[i].tolist(),
                                 normalized_scores=transformed[i].tolist()) for i, c in enumerate(ids))
    result = dict(protocol=protocol, summary=summary, records=evidence)
    (out/'normalization-results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(summary, indent=2))
    return result


if __name__ == '__main__':
    run()
