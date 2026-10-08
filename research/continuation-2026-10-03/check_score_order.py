"""Confirm whether a reachable dynamic RoPE cache changes one input's score.

The cached long length is initialized through the rotary module itself, avoiding
an unnecessary expensive forward pass on a second long block.
"""
import os
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
from pathlib import Path
import sys
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import torch
from bakeoff.probes import CASES, make_block
from bakeoff.adapters import default_roster

adapter = next(a for a in default_roster('mps') if a.name == 'specialist-exp04-unfreeze2-dyn-49k')
adapter.load()
case = CASES[0]
block = make_block(case, 8192, 'fact')
model = adapter._model
short = adapter.score(case.objective, block['text'])
actual_length = len(model.tokenizer(case.objective, block['text'], truncation=False)['input_ids'])
rotary = model.encoder.rotary_emb
dummy = torch.zeros(1, 1, 64, device='mps')
positions = torch.arange(20000, device='mps')[None, :]
for layer in rotary.layer_types:
    rotary(dummy, positions, layer_type=layer)
after_long = adapter.score(case.objective, block['text'])
result = dict(model=adapter.name, case_id=case.case_id, depth=8192, kind='fact',
              actual_length=actual_length, cache_initialized_to=20000,
              first_score=short.value, score_after_long_cache=after_long.value,
              absolute_delta=abs(short.value - after_long.value),
              note='Long cache initialized through rotary module only, without a long encoder forward.')
(OUT / 'score-order-check.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
