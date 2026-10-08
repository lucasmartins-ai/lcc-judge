import unittest

import torch

from research.factorized_relation_training import factorized_loss, conditional_loss, training_quartets


class FactorizedRelationTrainingTests(unittest.TestCase):
    def test_unknown_relevance_receives_no_gradient_and_support_is_independent(self):
        logits=torch.tensor([[2.,4.,-1.],[1.,-2.,-3.],[50.,-50.,1.]],requires_grad=True)
        items=[dict(class_id=i) for i in [1,0,2]]
        loss=factorized_loss(items,logits,binary_fraction=2/3,unknown_fraction=1/3)
        loss.backward()
        self.assertEqual(logits.grad[2,:2].tolist(),[0.,0.])
        self.assertLess(float(logits.grad[2,2]),0.)
        changed=logits.detach().clone();changed[2,:2]=torch.tensor([-999.,999.])
        self.assertAlmostEqual(float(loss.detach()),float(factorized_loss(items,changed,2/3,1/3)),7)

    def test_conditional_loss_requires_both_report_and_goal_orderings(self):
        # Matrix slots: requestedA/reportA, A/B, B/A, B/B. Relevant diagonal.
        good=torch.tensor([[[0.,2.,0.],[0.,-2.,0.],[0.,-2.,0.],[0.,2.,0.]]],requires_grad=True)
        report_bias=torch.tensor([[[0.,2.,0.],[0.,-2.,0.],[0.,2.,0.],[0.,-2.,0.]]])
        self.assertLess(float(conditional_loss(good).detach()),float(conditional_loss(report_bias)))
        conditional_loss(good).backward()
        self.assertLess(float(good.grad[0,0,1]),0.)
        self.assertGreater(float(good.grad[0,2,1]),0.)
        self.assertTrue(torch.equal(good.grad[:,:,2],torch.zeros((1,4))))

    def test_quartets_are_deduplicated_and_nontrain_or_missing_slot_is_rejected(self):
        rows=[];views=[]
        for repeat in [0,1]:
            for requested,observed in [('a','a'),('a','b'),('b','a'),('b','b')]:
                key=requested+observed
                row=dict(id=f'{repeat}-{key}',split='train',label=int(requested==observed),
                    group=f'fixture-{repeat}',report_variant='measured',requested_role=requested,
                    observed_role=observed,projected_input_hash=key)
                rows.append(row);views.append(dict(id=row['id'],view=dict(status='PROJECTED',
                    projected_input_sha256=key,objective=requested,text=observed)))
        self.assertEqual(training_quartets(rows,views),[['aa','ab','ba','bb']])
        with self.assertRaises(ValueError):training_quartets(rows[:-1],views[:-1])
        rows[0]['split']='final'
        with self.assertRaises(ValueError):training_quartets(rows,views)

    def test_invalid_shapes_labels_or_global_weights_fail_closed(self):
        for logits,items,binary,unknown in [
            (torch.zeros((1,2)),[dict(class_id=1)],.9,.1),
            (torch.zeros((1,3)),[dict(class_id=True)],.9,.1),
            (torch.zeros((1,3)),[dict(class_id=2)],1.,0.),
            (torch.zeros((1,3)),[dict(class_id=2)],float('nan'),.1),
        ]:
            with self.assertRaises(ValueError):factorized_loss(items,logits,binary,unknown)
        with self.assertRaises(ValueError):conditional_loss(torch.zeros((1,3,3)))


if __name__=='__main__':unittest.main()
