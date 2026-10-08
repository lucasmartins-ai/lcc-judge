from copy import deepcopy
import unittest

from research.audit_factorized_relation_dev import check_independent_axes


class FactorizedRelationDevAuditTests(unittest.TestCase):
    def test_axis_conversion_keeps_original_inputs_and_accounting_and_rejects_tampering(self):
        auxiliary=dict(rows=[dict(status='SCORED',logits=[-2.,3.,1.],score=5.,support_score=-2.,input_hash='original'),
                             dict(status='UNKNOWN',logits=None,score=None,support_score=None,input_hash=None)],
                       accounting=dict(valid_score_pairs=1,valid_score_tokens=7),complete=True,error=None)
        raw=deepcopy(auxiliary);raw['rows'][0]['support_score']=1.
        raw.update(axis='independent support logit2; relevance logit1-logit0',
                   auxiliary_logits_file_sha256='sha',additional_model_forwards=0)
        self.assertTrue(check_independent_axes(auxiliary,raw,'sha'))
        for field,value in [('support_score',-2.),('input_hash','changed')]:
            changed=deepcopy(raw);changed['rows'][0][field]=value
            with self.assertRaises(AssertionError):check_independent_axes(auxiliary,changed,'sha')
        changed=deepcopy(raw);changed['accounting']['valid_score_pairs']=2
        with self.assertRaises(AssertionError):check_independent_axes(auxiliary,changed,'sha')
        self.assertEqual(auxiliary['rows'][0]['support_score'],-2.)


if __name__=='__main__':unittest.main()
