import random
import unittest

import torch

from research.compact_relation_training import relation_loss, grouped_batches


class CompactRelationTrainingTests(unittest.TestCase):
    def test_rank_term_compares_reports_under_same_question(self):
        rows = [dict(objective='q1',label=1), dict(objective='q1',label=0),
                dict(objective='q2',label=1), dict(objective='q2',label=0)]
        good = torch.tensor([5.,4.,-4.,-5.],requires_grad=True)
        bad = torch.tensor([4.,5.,-5.,-4.],requires_grad=True)
        # Query-specific offset does not change the ranking contribution.
        shifted = good+torch.tensor([100.,100.,-100.,-100.])
        a = relation_loss(rows,good,'rank-only')
        self.assertLess(a,relation_loss(rows,bad,'rank-only'))
        self.assertEqual(float(a.detach()),float(relation_loss(rows,shifted,'rank-only').detach()))
        a.backward()
        self.assertLess(good.grad[0].item(),0.)
        self.assertGreater(good.grad[1].item(),0.)

    def test_joint_keeps_absolute_classification_supervision(self):
        rows = [dict(objective='q',label=1),dict(objective='q',label=0)]
        centered = torch.tensor([4.,-4.])
        retaining_all = centered+20.
        self.assertLess(relation_loss(rows,centered,'joint'),relation_loss(rows,retaining_all,'joint'))
        with self.assertRaises(ValueError):
            relation_loss([dict(objective='q',label=1)],torch.tensor([1.]),'joint')

    def test_group_batches_never_split_goal_alternatives_and_cover_once(self):
        rows = [dict(id=f'{g}-{i}',group=g,objective=f'{g}-q',label=i%2) for g in ['a','b','c'] for i in range(4)]
        batches = grouped_batches(rows,random.Random(101),groups_per_batch=2)
        self.assertEqual(sorted(r['id'] for batch in batches for r in batch),sorted(r['id'] for r in rows))
        for group in ['a','b','c']:
            self.assertEqual(sum(any(r['group']==group for r in b) for b in batches),1)
        self.assertEqual(batches,grouped_batches(rows,random.Random(101),groups_per_batch=2))


if __name__ == '__main__':
    unittest.main()
