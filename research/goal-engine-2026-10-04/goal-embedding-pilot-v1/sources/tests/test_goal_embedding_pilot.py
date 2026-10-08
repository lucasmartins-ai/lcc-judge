import importlib
import unittest

try:
    pilot = importlib.import_module('research.goal_embedding_pilot')
except ModuleNotFoundError:
    pilot = None


class GoalEmbeddingPilotTests(unittest.TestCase):
    def test_padding_cannot_change_query_representation_and_empty_input_is_invalid(self):
        self.assertIsNotNone(pilot, 'Frozen query embedding producer is absent')
        self.assertEqual(pilot.masked_mean([[[1., 3.], [3., 5.], [999., -999.]]], [[1, 1, 0]]), [[2., 4.]])
        self.assertEqual(pilot.masked_mean([[[1., 3.], [3., 5.]]], [[1, 1]]), [[2., 4.]])
        for hidden, mask in [([[[1., 3.]]], [[0]]), ([[[float('nan'), 3.]]], [[1]]),
                             ([[[1., 3.]]], [[1, 1]]), ([[[1., 3.]]], [[2]])]:
            with self.subTest(mask=mask), self.assertRaises(ValueError):
                pilot.masked_mean(hidden, mask)


if __name__ == '__main__':
    unittest.main()
