import unittest
import torch
from torch import nn


class DirectRelevanceTests(unittest.TestCase):
    def test_strict_auc_does_not_credit_ties(self):
        from research.relevance_study import auc
        self.assertEqual(auc([0, 1], [0, 1]), .25)
        self.assertIsNone(auc([], [0]))

    def test_validation_threshold_preserves_both_positive_strata(self):
        from research.relevance_study import choose_threshold
        rows = [dict(score=float(i), label=1, observation_status='healthy') for i in range(20)]
        rows += [dict(score=float(i+100), label=1, observation_status='anomalous') for i in range(20)]
        rows.append(dict(score=-100., label=0, observation_status='anomalous'))
        self.assertEqual(choose_threshold(rows), 1.)

    def test_matched_head_initialization_ignores_constructor_rng(self):
        from research.relevance_study import matched_reset_head
        def make():
            model = nn.Module()
            model.head = nn.Sequential(nn.Linear(4, 3), nn.GELU(), nn.Linear(3, 1))
            return model
        a, b = make(), make()
        matched_reset_head(a, 11)
        torch.randn(1000)
        matched_reset_head(b, 11)
        for left, right in zip(a.parameters(), b.parameters()):
            torch.testing.assert_close(left, right, rtol=0, atol=0)

    def test_cached_features_match_native_line_attention(self):
        from specialist.model import SpecialistHead
        from research.head_objective_study import occupied_line_representations
        from research.relevance_study import RelevanceHead
        make = lambda: nn.Sequential(nn.Linear(768, 256), nn.GELU(), nn.Dropout(.1), nn.Linear(256, 1))
        native = SpecialistHead.__new__(SpecialistHead)
        nn.Module.__init__(native)
        native.pooling = 'line-attn'
        native.line_score, native.head = make(), make()
        cached = RelevanceHead(native.state_dict())
        cached.load_state_dict(native.state_dict())
        native.eval()
        cached.eval()
        hidden, ids = torch.randn(2, 7, 768), torch.tensor([[0,0,2,2,-1,-1,-1],[1,1,3,3,3,-1,-1]])
        with torch.no_grad():
            expected = native._forward_lines(hidden, ids)
            actual = cached(occupied_line_representations(hidden, ids))
        torch.testing.assert_close(actual, expected)


if __name__ == '__main__':
    unittest.main()
