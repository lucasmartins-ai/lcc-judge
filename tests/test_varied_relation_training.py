import copy
import math
from pathlib import Path
import unittest

import torch

from research.varied_relation_training import adapt_records, balanced_loss, calibrate_bilingual
from research.audit_tool_relation_state_supervision import rows
from research.tool_role_policy import decision
from research.audit_varied_relation_dev import bilingual_thresholds

DATA = Path(__file__).resolve().parents[1] / 'research/goal-engine-2026-10-04/tool-relation-states-v2/supervision-v1'


class VariedRelationTrainingTests(unittest.TestCase):
    def test_complete_projected_strings_and_compatibility_identities_are_preserved(self):
        raw = list(rows(DATA / 'train.jsonl.gz'))[:8]
        saved = list(rows(DATA / 'train-views.jsonl.gz'))[:8]
        original = copy.deepcopy(saved)
        result, views = adapt_records(raw, saved)
        self.assertEqual(saved, original)
        self.assertEqual(result[0]['text'], raw[0]['text'])
        self.assertEqual(views[0]['view']['projected_input_sha256'], raw[0]['projected_input_hash'])
        self.assertEqual(result[0]['report_id'], result[4]['report_id'])
        changed = copy.deepcopy(saved); changed[0]['view']['text'] += ' label=1'
        with self.assertRaises(ValueError):
            adapt_records(raw, changed)

    def test_unequal_binary_classes_have_equal_total_gradient_and_unknown_is_masked(self):
        items = [dict(class_id=i) for i in [0,0,0,0,1,2]]
        logits = torch.zeros((6,3), requires_grad=True)
        balanced_loss(items, logits, [4,1,1]).backward()
        self.assertAlmostEqual(float(logits.grad[:4,1].sum()), -float(logits.grad[4,1]), 7)
        self.assertEqual(logits.grad[5,:2].tolist(), [0.,0.])
        self.assertLess(float(logits.grad[5,2]), 0.)
        changed = logits.detach().clone(); changed[5,:2] = torch.tensor([900.,-900.])
        self.assertAlmostEqual(float(balanced_loss(items, changed, [4,1,1])), float(balanced_loss(items, logits, [4,1,1]).detach()), 7)

    def test_invalid_global_counts_or_classes_fail_closed(self):
        for counts in ([0,1,1], [True,1,1], [1,1,float('nan')], [1,1]):
            with self.assertRaises(ValueError):
                balanced_loss([dict(class_id=1)], torch.zeros((1,3)), counts)

    def test_fast_cutoff_equals_bruteforce_under_both_language_constraints_and_ties(self):
        records=[]; scores=[]
        for qlang in ['en','pt']:
            for rlang in ['en','pt']:
                for i in range(40):
                    id=f'{qlang}:{rlang}:{i}'
                    records.append(dict(id=id,label=1,goal_language=qlang,report_language=rlang,fact_truth=i%2==0,unknown_kind=None))
                    scores.append(dict(id=id,status='SCORED',score=float(i//2),support_score=-1. if i%3 else 1.))
                id=f'{qlang}:{rlang}:negative'; records.append(dict(id=id,label=0,goal_language=qlang,report_language=rlang,fact_truth=True,unknown_kind=None))
                scores.append(dict(id=id,status='SCORED',score=-100.,support_score=-1.))
        records.append(dict(id='u',label=None,unknown_kind='diagnosis_goal',goal_language='en',report_language='pt',fact_truth=True))
        scores.append(dict(id='u',status='SCORED',score=-1000.,support_score=0.))
        result=calibrate_bilingual(records,scores)
        values={s['score'] for r,s in zip(records,scores) if r['label'] is not None}
        values|={math.nextafter(min(values),-math.inf),math.nextafter(max(values),math.inf)}
        valid=[]
        for cutoff in values:
            good=True
            for key in ['goal_language','report_language']:
                for lang in ['en','pt']:
                    for contradiction in [False,True]:
                        group=[s for r,s in zip(records,scores) if r['label']==1 and r[key]==lang and (not contradiction or not r['fact_truth'])]
                        good &= sum(decision(s,dict(support=0.,relevance=cutoff))!='DROP' for s in group)/len(group)>=.95
            if good:valid.append(cutoff)
        self.assertEqual(result['relevance'], max(valid))
        self.assertEqual(result['support'],0.)
        self.assertEqual(result, bilingual_thresholds(records,scores))


if __name__ == '__main__':
    unittest.main()
