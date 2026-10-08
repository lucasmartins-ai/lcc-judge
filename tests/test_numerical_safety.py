import copy
import unittest

import torch

from specialist.checkpoint import load_trained_weights
from specialist.numerical import NonFiniteTrainingError, finite_update


class NumericalSafetyTests(unittest.TestCase):
    def model(self):
        model=torch.nn.Linear(2,1)
        return model,torch.optim.AdamW(model.parameters(),lr=.01)

    def test_nonfinite_loss_never_updates_model_or_optimizer(self):
        model,opt=self.model();before=copy.deepcopy(model.state_dict())
        loss=model(torch.ones(1,2)).sum()*float('nan')
        with self.assertRaises(NonFiniteTrainingError):finite_update(loss,model,opt)
        self.assertFalse(opt.state)
        for name,value in before.items():self.assertTrue(torch.equal(value,model.state_dict()[name]))

    def test_nonfinite_backward_is_detected_before_optimizer_step(self):
        model,opt=self.model();before=copy.deepcopy(model.state_dict())
        hook=model.weight.register_hook(lambda gradient:torch.full_like(gradient,float('inf')))
        with self.assertRaises(NonFiniteTrainingError):finite_update(model(torch.ones(1,2)).square().mean(),model,opt)
        hook.remove();self.assertFalse(opt.state)
        for name,value in before.items():self.assertTrue(torch.equal(value,model.state_dict()[name]))

    def test_valid_update_matches_same_unclipped_optimizer(self):
        model,opt=self.model();reference=copy.deepcopy(model);refopt=torch.optim.AdamW(reference.parameters(),lr=.01)
        x=torch.tensor([[2.,3.]])
        finite_update(model(x).square().mean(),model,opt)
        refopt.zero_grad();reference(x).square().mean().backward();refopt.step()
        for left,right in zip(model.parameters(),reference.parameters()):self.assertTrue(torch.equal(left,right))

    def test_corrupt_checkpoint_rejected_before_any_parameter_changes(self):
        for corruption in ['nan','inf','shape','overflow']:
            model,_=self.model();before=copy.deepcopy(model.state_dict());state=copy.deepcopy(before)
            if corruption=='shape':state['weight']=torch.zeros(1,3)
            elif corruption=='overflow':state['weight']=torch.full((1,2),1e100,dtype=torch.float64)
            else:state['weight'][0,0]=float(corruption)
            with self.assertRaises(ValueError):load_trained_weights(model,state)
            for name,value in before.items():self.assertTrue(torch.equal(value,model.state_dict()[name]))


if __name__=='__main__':unittest.main()
