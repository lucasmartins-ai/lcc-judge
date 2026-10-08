import unittest
from unittest.mock import patch

from research.tool_relation_worker import require_worker, parse_status, retry_fields, udp_fields


class ToolRelationWorkerTests(unittest.TestCase):
    def test_actual_relations_cannot_be_executed_on_host(self):
        with self.assertRaises(RuntimeError):
            require_worker()

    def test_git_null_format_preserves_spaces_and_newlines_and_two_axes(self):
        self.assertEqual(parse_status('MM both name\0 M work\nname\0?? new name\0!! ignored\0'),
                         [('MM', 'both name'), (' M', 'work\nname'), ('??', 'new name'), ('!!', 'ignored')])
        for invalid in ['?? missing terminator', 'R  old\0new\0', 'UU conflict\0', '?? \0']:
            with self.assertRaises(ValueError):
                parse_status(invalid)

    def test_retry_scheduled_sleep_is_not_elapsed_or_actual_sleep(self):
        raw = dict(attempts=[dict(number=1, failed=True), dict(number=2, failed=False)],
                   sleeps=[dict(seconds=.001, before_ns=1000, after_ns=2001000)],
                   statistics=dict(attempt_number=2, idle_for=.001),
                   before_ns=0, after_ns=3000000)
        fields = retry_fields(raw)
        self.assertEqual(fields['retry_attempts'], 2)
        self.assertEqual(fields['retry_failures'], 1)
        self.assertEqual(fields['retry_scheduled_sleep_ns'], 1000000)
        self.assertEqual(fields['retry_actual_sleep_ns'], 2000000)
        self.assertEqual(fields['retry_elapsed_ns'], 3000000)
        raw['statistics']['attempt_number'] = 1
        with self.assertRaises(ValueError):
            retry_fields(raw)

    def test_empty_udp_payload_still_counts_as_a_datagram(self):
        raw = dict(events=[dict(sent_hex='',received_hex='',sent_bytes=0,received_bytes=0),
                           dict(sent_hex='00ff',received_hex='00ff',sent_bytes=2,received_bytes=2)])
        fields = udp_fields(raw)
        self.assertEqual(fields['udp_sent_datagrams'],2)
        self.assertEqual(fields['udp_received_datagrams'],2)
        self.assertEqual(fields['udp_received_payload_bytes'],2)
        raw['events'][1]['received_hex']='00'
        with self.assertRaises(ValueError):
            udp_fields(raw)

    def test_later_failure_preserves_completed_source_without_retry(self):
        from research.tool_relation_worker import measured_fixture
        with patch('research.tool_relation_worker.require_worker'), \
             patch('research.tool_relation_worker.observe_retry',return_value=({'retry_attempts':2},{'receipt':'captured'})), \
             patch('research.tool_relation_worker.observe_udp',side_effect=ValueError('socket unavailable')) as udp, \
             patch('research.tool_relation_worker.observe_git') as git:
            with self.assertRaises(ValueError) as caught:
                measured_fixture(42,0)
        partial=getattr(caught.exception,'partial',None)
        self.assertIsNotNone(partial)
        self.assertEqual(partial['raw_observations'],{'retry':{'receipt':'captured'}})
        self.assertEqual(partial['fields'],{'retry_attempts':2})
        self.assertFalse(partial['all_reference_checks_passed'])
        udp.assert_called_once();git.assert_not_called()


if __name__ == '__main__':
    unittest.main()
