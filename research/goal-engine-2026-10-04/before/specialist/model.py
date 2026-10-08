"""EXP-02 decision model: ModernBERT backbone + typed keep/necessity head.

Outputs one logit per (objective, block) pair; sigmoid(logit) = P(evidence).
Mean pooling matches the bake-off bi-encoder adapters so curves are comparable.

EXP-02c line pooling (research/experiments.md EXP-2026-10-02-03): the measured
dilution cliff (<~10% decisive-token share) is a pooling failure, so the head can
aggregate at LINE granularity instead of over all tokens:
  - "line-max": score every token, max within each line, max over lines
    (multiple-instance MIL — gradient flows only through the best line);
  - "line-attn": mean-represent each line, learned attention over lines.
Line ids come from the fast tokenizer's offset mapping (blocks are newline
log lines in both corpus and probes), so both stay single forward passes.
"""

from __future__ import annotations

import bisect

import inspect

import torch
from torch import nn
from transformers import AutoModel, AutoTokenizer
from transformers.modeling_rope_utils import ROPE_INIT_FUNCTIONS


def make_rotary_deterministic(rotary: nn.Module) -> None:
    """Ensure dynamic RoPE frequencies depend strictly on the current input length.

    HuggingFace's default dynamic_rope_update caches frequencies up to the longest
    sequence seen and does not reset for shorter sequences above original_max_position_embeddings.
    This patch recalculates frequencies for the exact current seq_len whenever seq_len > original_max,
    and resets to original_inv_freq when seq_len <= original_max, guaranteeing input determinism.
    """
    raw_forward = inspect.unwrap(rotary.forward)

    def deterministic_forward(x, position_ids, layer_type=None):
        rope_type = (
            rotary.rope_type[layer_type]
            if (layer_type is not None and isinstance(rotary.rope_type, dict))
            else getattr(rotary, "rope_type", "default")
        )
        if isinstance(rope_type, str) and "dynamic" in rope_type:
            seq_len = int(torch.max(position_ids).item()) + 1
            prefix = f"{layer_type}_" if layer_type is not None else ""
            original_inv_freq = getattr(rotary, f"{prefix}original_inv_freq")
            cached_len = getattr(rotary, f"{prefix}cached_len", None)

            if cached_len != seq_len:
                if seq_len > rotary.original_max_seq_len:
                    rope_init_fn = ROPE_INIT_FUNCTIONS[rope_type]
                    inv_freq, attention_scaling = rope_init_fn(
                        rotary.config,
                        x.device,
                        seq_len=seq_len,
                        layer_type=layer_type,
                    )
                    rotary.register_buffer(f"{prefix}inv_freq", inv_freq, persistent=False)
                    setattr(rotary, f"{prefix}attention_scaling", attention_scaling)
                    setattr(rotary, f"{prefix}cached_len", seq_len)
                    setattr(rotary, f"{prefix}max_seq_len_cached", seq_len)
                else:
                    original_inv_freq = original_inv_freq.to(x.device)
                    rotary.register_buffer(f"{prefix}inv_freq", original_inv_freq, persistent=False)
                    setattr(rotary, f"{prefix}cached_len", rotary.original_max_seq_len)
                    setattr(rotary, f"{prefix}max_seq_len_cached", rotary.original_max_seq_len)
        return raw_forward(rotary, x, position_ids, layer_type=layer_type)

    rotary.forward = deterministic_forward


