import unittest
from types import SimpleNamespace
import torch
from torch import nn
from specialist.train_detect import MultiTaskSpecialistHead


class IdentityEncoder(nn.Module):
    def forward(self,input_ids,**kwargs):
        return SimpleNamespace(last_hidden_state=input_ids.unsqueeze(-1).float())


def tiny_joint():
    model=MultiTaskSpecialistHead.__new__(MultiTaskSpecialistHead)
    nn.Module.__init__(model)
    model.encoder=IdentityEncoder();model.use_lines=True
    model.line_score=nn.Linear(1,1);model.head_judge=nn.Linear(1,1);model.head_detect=nn.Linear(1,1)
    with torch.no_grad():
        model.line_score.weight.zero_();model.line_score.bias.zero_()
        for head in [model.head_judge,model.head_detect]:head.weight.fill_(1);head.bias.fill_(2)
    return model


class JointPoolingTests(unittest.TestCase):
    def test_gap_lines_do_not_create_phantom_candidates(self):
        model=tiny_joint()
        compact=model({'input_ids':torch.tensor([[2,4]]),'line_ids':torch.tensor([[0,1]])})
        gap=model({'input_ids':torch.tensor([[2,4]]),'line_ids':torch.tensor([[0,2]])})
        for a,b in zip(compact,gap):torch.testing.assert_close(a,b)

    def test_empty_example_stays_empty_in_a_batch(self):
        model=tiny_joint()
        alone=model({'input_ids':torch.tensor([[0,0]]),'line_ids':torch.tensor([[-1,-1]])})
        batch=model({'input_ids':torch.tensor([[0,0],[2,4]]),'line_ids':torch.tensor([[-1,-1],[0,1]])})
        for a,b in zip(alone,batch):torch.testing.assert_close(a[0],b[0])


if __name__=='__main__':unittest.main()
