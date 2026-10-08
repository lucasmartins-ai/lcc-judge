"""Expand a scalar ranking head without discarding its initial relevance margin.

This is an initialization invariant, not evidence that training improves quality.
Only the CPU float32 BERT and XLM-R sequence classifiers used by the research
protocol are supported. The encoder and XLM-R's intermediate dense layer stay
unchanged. UNKNOWN starts with a separate seeded row, with no safety guarantee.
"""

import hashlib
import json

import torch


CLASSES = ("IRRELEVANT", "RELEVANT", "UNKNOWN")


def _head_sha256(head):
    digest = hashlib.sha256()
    for name, parameter in sorted(head.state_dict().items()):
        metadata = {"name": name, "shape": list(parameter.shape), "dtype": str(parameter.dtype)}
        digest.update(json.dumps(metadata, sort_keys=True).encode("utf-8"))
        digest.update(b"\0")
        digest.update(parameter.detach().contiguous().numpy().tobytes())
    return digest.hexdigest()


def retain_ranking_prior(model, seed):
    """Mutate a supported scalar classifier and return its initialization receipt.

    In evaluation mode, ``logit(RELEVANT) - logit(IRRELEVANT)`` initially equals
    the original scalar ranking score. Training can change that relation. This
    function validates the entire supported output shape before mutating model
    state, and leaves the caller's random generator unchanged.
    """
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**31:
        raise ValueError("seed must be an integer in [0, 2**31)")
    if model.config.num_labels != 1 or model.num_labels != 1:
        raise ValueError("expected a scalar ranking classifier")
    model_type = model.config.model_type
    if model_type == "bert":
        old_head = model.classifier
    elif model_type == "xlm-roberta":
        if not isinstance(model.classifier.dense, torch.nn.Linear):
            raise ValueError("unsupported XLM-R classifier dense layer")
        old_head = model.classifier.out_proj
    else:
        raise ValueError("unsupported model architecture")
    if not isinstance(old_head, torch.nn.Linear) or old_head.out_features != 1:
        raise ValueError("expected one linear output")
    if old_head.in_features != model.config.hidden_size or old_head.bias is None:
        raise ValueError("unsupported output shape or missing bias")
    if any(p.device.type != "cpu" or p.dtype != torch.float32 for p in model.parameters()):
        raise ValueError("initialization requires CPU float32 parameters")
    if not all(torch.isfinite(p).all().item() for p in old_head.parameters()):
        raise ValueError("nonfinite ranking output head")

    original_head_sha256 = _head_sha256(old_head)
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    with torch.random.fork_rng(devices=[]):
        new_head = torch.nn.Linear(old_head.in_features, 3)
        with torch.no_grad():
            new_head.weight[0].copy_(-0.5 * old_head.weight[0])
            new_head.weight[1].copy_(0.5 * old_head.weight[0])
            new_head.bias[0].copy_(-0.5 * old_head.bias[0])
            new_head.bias[1].copy_(0.5 * old_head.bias[0])
            torch.nn.init.normal_(new_head.weight[2], mean=0.0, std=0.02, generator=generator)
            new_head.bias[2].zero_()
    new_head.train(old_head.training)
    new_head.weight.requires_grad_(old_head.weight.requires_grad)
    new_head.bias.requires_grad_(old_head.bias.requires_grad)
    if model_type == "bert":
        model.classifier = new_head
    else:
        model.classifier.out_proj = new_head
    model.num_labels = 3
    model.config.num_labels = 3
    model.config.id2label = dict(enumerate(CLASSES))
    model.config.label2id = {name: index for index, name in enumerate(CLASSES)}
    model.config.problem_type = "single_label_classification"
    return {
        "model_type": model_type,
        "classes": list(CLASSES),
        "seed": seed,
        "original_output_head_sha256": original_head_sha256,
        "initial_output_head_sha256": _head_sha256(new_head),
        "initial_relevance_margin": "original scalar ranking logit",
        "unknown_initialization": "normal(0, 0.02) weight, zero bias; uncalibrated",
        "encoder_and_intermediate_dense_preserved": True,
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "quality_or_safety_verified": False,
    }
