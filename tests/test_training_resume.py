import json
from pathlib import Path
import random
import tempfile
import unittest

import torch
from torch import nn


ARGS = dict(seed=7, device='cpu', pooling='mean', unfreeze_last_n=0,
            batch_size=2, max_len=16, lr_head=.001, lr_encoder=.00002)


def step(model, optimizer):
    model.train()
    loss = model(torch.randn(2, 2)).square().mean()
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    return random.random(), float(loss.detach())


class TrainingResumeTests(unittest.TestCase):
    def test_interrupted_training_matches_uninterrupted_next_step(self):
        from specialist.training_state import save_resume, restore_resume
        torch.manual_seed(7)
        random.seed(7)
        model = nn.Sequential(nn.Linear(2, 2), nn.Dropout(.5))
        optimizer = torch.optim.AdamW(model.parameters(), lr=.001)
        step(model, optimizer)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'resume.pt'
            save_resume(path, model, optimizer, epoch=1, history=[dict(epoch=1)],
                        args=ARGS, data_digest='dataset-a')
            expected = step(model, optimizer)
            state = {k: v.clone() for k, v in model.state_dict().items()}
            replacement = nn.Sequential(nn.Linear(2, 2), nn.Dropout(.5))
            new_optimizer = torch.optim.AdamW(replacement.parameters(), lr=.001)
            resume = restore_resume(path, replacement, new_optimizer, args=ARGS,
                                    data_digest='dataset-a', total_epochs=2)
            self.assertEqual(resume['epoch'], 1)
            self.assertEqual(expected, step(replacement, new_optimizer))
            for name, value in replacement.state_dict().items():
                torch.testing.assert_close(value, state[name], rtol=0, atol=0)

    def test_resume_rejects_shortened_run_or_changed_data_or_optimizer(self):
        from specialist.training_state import save_resume, restore_resume
        model = nn.Linear(2, 2)
        optimizer = torch.optim.AdamW(model.parameters(), lr=.001)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'resume.pt'
            save_resume(path, model, optimizer, epoch=2, history=[dict(epoch=1),dict(epoch=2)],
                        args=ARGS, data_digest='dataset-a')
            for arguments, digest, epochs in [(ARGS,'dataset-a',1), (ARGS,'changed',3),
                                              ({**ARGS,'lr_head':.02},'dataset-a',3)]:
                with self.subTest(arguments=arguments, digest=digest, epochs=epochs):
                    with self.assertRaises(ValueError):
                        restore_resume(path,model,optimizer,args=arguments,
                                       data_digest=digest,total_epochs=epochs)

    def test_missing_rng_state_cannot_silently_resume_legacy_weights(self):
        from specialist.training_state import restore_resume
        model = nn.Linear(2, 2)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'resume.pt'
            torch.save(dict(epoch=3,weights=model.state_dict()),path)
            with self.assertRaisesRegex(ValueError, 'resume state'):
                restore_resume(path, model, torch.optim.AdamW(model.parameters()),
                               args=ARGS,data_digest='dataset-a',total_epochs=4)


if __name__ == '__main__':
    unittest.main()
