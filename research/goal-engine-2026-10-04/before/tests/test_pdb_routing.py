import unittest
from replay.pdb_verifier import check_budget


class PDBRoutingRegressionTests(unittest.TestCase):
    def test_percentage_with_leading_zeroes_is_valid(self):
        self.assertTrue(check_budget({'min_available':'060%'},replicas=5,quorum=3))

    def test_integer_must_fit_kubernetes_int32(self):
        self.assertFalse(check_budget({'min_available':2147483648},replicas=2147483650,quorum=1))

    def test_equivalent_budget_encodings_have_identical_text_review_state(self):
        from replay import pdb_verifier
        self.assertTrue(callable(getattr(pdb_verifier,'prepare_text_review',None)),'text routing is missing')
        a={'status':'ANSWER','mechanism':'configure_pdb','parameters':{'min_available':5},'answer':'This permits maintenance while preserving quorum.'}
        b=dict(a,parameters={'max_unavailable':4})
        contract={'replicas':9,'quorum':5,'drain':1}
        self.assertEqual(pdb_verifier.prepare_text_review(a,contract),pdb_verifier.prepare_text_review(b,contract))

    def test_invalid_math_is_rejected_without_semantic_probability(self):
        from replay import pdb_verifier
        self.assertTrue(callable(getattr(pdb_verifier,'combine',None)),'separate decision is missing')
        self.assertIs(pdb_verifier.combine({'passed':False},None,.5)['passed'],False)

    def test_missing_text_review_is_unknown(self):
        from replay import pdb_verifier
        self.assertTrue(callable(getattr(pdb_verifier,'combine',None)),'separate decision is missing')
        self.assertIsNone(pdb_verifier.combine({'passed':True},None,.5)['passed'])

    def test_numeric_prose_claim_is_checked_by_code(self):
        from replay.pdb_verifier import numeric_verdict
        self.assertIs(numeric_verdict({'max_unavailable':2},9,5,numeric_claims={'min_remaining':9})['passed'],False)

    def test_unhealthy_scope_is_unknown(self):
        from replay.pdb_verifier import numeric_verdict
        self.assertIsNone(numeric_verdict({'max_unavailable':2},9,5,healthy=8)['passed'])


if __name__=='__main__':unittest.main()
