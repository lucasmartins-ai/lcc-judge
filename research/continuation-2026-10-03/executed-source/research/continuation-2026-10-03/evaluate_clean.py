"""Read-only offline evaluation of the saved clean EXP-05 checkpoints.

Run with the existing LCC Python environment. Saves individual logits and identity
hashes; never trains or rewrites a checkpoint, dataset, or benchmark result.
"""
import os
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
from pathlib import Path
import sys
import hashlib
import json
import time
import statistics
import bisect
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import torch
import transformers
from specialist.model import SpecialistHead


def auc(positive, negative):
    negative = sorted(negative)
    n = len(positive) * len(negative)
    wins = sum(bisect.bisect_left(negative, p) for p in positive)
    ties = sum(bisect.bisect_right(negative, p) - bisect.bisect_left(negative, p) for p in positive)
    return (wins + ties / 2) / n if n else None


device = 'mps' if torch.backends.mps.is_available() else 'cpu'
output = dict(device=device, source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), torch=torch.__version__, transformers=transformers.__version__, models={})
for name in ('exp02e-line-attn', 'exp02e-unfreeze2'):
    path = ROOT / 'models' / name
    config = json.loads((path / 'config.json').read_text())
    model = SpecialistHead(model_id=config['model_id'], pooling=config['pooling'])
    state = torch.load(path / 'weights.pt', map_location='cpu', weights_only=True)
    missing, unexpected = model.load_state_dict(state, strict=False)
    assert not unexpected, unexpected
    assert not any(n.startswith(('head.', 'line_score.')) for n in missing), missing
    model.to(device).eval()
    model_out = dict(checkpoint_sha256=hashlib.sha256((path / 'weights.pt').read_bytes()).hexdigest(),
                     config=config, missing_key_count=len(missing), splits={})
    for split in ('ood', 'val'):
        data_path = ROOT / f'data/exp02e/{split}.jsonl'
        records = [json.loads(line) for line in data_path.read_text().splitlines()]
        predictions = []
        started = time.perf_counter()
        with torch.no_grad():
            for start in range(0, len(records), 8):
                batch = records[start:start + 8]
                enc = model.encode([r['objective'] for r in batch], [r['text'] for r in batch],
                                   max_len=config['max_len'])
                enc = {k: v.to(device) for k, v in enc.items()}
                logits = model(enc).float().cpu().tolist()
                predictions.extend(dict(id=r['id'], domain=r['domain'], kind=r['kind'],
                                        label=r['label'], logit=logit)
                                   for r, logit in zip(batch, logits))
        positives = [r['logit'] for r in predictions if r['label'] == 1]
        negatives = [r['logit'] for r in predictions if r['label'] == 0]
        decoys = [r['logit'] for r in predictions if r['kind'] == 'neg_decoy']
        per_domain = {}
        for domain in sorted({r['domain'] for r in predictions}):
            pp = [r['logit'] for r in predictions if r['domain'] == domain and r['kind'] == 'pos']
            dd = [r['logit'] for r in predictions if r['domain'] == domain and r['kind'] == 'neg_decoy']
            per_domain[domain] = dict(n_pos=len(pp), n_decoy=len(dd), judge_auc=auc(pp, dd),
                                      mean_fact=statistics.mean(pp), mean_decoy=statistics.mean(dd))
        metrics = dict(n=len(predictions), auc_full=auc(positives, negatives),
                       judge_pooled=auc(positives, decoys), per_domain=per_domain,
                       mean_within_domain_judge=statistics.mean(v['judge_auc'] for v in per_domain.values()),
                       seconds=round(time.perf_counter() - started, 1))
        model_out['splits'][split] = dict(data_sha256=hashlib.sha256(data_path.read_bytes()).hexdigest(),
                                         metrics=metrics, predictions=predictions)
        print(name, split, json.dumps(metrics), flush=True)
    output['models'][name] = model_out
    (OUT / 'saved-evaluation.json').write_text(json.dumps(output, indent=2) + '\n')
    del model
    if device == 'mps':
        torch.mps.empty_cache()
print('saved:', OUT / 'saved-evaluation.json', flush=True)
