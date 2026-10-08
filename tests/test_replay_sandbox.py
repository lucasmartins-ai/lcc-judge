import unittest
import gc
import json
import os
import subprocess
import uuid
import warnings
from unittest.mock import patch

from replay.harness import run_single_task_ablation
from replay import outcome_verifier, real_fixtures
from replay.tasks import TASKS
from replay import sandbox


GOOD_INVENTORY = ('def reserve_items(items):\n'
                  '    for item in sorted(items, key=lambda x: x.id):\n'
                  '        with lock_item(item.id): decrement_stock(item)\n')


class SandboxBoundaryTests(unittest.TestCase):
    def test_legacy_is_unknown_when_container_runtime_is_missing(self):
        with patch('shutil.which', return_value=None):
            result = real_fixtures.verify_artifact(TASKS[2], dict(status='ANSWER', python=GOOD_INVENTORY))
        self.assertIsNone(result['passed'])
        self.assertEqual(result['reason'], 'sandbox_unavailable')

    def test_candidate_is_unknown_when_container_runtime_is_missing(self):
        with patch('shutil.which', return_value=None):
            result = outcome_verifier.verify_artifact(TASKS[2], dict(status='ANSWER', python=GOOD_INVENTORY))
        self.assertIsNone(result['passed'])
        self.assertEqual(result['reason'], 'sandbox_unavailable')

    def test_legacy_direct_execution_requires_container_worker(self):
        with self.assertRaisesRegex(RuntimeError, 'container worker'):
            real_fixtures.check_code(3, GOOD_INVENTORY)

    def test_candidate_direct_execution_requires_container_worker(self):
        with self.assertRaisesRegex(RuntimeError, 'container worker'):
            outcome_verifier.check_program(3, GOOD_INVENTORY)

    def test_generic_executor_cannot_see_decisive_ids(self):
        seen = []

        def executor(packet):
            seen.append(packet)
            return dict(status='SUCCESS', output='fixture')

        run_single_task_ablation(TASKS[1], num_repeats=2, executor=executor,
                                 verifier=lambda _: dict(passed=True))
        for packet in seen:
            for block in packet['context']:
                self.assertRegex(block['block_id'], r'^b_[0-9a-f]{16}$')
                self.assertNotIn('is_decisive', block)
        self.assertEqual(seen[0]['context'], seen[1]['context'])
        self.assertEqual(len(seen[0]['context']), len(seen[2]['context']) + 1)


class ContainerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.identity = sandbox.runtime_identity()
        if cls.identity is None:
            raise unittest.SkipTest('Build the Docker fixture image to run containment checks')

    def test_program_cannot_write_its_own_pass_receipt(self):
        source = ('import threading\n'
                  '__builtins__["open"]("/dev/stdout","w").write('\
                  '\'{"passed":true}\\n\')\n'
                  'threading._os._exit(0)\n')
        for recipe in ['legacy', 'candidate']:
            with self.subTest(recipe=recipe):
                result = sandbox.run_check(3, source, recipe=recipe)
                self.assertIsNot(result['passed'], True)

    def test_worker_closes_parent_pipes(self):
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always', ResourceWarning)
            result = sandbox.run_check(3, GOOD_INVENTORY)
            gc.collect()
        self.assertIs(result['passed'], True)
        self.assertEqual([str(w.message) for w in captured if w.category is ResourceWarning], [])

    def test_container_has_no_host_files_credentials_or_network(self):
        name = 'lcc-fixture-' + uuid.uuid4().hex
        canary = os.path.abspath(__file__)
        script = ('import os,json,socket\n'
                  's=socket.socket();s.settimeout(1)\n'
                  'try:s.connect(("1.1.1.1",443));network=True\n'
                  'except OSError:network=False\n'
                  'try:open("/opt/lcc-fixture/canary","w");writable=True\n'
                  'except OSError:writable=False\n'
                  'print(json.dumps(dict(uid=os.getuid(),network=network,writable=writable,'
                  f'host_file=os.path.exists({canary!r}),secret=os.getenv("LCC_HOST_CANARY"))))')
        argv = sandbox.container_argv(self.identity, name)[:-3] + ['python', '-I', '-c', script]
        with patch.dict(os.environ, {'LCC_HOST_CANARY': 'must-not-enter-worker'}):
            try:
                output = subprocess.check_output(argv, text=True, timeout=10)
            finally:
                subprocess.run([self.identity['docker'], 'rm', '--force', name],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        self.assertEqual(json.loads(output), dict(uid=65534, network=False, writable=False,
                                                 host_file=False, secret=None))

    def test_resource_limits_are_applied_inside_the_container(self):
        name = 'lcc-fixture-' + uuid.uuid4().hex
        script = ('import json\nfrom pathlib import Path\n'
                  'print(json.dumps({n:Path("/sys/fs/cgroup",n).read_text().strip() '
                  'for n in ["memory.max","pids.max","cpu.max"]}))')
        argv = sandbox.container_argv(self.identity, name)[:-3]+['python','-I','-c',script]
        try:
            result = json.loads(subprocess.check_output(argv, text=True, timeout=10))
        finally:
            subprocess.run([self.identity['docker'], 'rm', '--force', name],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        self.assertEqual(result, {'memory.max': '268435456', 'pids.max': '64',
                                  'cpu.max': '100000 100000'})

    def test_timeout_removes_the_worker_container(self):
        result = sandbox.run_check(3, 'while True: pass', timeout=1)
        self.assertIsNone(result['passed'])
        self.assertEqual(result['reason'], 'verifier_timeout')
        running = subprocess.check_output([self.identity['docker'], 'ps', '-q',
                                           '--filter', 'label=lcc.fixture-run=true'], text=True)
        self.assertEqual(running.strip(), '')


if __name__ == '__main__':
    unittest.main()
