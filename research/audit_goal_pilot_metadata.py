"""Extend the frozen support/embedding pilot audits without changing their executed sources.

Closes the Minor gap in goal-embedding-pilot-v1/INDEPENDENT_REVIEW.md: started.json must bind
the frozen protocol hash, load.json must match the declared encoder and clean loading, and the
start/load receipts are hash-bound in a new create-only audit-metadata-v2.json per pilot.
"""
from datetime import datetime
import json
import math

from research import goal_embedding_pilot as embedding
from research import goal_support_pilot as support

ALLOWED_UNEXPECTED = {'bert.embeddings.position_ids'}  # same allowance as PairReranker.from_snapshot


def _finite_nonnegative(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate_started(started, protocol):
    assert set(started) == {'protocol_sha256', 'utc'}
    assert started['protocol_sha256'] == protocol['sha256']
    assert datetime.fromisoformat(protocol['frozen_at_utc']) <= datetime.fromisoformat(started['utc'])


def validate_load(load, protocol):
    assert set(load) == {'identity', 'elapsed_s', 'encoder_trainable_parameters'}
    identity, model, encoder = load['identity'], protocol['model'], protocol['encoder']
    assert set(identity) == {'repo_id', 'revision', 'model_sha256', 'parameters', 'dtype', 'device', 'load_s', 'loading_info'}
    assert identity['repo_id'] == model['repo_id'] and identity['revision'] == model['revision']
    assert identity['model_sha256'] == model['files']['model.safetensors']
    assert identity['dtype'] == encoder['dtype'] and identity['device'] == encoder['device']
    assert type(identity['parameters']) is int and identity['parameters'] > 0
    assert _finite_nonnegative(identity['load_s']) and _finite_nonnegative(load['elapsed_s'])
    assert load['elapsed_s'] >= identity['load_s']
    info = identity['loading_info']
    assert set(info) == {'missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs'}
    assert info['missing_keys'] == info['mismatched_keys'] == info['error_msgs'] == []
    assert set(info['unexpected_keys']) <= ALLOWED_UNEXPECTED
    assert load['encoder_trainable_parameters'] == 0


def audit_pilot(module, receipts):
    module.audit()  # frozen audit; audit.json already exists, so it only compares
    base = module.base
    protocol = module.checked()
    validate_started(base.load(module.OUT / 'started.json'), protocol)
    if 'load.json' in receipts:
        validate_load(base.load(module.OUT / 'load.json'), protocol)
    result = dict(status='PASS', protocol_sha256=protocol['sha256'],
                  scope='Supplement to the frozen audit: started protocol binding, load metadata (embedding only) and receipt hashes',
                  frozen_audit_sha256=base.sha(module.OUT / 'audit.json'),
                  receipts={name: base.sha(module.OUT / name) for name in ('protocol.json', *receipts)},
                  sources={name: base.sha(base.ROOT / name) for name in (
                      'research/audit_goal_pilot_metadata.py', 'tests/test_goal_pilot_metadata_audit.py')},
                  additional_encoder_forwards=0, additional_training_updates=0)
    path = module.OUT / 'audit-metadata-v2.json'
    if path.exists():
        assert result == base.load(path)
    else:
        base.save(path, result)
    print(json.dumps(result))


def audit():
    audit_pilot(support, ('started.json',))
    audit_pilot(embedding, ('started.json', 'load.json'))


if __name__ == '__main__':
    audit()
