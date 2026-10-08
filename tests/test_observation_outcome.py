import unittest


class ObservationOutcomeTests(unittest.TestCase):
    def expected(self):
        return dict(observations=[dict(time='2027-01-01T12:02:00Z', value=0, unit='count'),
                                  dict(time='2027-01-01T12:02:00Z', value=90, unit='count')],
                    unresolved=['entity', 'time'])

    def test_order_does_not_matter_but_values_and_unknowns_do(self):
        import copy
        from research.observation_lcc_pilot import verify_answer
        expected = self.expected()
        answer = dict(status='ANSWER', observations=copy.deepcopy(list(reversed(expected['observations']))),
                      unresolved=list(reversed(expected['unresolved'])))
        self.assertTrue(verify_answer(expected, answer)['passed'])
        answer['observations'][0]['value'] = 91
        self.assertFalse(verify_answer(expected, answer)['passed'])

    def test_missing_unknowns_extra_evidence_and_bool_values_are_rejected(self):
        import copy
        from research.observation_lcc_pilot import verify_answer
        expected = self.expected()
        original = dict(status='ANSWER', **expected)
        for change in ['missing_unknown', 'extra_obs', 'bool', 'nan', 'unit', 'abstain']:
            answer = copy.deepcopy(original)
            if change == 'missing_unknown': answer['unresolved'] = []
            if change == 'extra_obs': answer['observations'].append(dict(time='2027-01-01T12:02:00Z',value=3,unit='count'))
            if change == 'bool': answer['observations'][0]['value'] = False
            if change == 'nan': answer['observations'][0]['value'] = float('nan')
            if change == 'unit': answer['observations'][0]['unit'] = 'ms'
            if change == 'abstain': answer['status'] = 'ABSTAIN'
            self.assertFalse(verify_answer(expected, answer)['passed'], change)

    def test_duplicate_json_keys_cannot_override_answer(self):
        from research.observation_lcc_pilot import parse_answer
        with self.assertRaises(ValueError):
            parse_answer('{"status":"ANSWER","status":"ABSTAIN","observations":[],"unresolved":[]}')

    def test_fixture_unknown_flags_vary_and_unsupported_blocks_are_covered(self):
        from research.observation_lcc_pilot import task_rows
        tasks = task_rows()
        self.assertEqual(len(tasks), 6)
        self.assertEqual({tuple(t['expected']['unresolved']) for t in tasks},
                         {(), ('entity',), ('time',), ('entity','time')})
        for task in tasks:
            self.assertEqual(len(task['expected']['observations']), 2)
            self.assertTrue(task['critical_ids'])


if __name__ == '__main__':
    unittest.main()
