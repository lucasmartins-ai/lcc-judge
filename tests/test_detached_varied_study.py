import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from research.detached_varied_study import checked_protocol, digest, launch, sha, status, supervise


class DetachedVariedStudyTests(unittest.TestCase):
    def test_observation_checks_archives_but_execution_still_rejects_current_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'study';archive=out/'sources/source.py'
            archive.parent.mkdir(parents=True);archive.write_text('executed source')
            (root/'source.py').write_text('later correction')
            protocol=dict(sources={'source.py':sha(archive)})
            protocol['sha256']=digest(protocol)
            (out/'protocol.json').write_text(json.dumps(protocol))
            with mock.patch('research.detached_varied_study.ROOT',root):
                with self.assertRaises(ValueError):checked_protocol(out)
                self.assertEqual(checked_protocol(out,verify_current=False),protocol)
                archive.write_text('altered archive')
                with self.assertRaises(ValueError):checked_protocol(out,verify_current=False)

    def test_status_uses_the_existing_pid_birth_and_module_observer(self):
        result=dict(state='RUNNING',child=dict(pid=24680))
        with mock.patch('research.observe_detached_varied.observe',return_value=result) as observe:
            self.assertEqual(status(),result)
            observe.assert_called_once_with()

    def test_protocol_and_source_drift_fail_before_spawning(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            with self.assertRaises(FileNotFoundError):checked_protocol(out)
            (out/'protocol.json').write_text(json.dumps(dict(sha256='changed',sources={})))
            with self.assertRaises(ValueError):checked_protocol(out)

    def test_launcher_is_fixed_session_and_stdio_with_immutable_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory);child=mock.Mock(pid=12345)
            with mock.patch('research.detached_varied_study.OUT',out),mock.patch('research.detached_varied_study.checked_protocol',return_value=dict(sha256='fixed')),mock.patch('research.detached_varied_study.subprocess.Popen',return_value=child) as spawn,mock.patch('research.detached_varied_study.process_identity',return_value=dict(pid=12345,birth='date',command='cmd',live=True)):
                result=launch()
                self.assertEqual(result['pid'],12345)
                args=spawn.call_args.kwargs
                self.assertIs(args['start_new_session'],True)
                self.assertIs(args['shell'],False)
                self.assertIs(args['close_fds'],True)
                self.assertEqual(args['env']['HF_HUB_OFFLINE'],'1')
                self.assertNotEqual(args['stdout'],args['stderr'])
                self.assertIn('research.detached_varied_study',spawn.call_args.args[0])
                with self.assertRaises(ValueError):launch()
                self.assertEqual(spawn.call_count,1)

    def test_supervisor_saves_actual_returncode_instead_of_inventing_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory);child=mock.Mock(pid=24680);child.wait.return_value=137
            with mock.patch('research.detached_varied_study.OUT',out),mock.patch('research.detached_varied_study.checked_protocol',return_value=dict(sha256='fixed')),mock.patch('research.detached_varied_study.subprocess.Popen',return_value=child),mock.patch('research.detached_varied_study.process_identity',return_value=dict(pid=24680,birth='date',command='cmd',live=True)):
                result=supervise()
                self.assertEqual(result['returncode'],137)
                self.assertIs(result['study_complete'],False)
                self.assertFalse((out/'summary.json').exists())
                self.assertEqual(json.loads((out/'process-exit.json').read_text())['returncode'],137)


if __name__=='__main__':unittest.main()
