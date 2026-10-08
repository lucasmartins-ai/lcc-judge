"""Check ranking-margin preservation on an immutable local pretrained artifact.

The examples are exposed implementation checks, with no relevance labels or
quality decision. This performs two passes, before and after initialization, and
does not train, fit cutoffs, score a reserved cohort, or save a candidate model.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import time

import torch

from research.ranking_support_initialization import retain_ranking_prior
from research.reranker_control import PairReranker


EXAMPLES = (
    ("Which report directly states the total retry attempts?", "Retry attempts including the first call: 4."),
    ("Qual relato informa diretamente os bytes de conteúdo recebidos?", "Received UDP payload bytes: 120."),
    ("Explain why the Git operation failed.", "Worktree edits: 3."),
)


def _save_once(path, value):
    with path.open("x") as target:
        target.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _preserved_parameters_sha(model):
    output_prefix = "classifier.out_proj." if model.config.model_type == "xlm-roberta" else "classifier."
    digest = hashlib.sha256()
    for name, parameter in sorted(model.named_parameters()):
        if not name.startswith(output_prefix):
            digest.update(name.encode() + b"\0")
            digest.update(parameter.detach().contiguous().numpy().tobytes())
    return digest.hexdigest()


def run(snapshot, manifest_path, output):
    root = Path(__file__).resolve().parents[1]
    if output.exists():
        raise ValueError("Use a new receipt directory; no selective retry/overwrite")
    output.mkdir(parents=True)
    manifest = json.loads(manifest_path.read_text())
    sources = {name: _sha(root / name) for name in (
        "research/verify_ranking_initialization.py", "research/ranking_support_initialization.py",
        "research/reranker_control.py")}
    protocol = dict(schema="ranking-margin-initialization/0.1", sources=sources,
        model=manifest, examples=EXAMPLES, seed=101, device="cpu", dtype="float32", threads=8,
        started_at_utc=datetime.now(timezone.utc).isoformat(),
        scope="Exposed unlabeled implementation examples only; not a quality or outcome test",
        training=False, adoption=False, API_calls=0, threshold_tuning=False, P2_admission=False)
    _save_once(output / "protocol.json", protocol)
    for name in sources:
        saved = output / "executed-source" / name
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes((root / name).read_bytes())
    torch.set_num_threads(8)
    original_connect = socket.socket.connect
    def denied(*args, **kwargs):
        raise RuntimeError("Network forbidden during initialization check")
    socket.socket.connect = denied
    began = time.perf_counter()
    receipt = dict(status="UNKNOWN", error=None, original_scores=[], expanded_logits=[],
                   original_forwards=0, expanded_forwards=0, truncated=False)
    try:
        scorer = PairReranker.from_snapshot(snapshot, manifest, max_pair_tokens=512, batch_size=3)
        receipt["model_identity"] = scorer.identity
        receipt["setup_s"] = time.perf_counter() - began
        before_sha = _preserved_parameters_sha(scorer.model)
        scores = scorer.score([q for q, t in EXAMPLES], [t for q, t in EXAMPLES])
        receipt["original_scores"] = scores
        receipt["original_forwards"] = sum(score["forward_completed"] for score in scores)
        if any(score["status"] != "SCORED" for score in scores):
            raise ValueError("Original implementation check did not produce complete scores")
        receipt["initialization"] = retain_ranking_prior(scorer.model, 101)
        receipt["preserved_parameters_before_sha256"] = before_sha
        receipt["preserved_parameters_after_sha256"] = _preserved_parameters_sha(scorer.model)
        if receipt["preserved_parameters_after_sha256"] != before_sha:
            raise ValueError("Encoder or intermediate classifier parameters changed")
        encoded = scorer.tokenizer([q for q, t in EXAMPLES], [t for q, t in EXAMPLES],
                                   padding=True, truncation=False, return_tensors="pt")
        lengths = encoded["attention_mask"].sum(1).tolist()
        if lengths != [score["actual_tokens"] for score in scores] or max(lengths) > scorer.window:
            raise ValueError("Complete pair accounting changed or exceeded the window")
        with torch.inference_mode():
            expanded = scorer.model(**encoded).logits
        receipt["expanded_forwards"] = len(EXAMPLES)
        if expanded.shape != (len(EXAMPLES), 3) or not torch.isfinite(expanded).all():
            raise ValueError("Invalid expanded outputs")
        receipt["expanded_logits"] = expanded.tolist()
        error = max(abs(float(values[1] - values[0]) - score["score"])
                    for values, score in zip(expanded, scores))
        receipt["maximum_absolute_margin_error"] = error
        receipt["tolerance"] = 1e-6
        receipt["counted_pair_tokens_per_pass"] = sum(lengths)
        if error > 1e-6:
            raise ValueError("Expanded relevance margin differs from the scalar ranking output")
        receipt["status"] = "PASS"
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        socket.socket.connect = original_connect
        receipt["whole_check_wall_s"] = time.perf_counter() - began
        receipt["scope"] = protocol["scope"]
        receipt["quality_verified"] = False
        receipt["saved_candidate_weights"] = False
        _save_once(output / "receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.snapshot, args.manifest, args.out), indent=2, allow_nan=False))
