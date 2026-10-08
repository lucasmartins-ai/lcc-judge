import hashlib
import json
from pathlib import Path
import socket
import sys

import torch
import lcc_engine
from lcc_engine import ContextEngine
from lcc_engine.observations import ObservationEngine, ObservationRequest

ROOT = Path('/Users/Master/Downloads/LCC-judge')
torch.set_num_threads(4)
def denied(*args, **kwargs):
    raise RuntimeError('Network disabled for installed package smoke')
socket.socket.connect = denied
installed = Path(lcc_engine.__file__).with_name('engine.py')
assert installed.read_bytes() == (ROOT / 'lcc_engine/engine.py').read_bytes()
engine = ContextEngine(ROOT / 'models/exp02e-unfreeze2')
result = engine.rank_context('Find invoice failure', [dict(id='a', text='billing-api invoice_dispatch=failed errors=22'),
                                                       dict(id='b', text='search-api queue_depth=0 status=healthy')])
assert all(item['status'] == 'SCORED' and item['decision'] == 'KEEP' for item in result['items'])
long = engine.rank_context('Find invoice failure', [dict(id='long', text='status=healthy ' * 10000)])
assert long['items'][0]['status'] == 'UNKNOWN' and long['encoded_tokens'] == 0
assert long['counted_input_tokens'] > 8192
sys.path.insert(0, '/Users/Master/LCC/src')
from lcc.relevance.compactor import RelevanceCompactionRequest, compact_context
text = 'billing-api invoice_dispatch=failed errors=22\n\nsearch-api queue_depth=0 status=healthy\n'
compiled = compact_context(RelevanceCompactionRequest(text=text, question='Find invoice failure',
    provider='specialist', client=engine, enable_sufficiency=False, trim_head_chars=0, marker=False,
    min_block_chars=1, max_workers=1))
assert compiled.compacted_text == text
observation = ObservationEngine().rank_observations(ObservationRequest(entity='billing-api',field='http_5xx_count',
    start='2027-01-01T12:00:00Z',end='2027-01-01T12:05:00Z'), [
    dict(id='healthy',text='time=2027-01-01T12:02:00Z level=INFO entity=billing-api field=http_5xx_count value=0 unit=count'),
    dict(id='other',text='time=2027-01-01T12:02:00Z level=ERROR entity=search-api field=http_5xx_count value=99 unit=count')])
assert [item['decision'] for item in observation['items']] == ['KEEP','DROP']
print(json.dumps(dict(installed_package=str(installed), engine_sha256=hashlib.sha256(installed.read_bytes()).hexdigest(),
    consumer_sha256=hashlib.sha256(Path('/Users/Master/LCC/src/lcc/relevance/compactor.py').read_bytes()).hexdigest(),
    socket_connect_blocked=True, result=result, over_window=long, lcc_bytes_preserved=True, typed_observation=observation), indent=2))
