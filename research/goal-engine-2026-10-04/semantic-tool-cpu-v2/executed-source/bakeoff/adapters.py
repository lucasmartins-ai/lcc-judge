"""Model adapters for the Sprint 2 encoder bake-off.

Each adapter scores (objective, block) -> relevance/keep signal in [0, 1].
Contract: higher = more worth keeping. Everything else (errors, truncation
flags, latency) is recorded so the runner can build honest curves.

Judges use the exact LCC ``noul`` question (compactor.keep_question) so the
bake-off measures the same decision LCC production asks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .probes import count_tokens

try:  # fidelity to production phrasing
    from lcc.relevance.compactor import keep_question  # type: ignore
except Exception:  # pragma: no cover - fallback keeps the exact text
    def keep_question(block_id: str) -> dict:
        return {
            "type": "noul",
            "instructions": (
                "Judge the probability that block {block_id} (in the state) is relevant and "
                "worth keeping in the context that will be shown to a larger model. The "
                "objective is also in the state. Irrelevant noise, redundant logs, and "
                "unrelated chatter should score low; when unsure, prefer keeping."
            ).format(block_id=block_id),
            "criteria": {
                "true": "The block is relevant or plausibly useful for the objective.",
                "false": "The block is unrelated noise for the objective.",
            },
        }


@dataclass
class Score:
    value: float | None
    latency_ms: float
    error: str | None = None
    truncated: bool = False
    actual_tokens: int | None = None


@dataclass
class BaseAdapter:
    name: str
    declared_window: int
    params_m: float
    load_s: float = 0.0
    rss_before: float = 0.0
    rss_after: float = 0.0

    def load(self) -> None:  # override
        self.rss_before = _rss_gb()
        t0 = time.perf_counter()
        self._load()
        self.load_s = time.perf_counter() - t0
        self.rss_after = _rss_gb()

    def _load(self) -> None:  # override
        pass

    def score(self, objective: str, text: str) -> Score:  # override
        raise NotImplementedError

    def close(self) -> None:
        pass


def _rss_gb() -> float:
    import resource

    import sys
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / 1e9 if sys.platform == 'darwin' else rss * 1024 / 1e9


class LexicalAdapter(BaseAdapter):
    """Unbounded-token overlap baseline (BL0): depth-insensitive reference."""

    def __init__(self) -> None:
        super().__init__(name="lexical-overlap", declared_window=10**9, params_m=0.0)

    def score(self, objective: str, text: str) -> Score:
        t0 = time.perf_counter()
        actual_tokens = count_tokens(text) + count_tokens(objective)
        obj = _content_words(objective)
        blk = _content_words(text)
        inter = len(obj & blk)
        value = min(1.0, inter / max(1, len(obj)))
        return Score(value=value, latency_ms=(time.perf_counter() - t0) * 1000,
                     truncated=False, actual_tokens=actual_tokens)


def _content_words(text: str) -> set[str]:
    import re

    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3}


class LayaJudgeAdapter(BaseAdapter):
    """Laya System-1 decision models via the laya runtime (batch 1, raw)."""

    def __init__(self, name: str, model_path: str, device: str = "cpu", declared_window: int = 1024) -> None:
        super().__init__(name=name, declared_window=declared_window, params_m=0.0)
        self.model_path = model_path
        self.device = device

    def _load(self) -> None:
        import laya

        self._agent = laya.load(self.model_path, device=self.device)

    def score(self, objective: str, text: str) -> Score:
        t0 = time.perf_counter()
        actual_tokens = count_tokens(text) + count_tokens(objective)
        truncated = actual_tokens > self.declared_window
        state = {"objective": objective, "blocks": [{"id": "blk", "text": text}]}
        questions = {"keep_blk": keep_question("blk")}
        try:
            res = self._agent.predict(state, questions)
            noul = float(res["answers"]["keep_blk"]["noul"])
            return Score(value=noul, latency_ms=(time.perf_counter() - t0) * 1000,
                         truncated=truncated, actual_tokens=actual_tokens)
        except Exception as exc:  # recorded, never fatal to the run
            return Score(
                value=None,
                latency_ms=(time.perf_counter() - t0) * 1000,
                error=f"{type(exc).__name__}: {exc}"[:200],
                truncated=truncated,
                actual_tokens=actual_tokens,
            )

    def close(self) -> None:
        self._agent = None


class PinnedLayaAdapter(LayaJudgeAdapter):
    """Offline snapshot with full runtime sequence accounting for new comparisons."""
    def __init__(self,name,snapshot,device='cpu'):
        super().__init__(name,snapshot,device=device)
        self.revision=__import__('pathlib').Path(snapshot).name

    def _load(self):
        import shutil
        import tempfile
        from pathlib import Path
        # Laya repairs tokenizer config files in place. Keep Hub files immutable.
        source=Path(self.model_path)
        if not source.is_dir(): raise FileNotFoundError('Explicit local Laya snapshot missing')
        self._temporary=tempfile.TemporaryDirectory(prefix='lcc-laya-')
        copied=Path(self._temporary.name)
        for name in ['encoder','model.safetensors']:
            (copied/name).symlink_to((source/name).resolve())
        shutil.copyfile(source/'rl_agent_config.json',copied/'rl_agent_config.json')
        shutil.copytree(source/'tokenizer',copied/'tokenizer')
        import laya
        self._agent=laya.load(str(copied),device=self.device)
        self.declared_window=self._agent.cfg['max_len']

    def score(self,objective,text):
        from laya.common import build_sequence
        state={'objective':objective,'blocks':[{'id':'blk','text':text}]}
        q=self._agent._to_internal(keep_question('blk'))
        full,_=build_sequence(self._agent.tok,state,q,max_len=10**9,
                              head_max_len=self._agent.cfg.get('head_max_len',192))
        result=super().score(objective,text)
        result.actual_tokens=len(full)
        result.truncated=len(full)>self.declared_window
        return result

    def close(self):
        super().close()
        if hasattr(self,'_temporary'): self._temporary.cleanup()


class HFSequenceAdapter(BaseAdapter):
    """Cross-encoder relevance scorer (single logit -> sigmoid)."""

    def __init__(self, name: str, model_id: str, declared_window: int, params_m: float, device: str = "cpu") -> None:
        super().__init__(name=name, declared_window=declared_window, params_m=params_m)
        self.model_id = model_id
        self.device = device

    def _load(self) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self._tok = AutoTokenizer.from_pretrained(self.model_id)
        self._model = AutoModelForSequenceClassification.from_pretrained(self.model_id).to(self.device).eval()

    def score(self, objective: str, text: str) -> Score:
        t0 = time.perf_counter()
        actual_tokens = len(self._tok(objective, text, truncation=False)["input_ids"])
        truncated = actual_tokens > self.declared_window
        try:
            enc = self._tok(
                objective, text, truncation=True, max_length=self.declared_window, return_tensors="pt"
            ).to(self.device)
            with self._torch.no_grad():
                logits = self._model(**enc).logits
            value = float(self._torch.sigmoid(logits).reshape(-1)[0])
            return Score(value=value, latency_ms=(time.perf_counter() - t0) * 1000,
                         truncated=truncated, actual_tokens=actual_tokens)
        except Exception as exc:
            return Score(value=None, latency_ms=(time.perf_counter() - t0) * 1000,
                         error=f"{type(exc).__name__}: {exc}"[:200],
                         truncated=truncated, actual_tokens=actual_tokens)


class BiEncoderAdapter(BaseAdapter):
    """Mean-pooled bi-encoder cosine similarity, rescaled to [0, 1]."""

    def __init__(self, name: str, model_id: str, declared_window: int, params_m: float,
                 device: str = "cpu", prefix: str = "") -> None:
        super().__init__(name=name, declared_window=declared_window, params_m=params_m)
        self.model_id = model_id
        self.device = device
        self.prefix = prefix
        self._obj_cache: dict[str, object] = {}

    def _load(self) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self._torch = torch
        self._tok = AutoTokenizer.from_pretrained(self.model_id)
        self._model = AutoModel.from_pretrained(self.model_id).to(self.device).eval()

    def _embed(self, text: str):
        enc = self._tok(
            self.prefix + text, truncation=True, max_length=self.declared_window, return_tensors="pt"
        ).to(self.device)
        with self._torch.no_grad():
            hidden = self._model(**enc).last_hidden_state
        mask = enc["attention_mask"].unsqueeze(-1).float()
        pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-6)
        return pooled.reshape(-1)

    def score(self, objective: str, text: str) -> Score:
        t0 = time.perf_counter()
        text_tokens = len(self._tok(self.prefix + text, truncation=False)["input_ids"])
        obj_tokens = len(self._tok(self.prefix + objective, truncation=False)["input_ids"])
        actual_tokens = text_tokens + obj_tokens
        truncated = (text_tokens > self.declared_window) or (obj_tokens > self.declared_window)
        try:
            e1 = self._obj_cache.get(objective)
            if e1 is None:
                e1 = self._embed(objective)
                self._obj_cache[objective] = e1
            e2 = self._embed(text)
            cos = float((e1 @ e2) / (e1.norm() * e2.norm()).clamp(min=1e-6))
            return Score(value=(cos + 1.0) / 2.0, latency_ms=(time.perf_counter() - t0) * 1000,
                         truncated=truncated, actual_tokens=actual_tokens)
        except Exception as exc:
            return Score(value=None, latency_ms=(time.perf_counter() - t0) * 1000,
                         error=f"{type(exc).__name__}: {exc}"[:200],
                         truncated=truncated, actual_tokens=actual_tokens)

    def close(self) -> None:
        self._model = None
        self._obj_cache.clear()


class OfficialEmbeddingAdapter(BiEncoderAdapter):
    """Pinned author recipes; distinct names preserve historical mean-pooling runs.

    Model cards: huggingface.co/BAAI/bge-small-en-v1.5 and
    huggingface.co/Alibaba-NLP/gte-multilingual-base. The latter's separate
    implementation revision was reviewed before enabling trust_remote_code.
    Artifact setup is explicit; loading here is offline.
    """
    def __init__(self, name, model_id, declared_window, params_m, revision,
                 device='cpu', query_prefix='', code_revision=None):
        super().__init__(name,model_id,declared_window,params_m,device=device)
        self.revision=revision
        self.code_revision=code_revision
        self.query_prefix=query_prefix

    @classmethod
    def bge(cls, device='cpu'):
        return cls('bge-small-en-v1.5-official','BAAI/bge-small-en-v1.5',512,33.4,
                   '5c38ec7c405ec4b44b94cc5a9bb96e735b38267a',device=device,
                   query_prefix='Represent this sentence for searching relevant passages: ')

    @classmethod
    def gte(cls, device='cpu'):
        return cls('gte-multilingual-base-official','Alibaba-NLP/gte-multilingual-base',8192,306.,
                   '9bbca17d9273fd0d03d5725c7a4b0f6b45142062',device=device,
                   code_revision='40ced75c3017eb27626c9d4ea981bde21a2662f4')

    def prepare_text(self,text,query=False):
        return (self.query_prefix if query else '')+text

    def pool(self,hidden):
        import torch.nn.functional as F
        return F.normalize(hidden[:,0],p=2,dim=1).reshape(-1)

    @staticmethod
    def restore_gte_buffers(model):
        """Transformers 5 meta loading loses nonpersistent author-derived buffers.

        Reuse the pinned implementation's constructor formulas, without touching
        learned weights. Always restore: finite zero-filled buffers also fail.
        """
        import torch
        embeddings=model.embeddings
        embeddings.register_buffer('position_ids',torch.arange(model.config.max_position_embeddings),
                                   persistent=False)
        embeddings._init_rope(model.config)

    def _load(self):
        import torch
        from transformers import AutoModel, AutoTokenizer
        self._torch=torch
        tokenizer_options=dict(revision=self.revision,local_files_only=True)
        if self.code_revision:
            tokenizer_options.update(trust_remote_code=True,code_revision=self.code_revision)
        self._tok=AutoTokenizer.from_pretrained(self.model_id,**tokenizer_options)
        options=dict(revision=self.revision,local_files_only=True)
        if self.code_revision:
            options.update(trust_remote_code=True,code_revision=self.code_revision,
                           unpad_inputs=False,use_memory_efficient_attention=False,
                           attn_implementation='eager')
        self._model,info=AutoModel.from_pretrained(self.model_id,output_loading_info=True,**options)
        allowed={'classifier.bias','classifier.weight'} if self.code_revision else set()
        if info.get('missing_keys') or set(info.get('unexpected_keys',[]))-allowed:
            raise ValueError('Official baseline weights do not match the pinned architecture')
        if self.code_revision: self.restore_gte_buffers(self._model)
        self._model=self._model.to(self.device).eval()

    def _embed_prepared(self,text):
        enc=self._tok(text,truncation=True,max_length=self.declared_window,return_tensors='pt').to(self.device)
        with self._torch.inference_mode():
            return self.pool(self._model(**enc).last_hidden_state)

    def score(self,objective,text):
        t0=time.perf_counter()
        query=self.prepare_text(objective,query=True)
        passage=self.prepare_text(text,query=False)
        try:
            lengths=[len(self._tok(s,truncation=False)['input_ids']) for s in [query,passage]]
            e1=self._obj_cache.get(query)
            if e1 is None:
                e1=self._embed_prepared(query)
                if len(self._obj_cache)>=256: self._obj_cache.clear()
                self._obj_cache[query]=e1
            e2=self._embed_prepared(passage)
            return Score(value=(float(e1@e2)+1)/2,latency_ms=(time.perf_counter()-t0)*1000,
                         actual_tokens=sum(lengths),truncated=max(lengths)>self.declared_window)
        except Exception as exc:
            return Score(value=None,latency_ms=(time.perf_counter()-t0)*1000,
                         error=f'{type(exc).__name__}: {exc}'[:200])


class TrainedJudgeAdapter(BaseAdapter):
    """EXP-02 trained decision head on ModernBERT (specialist/ package)."""

    def __init__(self, name: str, model_dir: str, max_len: int, device: str = "cpu",
                 rope_type: str | None = None, rope_factor: float = 1.0,
                 max_positions: int | None = None) -> None:
        super().__init__(name=name, declared_window=max_len, params_m=149.2)
        self.model_dir = model_dir
        self.max_len = max_len
        self.device = device
        # EXP-03 position-extension overrides (eval-only; weights stay the trained
        # checkpoint — single variable changes at the position layer)
        self.rope_type = rope_type
        self.rope_factor = rope_factor
        self.max_positions = max_positions

    def _load(self) -> None:
        import json
        import os

        import torch

        import specialist.model as sm

        self._torch = torch
        with open(os.path.join(self.model_dir, "config.json")) as stream:
            cfg = json.load(stream)
        model = sm.SpecialistHead(model_id=cfg["model_id"], freeze_encoder=True,
                                   unfreeze_last_n=cfg.get('unfreeze_last_n', 0),
                                   revision=cfg.get('revision'),
                                   pooling=cfg.get("pooling", "mean"),
                                   rope_type=self.rope_type or cfg.get("rope_type"),
                                   rope_factor=self.rope_factor or cfg.get("rope_factor", 1.0),
                                   max_positions=self.max_positions or cfg.get("max_positions"))
        from specialist.checkpoint import load_trained_weights
        sd = torch.load(os.path.join(self.model_dir, "weights.pt"), map_location="cpu", weights_only=True)
        load_trained_weights(model, sd)
        model.temperature = cfg.get("temperature", 1.0)
        self._model = model.to(self.device).eval()
        self._trained_max_len = cfg.get("max_len", 512)

    def score(self, objective: str, text: str) -> Score:
        t0 = time.perf_counter()
        actual_tokens = len(self._model.tokenizer(objective, text, truncation=False)["input_ids"])
        eff_limit = min(self.max_len, self.declared_window)
        truncated = actual_tokens > eff_limit
        try:
            value = self._model.prob(objective, text, max_len=self.max_len, device=self.device)
            return Score(value=value, latency_ms=(time.perf_counter() - t0) * 1000,
                         truncated=truncated, actual_tokens=actual_tokens)
        except Exception as exc:
            return Score(value=None, latency_ms=(time.perf_counter() - t0) * 1000,
                         error=f"{type(exc).__name__}: {exc}"[:200],
                         truncated=truncated, actual_tokens=actual_tokens)


def default_roster(device: str = "cpu") -> list[BaseAdapter]:
    import os

    home = os.path.expanduser("~")
    ws = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return [
        LexicalAdapter(),
        LayaJudgeAdapter("laya-multilingual", "convaiinnovations/laya-multilingual", device=device),
        LayaJudgeAdapter("laya-typed-decisions", "convaiinnovations/laya-typed-decisions", device=device),
        LayaJudgeAdapter("laya-lcc-relevance-v1", os.path.join(home, "Models/laya-lcc-relevance-v1"), device=device),
        HFSequenceAdapter("minilm-msmarco-ce", "cross-encoder/ms-marco-MiniLM-L-6-v2", 512, 22.7, device=device),
        OfficialEmbeddingAdapter.bge(device),
        BiEncoderAdapter("ModernBERT-base", "answerdotai/ModernBERT-base", 8192, 149.0, device=device),
        OfficialEmbeddingAdapter.gte(device),
        TrainedJudgeAdapter("specialist-exp02-512", os.path.join(ws, "models", "exp02-specialist-head"),
                            max_len=512, device=device),
        TrainedJudgeAdapter("specialist-exp02-8k", os.path.join(ws, "models", "exp02-specialist-head"),
                            max_len=8192, device=device),
        # EXP-02c line-level aggregation head (pooling=line-attn, corpus v0.2)
        TrainedJudgeAdapter("specialist-exp02c-512", os.path.join(ws, "models", "exp02c-line-attn"),
                            max_len=512, device=device),
        TrainedJudgeAdapter("specialist-exp02c-1k", os.path.join(ws, "models", "exp02c-line-attn"),
                            max_len=1024, device=device),
        # window extrapolation test: same head, no truncation up to 8K
        TrainedJudgeAdapter("specialist-exp02c-8k", os.path.join(ws, "models", "exp02c-line-attn"),
                            max_len=8192, device=device),
        # EXP-03 baseline: 12K window (positions >8192 are unseen territory for the
        # un-extended backbone — measures truncation vs position failure at depth 8192)
        TrainedJudgeAdapter("specialist-exp02c-12k", os.path.join(ws, "models", "exp02c-line-attn"),
                            max_len=12288, device=device),
        # EXP-03 position extension (same trained checkpoint — one variable at a time):
        # pure extrapolation vs dynamic-NTK stretch (8192 trained range -> ~49K)
        TrainedJudgeAdapter("specialist-exp03-extrap-49k", os.path.join(ws, "models", "exp02c-line-attn"),
                            max_len=49152, device=device),
        TrainedJudgeAdapter("specialist-exp03-dynamic-49k", os.path.join(ws, "models", "exp02c-line-attn"),
                            max_len=49152, device=device, rope_type="dynamic", rope_factor=6.0),
        # EXP-04 domain-diversity arms (corpus v0.3: +10 training archetypes,
        # 4 domains held out entirely — EXP-2026-10-03-02). Same dynamic-NTK
        # position recipe as the EXP-03 row so only the training data/model differ.
        TrainedJudgeAdapter("specialist-exp04-frozen-dyn-49k", os.path.join(ws, "models", "exp02d-line-attn"),
                            max_len=49152, device=device, rope_type="dynamic", rope_factor=6.0),
        TrainedJudgeAdapter("specialist-exp04-unfreeze2-dyn-49k", os.path.join(ws, "models", "exp02d-unfreeze2"),
                            max_len=49152, device=device, rope_type="dynamic", rope_factor=6.0),
        # EXP-05 clean baseline arms (corpus v0.4: zero holdout leakage, stratified eval,
        # <=8K working envelope with native RoPE, and optional dynamic-NTK for long checks)
        TrainedJudgeAdapter("specialist-exp05-frozen-8k", os.path.join(ws, "models", "exp02e-line-attn"),
                            max_len=8192, device=device),
        TrainedJudgeAdapter("specialist-exp05-unfreeze2-8k", os.path.join(ws, "models", "exp02e-unfreeze2"),
                            max_len=8192, device=device),
        TrainedJudgeAdapter("specialist-exp05-frozen-dyn-49k", os.path.join(ws, "models", "exp02e-line-attn"),
                            max_len=49152, device=device, rope_type="dynamic", rope_factor=6.0),
        TrainedJudgeAdapter("specialist-exp05-unfreeze2-dyn-49k", os.path.join(ws, "models", "exp02e-unfreeze2"),
                            max_len=49152, device=device, rope_type="dynamic", rope_factor=6.0),
    ]
