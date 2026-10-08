from __future__ import annotations

import hashlib
import math
from pathlib import Path
import threading
import time


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


class SpecialistBackend:
    """Offline ModernBERT pair scorer. Inputs beyond the window are never forwarded."""

    is_local = True

    def __init__(self, checkpoint, *, device='cpu', max_len=8192):
        if not 1 <= max_len <= 8192:
            raise ValueError('Native backend window must be within 1..8192 HF pair tokens')
        self.directory = Path(checkpoint)
        self.device = device
        self.window_tokens = max_len
        self.identity = dict(model='specialist-unloaded',checkpoint_sha256=None)
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        import json
        import torch
        from specialist.model import SpecialistHead
        from specialist.checkpoint import load_trained_weights

        config = json.loads((self.directory/'config.json').read_text())
        self._torch = torch
        config_sha = file_sha(self.directory/'config.json')
        weights_sha = file_sha(self.directory/'weights.pt')
        model = SpecialistHead(model_id=config['model_id'], revision=config.get('revision'),
                               local_files_only=True,pooling=config.get('pooling','mean'),
                               unfreeze_last_n=config.get('unfreeze_last_n',0))
        state = torch.load(self.directory/'weights.pt',map_location='cpu',weights_only=True)
        load_trained_weights(model,state)
        if weights_sha != file_sha(self.directory/'weights.pt') or config_sha != file_sha(self.directory/'config.json'):
            raise ValueError('Checkpoint changed while loading')
        self._model = model.to(self.device).eval()
        self.identity = dict(model=config['model_id'],backbone_revision=model.revision,
                             checkpoint_sha256=weights_sha,config_sha256=config_sha,
                             pooling=model.pooling,device=self.device,
                             revision_recorded_in_checkpoint=bool(config.get('revision')))

    def score(self,objective,text):
        with self._lock:
            start = time.perf_counter()
            if self._model is None:
                self._load()
            tokens = len(self._model.tokenizer(objective,text,truncation=False)['input_ids'])
            if tokens > self.window_tokens:
                return dict(logit=None,actual_tokens=tokens,truncated=False,forwarded=False,error='input_exceeds_window',
                            latency_ms=(time.perf_counter()-start)*1000)
            enc = self._model.encode([objective],[text],max_len=self.window_tokens)
            enc = {key:value.to(self.device) for key,value in enc.items()}
            with self._torch.no_grad():
                logit = float(self._model(enc)[0])
            return dict(logit=logit,actual_tokens=tokens,truncated=False,forwarded=True,error=None,
                        latency_ms=(time.perf_counter()-start)*1000)


class ContextEngine:
    """One operation: rank objective/block relevance. All decisions remain KEEP in shadow.

    Pair scores do not establish counterfactual necessity, set sufficiency, calibrated
    probabilities, or a safe drop threshold. Those require the LCC outcome gates.
    """

    name = 'specialist'

    def __init__(self,checkpoint=None,*,device='cpu',max_len=8192,backend=None):
        if backend is None and checkpoint is None:
            raise ValueError('Provide a local checkpoint')
        self._backend = backend or SpecialistBackend(checkpoint,device=device,max_len=max_len)

    @property
    def context_limit(self):
        """Capacity of each HF objective/block input, not useful dossier coverage."""
        return self._backend.window_tokens

    @property
    def is_local(self):
        return getattr(self._backend,'is_local',False) is True

    @property
    def model(self):
        return self._backend.identity['model']

    @property
    def last_resolved_model(self):
        identity = self._backend.identity
        return f"{identity['model']}@{identity.get('checkpoint_sha256') or 'unloaded'}"

    def supports_operation(self,operation):
        return operation == 'rank_context'

    def rank_context(self,objective,blocks):
        if not isinstance(objective,str) or not objective.strip():
            raise ValueError('Objective must be a nonempty string')
        if not isinstance(blocks,list):
            raise ValueError('Blocks must be a list')
        ids = []
        for block in blocks:
            if (not isinstance(block,dict) or not isinstance(block.get('id'),str)
                    or not block['id'] or not isinstance(block.get('text'),str)):
                raise ValueError('Each block needs a string id and text')
            ids.append(block['id'])
        if len(ids) != len(set(ids)):
            raise ValueError('Block IDs must be unique')
        start = time.perf_counter()
        items = []
        for block in blocks:
            try:
                result = self._backend.score(objective,block['text']) if block['text'].strip() else dict(error='empty_block')
            except Exception as exc:
                result = dict(error=f'{type(exc).__name__}: {exc}'[:200])
            value = result.get('logit')
            tokens = result.get('actual_tokens')
            if type(tokens) is not int or tokens < 0:
                tokens = None
            usable = (type(value) in (int,float) and math.isfinite(value)
                      and not result.get('error') and not result.get('truncated')
                      and type(tokens) is int and 0 < tokens <= self.context_limit)
            items.append(dict(id=block['id'],text_sha256=hashlib.sha256(block['text'].encode()).hexdigest(),
                              status='SCORED' if usable else 'UNKNOWN',logit=value if usable else None,
                              decision='KEEP',reason='shadow_policy' if usable else (result.get('error') or 'invalid_score'),
                              actual_tokens=tokens,latency_ms=result.get('latency_ms'),
                              truncated=bool(result.get('truncated',False)),
                              window_exceeded=tokens is not None and tokens>self.context_limit,
                              forwarded=result.get('forwarded')))
        ranked = sorted((item for item in items if item['status']=='SCORED'),
                        key=lambda item:-item['logit'])
        return dict(schema='lcc-context-ranking/0.1',operation='rank_context',mode='shadow',
                    model=dict(self._backend.identity),items=items,ranking=[item['id'] for item in ranked],
                    pair_window_tokens=self.context_limit,useful_context_tokens=None,
                    is_local=self.is_local,
                    encoded_tokens=sum(item['actual_tokens'] or 0 for item in items),
                    calibrated_probability=False,necessity_estimated=False,set_sufficiency_estimated=False,
                    latency_ms=(time.perf_counter()-start)*1000)
