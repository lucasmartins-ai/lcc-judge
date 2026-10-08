import unittest
from unittest.mock import patch

from research.tool_relation_state_runtime import measurement_argv,measure_batch,build_recipe
from research.tool_measurement_runtime import BASE


class ToolRelationStateRuntimeTests(unittest.TestCase):
    def test_fixed_module_and_both_verified_guards_retain_confinement(self):
        argv=measurement_argv(dict(docker='docker',image_id='sha256:fixed'),'state-name')
        for flag in ['--pull=never','--network=none','--read-only','--cap-drop=ALL',
                     '--security-opt=no-new-privileges','--user=65534:65534',
                     'LCC_TOOL_RELATION_STATE_WORKER=1','LCC_TOOL_RELATION_WORKER=1']:
            self.assertIn(flag,argv)
        self.assertEqual(argv[-4:],['python','-I','-m','research.tool_relation_state_worker'])
        self.assertFalse(any(arg in ['-v','--mount','--volume','--privileged'] for arg in argv))

    def test_invalid_request_and_missing_runtime_never_launch_host_tools(self):
        with patch('research.tool_relation_state_runtime.runtime_identity',return_value=None) as identify,patch('subprocess.Popen') as execute:
            for request in [dict(seed=1,fixtures=1,argv=['git']),dict(seed=1,fixtures=True),dict(seed=1,fixtures=0)]:
                with self.assertRaises(ValueError):measure_batch(request)
            identify.assert_not_called()
            self.assertEqual(measure_batch(dict(seed=1,fixtures=1))['status'],'UNKNOWN')
            execute.assert_not_called()

    def test_from_uses_original_pinned_python_and_offline_dependency_recipe(self):
        recipe=build_recipe('source','dependencies')
        self.assertTrue(recipe.startswith('FROM '+BASE+'\n'))
        self.assertIn('RUN ["python", "/opt/install-deps.py"]',recipe)
        self.assertIn('tool_relation_state_worker.py tool_relation_worker.py tool_measurement_worker.py',recipe)
        self.assertIn('USER 65534:65534',recipe)


if __name__=='__main__':unittest.main()
