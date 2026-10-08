"""One fixed fresh-final pass for all locked candidates and one scalar control.

Reuse complete-input/failure accounting; deduplicate identical projected strings
and expand saved logits for correlated-row metrics. No final calibration.
"""

from collections import Counter
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import socket
import subprocess
import sys
import time

import torch
from safetensors.torch import load_file

from research.audit_tool_relation_confirmation import BASE, audit, load, sha
from research.audit_tool_relation_state_supervision import digest
from research.audit_varied_relation_dev import read_population
from research.detached_varied_study import checked_protocol, now, process_identity, save
from research.reranker_control import PairReranker
from research.tool_relation_adaptation import configure_adaptation
from research.tool_relation_support_study import score_population, snapshot_path
from research.tool_role_policy import decision, metrics, passes
from specialist.checkpoint import load_trained_weights

ROOT = Path(__file__).resolve().parents[1]
FINAL = BASE/'supervision-v1'
OUT = BASE/'evaluation-v1'
SEEDS = (101, 202, 303)
SOURCES = [
    'research/varied_relation_confirmation_scoring.py', 'research/audit_varied_relation_confirmation.py',
    'research/detached_varied_study.py', 'research/audit_varied_relation_dev.py',
    'research/audit_tool_relation_confirmation.py', 'research/audit_tool_relation_state_supervision.py',
    'research/audit_tool_relation_states.py', 'research/audit_tool_role_support.py',
    'research/audit_tool_relation_support.py', 'research/audit_tool_relation_weights.py',
    'research/tool_relation_support_study.py', 'research/tool_relation_adaptation.py',
    'research/ranking_support_initialization.py', 'research/reranker_control.py',
    'research/tool_role_policy.py', 'research/measurement_projection.py',
    'specialist/checkpoint.py', 'specialist/numerical.py',
]


def candidate(seed):
    if type(seed) is not int or seed not in SEEDS:
        raise ValueError('Only the three predeclared candidates are permitted')
    out = BASE.parent/'varied-relation-dev-v2' if seed == 101 else BASE/f'seed{seed}'
    return out, ROOT/load(out/'training_meta.json')['weights_path']


def locked_candidates():
    """Require ALL candidates before reading/scoring any final population."""
    locked, files = {}, {}
    for seed in SEEDS:
        directory, weights = candidate(seed)
        p = load(directory/'protocol.json')
        meta = load(directory/'training_meta.json')
        cutoff = load(directory/'thresholds.json')
        audited = load(directory/'audit.json')
        exit_receipt = load(directory/'process-exit.json')
        summary = load(directory/'summary.json')
        if (digest({k:v for k,v in p.items() if k != 'sha256'}) != p['sha256']
                or meta['seed'] != seed or meta['epochs_completed'] != 3
                or any(v['protocol_sha256'] != p['sha256'] for v in (meta, cutoff, audited, exit_receipt, summary))
                or audited['status'] != 'PASS' or audited['private_weights_verified'] is not True
                or exit_receipt['returncode'] != 0 or exit_receipt['study_complete'] is not True
                or meta['final_inspected'] is not False or cutoff['final_inspected'] is not False
                or summary['final_evaluated'] is not False or sha(weights) != meta['weights_sha256']):
            raise ValueError('All completed audited candidates and validation-only cutoffs must be locked')
        names = ('protocol.json', 'training_meta.json', 'thresholds.json', 'audit.json', 'summary.json', 'process-exit.json')
        files.update({str((directory/name).relative_to(ROOT)):sha(directory/name) for name in names})
        files[str(weights.relative_to(ROOT))] = meta['weights_sha256']
        locked[str(seed)] = dict(protocol_sha256=p['sha256'], weights_path=str(weights.relative_to(ROOT)),
                                 weights_sha256=meta['weights_sha256'], trainability=meta['trainability'],
                                 thresholds=cutoff['thresholds'])
    return locked, files


