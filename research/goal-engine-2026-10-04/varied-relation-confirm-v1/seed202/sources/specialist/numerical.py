"""Abort corrupted training before it becomes an accepted epoch/checkpoint."""
from __future__ import annotations

import torch


class NonFiniteTrainingError(ValueError):
    def __init__(self, stage, names=()):
        self.stage, self.names = stage, tuple(names)
        super().__init__(f'Nonfinite training {stage}: {list(self.names)[:8]}')


def finite_update(loss, model, optimizer):
    """Same unclipped update when finite; stop on loss/gradient/state corruption.

    A post-update failure invalidates the in-memory run; no rollback or successful
    epoch is implied. Callers must preserve the failure and stop saving candidates.
    """
    optimizer.zero_grad()
    if loss.ndim != 0 or not bool(torch.isfinite(loss)):
        raise NonFiniteTrainingError('loss')
    parameters = {n:p for n,p in model.named_parameters() if p.requires_grad}
    loss.backward()
    bad = [n for n,p in parameters.items() if p.grad is not None and not bool(torch.isfinite(p.grad).all())]
    if bad:
        optimizer.zero_grad()
        raise NonFiniteTrainingError('gradient',bad)
    optimizer.step()
    bad = [n for n,p in parameters.items() if not bool(torch.isfinite(p).all())]
    if bad:
        raise NonFiniteTrainingError('parameter',bad)
    bad = [f'{n}.{key}' for n,p in parameters.items() for key,value in optimizer.state.get(p,{}).items()
           if isinstance(value,torch.Tensor) and not bool(torch.isfinite(value).all())]
    if bad:
        raise NonFiniteTrainingError('optimizer_state',bad)
