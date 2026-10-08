import unittest
from unittest.mock import patch

from research.tool_relation_runtime import measurement_argv, measure_batch, runtime_identity


class ToolRelationRuntimeTests(unittest.TestCase):
    def test_confined_fixed_module_not_caller_code(self):
        argv = measurement_argv(dict(docker='docker',image_id='sha256:fixed'),'relation-name')
        for flag in ['--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
                     '--user=65534:65534','--pull=never']:
            self.assertIn(flag,argv)
        self.assertEqual(argv[-4:],['python','-I','-m','research.tool_relation_worker'])
        self.assertFalse(any(arg in ['--mount','--volume','-v','--privileged'] for arg in argv))

    def test_unavailable_never_runs_host_git_or_socket(self):
        with patch('research.tool_relation_runtime.runtime_identity',return_value=None), patch('subprocess.Popen') as execute:
            result=measure_batch(dict(seed=42,fixtures=1))
        self.assertEqual(result['status'],'UNKNOWN')
        execute.assert_not_called()

    def test_only_bounded_seed_and_count_reach_identity(self):
        with patch('research.tool_relation_runtime.runtime_identity') as identify:
            for request in [dict(seed=True,fixtures=1),dict(seed=42,fixtures=0),
                            dict(seed=42,fixtures=1,argv=['git','bad']),dict(seed=42,fixtures=1,path='/private')]:
                with self.assertRaises(ValueError):measure_batch(request)
            identify.assert_not_called()

    def test_real_retry_git_and_udp_receipts_complete(self):
        if runtime_identity() is None:self.skipTest('Explicitly build trusted relation worker')
        result=measure_batch(dict(seed=442500,fixtures=1))
        self.assertEqual(result['status'],'MEASURED',result.get('stderr'))
        fixture=result['measurements']['fixtures'][0]
        self.assertEqual(len(fixture['fields']),18)
        self.assertTrue(fixture['all_reference_checks_passed'])
        self.assertTrue(any(event['sent_bytes']==0 for event in fixture['raw_observations']['udp']['events']))
        self.assertGreater(fixture['fields']['retry_attempts'],fixture['fields']['retry_failures'])


if __name__ == '__main__':
    unittest.main()
