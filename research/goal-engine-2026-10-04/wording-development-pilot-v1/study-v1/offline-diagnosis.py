"""Post-evaluation diagnosis only; saved logits, unchanged cutoffs, no inference."""
import json
from pathlib import Path

from research.audit_tool_relation_confirmation import load, sha
from research.audit_tool_role_support import audited_scores, close
from research.audit_varied_relation_dev import read_population
from research.detached_varied_study import now
from research.diagnose_varied_relation_confirmation import breakdown, strict_auc, summary

OUT = Path(__file__).resolve().parent
DATA = OUT.parent
p = load(OUT/'protocol.json')
cutoffs = load(OUT/'thresholds.json')['thresholds']
result = {}
files = ['protocol.json','thresholds.json','audit.json']
for split in ('train','validation'):
    rows, views = read_population(DATA,split)
    raw = audited_scores(OUT/f'{split}-logits.json',rows,views,p,False)
    scores = load(OUT/f'{split}-scores.json')['rows']
    measured = summary(rows,scores,cutoffs)
    metrics = load(OUT/f'{split}-metrics.json')['metrics']
    close({key:measured[key] for key in metrics},metrics)
    semantic = [s['logits'][2] for r,s in zip(rows,raw['rows'],strict=True)
                if r['label'] is None and r['unknown_kind'] != 'unbound_record']
    binary = [s['logits'][2] for r,s in zip(rows,raw['rows'],strict=True) if r['label'] is not None]
    result[split] = dict(support_pooled_auc=strict_auc(semantic,binary),dispositions=measured['dispositions'],
                         by_pair=breakdown(rows,scores,cutoffs,'family',binary_only=True),
                         by_intent_alias=breakdown(rows,scores,cutoffs,'intent_alias',binary_only=True))
    files += [f'{split}-{name}.json' for name in ('logits','scores','metrics')]
receipt = dict(status='PASS',protocol_sha256=p['sha256'],populations=result,
               input_files={name:sha(OUT/name) for name in files},source_sha256=sha(Path(__file__)),
               finished_at_utc=now(),model_forwards=0,API_calls=0,original_cutoffs_changed=False,
               quality_approved=False,scope='Exposed eight-field development pilot diagnosis; no causal or adoption claim')
print(json.dumps(receipt,indent=2,allow_nan=False))
