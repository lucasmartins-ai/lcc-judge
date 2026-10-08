import copy
import unittest

try:
    from research.audit_goal_pilot_metadata import validate_load, validate_started
except ModuleNotFoundError:
    validate_load = validate_started = None

PROTOCOL = dict(sha256='frozen', frozen_at_utc='2026-10-08T11:19:48+00:00',
                model=dict(repo_id='org/model', revision='abc', files={'model.safetensors': 'weights'}),
                encoder=dict(dtype='float32', device='cpu'))
STARTED = dict(protocol_sha256='frozen', utc='2026-10-08T11:20:03+00:00')
LOAD = dict(identity=dict(repo_id='org/model', revision='abc', model_sha256='weights', parameters=10,
                          dtype='float32', device='cpu', load_s=2.,
                          loading_info=dict(missing_keys=[], unexpected_keys=[], mismatched_keys=[], error_msgs=[])),
            elapsed_s=6., encoder_trainable_parameters=0)


class GoalPilotMetadataAuditTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(validate_started, 'Supplementary pilot metadata audit is absent')

    def test_started_receipt_must_bind_the_frozen_protocol(self):
        validate_started(STARTED, PROTOCOL)
        for key, value in [('protocol_sha256', 'tampered'), ('utc', '2026-10-08T11:00:00+00:00'),
                           ('extra', 1)]:
            with self.subTest(key=key), self.assertRaises(AssertionError):
                validate_started({**STARTED, key: value}, PROTOCOL)

    def test_load_metadata_must_match_declared_encoder_and_clean_loading(self):
        validate_load(LOAD, PROTOCOL)
        tampered = [('dtype', 'float16'), ('device', 'mps'), ('revision', 'other'), ('repo_id', 'other'),
                    ('model_sha256', 'other'), ('parameters', 0), ('load_s', -1.), ('load_s', 7.),
                    ('load_s', float('nan')), ('extra', 1)]
        for key, value in tampered:
            with self.subTest(key=key, value=value), self.assertRaises(AssertionError):
                bad = copy.deepcopy(LOAD)
                bad['identity'][key] = value
                validate_load(bad, PROTOCOL)
        for key, value in [('missing_keys', ['w']), ('mismatched_keys', ['w']), ('error_msgs', ['e']),
                           ('unexpected_keys', ['other.weight'])]:
            with self.subTest(key=key), self.assertRaises(AssertionError):
                bad = copy.deepcopy(LOAD)
                bad['identity']['loading_info'][key] = value
                validate_load(bad, PROTOCOL)
        for key, value in [('encoder_trainable_parameters', 1), ('elapsed_s', float('inf'))]:
            with self.subTest(key=key), self.assertRaises(AssertionError):
                validate_load({**LOAD, key: value}, PROTOCOL)
        allowed = copy.deepcopy(LOAD)
        allowed['identity']['loading_info']['unexpected_keys'] = ['bert.embeddings.position_ids']
        validate_load(allowed, PROTOCOL)


if __name__ == '__main__':
    unittest.main()