class SpecialistHead(nn.Module):
    def __init__(self, model_id: str = "answerdotai/ModernBERT-base", head_hidden: int = 256,
                 dropout: float = 0.1, freeze_encoder: bool = True, unfreeze_last_n: int = 0,
                 pooling: str = "mean", rope_type: str | None = None, rope_factor: float = 1.0,
                 max_positions: int | None = None):
        super().__init__()
        # pooling: "mean" (blind mean pool — measured dilution cliff below ~10%
        # decisive-token share, see research/experiments.md EXP-02b chain),
        # "attn" (learned token-gated pooling, the minimal fix), or
        # "line-max" / "line-attn" (EXP-02c line-level aggregation).
        assert pooling in ("mean", "attn", "line-max", "line-attn")
        self.pooling = pooling
        self.use_lines = pooling.startswith("line-")
        self.model_id = model_id
        self.rope_type = rope_type
        self.rope_factor = rope_factor
        self.max_positions = max_positions
        config = None
        if rope_type or max_positions:
            # EXP-03 position extension (research/experiments.md EXP-2026-10-02-05):
            # ModernBERT keeps RoPE per layer type (sliding_attention / full_attention)
            # — extension is config-level, no new weights. "dynamic" (NTK) keeps the
            # trained range untouched and stretches wavelengths beyond it; "linear"
            # compresses all positions by factor. max_positions caps the position
            # grid (only meaningful for non-dynamic types).
            from transformers import AutoConfig

            config = AutoConfig.from_pretrained(model_id)
            if max_positions:
                config.max_position_embeddings = max_positions
            if rope_type:
                for layer_type in ("sliding_attention", "full_attention"):
                    params = dict(config.rope_parameters.get(layer_type) or {})
                    params["rope_type"] = rope_type
                    params["factor"] = rope_factor
                    config.rope_parameters[layer_type] = params
        self.encoder = AutoModel.from_pretrained(model_id, config=config) if config is not None \
            else AutoModel.from_pretrained(model_id)
        rotary = getattr(self.encoder, "rotary_emb", None)
        if rotary is None:
            rotary = getattr(getattr(self.encoder, "encoder", None), "rotary_emb", None)
        if rotary is not None:
            make_rotary_deterministic(rotary)
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        hidden = self.encoder.config.hidden_size

        if freeze_encoder:
            for p in self.encoder.parameters():
                p.requires_grad = False
            if unfreeze_last_n > 0:
                # transformers 5.x ModernBertModel exposes .layers; older layouts
                # use .encoder.layer
                layers = getattr(self.encoder, "layers", None)
                if layers is None:
                    layers = self.encoder.encoder.layer
                for layer in list(layers)[-unfreeze_last_n:]:
                    for p in layer.parameters():
                        p.requires_grad = True

        self.attn_score = nn.Linear(hidden, 1) if pooling == "attn" else None
        # EXP-02c: per-token scorer (line-max) or per-line attention scorer
        # (line-attn). line_max_only distinguishes the two uses below.
        self.line_score = (
            nn.Sequential(
                nn.Linear(hidden, head_hidden),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(head_hidden, 1),
            )
            if self.use_lines else None
        )
        self.head = nn.Sequential(
            nn.Linear(hidden, head_hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(head_hidden, 1),
        )
        self.temperature = 1.0

    def encode(self, objectives: list[str], texts: list[str], max_len: int = 1024) -> dict:
        kwargs = dict(truncation=True, max_length=max_len, padding=True, return_tensors="pt")
        if not self.use_lines:
            return self.tokenizer(objectives, texts, **kwargs)
        enc = self.tokenizer(objectives, texts, return_offsets_mapping=True, **kwargs)
        enc["line_ids"] = self._line_ids(enc, texts)
        return enc

    @staticmethod
    def _line_ids(enc: dict, texts: list[str]) -> torch.Tensor:
        """Token -> line index within the *text* segment; -1 elsewhere/pad."""
        offsets = enc["offset_mapping"]
        B, T, _ = offsets.shape
        line_ids = torch.full((B, T), -1, dtype=torch.long)
        for i, text in enumerate(texts):
            # newline char positions -> line index = #newlines before token start
            nl = []
            p = text.find("\n")
            while p != -1:
                nl.append(p)
                p = text.find("\n", p + 1)
            seq = enc.sequence_ids(i)
            for t in range(T):
                if seq[t] != 1:
                    continue
                line_ids[i, t] = bisect.bisect_left(nl, int(offsets[i, t, 0]))
        return line_ids

    def forward(self, enc: dict) -> torch.Tensor:
        line_ids = enc.get("line_ids")
        core = {k: v for k, v in enc.items() if k != "line_ids"} if line_ids is not None else enc
        hidden = self.encoder(**core).last_hidden_state
        if self.use_lines:
            assert line_ids is not None, "line pooling needs line_ids from encode()"
            return self._forward_lines(hidden, line_ids.to(hidden.device))
        mask = enc["attention_mask"].unsqueeze(-1).float()
        if self.pooling == "attn" and self.attn_score is not None:
            scores = self.attn_score(hidden).squeeze(-1)          # [B, T]
            scores = scores.masked_fill(~enc["attention_mask"].bool(), -1e4)
            weights = scores.softmax(-1).unsqueeze(-1)            # [B, T, 1]
            pooled = (hidden * weights).sum(1)
        else:
            pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-6)
        return self.head(pooled).squeeze(-1)

    def _forward_lines(self, hidden: torch.Tensor, line_ids: torch.Tensor) -> torch.Tensor:
        """Segment-max / segment-mean aggregation over contiguous line ids."""
        B, T = line_ids.shape
        valid = line_ids >= 0
        if not bool(valid.any()):
            return hidden.new_zeros(B)
        # per-example line count (ids are contiguous 0..L_i-1 by construction)
        n_lines = (valid.long() * (line_ids + 1)).max(1).values.clamp(min=1)  # [B]
        L = int(n_lines.max())
        flat = line_ids.clamp(min=0) + torch.arange(B, device=hidden.device).unsqueeze(1) * L
        flat_v = flat[valid]  # [N]

        if self.pooling == "line-max":
            tok_scores = self.line_score(hidden).squeeze(-1)  # [B, T]
            buf = hidden.new_full((B * L,), -1e4)
            buf.scatter_reduce_(0, flat_v, tok_scores[valid], reduce="amax")
            seg = buf.view(B, L)
            pad = torch.arange(L, device=hidden.device).unsqueeze(0) >= n_lines.unsqueeze(1)
            return seg.masked_fill(pad, -1e4).max(1).values

        # line-attn: line rep = masked mean of token hiddens, attention over lines
        sums = hidden.new_zeros((B * L, hidden.shape[-1]))
        sums.scatter_add_(0, flat_v.unsqueeze(-1).expand(-1, hidden.shape[-1]), hidden[valid])
        counts = hidden.new_zeros((B * L,))
        counts.scatter_add_(0, flat_v, torch.ones_like(flat_v, dtype=hidden.dtype))
        rep = sums / counts.clamp(min=1.0).unsqueeze(-1)
        rep = rep.view(B, L, -1)
        att = self.line_score(rep).squeeze(-1)  # [B, L]
        pad = torch.arange(L, device=hidden.device).unsqueeze(0) >= n_lines.unsqueeze(1)
        att = att.masked_fill(pad, -1e4)
        w = att.softmax(-1).unsqueeze(-1)
        ctx = (rep * w).sum(1)
        return self.head(ctx).squeeze(-1)

    @torch.no_grad()
    def prob(self, objective: str, text: str, max_len: int = 1024, device: str = "cpu") -> float:
        self.eval()
        enc = self.encode([objective], [text], max_len=max_len)
        enc = {k: v.to(device) for k, v in enc.items()}
        logit = float(self(enc)[0])
        import math

        return 1.0 / (1.0 + math.exp(-logit / max(self.temperature, 1e-6)))
