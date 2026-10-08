import unittest

from replay.outcome_verifier import verify_artifact
from replay.tasks import TASKS


class VerifierCalibrationTests(unittest.TestCase):
    def test_budget_boolean_is_not_a_replica_count(self):
        result=verify_artifact(TASKS[17],dict(status='ANSWER',mechanism='configure_pdb',
            parameters={'max_unavailable':True}))
        self.assertFalse(result['passed'])

    def test_valid_budget_percentage_is_accepted(self):
        result=verify_artifact(TASKS[17],dict(status='ANSWER',mechanism='configure_pdb',
            parameters={'min_available':'60%'}))
        self.assertTrue(result['passed'])

    def test_test_contract_requires_assertion_failures(self):
        source='''def test_burst(TokenBucket):
    tick=[0.0]
    bucket=TokenBucket(3,2,lambda:tick[0])
    if [bucket.allow() for _ in range(4)] != [True,True,True,False]:
        raise RuntimeError('bad burst')
    tick[0]=0.5
    if not bucket.allow():raise RuntimeError('no refill')
'''
        self.assertIs(verify_artifact(TASKS[19],dict(status='ANSWER',python=source))['passed'],False)

    def test_inventory_is_not_allowed_to_handle_only_the_original_ids(self):
        source='''def reserve_items(items):
    selected={item.id:item for item in items}
    for ident in [2,5,7]:
        with lock_item(ident):decrement_stock(selected[ident])
'''
        self.assertIs(verify_artifact(TASKS[2],dict(status='ANSWER',python=source))['passed'],False)

    def test_positive_inventory_program_actually_runs(self):
        source='def reserve_items(items):\n    for item in sorted(items,key=lambda x:x.id):\n        with lock_item(item.id):decrement_stock(item)\n'
        self.assertIs(verify_artifact(TASKS[2],dict(status='ANSWER',python=source))['passed'],True)


if __name__=='__main__':unittest.main()
