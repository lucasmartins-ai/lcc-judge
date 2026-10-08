from pathlib import Path
import json
import tempfile
import unittest
from unittest import mock


class ReplicationBoundaryTests(unittest.TestCase):
    def test_independent_auditor_rejects_an_undeclared_training_seed(self):
        from research.audit_varied_relation_dev import audit
        from research.audit_tool_relation_state_supervision import digest
        with tempfile.TemporaryDirectory() as directory:
            p = {'seed':42}; p['sha256'] = digest(p)
            (Path(directory)/'protocol.json').write_text(json.dumps(p))
            with self.assertRaises(AssertionError):
                audit(Path(directory))

    def test_fixed_seed_and_launcher_refuse_arbitrary_work_and_duplicate_execution(self):
        from research import varied_relation_replications as job
        for seed in (101, 1, '202', True):
            with self.assertRaises(ValueError):
                job.seed_output(seed)
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(job,'BASE',Path(directory)), mock.patch.object(job,'checked',return_value={'sha256':'fixed'}), mock.patch.object(job.subprocess,'Popen',return_value=mock.Mock(pid=12345)) as spawn, mock.patch.object(job,'process_identity',return_value={'pid':12345,'live':True}):
                job.launch()
                self.assertEqual(spawn.call_args.args[0], [job.sys.executable,'-m','research.varied_relation_replications','supervise'])
                self.assertTrue(spawn.call_args.kwargs['start_new_session'])
                self.assertFalse(spawn.call_args.kwargs['shell'])
                self.assertEqual(spawn.call_args.kwargs['env']['HF_HUB_OFFLINE'],'1')
                with self.assertRaises(FileExistsError):
                    job.launch()
                self.assertEqual(spawn.call_count,1)


if __name__ == '__main__':
    unittest.main()
