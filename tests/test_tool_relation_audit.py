import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.audit_tool_relations import recount
from research.capture_tool_relations import capture


class ToolRelationAuditTests(unittest.TestCase):
    def fixture(self):
        path=Path(__file__).resolve().parents[1]/'research/goal-engine-2026-10-04/tool-relations-grounded-v1/calibration/raw.json'
        return json.loads(path.read_text())['measurements']['fixtures'][0]

    def test_independent_audit_distinguishes_attempt_sleep_datagram_and_git_axes(self):
        fixture=self.fixture();counts=recount(fixture)
        self.assertNotEqual(counts['retry_scheduled_sleep_ns'],counts['retry_actual_sleep_ns'])
        self.assertEqual(counts['retry_attempts'],counts['retry_failures']+1)
        self.assertLess(counts['udp_received_datagrams'],counts['udp_received_payload_bytes'])
        self.assertEqual((counts['git_index_edits'],counts['git_worktree_edits']),(2,3))

    def test_false_counter_and_lost_payload_cannot_pass(self):
        original=self.fixture()
        changed=copy.deepcopy(original);changed['fields']['udp_received_datagrams']-=1
        with self.assertRaises(AssertionError):recount(changed)
        changed=copy.deepcopy(original);changed['raw_observations']['udp']['events'][1]['received_hex']=''
        with self.assertRaises(AssertionError):recount(changed)

    def test_failed_or_interrupted_capture_is_saved_and_not_automatically_retried(self):
        protocol=dict(sha256='fixed',request=dict(seed=42,fixtures=1),runtime=dict(image_id='pinned'),timeout_s=45)
        identity=dict(docker='docker',image_id='pinned')
        with tempfile.TemporaryDirectory() as name:
            out=Path(name)
            with patch('research.capture_tool_relations.runtime_identity',return_value=identity), \
                 patch('research.capture_tool_relations.measure_batch',return_value=dict(status='UNKNOWN',error='failed',stdout='partial')) as measure:
                with self.assertRaises(RuntimeError):capture(out,protocol)
                self.assertEqual(json.loads((out/'raw.json').read_text())['stdout'],'partial')
                self.assertFalse(json.loads((out/'completion.json').read_text())['admission'])
                with self.assertRaises(FileExistsError):capture(out,protocol)
                measure.assert_called_once()


if __name__=='__main__':
    unittest.main()
