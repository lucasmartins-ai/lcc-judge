import math
import unittest

import torch

from research.tool_role_training import class_weights, classification_loss, training_items, score_axes


class ToolRoleTrainingTests(unittest.TestCase):
    def test_duplicate_views_are_not_independent_training_examples(self):
        rows = [dict(id='a', split='train', label=1), dict(id='b', split='train', label=1),
                dict(id='c', split='train', label=None), dict(id='d', split='train', label=None)]
        def view(identity, key, status='PROJECTED'):
            return dict(id=identity, view=dict(status=status, projected_input_sha256=key,
                                             objective='question', text='measurement'))
        views = [view('a', 'same'), view('b', 'same'), view('c', 'semantic-unknown'), view('d', None, 'UNKNOWN')]
        items = training_items(rows, views)
        self.assertEqual(len(items), 2)
        self.assertEqual({r['class_id'] for r in items}, {1, 2})
        self.assertEqual(next(r for r in items if r['class_id'] == 1)['receipt_ids'], ['a', 'b'])
        rows[1]['label'] = 0
        with self.assertRaises(ValueError):
            training_items(rows, views)

    def test_balancing_uses_all_unique_training_classes(self):
        items = [dict(class_id=0)] * 4 + [dict(class_id=1)] * 4 + [dict(class_id=2)]
        weights = class_weights(items)
        for label, count in [(0, 4), (1, 4), (2, 1)]:
            self.assertAlmostEqual(weights[label] * count, 3)
        logits = torch.zeros((9, 3), requires_grad=True)
        loss = classification_loss(items, logits, weights)
        self.assertAlmostEqual(float(loss.detach()), math.log(3), places=6)
        loss.backward()
        self.assertTrue(bool(torch.isfinite(logits.grad).all()))
        with self.assertRaises(ValueError):
            class_weights([dict(class_id=1)])

    def test_answerability_is_a_distinct_score_axis(self):
        logits = torch.tensor([[1.0, 4.0, -2.0], [1.0, 4.0, 8.0]])
        relevant, unknown = score_axes(logits)
        self.assertEqual(relevant.tolist(), [3.0, 3.0])
        self.assertGreater(float(unknown[1]), float(unknown[0]))
        with self.assertRaises(ValueError):
            score_axes(torch.zeros(1, 1))


if __name__ == '__main__':
    unittest.main()
