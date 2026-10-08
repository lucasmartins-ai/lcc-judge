import unittest

import torch

from research.tool_role_study import fresh_head, numeric_batch


class DummyModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = torch.nn.Linear(4, 4)
        self.classifier = torch.nn.Linear(4, 1)
        self.config = type('Config', (), dict(hidden_size=4, num_labels=1))()
        self.num_labels = 1


class ToolRoleStudyTests(unittest.TestCase):
    def test_new_head_is_three_class_and_seeded_without_touching_encoder(self):
        model = DummyModel()
        encoder_before = {k: v.detach().clone() for k, v in model.encoder.state_dict().items()}
        fresh_head(model, 101)
        first = model.classifier.weight.detach().clone()
        self.assertEqual(model.classifier.weight.shape, (3, 4))
        self.assertEqual(model.config.num_labels, 3)
        self.assertEqual(model.num_labels, 3)
        self.assertTrue(bool((model.classifier.bias == 0).all()))
        self.assertTrue(all(torch.equal(v, model.encoder.state_dict()[k]) for k, v in encoder_before.items()))
        fresh_head(model, 101)
        self.assertTrue(torch.equal(first, model.classifier.weight))
        fresh_head(model, 202)
        self.assertFalse(torch.equal(first, model.classifier.weight))

    def test_attention_mask_checks_complete_pair_submission(self):
        encoded = dict(input_ids=torch.zeros((2, 4), dtype=torch.long),
                       attention_mask=torch.tensor([[1, 1, 1, 0], [1, 1, 1, 1]]))
        self.assertEqual(numeric_batch(encoded, [3, 4], 512), (7, 8))
        with self.assertRaises(ValueError):
            numeric_batch(encoded, [3, 5], 512)
        with self.assertRaises(ValueError):
            numeric_batch(encoded, [3, 4], 3)


if __name__ == '__main__':
    unittest.main()