def prepare():
    if OUT.exists():
        raise ValueError('Original evaluation destination required; no implicit restart')
    candidates, files = locked_candidates()
    data_audit = audit(FINAL, recount_tokenizer=False)
    if data_audit['status'] != 'PASS' or load(FINAL/'audit-corrected-v1.json')['status'] != 'PASS':
        raise ValueError('Independently audited final population required')
    design = load(BASE/'design-v2/protocol.json')
    if design['sha256'] != digest({k:v for k,v in design.items() if k != 'sha256'}) or design['candidate_seeds'] != list(SEEDS):
        raise ValueError('Frozen confirmation design required')
    names = ['protocol.json', 'coverage.json', 'final.jsonl.gz', 'final-views.jsonl.gz', 'audit-corrected-v1.json']
    files.update({str((FINAL/name).relative_to(ROOT)):sha(FINAL/name) for name in names})
    upstream = BASE.parent/'semantic-next/upstream/artifacts.json'
    files.update({str(upstream.relative_to(ROOT)):sha(upstream),
                  str((BASE/'design-v2/protocol.json').relative_to(ROOT)):sha(BASE/'design-v2/protocol.json')})
    p = dict(schema='varied-relation-fresh-confirmation-evaluation/0.1', frozen_at_utc=now(),
             sources={name:sha(ROOT/name) for name in SOURCES}, files=files,
             design_sha256=design['sha256'], data_protocol_sha256=data_audit['protocol_sha256'],
             seeds=list(SEEDS), candidates=candidates, model=load(upstream),
             versions={n:importlib.metadata.version(n) for n in ('torch','transformers','tokenizers','numpy','safetensors')},
             device='cpu', dtype='float32', threads=8, batch_size=16, window=512,
             criteria=design['criteria'], score_axes=dict(relevance='logit1-logit0', unsupported='independent logit2'),
             reduction='Identical-input dedup; shared UNKNOWN in primary/control; all15 slices perseed required',
             expected_rows=163712, expected_unique_inputs=120220,
             final_action='Fixed101,202,303 then one scalar control; one pass per unique input each; no final fitting',
             scope=design['scope'], API_calls=0, P2_admission=False, quality_approved=False, default_changed=False)
    p['sha256'] = digest(p)
    OUT.mkdir()
    for name, expected in p['sources'].items():
        target = OUT/'sources'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write((ROOT/name).read_bytes())
        if sha(target) != expected:
            raise ValueError('Source changed during evaluation freeze')
    save(OUT/'protocol.json', p)
    save(OUT/'input-audit-before-scoring.json', data_audit)
    return dict(protocol_sha256=p['sha256'], candidates_locked=list(candidates), model_forwards=0)


def checked():
    p = checked_protocol(OUT)
    if any(sha(ROOT/name) != expected for name,expected in p['files'].items()):
        raise ValueError('Locked candidate/data bytes changed')
    if p['versions'] != {n:importlib.metadata.version(n) for n in p['versions']}:
        raise ValueError('Frozen runtime versions changed')
    return p


def unique_population(rows, views):
    unique = {}
    for row,saved in zip(rows,views,strict=True):
        if row['id'] != saved['id']:
            raise ValueError('Aligned frozen rows required')
        if saved['view']['status'] != 'PROJECTED':
            continue
        key = row['projected_input_hash']
        if digest([saved['view']['objective'],saved['view']['text']]) != key:
            raise ValueError('Projection hash changed')
        if key in unique:
            previous, old_view = unique[key]
            if (previous['label'] != row['label'] or old_view['view'] != saved['view']
                    or old_view['projected_tokens'] != saved['projected_tokens']):
                raise ValueError('Conflicting identical projected input')
        else:
            unique[key] = row,saved
    keys = sorted(unique)
    return [unique[k][0] for k in keys], [unique[k][1] for k in keys]


def attach_scores(rows, views, logits, scalar=False):
    scores = []
    for row,saved in zip(rows,views,strict=True):
        score = dict(id=row['id'], input_hash=row['projected_input_hash'], status='UNKNOWN',
                     score=None, support_score=None, actual_tokens=saved['projected_tokens'], truncated=False, error=None)
        if saved['view']['status'] == 'PROJECTED':
            value = logits[row['projected_input_hash']]
            score.update(status='SCORED', score=value[0] if scalar else value[1]-value[0],
                         support_score=None if scalar else value[2])
        scores.append(score)
    return scores


def slices(rows, scores, cutoff, scalar=False):
    result = {}
    for cohort in ('overall','primary','seen_control'):
        for field,language in ((None,None),('goal_language','en'),('goal_language','pt'),
                               ('report_language','en'),('report_language','pt')):
            paired = [(r,s) for r,s in zip(rows,scores,strict=True)
                      if (cohort == 'overall' or r['label'] is None or r['family'].startswith(cohort+':'))
                      and (field is None or r[field] == language)]
            rs, ss = [r for r,s in paired], [s for r,s in paired]
            name = cohort if field is None else f'{cohort}/{field}/{language}'
            value = metrics(rs, ss, cutoff, shadow=scalar)
            value['dispositions'] = {}
            for group,predicate in [('positive',lambda r:r['label'] == 1), ('negative',lambda r:r['label'] == 0),
                                    ('semantic_unknown',lambda r:r['label'] is None and r['unknown_kind'] != 'unbound_record'),
                                    ('structural_unknown',lambda r:r['unknown_kind'] == 'unbound_record')]:
                counts = Counter(decision(s,cutoff,shadow=scalar) for r,s in paired if predicate(r))
                value['dispositions'][group] = {d:counts[d] for d in ('KEEP','DROP','UNKNOWN')}
            result[name] = value
    return result


