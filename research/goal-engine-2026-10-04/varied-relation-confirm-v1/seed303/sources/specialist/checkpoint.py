"""Validate partial specialist checkpoints against the declared trainable layers."""

import torch


def load_trained_weights(model, state):
    expected = model.state_dict()
    required = {name for name in expected if not name.startswith('encoder.')}
    required.update(name for name, parameter in model.named_parameters() if parameter.requires_grad)
    missing = sorted(required-set(state))
    unexpected = sorted(set(state)-set(expected))
    if missing or unexpected:
        raise ValueError(f'Incomplete checkpoint: missing={missing[:8]}, unexpected={unexpected[:8]}')
    # Validate all supplied tensors before load_state_dict can mutate any layer.
    for name,value in state.items():
        target=expected[name]
        if not isinstance(value,torch.Tensor) or value.layout!=torch.strided or value.shape!=target.shape:
            raise ValueError(f'Invalid checkpoint tensor: {name}')
        if not bool(torch.isfinite(value).all()):
            raise ValueError(f'Nonfinite checkpoint tensor: {name}')
        if target.is_floating_point() and value.numel():
            limit=torch.finfo(target.dtype).max
            if bool((value.abs()>limit).any()):
                raise ValueError(f'Checkpoint tensor overflows target dtype: {name}')
    return model.load_state_dict(state, strict=False)
