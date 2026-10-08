"""Verified XLM-R classifier/tail adaptation with a retained scalar ranking prior."""

import hashlib
import json

import torch

from research.ranking_support_initialization import retain_ranking_prior


def frozen_parameter_sha256(model):
    digest = hashlib.sha256()
    for name, parameter in sorted(model.named_parameters()):
        if not parameter.requires_grad:
            metadata = dict(name=name, shape=list(parameter.shape), dtype=str(parameter.dtype))
            digest.update(json.dumps(metadata, sort_keys=True).encode() + b'\0')
            digest.update(parameter.detach().contiguous().numpy().tobytes())
    return digest.hexdigest()


def configure_adaptation(model, seed, last_n=2):
    if model.config.model_type != 'xlm-roberta' or model.config.num_labels != 1:
        raise ValueError('A scalar pretrained XLM-R classifier is required')
    layers = model.roberta.encoder.layer
    if (type(last_n) is not int or not 1 <= last_n <= len(layers)
            or len(layers) != model.config.num_hidden_layers
            or not isinstance(model.classifier.dense, torch.nn.Linear)
            or not isinstance(model.classifier.out_proj, torch.nn.Linear)):
        raise ValueError('Verified XLM-R layer structure and a bounded tail are required')
    initial = retain_ranking_prior(model, seed)
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    for block in layers[-last_n:]:
        for parameter in block.parameters():
            parameter.requires_grad_(True)
    for parameter in model.classifier.parameters():
        parameter.requires_grad_(True)
    names = [name for name, parameter in model.named_parameters() if parameter.requires_grad]
    total = sum(parameter.numel() for parameter in model.parameters())
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    return dict(initialization=initial, encoder_blocks=len(layers), last_n=last_n,
                total_parameters=total, trainable_parameters=trainable,
                frozen_parameters=total-trainable, trainable_names=names,
                frozen_names=[name for name,p in model.named_parameters() if not p.requires_grad],
                frozen_parameter_sha256=frozen_parameter_sha256(model))
