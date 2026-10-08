import unittest

from research.tool_relation_state_contracts import ROLES,PAIRS,goal,report_caption,wording_assignment


class ToolRelationStateContractsTests(unittest.TestCase):
    def test_all_competing_roles_form_one_connected_graph(self):
        graph={role:set() for role in ROLES}
        for a,b in PAIRS.values():graph[a].add(b);graph[b].add(a)
        visited=set();pending=[next(iter(graph))]
        while pending:
            role=pending.pop()
            if role in visited:continue
            visited.add(role);pending.extend(graph[role]-visited)
        self.assertEqual(visited,set(ROLES))
        self.assertGreaterEqual(min(len(v) for v in graph.values()),3)

    def test_wording_is_crossed_and_seed_shuffled_separately_from_fixture_modes(self):
        assignments=wording_assignment(442601,64)
        self.assertEqual(len(assignments),64)
        self.assertEqual(len(set(assignments)),32)
        self.assertTrue(all(assignments.count(combination)==2 for combination in set(assignments)))
        self.assertNotEqual(assignments,wording_assignment(442602,64))
        with self.assertRaises(ValueError):wording_assignment(442601,31)

    def test_both_report_languages_and_scope_queries_are_distinct_from_direct_request(self):
        for role in ROLES:
            for language in ['en','pt']:
                self.assertTrue(report_caption(role,language,0))
                direct=goal(role,language,0,'train',None,0)
                broader=goal(role,language,0,'train','diagnosis_goal',0)
                self.assertNotEqual(direct,broader)
                self.assertIn(ROLES[role][2 if language=='en' else 3][0],broader)

    def test_retry_and_git_captions_do_not_assert_success_or_fixed_deleted_path(self):
        for language in ['en','pt']:
            for alias in range(4):
                self.assertNotIn('until success',goal('retry_elapsed_ns',language,alias,'train',None,0))
                self.assertNotIn('até o sucesso',goal('retry_attempts',language,alias,'train',None,0))
                self.assertNotIn('at success',report_caption('retry_attempts',language,alias))
                self.assertNotIn('the deleted path',report_caption('git_tracked_fs_bytes',language,alias))
        self.assertIn('deletions',report_caption('git_index_edits','en',3))

    def test_every_received_counter_query_and_caption_names_the_observation_budget(self):
        for role in ['udp_received_datagrams','udp_received_payload_bytes']:
            for alias in range(4):
                self.assertIn('read budget',goal(role,'en',alias,'train',None,0))
                self.assertIn('read budget',report_caption(role,'en',alias))
                self.assertIn('limite de leitura',goal(role,'pt',alias,'train',None,0))
                self.assertIn('limite de leitura',report_caption(role,'pt',alias))


if __name__=='__main__':unittest.main()
