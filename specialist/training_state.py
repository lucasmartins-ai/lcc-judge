"""Epoch-boundary resume with weights, optimizer, input identity and random state."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import random
import torch
from .checkpoint import load_trained_weights

SCHEMA = 'lcc-training-resume/0.1'
INVARIANTS = ('seed', 'device', 'pooling', 'unfreeze_last_n', 'batch_size',
              'max_len', 'lr_head', 'lr_encoder', 'model_id', 'revision')


def data_digest(directory):
    directory = Path(directory)
    files = {name: hashlib.sha256((directory/name).read_bytes()).hexdigest()
             for name in ['train.jsonl', 'val.jsonl', 'ood.jsonl', 'manifest.json']}
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def save_resume(path, model, optimizer, *, epoch, history, args, data_digest):
    rng = dict(python=random.getstate(), cpu=torch.get_rng_state())
    if args['device'] == 'mps':
        rng['mps'] = torch.mps.get_rng_state()
    elif args['device'].startswith('cuda'):
        rng['cuda'] = torch.cuda.get_rng_state_all()
    state = model.state_dict()
    names = {name for name, value in model.named_parameters() if value.requires_grad}
    names.update(name for name in state if not name.startswith('encoder.'))
    payload = dict(schema=SCHEMA, weights={name: state[name] for name in names},
                   optimizer=optimizer.state_dict(), epoch=epoch, history=history,
                   args={k: args.get(k) for k in INVARIANTS}, data_digest=data_digest,
                   rng=rng, torch_version=str(torch.__version__))
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    try:
        torch.save(payload, temporary)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def restore_resume(path, model, optimizer, *, args, data_digest, total_epochs):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing resume state; legacy weights cannot restore RNG/optimizer provenance')
    state = torch.load(path, map_location='cpu', weights_only=True)
    if (state.get('schema') != SCHEMA or not {'rng','optimizer','weights','epoch','history','args','data_digest'} <= set(state)):
        raise ValueError('Incomplete resume state; legacy weights cannot restore RNG/optimizer provenance')
    if state['args'] != {k: args.get(k) for k in INVARIANTS}:
        raise ValueError('Resume hyperparameters or runtime changed')
    if state['data_digest'] != data_digest:
        raise ValueError('Resume dataset changed')
    if state['torch_version'] != str(torch.__version__):
        raise ValueError('Resume torch version changed')
    if total_epochs < state['epoch']:
        raise ValueError('Requested epochs are below the completed checkpoint epoch')
    if [row['epoch'] for row in state['history']] != list(range(1,state['epoch']+1)):
        raise ValueError('Resume history is incomplete or contradicts completed epochs')
    load_trained_weights(model, state['weights'])
    optimizer.load_state_dict(state['optimizer'])
    random.setstate(state['rng']['python'])
    torch.set_rng_state(state['rng']['cpu'])
    if args['device'] == 'mps':
        torch.mps.set_rng_state(state['rng']['mps'])
    elif args['device'].startswith('cuda'):
        torch.cuda.set_rng_state_all(state['rng']['cuda'])
    return state