def run():
    p = checked()
    save(OUT/'started.json', dict(protocol_sha256=p['sha256'], utc=now(), pid=os.getpid()))
    began = time.perf_counter()
    error, complete = None, False
    original_connect = socket.socket.connect
    def denied(*args, **kwargs):
        raise RuntimeError('Network disabled during local final scoring')
    socket.socket.connect = denied
    try:
        torch.set_num_threads(p['threads'])
        rows, views = read_population(FINAL,'final')
        unique_rows, unique_views = unique_population(rows,views)
        if len(rows) != p['expected_rows'] or len(unique_rows) != p['expected_unique_inputs']:
            raise ValueError('Frozen population cardinality changed')
        receipts = {}
        for key in [str(seed) for seed in SEEDS]+['scalar']:
            scalar = key == 'scalar'
            directory = OUT/key
            directory.mkdir()
            save(directory/'started.json',dict(protocol_sha256=p['sha256'], utc=now()))
            print('START',key,now(),flush=True)
            scorer = PairReranker.from_snapshot(snapshot_path(p['model']),p['model'],max_pair_tokens=p['window'],batch_size=p['batch_size'])
            cutoff = dict(support=None,relevance=None) if scalar else p['candidates'][key]['thresholds']
            if not scalar:
                locked = p['candidates'][key]
                if configure_adaptation(scorer.model,int(key),last_n=2) != locked['trainability']:
                    raise ValueError('Candidate adaptation drift')
                load_trained_weights(scorer.model,load_file(str(ROOT/locked['weights_path'])))
            raw_path = directory/'unique-scores.json'
            raw = score_population(scorer,unique_rows,unique_views,p,raw_path,scalar=scalar)
            logits = {s['input_hash']:([s['score']] if scalar else s['logits']) for s in raw['rows']}
            scores = attach_scores(rows,views,logits,scalar=scalar)
            result = slices(rows,scores,cutoff,scalar=scalar)
            receipt = dict(protocol_sha256=p['sha256'], candidate=key, thresholds=cutoff, metrics=result,
                           passes_point_criteria=False if scalar else all(passes(v) for v in result.values()),
                           raw_scores_sha256=sha(raw_path), accounting=raw['accounting'],
                           elapsed_scoring_s=raw['elapsed_s'], finished_at_utc=now(),
                           correlated_rows=len(rows), fixture_denominator=64, additional_model_forwards=0,
                           quality_approved=False, default_changed=False, P2_admission=False)
            save(directory/'metrics.json',receipt)
            receipts[key] = receipt
            print('COMPLETE',key,'gate',receipt['passes_point_criteria'],flush=True)
            del scorer, raw, scores, logits
        summary = dict(protocol_sha256=p['sha256'], seed_passes=[receipts[str(s)]['passes_point_criteria'] for s in SEEDS],
                       all_seeds_pass=all(receipts[str(s)]['passes_point_criteria'] for s in SEEDS),
                       model_forwards=sum(r['accounting']['forward_completed_pairs'] for r in receipts.values()),
                       nonpadding_tokens=sum(r['accounting']['forward_completed_tokens'] for r in receipts.values()),
                       elapsed_total_s=time.perf_counter()-began, peak_process_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                       finished_at_utc=now(), API_calls=0, quality_approved=False, default_changed=False, P2_admission=False,
                       scope=p['scope'])
        save(OUT/'summary.json',summary)
        complete = True
        return summary
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        socket.socket.connect = original_connect
        save(OUT/'process-exit.json',dict(protocol_sha256=p['sha256'], study_complete=complete,
                                       returncode=0 if complete else 1, error=error, utc=now()))


def launch():
    p = checked()
    save(OUT/'launch-marker.json',dict(protocol_sha256=p['sha256'],utc=now()))
    env = dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    with (OUT/'run.log').open('xb') as stdout, (OUT/'run-errors.log').open('xb') as stderr:
        child = subprocess.Popen([sys.executable,'-m','research.varied_relation_confirmation_scoring','run'],
            cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True,close_fds=True,shell=False)
    receipt = dict(protocol_sha256=p['sha256'],**process_identity(child.pid),utc=now())
    save(OUT/'launch.json',receipt)
    return receipt


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','launch','run'))
    args = parser.parse_args()
    print(json.dumps({'prepare':prepare,'launch':launch,'run':run}[args.action](),indent=2,allow_nan=False))
