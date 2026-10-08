"""Small tensor controls; no pretrained download or model-quality claims."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch
from torch import nn
from specialist.model import SpecialistHead
from bakeoff.adapters import TrainedJudgeAdapter


def small_head(pooling='line-attn'):
    model = SpecialistHead.__new__(SpecialistHead)
    nn.Module.__init__(model)
    model.pooling = pooling
    model.use_lines = True
    model.encoder = nn.Linear(1, 1)
    for parameter in model.encoder.parameters():
        parameter.requires_grad = False
    model.line_score = nn.Linear(1, 1)
    model.head = nn.Linear(1, 1)
    with torch.no_grad():
        model.line_score.weight.zero_()
        model.line_score.bias.zero_()
        model.head.weight.fill_(1)
        model.head.bias.zero_()
    return model


class PoolingInvariantTests(unittest.TestCase):
    def test_empty_lines_cannot_change_the_score(self):
        model = small_head()
        hidden = torch.tensor([[[2.], [4.]]])
        compact = model._forward_lines(hidden, torch.tensor([[0, 1]]))
        gaps = model._forward_lines(hidden, torch.tensor([[0, 2]]))
        torch.testing.assert_close(compact, gaps)

    def test_empty_example_has_the_same_score_alone_and_in_batch(self):
        model = small_head()
        with torch.no_grad():
            model.head.bias.fill_(2)
        single = model._forward_lines(torch.zeros(1, 2, 1), torch.tensor([[-1, -1]]))
        batch = model._forward_lines(torch.tensor([[[0.], [0.]], [[2.], [4.]]]),
                                     torch.tensor([[-1, -1], [0, 1]]))
        torch.testing.assert_close(single[0], batch[0])
        self.assertTrue(torch.isfinite(batch).all())

    def test_line_max_has_no_artificial_logit_floor(self):
        model = small_head('line-max')
        with torch.no_grad():
            model.line_score.bias.fill_(-20000)
        score = model._forward_lines(torch.tensor([[[2.], [4.]]]), torch.tensor([[0, 2]]))
        self.assertEqual(score.item(), -20000)


class CheckpointLoaderTests(unittest.TestCase):
    def test_missing_head_tensor_is_rejected(self):
        model = small_head()
        state = {name: value for name, value in model.state_dict().items()
                 if not name.startswith('encoder.') and name != 'head.bias'}
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory/'config.json').write_text(json.dumps(dict(model_id='stub', pooling='line-attn')))
            torch.save(state, directory/'weights.pt')
            adapter = TrainedJudgeAdapter('stub', str(directory), 32)
            with patch('specialist.model.SpecialistHead', return_value=model):
                with self.assertRaisesRegex((ValueError, RuntimeError), 'Incomplete|missing'):
                    adapter._load()

    def test_partial_frozen_checkpoint_is_accepted(self):
        model = small_head()
        state = {name: value for name, value in model.state_dict().items()
                 if not name.startswith('encoder.')}
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory/'config.json').write_text(json.dumps(dict(model_id='stub', pooling='line-attn')))
            torch.save(state, directory/'weights.pt')
            adapter = TrainedJudgeAdapter('stub', str(directory), 32)
            with patch('specialist.model.SpecialistHead', return_value=model):
                adapter._load()


if __name__ == '__main__':
    unittest.main()
