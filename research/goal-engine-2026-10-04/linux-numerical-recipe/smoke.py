import hashlib
import importlib.metadata
import json
import platform
import socket
import sys

import torch
import lcc_engine
from lcc_engine import ContextEngine
from lcc_engine.observations import ObservationEngine, ObservationRequest

torch.set_num_threads(4)
def denied(*args, **kwargs): raise RuntimeError('Network access is forbidden in this smoke')
socket.socket.connect = denied
engine = ContextEngine('/opt/checkpoint')
result = engine.rank_context('Find the invoice failure', [
    {'id': 'invoice', 'text': 'billing-api errors=22 invoice_dispatch=failed root=pool_exhaustion'},
    {'id': 'other', 'text': 'search-api indexing=healthy errors=0 queue_depth=3'},
])
assert engine.is_local and result['mode'] == 'shadow'
assert all(r['status'] == 'SCORED' and r['decision'] == 'KEEP' and not r['truncated'] for r in result['items'])
assert result['model']['backbone_revision'] == '8949b909ec900327062f0ebf497f51aef5e6f0c8'
over_window = engine.rank_context('Find the invoice failure', [{'id':'long','text':'status=healthy '*10000}])
assert over_window['items'][0]['status'] == 'UNKNOWN' and over_window['items'][0]['forwarded'] is False
assert over_window['encoded_tokens'] == 0 and over_window['counted_input_tokens'] > 8192
request = ObservationRequest(entity='billing-api', field='http_5xx_count',
    start='2027-01-01T12:00:00Z', end='2027-01-01T12:05:00Z')
observation = ObservationEngine().rank_observations(request, [
    {'id':'healthy','text':'time=2027-01-01T12:02:00Z level=INFO entity=billing-api field=http_5xx_count value=0 unit=count'},
    {'id':'other','text':'time=2027-01-01T12:02:00Z level=ERROR entity=search-api field=http_5xx_count value=99 unit=count'},
])
assert [item['decision'] for item in observation['items']] == ['KEEP','DROP']

from pathlib import Path
import specialist.checkpoint
from specialist.checkpoint import load_trained_weights
from specialist.numerical import finite_update, NonFiniteTrainingError
for name, expected in json.loads(Path('/opt/source-manifest.json').read_text()).items():
    module=__import__(name.replace('/', '.').removesuffix('.py'),fromlist=['unused'])
    assert hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()==expected
probe=torch.nn.Linear(2,1);before=probe.weight.detach().clone();bad=probe.state_dict()
bad['weight']=torch.full_like(bad['weight'],float('nan'))
try:load_trained_weights(probe,bad)
except ValueError:pass
else:raise AssertionError('Corrupt checkpoint accepted')
assert torch.equal(before,probe.weight)
optimizer=torch.optim.AdamW(probe.parameters())
try:finite_update(probe(torch.ones(1,2)).sum()*float('nan'),probe,optimizer)
except NonFiniteTrainingError:pass
else:raise AssertionError('Nonfinite update accepted')
assert not optimizer.state and torch.equal(before,probe.weight)

print(json.dumps(dict(numerical_guards_checked=True, platform=platform.platform(), python=sys.version, package=lcc_engine.__file__,
    versions={n: importlib.metadata.version(n) for n in ['lcc-context-engine', 'torch', 'transformers', 'numpy']},
    socket_connect_blocked=True, result=result, over_window=over_window, typed_observation=observation), indent=2))
