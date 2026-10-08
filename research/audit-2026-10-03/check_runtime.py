"""Offline checks of actual tokenizer lengths and dynamic RoPE cache behavior."""
import os
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
from pathlib import Path
import sys
import json
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import torch
from transformers import AutoConfig, AutoTokenizer
from transformers.models.modernbert.modeling_modernbert import ModernBertRotaryEmbedding
from bakeoff.probes import CASES, make_block

cfg = AutoConfig.from_pretrained('answerdotai/ModernBERT-base')
for layer in cfg.rope_parameters:
    cfg.rope_parameters[layer]['rope_type'] = 'dynamic'
    cfg.rope_parameters[layer]['factor'] = 6.
a, b = ModernBertRotaryEmbedding(cfg), ModernBertRotaryEmbedding(cfg)
x = torch.zeros(1, 1, 64)
a(x, torch.arange(20000)[None, :], layer_type='full_attention')
a(x, torch.arange(12000)[None, :], layer_type='full_attention')
b(x, torch.arange(12000)[None, :], layer_type='full_attention')
cache = dict(original_max_positions=cfg.max_position_embeddings,
             after_long_then_short=int(a.full_attention_max_seq_len_cached),
             fresh_short=int(b.full_attention_max_seq_len_cached),
             equal_frequencies=torch.equal(a.full_attention_inv_freq, b.full_attention_inv_freq),
             maximum_frequency_difference=float((a.full_attention_inv_freq - b.full_attention_inv_freq).abs().max()))
print('cache:', json.dumps(cache), flush=True)

tokenizer = AutoTokenizer.from_pretrained('answerdotai/ModernBERT-base')
source = json.loads((ROOT / 'bakeoff/results/results.json').read_text())
case_map = {c.case_id: c for c in CASES}
selected = [r for r in source['rows'] if r['model'] in
            ('specialist-exp04-unfreeze2-dyn-49k', 'specialist-exp03-dynamic-49k',
             'specialist-exp02c-512')]
lengths = []
reconstructed = {}
for r in selected:
    key = (r['case_id'], r['depth_tokens'], r['kind'])
    if key not in reconstructed:
        block = make_block(case_map[r['case_id']], r['depth_tokens'], r['kind'])
        actual = len(tokenizer(case_map[r['case_id']].objective, block['text'], truncation=False)['input_ids'])
        reconstructed[key] = (block, actual)
    block, actual = reconstructed[key]
    lengths.append(dict(model=r['model'], case_id=r['case_id'], depth=r['depth_tokens'], kind=r['kind'],
                        recorded_reference_tokens=r['block_tokens'],
                        reconstructed_reference_tokens=block['total_tokens'],
                        reference_length_matches=r['block_tokens'] == block['total_tokens'],
                        actual_pair_tokens=actual, recorded_truncated=r['truncated'],
                        actual_truncated=actual > source['model_meta'][r['model']]['declared_window']))
summary = {}
groups = defaultdict(list)
for r in lengths:
    groups[r['model'], r['depth']].append(r)
for (model, depth), records in groups.items():
    summary[f'{model}@{depth}'] = dict(n_rows=len(records),
        min_pair_tokens=min(r['actual_pair_tokens'] for r in records),
        max_pair_tokens=max(r['actual_pair_tokens'] for r in records),
        reference_mismatches=sum(not r['reference_length_matches'] for r in records),
        actual_truncated=sum(r['actual_truncated'] for r in records),
        recorded_truncated=sum(r['recorded_truncated'] for r in records),
        false_untruncated=sum(r['actual_truncated'] and not r['recorded_truncated'] for r in records))
    print(model, depth, json.dumps(summary[f'{model}@{depth}']), flush=True)
(OUT / 'runtime-checks.json').write_text(json.dumps(dict(cache=cache, token_lengths=summary, rows=lengths), indent=2) + '\n')
