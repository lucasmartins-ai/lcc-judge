"""Native-window late-evidence diagnostic, explicitly exploratory known probes."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research/goal-engine-2026-10-04/hf-frontier'
KINDS = ['fact', 'noise_decoy', 'noise_unrelated']


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fit_prefix(tokenizer, objective, middles, filler, budget):
    """One identical whole-line prefix for all three candidates; no evidence cut."""
    low, high = 0, len(filler)
    while low < high:
        mid = (low+high+1)//2
        prefix = '\n'.join(filler[:mid])+'\n' if mid else ''
        length = max(len(tokenizer(objective, prefix+m, truncation=False)['input_ids']) for m in middles)
        if length <= budget: low = mid
        else: high = mid-1
    prefix = '\n'.join(filler[:low])+'\n' if low else ''
    assert all(len(tokenizer(objective, prefix+m, truncation=False)['input_ids']) <= budget for m in middles)
    return prefix


def prepare():
    from transformers import AutoTokenizer
    from bakeoff.probes import CASES, make_block, _filler_line
    from specialist.model import MODERNBERT_REVISION
    tok = AutoTokenizer.from_pretrained('answerdotai/ModernBERT-base', revision=MODERNBERT_REVISION, local_files_only=True)
    grid = []
    for case in CASES:
        middles = [make_block(case, 0, kind, seed=442381)['text'] for kind in KINDS]
        rng = random.Random('hf-frontier:'+case.case_id+':442381')
        filler = [_filler_line(rng) for _ in range(2400)]
        for budget in [512, 2048, 4096, 8192]:
            prefix = fit_prefix(tok, case.objective, middles, filler, budget)
            for kind, middle in zip(KINDS, middles):
                text = prefix+middle
                grid.append(dict(case_id=case.case_id, objective=case.objective, kind=kind,
                    pair_budget_hf=budget, actual_pair_tokens=len(tok(case.objective, text, truncation=False)['input_ids']),
                    prefix_tokens_hf=len(tok(prefix, add_special_tokens=False)['input_ids']), text=text,
                    input_sha256=hashlib.sha256(json.dumps([case.objective,text], ensure_ascii=False).encode()).hexdigest()))
    files = ['research/hf_frontier.py', 'specialist/model.py', 'specialist/checkpoint.py', 'bakeoff/probes.py', 'lcc_engine/engine.py']
    protocol = dict(schema='hf-frontier/0.1', pair_budgets_hf=[512,2048,4096,8192],
        seed=442381, n_cases=62, probe_version='1.2', device='mps',
        metric='strict pooled P(fact > noise), ties zero', gate=.90,
        prefix='same complete filler lines for each objective/candidate triplet; late whole evidence; no tail',
        scope='Known authored suite; placement variant only; not unseen semantics or LCC outcome proof',
        checkpoint_sha256=sha(ROOT/'models/exp02e-unfreeze2/weights.pt'),
        config_sha256=sha(ROOT/'models/exp02e-unfreeze2/config.json'), backbone_revision=MODERNBERT_REVISION,
        sources={n:sha(ROOT/n) for n in files}, grid_sha256=hashlib.sha256(json.dumps(grid,sort_keys=True).encode()).hexdigest())
    protocol['sha256'] = hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest()
    OUT.mkdir(parents=True,exist_ok=True)
    for name, value in [('protocol.json', protocol), ('grid.json', grid)]:
        path = OUT/name; encoded=json.dumps(value,indent=2)+'\n'
        if path.exists(): assert path.read_text() == encoded, 'Frozen frontier changed'
        else: path.write_text(encoded)
    for name in files:
        target=OUT/'executed-source'/name;target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():target.write_bytes((ROOT/name).read_bytes())
        assert sha(target)==protocol['sources'][name]
    return protocol, grid


def score():
    from lcc_engine.engine import SpecialistBackend
    import torch
    torch.set_num_threads(8)
    protocol, grid = prepare()
    path = OUT/'scores.jsonl'
    existing = [json.loads(s) for s in path.read_text().splitlines()] if path.exists() else []
    assert len(existing) <= len(grid)
    for row, item in zip(existing, grid):
        assert row['input_sha256']==item['input_sha256'] and row['protocol_sha256']==protocol['sha256']
    # Only completed saved calls are reused; deterministic untouched remaining inputs.
    backend = SpecialistBackend(ROOT/'models/exp02e-unfreeze2',device='mps')
    with path.open('a') as stream:
        for index, item in enumerate(grid[len(existing):],start=len(existing)):
            value = backend.score(item['objective'],item['text'])
            assert value['actual_tokens']==item['actual_pair_tokens'] and not value['truncated'] and value['forwarded']
            row={k:v for k,v in item.items() if k not in ['text','objective']}
            row.update(value,protocol_sha256=protocol['sha256'])
            stream.write(json.dumps(row)+'\n');stream.flush()
            if (index+1)%24==0:print(f'{index+1}/{len(grid)} saved',flush=True)
    print('All native-window frontier calls saved',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    prepare() if args.prepare_only else score()
