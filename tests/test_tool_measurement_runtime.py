import unittest
from unittest.mock import patch

from research.tool_measurement_runtime import measurement_argv, measure_batch, runtime_identity


class ToolMeasurementRuntimeTests(unittest.TestCase):
    def test_trusted_worker_still_has_no_host_network_or_credentials(self):
        argv=measurement_argv({'docker':'docker','image_id':'sha256:fixed'},'unique-measurement')
        for flag in ['--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--user=65534:65534','--pull=never']:
            self.assertIn(flag,argv)
        self.assertFalse(any(v in ['-v','--volume','--mount','--privileged','--network=host'] for v in argv))
        self.assertEqual(argv[-1],'/opt/lcc-measure/worker.py')
        self.assertIn('LCC_TOOL_MEASUREMENT_WORKER=1',argv)
        self.assertNotIn('LCC_FIXTURE_WORKER=1',argv)

    def test_unavailable_runtime_is_unknown_without_host_execution(self):
        with patch('research.tool_measurement_runtime.runtime_identity',return_value=None), patch('subprocess.Popen') as execute:
            result=measure_batch({'seed':42,'fixtures':1})
        self.assertEqual(result['status'],'UNKNOWN')
        execute.assert_not_called()

    def test_untrusted_commands_never_reach_docker(self):
        with patch('research.tool_measurement_runtime.runtime_identity') as identity:
            with self.assertRaises(ValueError):
                measure_batch({'seed':42,'fixtures':1,'argv':['bad']})
        identity.assert_not_called()

    def test_pinned_tools_complete_the_independent_reference_checks(self):
        if runtime_identity() is None:
            self.skipTest('Explicitly build the trusted measurement worker')
        result=measure_batch({'seed':442420,'fixtures':1})
        self.assertEqual(result['status'],'MEASURED',result.get('stderr'))
        fixture=result['measurements']['fixtures'][0]
        self.assertEqual(len(fixture['fields']),31)
        self.assertTrue(all(c['passed'] for c in fixture['checks']))


if __name__=='__main__':
    unittest.main()
