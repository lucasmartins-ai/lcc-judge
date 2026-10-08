import importlib
import unittest

try:
    probe = importlib.import_module('research.goal_interpreter_probe')
except ModuleNotFoundError:
    probe = None


class GoalInterpreterProbeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(probe, 'The bounded goal-only probe is not implemented')

    def test_malformed_record_does_not_make_a_supported_query_unknown(self):
        suffix = ' Report evidence for tool-0123456789ab; ordinary and unusual values both count.'
        row = dict(objective='Read failed operation calls.' + suffix, goal_language='en',
                   requested_role=None, observed_role='retry_failures', unknown_kind='unbound_record',
                   id='one', intent_alias=0)
        inputs, annotations = probe.extract_queries([row], ['retry_failures'])
        self.assertEqual(inputs[0]['question'], 'Read failed operation calls.')
        self.assertEqual(set(inputs[0]), {'id', 'question', 'language'})
        self.assertEqual(annotations[inputs[0]['id']]['target'], 'retry_failures')
        outside = dict(row, id='two', objective='Read incoming datagrams.' + suffix,
                       observed_role='udp_received_datagrams')
        other, labels = probe.extract_queries([outside], ['retry_failures'])
        self.assertIsNone(labels[other[0]['id']]['target'])
        self.assertEqual(labels[other[0]['id']]['kind'], 'out_of_registry')

    def test_duplicate_question_with_conflicting_target_is_rejected(self):
        row = dict(objective='Read operation calls. Report evidence for tool-0123456789ab; ordinary and unusual values both count.',
                   goal_language='en', requested_role='retry_attempts', observed_role='retry_failures',
                   unknown_kind=None, id='one', intent_alias=0)
        with self.assertRaises(ValueError):
            probe.extract_queries([row, dict(row, id='two', requested_role='retry_failures')],
                                  ['retry_attempts', 'retry_failures'])

    def test_ties_abstain_and_invalid_scores_cannot_form_a_partial_pass(self):
        candidates = ['retry_attempts', 'retry_failures', 'UNKNOWN:diagnosis']
        self.assertEqual(probe.route([3., 1., 0.], candidates), 'retry_attempts')
        self.assertIsNone(probe.route([3., 3., 0.], candidates))
        self.assertIsNone(probe.route([1., 0., 3.], candidates))
        with self.assertRaises(ValueError):
            probe.route([3., float('nan'), 0.], candidates)
        with self.assertRaises(ValueError):
            probe.route([3.], candidates)

    def test_wrong_supported_field_counts_against_binding_precision(self):
        inputs = [dict(id=str(i), language='en') for i in range(4)]
        labels = {'0':dict(target='retry_attempts', kind='direct'),
                  '1':dict(target='retry_failures', kind='direct'),
                  '2':dict(target=None, kind='diagnosis_goal'),
                  '3':dict(target=None, kind='diagnosis_goal')}
        result = probe.reduction(inputs, labels, ['retry_attempts', 'retry_attempts', None, 'retry_failures'])
        self.assertEqual(result['accepted_binding_precision'], 1 / 3)
        self.assertEqual(result['supported_coverage'], 1.)
        self.assertEqual(result['correct_supported_coverage'], .5)
        self.assertEqual(result['unknown_recognition'], .5)
        self.assertFalse(result['gate_pass'])
        abstaining = probe.reduction(inputs, labels, [None] * 4)
        self.assertIsNone(abstaining['accepted_binding_precision'])
        self.assertFalse(abstaining['gate_pass'])


if __name__ == '__main__':
    unittest.main()
