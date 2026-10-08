import unittest

from replay.real_fixtures import make_packet, verify_artifact
from replay.tasks import TASKS


class RealReplayTests(unittest.TestCase):
    def test_packet_hides_oracle_and_decisive_ids(self):
        import json
        task=TASKS[1]
        packet=make_packet(task, task.blocks, 42)
        encoded=json.dumps(packet)
        for name in ['is_decisive','required_keywords','candidate_block','blk_02_decisive']:
            self.assertNotIn(name,encoded)

    def test_repeats_do_not_put_unapplied_seed_into_model_state(self):
        self.assertEqual(make_packet(TASKS[0],TASKS[0].blocks,42),make_packet(TASKS[0],TASKS[0].blocks,59))

    def test_root_cause_is_checked_as_an_answer_not_keyword_coverage(self):
        result=verify_artifact(TASKS[0], {'status':'ANSWER','mechanism':'cache_expiry_stampede',
            'answer':'billing.py:144 stripe_webhook_handler acquire_conn'})
        self.assertFalse(result['passed'])

    def test_kubernetes_configuration_rejects_both_budget_fields(self):
        result=verify_artifact(TASKS[17], {'status':'ANSWER','mechanism':'configure_pdb',
            'parameters':{'min_available':3,'max_unavailable':2}})
        self.assertFalse(result['passed'])

    def test_kubernetes_either_valid_budget_form_is_accepted(self):
        for params in [{'min_available':3},{'max_unavailable':2}, {'min_available':4},{'max_unavailable':1}]:
            self.assertTrue(verify_artifact(TASKS[17], {'status':'ANSWER','mechanism':'configure_pdb',
                'parameters':params})['passed'])

    def test_sql_fix_is_executed_against_injection_and_normal_search(self):
        good='def search_users(tenant_id, query):\n    return db.execute("SELECT * FROM users WHERE tenant_id = ? AND name LIKE ?", (tenant_id, "%" + query + "%")).fetchall()\n'
        bad='def search_users(tenant_id, query):\n    return db.execute(f"SELECT * FROM users WHERE tenant_id = \'{tenant_id}\' AND name LIKE \'%{query}%\'").fetchall()\n'
        self.assertTrue(verify_artifact(TASKS[5], {'status':'ANSWER','python':good})['passed'])
        self.assertFalse(verify_artifact(TASKS[5], {'status':'ANSWER','python':bad})['passed'])

    def test_vacuous_generated_test_is_rejected_by_mutants(self):
        result=verify_artifact(TASKS[19], {'status':'ANSWER','python':'def test_burst(TokenBucket):\n    assert True\n'})
        self.assertFalse(result['passed'])

    def test_execution_error_is_not_task_failure_evidence(self):
        self.assertIsNone(verify_artifact(TASKS[0], None)['passed'])


if __name__=='__main__':
    unittest.main()
