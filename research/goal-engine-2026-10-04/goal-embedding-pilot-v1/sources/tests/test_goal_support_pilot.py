import importlib
import unittest

try:
    pilot = importlib.import_module('research.goal_support_pilot')
except ModuleNotFoundError:
    pilot = None


class GoalSupportPilotTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(pilot, 'Supervised goal support pilot is absent')

    def test_affinity_without_support_and_field_ties_abstain(self):
        thresholds = dict(support_floor=0., margin_floor=1.)
        got = pilot.predict([2., -2., 3.], [[4., 0.], [8., 0.], [4., 4.]],
                            ['a', 'b'], thresholds)
        self.assertEqual(got, ['a', None, None])
        with self.assertRaises(ValueError):
            pilot.predict([float('nan')], [[4., 0.]], ['a', 'b'], thresholds)
        with self.assertRaises(ValueError):
            pilot.predict([2.], [[4.]], ['a', 'b'], thresholds)

    def test_train_policy_needs_correct_coverage_and_both_languages(self):
        inputs = [dict(id=str(i), language='en' if i < 4 else 'pt') for i in range(8)]
        labels = {r['id']:dict(target=['a', 'b', None, None][i % 4],
                              kind='direct' if i % 4 < 2 else 'diagnosis_goal',
                              wording_families=['toy']) for i, r in enumerate(inputs)}
        support = [3., 3., -2., -2.] * 2
        fields = [[4., 0.], [0., 4.], [8., 0.], [0., 8.]] * 2
        chosen = pilot.calibrate(inputs, labels, support, fields, ['a', 'b'])
        self.assertIsNotNone(chosen['thresholds'])
        self.assertTrue(chosen['metrics']['router_gate_pass'])
        wrong = [[4., 0.], [4., 0.], [8., 0.], [0., 8.]] * 2
        self.assertIsNone(pilot.calibrate(inputs, labels, support, wrong, ['a', 'b'])['thresholds'])
        self.assertIsNone(pilot.calibrate(inputs[:4], labels, support[:4], fields[:4], ['a', 'b'])['thresholds'])

    def test_separate_objectives_learn_support_despite_high_field_affinity(self):
        features = [[4., 3., 1.], [4., -3., 1.], [-4., 3., 1.], [-4., -3., 1.]]
        model, history = pilot.fit(features, ['a', 'b', None, None], ['a', 'b'])
        self.assertEqual(len(history), 200)
        self.assertLess(history[-1]['loss'], history[0]['loss'])
        self.assertEqual(model['scale'][2], 1.)
        support, field = pilot.logits(features, model)
        predictions = pilot.predict(support, field, ['a', 'b'], dict(support_floor=0., margin_floor=0.))
        self.assertEqual(predictions, ['a', 'b', None, None])


if __name__ == '__main__':
    unittest.main()
