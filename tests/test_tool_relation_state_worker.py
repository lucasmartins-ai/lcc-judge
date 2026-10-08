import unittest
import random
from unittest.mock import patch,MagicMock

from research.tool_relation_state_worker import require_worker,retry_fields,udp_fields,git_fields,measured_fixture,observe_udp


def retry(outcome,failed):
    return dict(outcome=outcome,attempts=[dict(number=i+1,failed=value,at_ns=i*3000000+1) for i,value in enumerate(failed)],
        sleeps=[dict(seconds=.001,before_ns=i*3000000+2,after_ns=i*3000000+2000002) for i in range(len(failed)-1)],
        statistics=dict(attempt_number=len(failed),idle_for=(len(failed)-1)*.001),before_ns=0,after_ns=len(failed)*3000000)


class ToolRelationStateWorkerTests(unittest.TestCase):
    def test_new_fixed_worker_refuses_host_execution(self):
        with self.assertRaises(RuntimeError):require_worker()

    def test_first_success_and_expected_exhaustion_have_distinct_failure_counts(self):
        self.assertEqual(retry_fields(retry('success',[False]))['retry_failures'],0)
        result=retry_fields(retry('exhausted',[True,True,True]))
        self.assertEqual(result['retry_attempts'],3)
        self.assertEqual(result['retry_failures'],3)
        self.assertEqual(result['retry_sleep_calls'],2)
        self.assertEqual(result['retry_actual_sleep_ns'],4000000)
        with self.assertRaises(ValueError):retry_fields(retry('success',[True,True]))

    def test_udp_prefix_budget_does_not_count_unread_sends_or_zero_bytes_as_no_event(self):
        raw=dict(read_limit=1,send_events=[dict(payload_hex='',bytes=0),dict(payload_hex='abcd',bytes=2)],
                 receive_events=[dict(payload_hex='',bytes=0)])
        result=udp_fields(raw)
        self.assertEqual(result,dict(udp_sent_datagrams=2,udp_received_datagrams=1,
                                    udp_sent_payload_bytes=2,udp_received_payload_bytes=0))
        raw['read_limit']=0;raw['receive_events']=[]
        self.assertEqual(udp_fields(raw)['udp_received_datagrams'],0)
        raw['read_limit']=1;raw['receive_events']=[dict(payload_hex='ab',bytes=1)]
        with self.assertRaises(ValueError):udp_fields(raw)

    def test_staged_delete_is_head_index_edit_even_when_missing_from_index(self):
        raw=dict(head_paths_stdout='clean\0removed\0',index_stdout='clean\0new\0',untracked_stdout='',ignored_stdout='',
            status_stdout='D  removed\0A  new\0',current_file_hex={'clean':'00','new':'0102'})
        result=git_fields(raw)
        self.assertEqual(result['git_index_files'],2)
        self.assertEqual(result['git_index_edits'],2)
        self.assertEqual(result['git_worktree_edits'],0)
        self.assertEqual(result['git_clean_tracked_files'],1)
        self.assertEqual(result['git_tracked_fs_bytes'],3)
        raw['status_stdout']='D  nonexistent\0A  new\0'
        with self.assertRaises(ValueError):git_fields(raw)

    def test_clean_git_with_empty_other_lists_is_valid(self):
        raw=dict(head_paths_stdout='clean\0',index_stdout='clean\0',untracked_stdout='',ignored_stdout='',
                 status_stdout='',current_file_hex={'clean':'0102'})
        result=git_fields(raw)
        self.assertEqual(result['git_index_edits'],0)
        self.assertEqual(result['git_worktree_edits'],0)
        self.assertEqual(result['git_clean_tracked_files'],1)

    def test_later_capture_failure_keeps_prior_sources_and_never_retries(self):
        with patch('research.tool_relation_state_worker.require_worker'), \
             patch('research.tool_relation_state_worker.observe_retry',return_value=({'retry_attempts':1},{'captured':'first'})), \
             patch('research.tool_relation_state_worker.observe_udp',side_effect=ValueError('socket failed')) as udp, \
             patch('research.tool_relation_state_worker.observe_git') as git:
            with self.assertRaises(ValueError) as caught:measured_fixture(42,0)
        self.assertEqual(caught.exception.partial['fields'],{'retry_attempts':1})
        self.assertEqual(caught.exception.partial['raw_observations'],{'retry':{'captured':'first'}})
        udp.assert_called_once();git.assert_not_called()

    def test_udp_timeout_retains_completed_sends_inside_failed_source(self):
        receiver=MagicMock();sender=MagicMock()
        receiver.__enter__.return_value=receiver;sender.__enter__.return_value=sender
        receiver.getsockname.return_value=('127.0.0.1',2001);sender.getsockname.return_value=('127.0.0.1',2002)
        sender.sendto.side_effect=lambda payload,address:len(payload)
        receiver.recvfrom.side_effect=TimeoutError('mock bounded receive timeout')
        with patch('research.tool_relation_state_worker.require_worker'), \
             patch('research.tool_relation_state_worker.socket.socket',side_effect=[receiver,sender]):
            with self.assertRaises(TimeoutError) as caught:observe_udp(random.Random(42),0)
        self.assertGreater(len(caught.exception.partial['send_events']),0)
        self.assertEqual(caught.exception.partial['receive_events'],[])
        receiver.recvfrom.assert_called_once()


if __name__=='__main__':unittest.main()
