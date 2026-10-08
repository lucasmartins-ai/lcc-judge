import unittest
import torch
from torch import nn
from specialist.model import SpecialistHead
from research.head_objective_study import occupied_line_representations,FeatureHeads,objective_loss


class HeadObjectiveTests(unittest.TestCase):
    def test_cached_line_means_match_full_corrected_pooling(self):
        torch.manual_seed(18)
        def head():return nn.Sequential(nn.Linear(768,256),nn.GELU(),nn.Dropout(.1),nn.Linear(256,1))
        original=SpecialistHead.__new__(SpecialistHead);nn.Module.__init__(original)
        original.pooling='line-attn';original.line_score=head();original.head=head();original.eval()
        cached=FeatureHeads({'line_score':original.line_score.state_dict(),'head':original.head.state_dict()}).eval()
        hidden=torch.randn(1,5,768);ids=torch.tensor([[0,0,2,2,-1]])
        features=occupied_line_representations(hidden,ids)
        self.assertEqual(features[0].shape,(2,768))
        with torch.no_grad():
            expected=original._forward_lines(hidden,ids)
            actual,_=cached(features)
        torch.testing.assert_close(actual,expected)

    def test_objective_loss_keeps_unrelated_out_of_judge_target(self):
        items=[{'kind':k,'domain':'fixture'} for k in ['pos','neg_decoy','neg_unrelated']]
        j=torch.tensor([1.,-1.,-100.]);d=torch.tensor([2.,2.,-2.])
        value=objective_loss(j,d,items,'joint')
        j[-1]=100.
        self.assertEqual(value,objective_loss(j,d,items,'joint'))
        d[-1]=2.
        self.assertGreater(objective_loss(j,d,items,'joint'),value)


if __name__=='__main__':unittest.main()
