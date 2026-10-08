"""Validate partial specialist checkpoints against the declared trainable layers."""


def load_trained_weights(model, state):
    expected = model.state_dict()
    required = {name for name in expected if not name.startswith('encoder.')}
    required.update(name for name, parameter in model.named_parameters() if parameter.requires_grad)
    missing = sorted(required-set(state))
    unexpected = sorted(set(state)-set(expected))
    if missing or unexpected:
        raise ValueError(f'Incomplete checkpoint: missing={missing[:8]}, unexpected={unexpected[:8]}')
    return model.load_state_dict(state, strict=False)
