"""Audit controls, no downloads, training, API calls or changes to research inputs.

Standard-library snapshot checks; --controls also uses the existing ML environment.
The deliberately malformed summary inputs and line tensors are counterexamples,
not measurements of trained models. Never execute the AST bypass string.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def auc(pos, neg):
    wins = sum(p > n for p in pos for n in neg)
    pairs = len(pos) * len(neg)
    return dict(wins=wins, pairs=pairs, auc=wins / pairs if pairs else None)


def snapshot():
    raw_path = ROOT / 'bakeoff/results/results.json'
    data = json.loads(raw_path.read_text())
    cells = defaultdict(list)
    for row in data['rows']:
        cells[row['model'], row['depth_tokens']].append(row)
    invalid = []
    measured = {}
    for (model, depth), rows in sorted(cells.items()):
        ids = {k: {r['case_id'] for r in rows if r['kind'] == k}
               for k in ['fact', 'noise_decoy', 'noise_unrelated']}
        scores = {k: [r['score'] for r in rows if r['kind'] == k and r['score'] is not None]
                  for k in ids}
        duplicate_count = sum(n - 1 for n in Counter((r['case_id'], r['kind']) for r in rows).values())
        versions = sorted({r.get('probe_version', 'unknown') for r in rows})
        devices = sorted({r.get('device', 'unknown') for r in rows})
        if duplicate_count or any(ids[k] != ids['fact'] for k in ids) or len(versions) > 1 or len(devices) > 1:
            invalid.append(dict(model=model, depth=depth, duplicates=duplicate_count,
                                sizes={k: len(v) for k, v in ids.items()}, versions=versions, devices=devices))
        measured.setdefault(model, {})[str(depth)] = dict(
            n_unique_cases=len(ids['fact']), J=auc(scores['fact'], scores['noise_decoy']),
            D=auc(scores['fact'], scores['noise_unrelated']), rows=len(rows),
            truncated=sum(bool(r['truncated']) for r in rows), errors=sum(bool(r['error']) for r in rows),
            versions=versions, devices=devices)
    historical = measured['specialist-exp04-unfreeze2-dyn-49k']['16384']
    assert historical['J']['wins'] == 2907 and historical['D']['wins'] == 1965
    assert historical['J']['pairs'] == historical['D']['pairs'] == 3844
    effective = {}
    for model in ['specialist-exp04-unfreeze2-dyn-49k', 'specialist-exp05-unfreeze2-8k']:
        effective[model] = {family: [int(d) for d, c in measured[model].items()
                                   if c[family]['auc'] is not None and c[family]['auc'] >= .90]
                            for family in ['J', 'D']}
        assert not any(effective[model].values())

    tree = ast.parse((ROOT / 'specialist/corpus.py').read_text())
    signatures = {ast.literal_eval(n.args[0]): set(ast.literal_eval(n.args[2]))
                  for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == 'Domain'}
    holdouts = ['vector_drift', 'bot_traffic', 'pdf_render', 'sms_delivery']
    corpus = {}
    for version in ['exp02d', 'exp02e']:
        corpus[version] = {}
        for split in ['train', 'val']:
            rows = [json.loads(s) for s in (ROOT / 'data' / version / (split + '.jsonl')).read_text().splitlines()]
            counts = {name: sum(any(signatures[name] <= set(re.findall(r'\b([A-Za-z_][A-Za-z_0-9]*)=', line))
                                    for line in r['text'].splitlines()) for r in rows) for name in holdouts}
            corpus[version][split] = dict(n=len(rows), domains=dict(Counter(r['domain'] for r in rows)),
                                          holdout_signature_examples=counts)
    assert all(sum(c['holdout_signature_examples'].values()) == 0 for c in corpus['exp02e'].values())
    epochs = {}
    for folder in ['exp02e-line-attn', 'exp02e-unfreeze2']:
        meta = json.loads((ROOT / 'models' / folder / 'training_meta.json').read_text())
        epochs[folder] = dict(current_epoch=meta['current_epoch'], history_epochs=[r['epoch'] for r in meta['history']])
        assert epochs[folder] == dict(current_epoch=3, history_epochs=[1, 2, 3])

    required = ['.git', 'README.md', 'LICENSE', 'CONTRIBUTING.md', 'CODE_OF_CONDUCT.md', 'CITATION.cff',
                'SECURITY.md', 'pyproject.toml', 'requirements.txt', '.gitignore', '.github/workflows']
    files = [p for p in ROOT.rglob('*') if p.is_file() and OUT not in p.parents]
    inventory = dict(scope='excludes this audit directory; includes existing caches and archived experiments',
                     n_files=len(files), bytes=sum(p.stat().st_size for p in files),
                     absent_root=[p for p in required if not (ROOT / p).exists()],
                     files_over_100mib=[dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size)
                                        for p in files if p.stat().st_size > 100 * 1024**2])
    return dict(raw_sha256=sha(raw_path), n_raw_rows=len(data['rows']), invalid_current_cells=invalid,
                measured=measured, passing_depths=effective, corpus=corpus, clean_epochs=epochs, inventory=inventory)


def controls():
    import torch
    from torch import nn
    from specialist.model import SpecialistHead
    from bakeoff.probes import CASES
    from bakeoff.runner import summarize
    from replay.tasks import TASKS
    from replay.real_fixtures import make_packet

    model = SpecialistHead.__new__(SpecialistHead)
    nn.Module.__init__(model)
    model.pooling = 'line-attn'
    model.line_score = nn.Linear(1, 1, bias=False)
    nn.init.zeros_(model.line_score.weight)
    model.head = nn.Identity()
    hidden = torch.tensor([[[2.0], [4.0]]])
    normal = float(model._forward_lines(hidden, torch.tensor([[0, 1]]))[0].detach())
    gap = float(model._forward_lines(hidden, torch.tensor([[0, 2]]))[0].detach())
    assert normal == 3.0 and gap == 2.0

    def row(case, kind, score, run='a', version='1.2'):
        return dict(model='audit_toy', case_id=case, depth_tokens=512, kind=kind, score=score,
                    error=None, latency_ms=0, truncated=False, run_id=run, probe_version=version, device='cpu')

    def summary(rows):
        return summarize(dict(rows=rows, depths=[512], model_meta={'audit_toy': {}}))[0]

    duplicated = [row('one', k, (0.9 if k == 'fact' else 0.1), 'a', '1.1')
                  for k in ['fact', 'noise_decoy', 'noise_unrelated']]
    duplicated += [row('one', k, (0.1 if k == 'fact' else 0.9), 'b', '1.2')
                   for k in ['fact', 'noise_decoy', 'noise_unrelated']]
    duplicate_summary = summary(duplicated)
    disjoint_summary = summary([row('a', 'fact', 1), row('b', 'noise_decoy', 0), row('b', 'noise_unrelated', 0)])
    assert duplicate_summary['by_depth']['512']['n'] == 2
    assert duplicate_summary['by_depth']['512']['auc_judge'] == .25
    assert disjoint_summary['effective_context_judge'] == 512
    alpha = lambda s: set(re.findall(r'[a-z]+', s.lower()))
    lexical = [c.case_id for c in CASES if alpha(c.fact_body) != alpha(c.decoy_body)]

    # STATIC ONLY: mirror current checks, never compile or exec this string.
    candidate = "__builtins__['open']('/tmp/audit_static_only','w').write('example')"
    nodes = list(ast.walk(ast.parse(candidate)))
    blocked_calls = {'open', 'eval', 'exec', 'compile', '__import__', 'input'}
    ast_reject = any((isinstance(n, (ast.Import, ast.ImportFrom))) or
                     (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in blocked_calls) or
                     (isinstance(n, ast.Attribute) and n.attr.startswith('__')) for n in nodes)
    assert not ast_reject
    generic = [{'context': [b.to_dict() for b in t.blocks]} for t in TASKS]
    actual = [make_packet(t, t.blocks, 42) for t in TASKS]
    def reveals(packets):
        return any('decisive' in b['block_id'] for p in packets for b in p['context'])
    assert reveals(generic) and not reveals(actual)
    return dict(line_attn_uniform_toy=dict(contiguous=normal, gap=gap),
                duplicate_summary=duplicate_summary, disjoint_summary=disjoint_summary,
                alphabetic_body_word_set_differences=dict(n=len(lexical), total=len(CASES), cases=lexical),
                static_ast_bypass_accepted=True, static_candidate_executed=False,
                generic_payload_reveals_decisive_id=reveals(generic),
                real_pilot_payload_reveals_decisive_id=reveals(actual))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--controls', action='store_true')
    args = ap.parse_args()
    result = snapshot()
    if args.controls:
        result['controls'] = controls()
    target = OUT / ('checks-with-controls.json' if args.controls else 'checks.json')
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(dict(output=str(target), raw_rows=result['n_raw_rows'],
                          invalid_current_cells=len(result['invalid_current_cells']),
                          historical_16k=result['measured']['specialist-exp04-unfreeze2-dyn-49k']['16384'],
                          controls_included=args.controls), indent=2))
