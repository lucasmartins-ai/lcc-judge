"""Independent disk checks; standard library, no runner imports, no source mutations."""
import ast
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_auc(pos, neg):
    pairs = len(pos)*len(neg)
    wins = sum(p > n for p in pos for n in neg)
    ties = sum(p == n for p in pos for n in neg)
    return dict(wins=wins, pairs=pairs, ties=ties, auc=wins/pairs if pairs else None)


def conventional_auc(pos, neg):
    result = strict_auc(pos, neg)
    return (result['wins'] + result['ties']/2)/result['pairs']


def run(verify_weights=False):
    archive = json.loads((OUT/'history-manifest.json').read_text())
    for name, expected in archive['sources'].items():
        assert digest(OUT/'executed-source'/name) == expected, f'Archived source changed: {name}'
    for name, expected in archive['metadata'].items():
        assert digest(OUT/name) == expected, f'Archived metadata changed: {name}'
    if verify_weights:
        for name, expected in archive['weights'].items():
            assert digest(ROOT/name) == expected, f'Checkpoint weights changed: {name}'
    tree = ast.parse((OUT/'executed-source/specialist/corpus.py').read_text())
    domains = {ast.literal_eval(node.args[0]): set(ast.literal_eval(node.args[2]))
               for node in ast.walk(tree) if isinstance(node, ast.Call)
               and isinstance(node.func, ast.Name) and node.func.id == 'Domain'}
    holdouts = ['vector_drift', 'bot_traffic', 'pdf_render', 'sms_delivery']
    manifest = json.loads((ROOT/'data/exp02e/manifest.json').read_text())
    corpus, hashes = {}, {}
    for split in ['train', 'val', 'ood']:
        path = ROOT/f'data/exp02e/{split}.jsonl'
        items = [json.loads(line) for line in path.read_text().splitlines()]
        hashes[split] = {r['content_hash'] for r in items}
        signatures = {name: sum(any(domains[name] <= set(re.findall(r'\b([A-Za-z_][A-Za-z_0-9]*)=', line))
                                   for line in r['text'].splitlines()) for r in items) for name in holdouts}
        bad_hashes = sum(hashlib.sha256((r['objective']+'\n'+r['text']).encode()).hexdigest()[:16]
                         != r['content_hash'] for r in items)
        computed_digest = hashlib.sha256(''.join(sorted(r['content_hash'] for r in items)).encode()).hexdigest()[:16]
        corpus[split] = dict(n=len(items), domains=dict(Counter(r['domain'] for r in items)),
                             holdout_signatures=signatures, bad_hashes=bad_hashes,
                             digest=computed_digest, sha256=digest(path))
        assert len(items) == manifest['splits'][split]['n']
        assert computed_digest == manifest['splits'][split]['digest']
        assert bad_hashes == 0
        if split != 'ood':
            assert len(corpus[split]['domains']) == 18
            assert not (set(corpus[split]['domains']) & set(holdouts))
            assert sum(signatures.values()) == 0
    intersections = {a+'/'+b: len(hashes[a]&hashes[b]) for a,b in [('train','val'),('train','ood'),('val','ood')]}
    assert not any(intersections.values())
    source = ROOT/'bakeoff/results/results.json'
    data = json.loads(source.read_text())
    old = json.loads((OUT/'inherited/bakeoff/results/results.json').read_text())
    assert old['rows'] == data['rows'], 'Original scores must be preserved'
    duplicates = sum(n-1 for n in Counter((r['model'],r['depth_tokens'],r['case_id'],r['kind'])
                                          for r in data['rows']).values())
    assert duplicates == 0
    measured = {}
    for model in ['specialist-exp05-frozen-8k','specialist-exp05-unfreeze2-8k', 'specialist-exp04-unfreeze2-dyn-49k']:
        measured[model] = {}
        summary = next(s for s in data['summary'] if s['model'] == model)
        for depth in [0,512,4096,8192,16384,32768]:
            rows = [r for r in data['rows'] if r['model']==model and r['depth_tokens']==depth]
            by_kind = {kind:[r['score'] for r in rows if r['kind']==kind and r['score'] is not None]
                       for kind in ['fact','noise_decoy','noise_unrelated']}
            j = strict_auc(by_kind['fact'],by_kind['noise_decoy'])
            d = strict_auc(by_kind['fact'],by_kind['noise_unrelated'])
            cell = dict(n_by_kind={k:len(v) for k,v in by_kind.items()}, J=j, D=d,
                        truncated=sum(r['truncated'] for r in rows), errors=sum(bool(r['error']) for r in rows),
                        actual_tokens_range=[min(r['actual_tokens'] for r in rows),max(r['actual_tokens'] for r in rows)]
                        if rows and all(r.get('actual_tokens') is not None for r in rows) else None,
                        versions=sorted({r.get('probe_version','missing') for r in rows}),
                        run_ids=sorted({r.get('run_id','missing') for r in rows}))
            measured[model][str(depth)] = cell
            if rows:
                assert round(j['auc'],3) == summary['by_depth'][str(depth)]['auc_judge']
                assert round(d['auc'],3) == summary['by_depth'][str(depth)]['auc_detect']
            if model.startswith('specialist-exp05') and depth in [0,512,4096,8192]:
                assert all(len(v)==62 for v in by_kind.values())
                assert cell['errors']==0
        assert summary['effective_context_judge']==summary['effective_context_detect']==0
    checkpoints = {}
    for name in ['exp02e-line-attn','exp02e-unfreeze2']:
        path = OUT/'checkpoint-metadata'/name
        cfg = json.loads((path/'config.json').read_text())
        meta = json.loads((path/'training_meta.json').read_text())
        assert meta['current_epoch']==3
        assert [r['epoch'] for r in meta['history']]==[1,2,3]
        assert cfg['data_manifest']==manifest
        checkpoints[name] = dict(weights_sha256=archive['weights'][f'models/{name}/weights.pt'], history=meta['history'],
                                 final=meta['final'], provenance='three epoch entries stored; original training not repeated')
    replay = json.loads((ROOT/'data/d6_pilot/summary.json').read_text())
    assert replay['dataset_type']=='SYNTHETIC' and replay['training_eligible_records']==0
    evaluation = json.loads((OUT/'saved-evaluation.json').read_text())
    for model, entry in evaluation['models'].items():
        assert entry['checkpoint_sha256'] == checkpoints[model]['weights_sha256']
        for split in ['ood','val']:
            measured_auc = entry['splits'][split]['metrics']['auc_full']
            predictions = entry['splits'][split]['predictions']
            reproduced = conventional_auc([r['logit'] for r in predictions if r['label']==1],
                                           [r['logit'] for r in predictions if r['label']==0])
            assert abs(reproduced-measured_auc) < 1e-12
            assert round(measured_auc,4) == checkpoints[model]['final'][f'auc_{split}_full']
            assert entry['splits'][split]['data_sha256'] == corpus[split]['sha256']
    normalization = json.loads((OUT/'normalization-results.json').read_text())
    assert normalization['protocol']['source_sha256'] == digest(source)
    assert normalization['protocol']['script_sha256'] == archive['sources']['research/normalization_pilot.py']
    runtime = json.loads((OUT/'score-order-check.json').read_text())
    assert runtime['absolute_delta'] <= 1e-6
    detector = json.loads((ROOT/'research/detect-supervision-results.scores.json').read_text())
    assert len(detector['records']) == 124
    assert all(value['actual_tokens'] <= 1024 for record in detector['records'] for value in record['inputs'].values())
    for path, expected in detector['protocol']['hashes'].items():
        if path in archive['weights']:
            assert archive['weights'][path] == expected
        elif path in archive['original_protocol_source_mapping']:
            assert digest(OUT/archive['original_protocol_source_mapping'][path]) == expected
        else:
            assert digest(ROOT/path) == expected
    cpu = json.loads((OUT/'bench-cpu-unfreeze2.json').read_text())
    assert cpu['protocol']['weights_sha256'] == checkpoints['exp02e-unfreeze2']['weights_sha256']
    assert cpu['protocol']['source_sha256'] == archive['sources']['research/bench_cpu.py']
    assert cpu['reference_dossier']['context_tokens'] == 66000
    assert cpu['reference_dossier']['truncated'] == 0
    assert cpu['m8_evaluation']['dossier_pass'] and not cpu['m8_evaluation']['overall_m8_compliant']
    return dict(corpus=corpus, split_intersections=intersections, raw_rows_preserved=True,
                raw_sha256=digest(source), duplicate_row_keys=duplicates, measured=measured,
                checkpoints=checkpoints, replay=replay,
                checkpoint_final_metrics_reproduced=True, experiment_hashes_verified=True,
                source_verification_mode='archived', actual_weights_verified=verify_weights,
                training_reexecuted=False, temporal_preregistration_certified=False,
                runtime_cache_delta=runtime['absolute_delta'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-weights', action='store_true', help='Additionally hash local checkpoint weights')
    parser.add_argument('--write-report', action='store_true', help='Explicitly replace verification.json')
    args = parser.parse_args()
    result=run(verify_weights=args.verify_weights)
    if args.write_report:
        (OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
